"""Hilaire Legentil — Artiste aquarelliste · Aquarelles mer & paysage.

Site public (galerie, actualités, contact, carte) + espace administrateur
(gestion des œuvres, des actualités, des réglages, des messages).
"""
import os
import sys
import json
import base64
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
VENDOR = os.path.join(BASE_DIR, "vendor")
if VENDOR not in sys.path:
    sys.path.insert(0, VENDOR)

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, Response, send_from_directory, session, url_for)
from werkzeug.exceptions import NotFound
from werkzeug.middleware.proxy_fix import ProxyFix

import auth
import db
import imaging
from utils import nl2paras, parse_date, slugify, unique_slug

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 12  # 12 h
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 3600  # 1 h de cache pour les fichiers statiques
app.config["STATIC_EXPORT"] = os.environ.get("HL_STATIC_EXPORT") == "1"

# --------------------------------------------- notifications navigateur
# Web Push (VAPID) : la clé privée est générée localement si absente,
# jamais publiée. Si le module n'est pas installé, tout se désactive proprement.
PUSH_ENABLED = False
VAPID_PUB = ""
_VAPID_PRIV = os.path.join(BASE_DIR, "data", "vapid_private.pem")
_VAPID_OBJ = None
try:
    from py_vapid import Vapid02
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from pywebpush import webpush, WebPushException
    if not os.path.exists(_VAPID_PRIV):
        _v = Vapid02()
        _v.generate_keys()
        _v.save_key(_VAPID_PRIV)
    _VAPID_OBJ = Vapid02.from_pem(open(_VAPID_PRIV, "rb").read())
    VAPID_PUB = base64.urlsafe_b64encode(
        _VAPID_OBJ.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    ).rstrip(b"=").decode()
    PUSH_ENABLED = True
except Exception:
    PUSH_ENABLED = False


def push_send_all(title, body, url="/galerie"):
    """Envoie une notification Web Push à tous les abonnés du site.
    Retourne (envoyées, échecs, abonnements obsolètes nettoyés)."""
    if not PUSH_ENABLED:
        return 0, 0, 0
    conn = db.connect()
    subs_rows = conn.execute("SELECT * FROM push_subs").fetchall()
    conn.close()
    sent = failed = gone = 0
    gone_ids = []
    for row in subs_rows:
        info = {"endpoint": row["endpoint"],
                "keys": {"p256dh": row["p256dh"], "auth": row["auth"]}}
        try:
            webpush(info, data=json.dumps({"title": title, "body": body,
                                           "url": url}),
                    vapid_private_key=_VAPID_OBJ,
                    vapid_claims={"sub": "mailto:hilaire.legentil@free.fr"},
                    timeout=12)
            sent += 1
        except WebPushException as e:
            st = e.response.status_code if getattr(e, "response", None) is not None else 0
            if st in (404, 410):          # abonnement expiré côté navigateur
                gone += 1
                gone_ids.append(row["id"])
            else:
                failed += 1
        except Exception:
            failed += 1
    if gone_ids:
        conn = db.connect()
        conn.executemany("DELETE FROM push_subs WHERE id=?",
                         [(i,) for i in gone_ids])
        conn.commit()
        conn.close()
    return sent, failed, gone


def _push_new_work():
    """Notification automatique : une nouvelle aquarelle est en ligne."""
    try:
        sent, _failed, _gone = push_send_all(
            "Nouvelle aquarelle en ligne",
            "Une nouvelle aquarelle vient d'être ajoutée à la galerie.")
        return sent
    except Exception:
        return 0

SECRET_FILE = os.path.join(db.DATA_DIR, "secret_key")
os.makedirs(db.DATA_DIR, exist_ok=True)
if not os.path.exists(SECRET_FILE):
    with open(SECRET_FILE, "w") as f:
        f.write(os.urandom(32).hex())
with open(SECRET_FILE) as f:
    app.secret_key = f.read().strip()

UPLOADS = os.path.join(BASE_DIR, "uploads")
WORKS_DIR = os.path.join(UPLOADS, "works")
NEWS_DIR = os.path.join(UPLOADS, "news")
ATELIER_DIR = os.path.join(UPLOADS, "atelier")
for d in (WORKS_DIR, NEWS_DIR, ATELIER_DIR):
    os.makedirs(d, exist_ok=True)

SITE = {
    "name": "Hilaire Legentil",
    "tagline": "Artiste aquarelliste",
    "baseline": "Aquarelles — mer & paysage",
    "domain": "",  # ex. https://www.hilaire-legentil-aquarelles.fr (à renseigner à la mise en ligne)
}

# ------------------------------------------------------------------ filtres

@app.template_filter("date_fr")
def date_fr(value):
    return parse_date(value)[0]


@app.template_filter("paras")
def paras(value):
    return nl2paras(value)


# --------------------------------------------------------- contexte global

@app.context_processor
def inject_globals():
    s = db.get_settings()
    hl_works = get_works()
    return {
        "SITE": SITE,
        "S": s,
        "admin_user": auth.current_admin(),
        "csrf": auth.csrf_token(),
        "year": date.today().year,
        "map_center": [49.4894, -1.5048],   # Yvetot-Bocage (Normandie)
        "map_radius": 75000,                # 75 km
        "hl_slugs": ",".join(w["slug"] for w in hl_works),
        "hl_total": len(hl_works),
        "vapid_pub": VAPID_PUB,
        "static_export": app.config.get("STATIC_EXPORT", False),
    }


def current_domain():
    """Domaine public du site — réglage admin « site_domain » (prioritaire),
    sinon la constante SITE["domain"]. Vide = site sans domaine personnalisé."""
    try:
        return (db.get_settings().get("site_domain") or SITE["domain"]).rstrip("/")
    except Exception:
        return SITE["domain"].rstrip("/")


def site_url(path="/"):
    domain = current_domain()
    return domain + path if domain else path


# ------------------------------------------------------------- raccourcis

def get_works(only_published=True):
    conn = db.connect()
    q = "SELECT * FROM works"
    if only_published:
        q += " WHERE published = 1"
    q += " ORDER BY position, id"
    rows = conn.execute(q).fetchall()
    conn.close()
    return rows


def get_work(slug):
    conn = db.connect()
    row = conn.execute("SELECT * FROM works WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    return row


def get_news(only_published=True, limit=None):
    conn = db.connect()
    q = "SELECT * FROM news"
    if only_published:
        q += " WHERE published = 1"
    q += " ORDER BY COALESCE(NULLIF(event_date,''), created_at) DESC, id DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = conn.execute(q).fetchall()
    conn.close()
    return rows


def get_news_item(slug):
    conn = db.connect()
    row = conn.execute("SELECT * FROM news WHERE slug = ?", (slug,)).fetchone()
    images = []
    if row:
        images = conn.execute(
            "SELECT * FROM news_images WHERE news_id = ? ORDER BY position, id",
            (row["id"],)).fetchall()
    conn.close()
    return row, images


# =================================================================
#  SITE PUBLIC
# =================================================================

@app.route("/")
def home():
    works = get_works()
    items = get_news()
    today = db.now_iso()[:10]
    upcoming = sorted([n for n in items if (n["event_date"] or "")[:10] >= today],
                      key=lambda n: n["event_date"] or "")
    past = sorted([n for n in items if (n["event_date"] or "")[:10] < today],
                  key=lambda n: n["event_date"] or "", reverse=True)
    return render_template("index.html", works=works[:6], news=(upcoming + past)[:3],
                           hero_works=works[:5], flip=works[:10])


@app.route("/artiste")
def artist():
    return render_template("artist.html", expositions=get_news(limit=12))


@app.route("/atelier")
def atelier():
    conn = db.connect()
    photos = conn.execute(
        "SELECT folder, img_w, img_h FROM atelier "
        "WHERE kind='palette' ORDER BY position, id").fetchall()
    vif = conn.execute("SELECT folder, img_w, img_h FROM atelier "
                       "WHERE kind='vif' ORDER BY position, id").fetchall()
    materiel = conn.execute("SELECT folder, img_w, img_h FROM atelier "
                            "WHERE kind='materiel' ORDER BY position, id").fetchall()
    conn.close()
    return render_template("atelier.html", photos=photos, vif=vif,
                           materiel=materiel)


@app.route("/galerie")
def gallery():
    works = get_works()
    cats = []
    for w in works:
        if w["category"] and w["category"] not in cats:
            cats.append(w["category"])
    def _tallies(key):
        out = {}
        for w in works:
            v = (w[key] or "").strip()
            if v:
                out[v] = out.get(v, 0) + 1
        return list(out.items())
    sujets = _tallies("sujet")
    ambiances = _tallies("ambiance")
    techs = _tallies("technique")
    years = _tallies("year")
    years.sort(key=lambda p: p[0], reverse=True)
    conn = db.connect()
    vif = conn.execute("SELECT folder, img_w, img_h FROM atelier "
                       "WHERE kind='vif' ORDER BY position, id").fetchall()
    conn.close()
    return render_template("gallery.html", works=works, categories=cats,
                           sujets=sujets, ambiances=ambiances, techs=techs,
                           years=years, vif=vif)


@app.route("/galerie/<slug>")
def work(slug):
    works = get_works()
    row = next((w for w in works if w["slug"] == slug), None)
    if row is None:
        abort(404)
    idx = works.index(row)
    prev = works[idx - 1] if idx > 0 else (works[-1] if works else None)
    nxt = works[idx + 1] if idx < len(works) - 1 else (works[0] if works else None)
    conn = db.connect()
    imgs = conn.execute("SELECT image FROM works_images WHERE work_id=? "
                        "ORDER BY position, id", (row["id"],)).fetchall()
    conn.close()
    return render_template("work.html", w=row, prev=prev, next=nxt,
                           index=idx + 1, total=len(works), imgs=imgs)


@app.route("/evenements")
def news_list():
    items = get_news()
    today = db.now_iso()[:10]
    upcoming = sorted([n for n in items if (n["event_date"] or "")[:10] >= today],
                      key=lambda n: n["event_date"] or "")
    past = sorted([n for n in items if (n["event_date"] or "")[:10] < today],
                  key=lambda n: n["event_date"] or "", reverse=True)
    return render_template("news.html", items=upcoming + past, upcoming=upcoming,
                           past=past)


@app.route("/evenements/<slug>")
def news_item(slug):
    row, images = get_news_item(slug)
    if row is None or (not row["published"] and not auth.current_admin()):
        abort(404)
    others = [n for n in get_news(limit=4) if n["id"] != row["id"]][:3]
    return render_template("news_item.html", n=row, images=images, others=others)


# ------------------------------------------- anciennes adresses (301)
@app.route("/aquarelles")
def legacy_gallery():
    return redirect(url_for("gallery"), code=301)


@app.route("/aquarelles/<slug>")
def legacy_work(slug):
    return redirect(url_for("work", slug=slug), code=301)


@app.route("/actualites")
def legacy_news():
    return redirect(url_for("news_list"), code=301)


@app.route("/actualites/<slug>")
def legacy_news_item(slug):
    return redirect(url_for("news_item", slug=slug), code=301)


@app.route("/contact")
def contact():
    oeuvre = request.args.get("oeuvre", "")
    sujet = request.args.get("sujet", "")
    prefill = ""
    if oeuvre:
        w = get_work(oeuvre)
        if w:
            prefill = f"Demande d'information — aquarelle « {w['title']} »"
    elif sujet == "demande-specifique":
        prefill = "Demande spécifique"
    return render_template("contact.html", prefill=prefill,
                           sent=session.pop("contact_sent", False))


@app.post("/contact/envoyer")
def contact_send():
    if auth.rate_limited(f"contact:{auth.fingerprint(request)}", 5, 3600):
        flash("Trop d'envois successifs. Merci de réessayer dans un instant.", "error")
        return redirect(url_for("contact"))
    if not auth.csrf_ok(request):
        abort(400)

    # Anti-spam : champ pot de miel + délai minimal de remplissage
    if request.form.get("site_web", "").strip():
        return redirect(url_for("contact"))
    if request.form.get("form_ts", "0").isdigit() and \
            time_now() - int(request.form.get("form_ts", "0")) < 3:
        flash("Le formulaire a été envoyé trop vite. Merci de vérifier votre message.",
              "error")
        return redirect(url_for("contact"))

    name = clean(request.form.get("name", ""), 120)
    email = clean(request.form.get("email", ""), 160)
    phone = clean(request.form.get("phone", ""), 40)
    subject = clean(request.form.get("subject", ""), 160)
    category = clean(request.form.get("category", ""), 80)
    body = clean(request.form.get("message", ""), 4000)

    errors = []
    if len(name) < 2:
        errors.append("Merci d'indiquer votre nom.")
    if "@" not in email or "." not in email.split("@")[-1]:
        errors.append("L'adresse e-mail ne semble pas valide.")
    if len(subject) < 2:
        errors.append("Merci d'indiquer l'objet de votre demande.")
    if len(body) < 10:
        errors.append("Votre message est un peu court (10 caractères minimum).")
    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("contact") + "#formulaire")

    conn = db.connect()
    conn.execute(
        "INSERT INTO messages(created_at,name,email,phone,subject,category,body,ip) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (db.now_iso(), name, email, phone, subject, category, body,
         request.remote_addr or ""))
    conn.commit()
    conn.close()

    session["contact_sent"] = True
    return redirect(url_for("contact") + "#formulaire")


@app.route("/demande-specifique")
def specific_request():
    return redirect(url_for("contact", sujet="demande-specifique") + "#demande-specifique")


@app.route("/mentions-legales")
def legal():
    return render_template("legal.html")


@app.route("/confidentialite")
def privacy():
    return render_template("privacy.html")


# --- fichiers téléversés (jamais d'exécution, types forcés) ---------------

@app.route("/uploads/<area>/<folder>/<path:filename>")
def uploaded_file(area, folder, filename):
    root = {"works": WORKS_DIR, "news": NEWS_DIR, "atelier": ATELIER_DIR}.get(area)
    if root is None or "/" in folder or ".." in folder:
        abort(404)
    try:
        return send_from_directory(os.path.join(root, folder), filename,
                                   max_age=31536000)
    except NotFound:
        # repli : les aquarelles « sur le vif » sont stockées avec l'atelier
        if area == "works":
            return send_from_directory(os.path.join(ATELIER_DIR, folder), filename,
                                       max_age=31536000)
        raise


# --- sitemap & robots ------------------------------------------------------

@app.route("/sitemap.xml")
def sitemap():
    items = [("artist", None), ("atelier", None), ("gallery", None),
             ("news_list", None), ("contact", None)]
    conn = db.connect()
    works = conn.execute("SELECT slug FROM works WHERE published=1").fetchall()
    news = conn.execute("SELECT slug FROM news WHERE published=1").fetchall()
    conn.close()
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml.append(f"<url><loc>{site_url('/')}</loc><priority>1.0</priority></url>")
    for endpoint, _ in items:
        xml.append(f"<url><loc>{site_url(url_for(endpoint))}</loc><priority>0.8</priority></url>")
    for w in works:
        xml.append(f"<url><loc>{site_url(url_for('work', slug=w['slug']))}</loc></url>")
    for n in news:
        xml.append(f"<url><loc>{site_url(url_for('news_item', slug=n['slug']))}</loc></url>")
    xml.append("</urlset>")
    return app.response_class("\n".join(xml), mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    body = "User-agent: *\nDisallow: /admin\nDisallow: /uploads\n"
    domain = current_domain()
    if domain:
        body += f"Sitemap: {domain}/sitemap.xml\n"
    return app.response_class(body, mimetype="text/plain")


# --- erreurs ----------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404,
                           message="Cette page n'existe pas ou plus."), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500,
                           message="Une erreur inattendue est survenue."), 500


# =================================================================
#  ADMINISTRATION
# =================================================================

def require_admin(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not auth.current_admin():
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


# --------------------------------------------- service worker & abonnements
@app.route("/sw.js")
def service_worker():
    resp = app.send_static_file("sw.js")
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/google<token>.html")
def google_verification(token):
    """Fichier de vérification Google Search Console (référencement) :
    servi tel quel à la racine du site, contenu strictement identique
    au fichier déposé par Google."""
    import re as _re
    name = f"google{token}.html"
    if not _re.fullmatch(r"[a-f0-9]+", token) or \
            not os.path.isfile(os.path.join(BASE_DIR, name)):
        abort(404)
    return send_from_directory(BASE_DIR, name, mimetype="text/plain")


@app.route("/push/subscribe", methods=["POST"])
def push_subscribe():
    d = request.get_json(silent=True) or {}
    keys = d.get("keys") or {}
    ep = (d.get("endpoint") or "").strip()
    if not ep.startswith("https://") or not keys.get("p256dh") or not keys.get("auth"):
        return jsonify({"ok": False}), 400
    conn = db.connect()
    conn.execute(
        "INSERT INTO push_subs(endpoint,p256dh,auth,created_at) VALUES(?,?,?,?) "
        "ON CONFLICT(endpoint) DO UPDATE SET p256dh=excluded.p256dh, "
        "auth=excluded.auth",
        (ep, keys["p256dh"], keys["auth"], db.now_iso()))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/push/unsubscribe", methods=["POST"])
def push_unsubscribe():
    d = request.get_json(silent=True) or {}
    ep = (d.get("endpoint") or "").strip()
    if ep:
        conn = db.connect()
        conn.execute("DELETE FROM push_subs WHERE endpoint=?", (ep,))
        conn.commit()
        conn.close()
    return jsonify({"ok": True})


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        key = f"login:{auth.fingerprint(request)}"
        if auth.rate_limited(key, 8, 900):
            flash("Trop de tentatives. Réessayez dans un quart d'heure.", "error")
        else:
            username = request.form.get("username", "").strip()[:60]
            password = request.form.get("password", "")
            if auth.login(username, password):
                return redirect(url_for("admin_home"))
            flash("Identifiant ou mot de passe incorrect.", "error")
    if auth.current_admin():
        return redirect(url_for("admin_home"))
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    auth.logout()
    return redirect(url_for("home"))


@app.route("/admin", methods=["GET", "POST"])
@require_admin
def admin_home():
    if request.method == "POST":
        if not auth.csrf_ok(request):
            abort(400)
        action = request.form.get("action")
        if action == "github_key":
            token = request.form.get("github_token", "").strip()
            if not token:
                flash("Collez d’abord la clé (jeton d’accès).", "error")
            else:
                st, me = _gh_call("GET", "https://api.github.com/user", token)
                if st == 200:
                    db.set_setting("github_token", token)
                    # Détection automatique du dépôt du site : celui qui contient
                    # index.html à sa racine — rien à choisir à la main.
                    found = ""
                    if not db.get_settings().get("github_repo"):
                        st2, rl = _gh_call("GET",
                                           "https://api.github.com/user/repos"
                                           "?per_page=100&sort=pushed", token)
                        hits = []
                        if st2 == 200 and isinstance(rl, list):
                            for r in rl[:10]:
                                if not (r.get("permissions") or {}).get("push"):
                                    continue
                                st3, _c = _gh_call(
                                    "GET",
                                    "https://api.github.com/repos/"
                                    + r["full_name"] + "/contents/index.html",
                                    token)
                                if st3 == 200:
                                    hits.append((r["full_name"],
                                                 r.get("default_branch") or "main"))
                        if len(hits) == 1:
                            found, _br = hits[0]
                            db.set_setting("github_repo", found)
                            db.set_setting("github_branch", _br)
                    if found:
                        flash(f"Clé vérifiée ✔ — connecté en tant que "
                              f"{me.get('login', '?')}. Dépôt du site trouvé "
                              f"automatiquement : {found}.", "ok")
                    else:
                        flash(f"Clé vérifiée ✔ — connecté en tant que "
                              f"{me.get('login', '?')}.", "ok")
                else:
                    hint = {401: "clé invalide ou expirée",
                            403: "clé sans accès"}.get(st, me.get("message", ""))
                    flash(f"GitHub a refusé la clé ({st}) : {hint}.", "error")
            return redirect(url_for("admin_home"))
        if action == "github_forget":
            db.set_setting("github_token", "")
            flash("Clé supprimée de cet ordinateur.", "ok")
            return redirect(url_for("admin_home"))
        if action == "github_repo":
            repo = clean(request.form.get("github_repo", ""), 120).strip().strip("/")
            branch = clean(request.form.get("github_branch", ""), 60).strip() or "main"
            if "/" not in repo:
                flash("Choisissez le dépôt dans la liste (ou indiquez compte/dépôt).",
                      "error")
            else:
                db.set_setting("github_repo", repo)
                db.set_setting("github_branch", branch)
                flash(f"Dépôt enregistré : {repo} (branche {branch}).", "ok")
            return redirect(url_for("admin_home"))
        if action == "github_publish_site":
            s = db.get_settings()
            repo = s.get("github_repo", "")
            branch = s.get("github_branch", "main") or "main"
            token = s.get("github_token", "")
            if not token:
                flash("Ajoutez d’abord votre clé GitHub (étape 1).", "error")
                return redirect(url_for("admin_home"))
            if not repo:
                flash("Choisissez d’abord le dépôt (étape 2).", "error")
                return redirect(url_for("admin_home"))
            if _PUB.get("state") == "running":
                flash("Une publication est déjà en cours — suivez sa progression "
                      "ci-dessous.", "error")
                return redirect(url_for("admin_home"))
            threading.Thread(target=_publish_site_thread,
                             args=(repo, branch, token), daemon=True).start()
            flash("Publication du site rapide lancée — suivez la progression "
                  "ci-dessous.", "ok")
            return redirect(url_for("admin_home"))
        if action == "github_publish":
            s = db.get_settings()
            repo = s.get("github_repo", "")
            branch = s.get("github_branch", "main") or "main"
            token = s.get("github_token", "")
            if not token:
                flash("Ajoutez d’abord votre clé (étape 1).", "error")
                return redirect(url_for("admin_home"))
            if not repo:
                flash("Choisissez d’abord le dépôt (étape 2).", "error")
                return redirect(url_for("admin_home"))
            try:
                import build_standalone
                html = build_standalone.build_html()
            except Exception as e:
                flash(f"Impossible de générer la page unique : {e}", "error")
                return redirect(url_for("admin_home"))
            import base64 as _b64, time as _time
            api = f"https://api.github.com/repos/{repo}/contents/index.html"

            def _fresh_sha():
                """SHA actuel du fichier — l'URL unique contourne le cache (~60 s)
                de l'API GitHub, cause des conflits 409 après une publication."""
                u = f"{api}?ref={branch}&_={int(_time.time() * 1000)}"
                st1, cur = _gh_call("GET", u, token)
                return ((cur or {}).get("sha") or "") if st1 == 200 else ""

            published, result, st = False, {}, 0
            for attempt in range(3):  # reprise automatique sur conflit 409
                sha = _fresh_sha()
                payload = {"message": "Site mis à jour depuis l'espace d'administration",
                           "content": _b64.b64encode(html.encode()).decode(),
                           "branch": branch}
                if sha:
                    payload["sha"] = sha
                st, res = _gh_call("PUT", api, token, payload)
                result = res or {}
                if st in (200, 201):
                    published = True
                    break
                if st != 409:
                    break
                if attempt < 2:
                    _time.sleep(2)  # le fichier a changé : on relit, on retente

            if published:
                sha = (result.get("commit") or {}).get("sha", "")[:7]
                flash(f"Site publié sur GitHub ✔ (commit {sha}). GitHub Pages se met "
                      "à jour dans une à deux minutes.", "ok")
            else:
                hint = {401: "clé invalide", 403: "clé sans droit d’écriture",
                        404: "dépôt ou branche introuvable",
                        409: "conflit GitHub — attendez une minute puis cliquez à "
                             "nouveau sur Publier"}.get(st, result.get("message", ""))
                flash(f"Publication refusée ({st}) : {hint}.", "error")
            return redirect(url_for("admin_home"))
        abort(400)
    conn = db.connect()
    stats = {
        "works": conn.execute("SELECT COUNT(*) c FROM works").fetchone()["c"],
        "published": conn.execute(
            "SELECT COUNT(*) c FROM works WHERE published=1").fetchone()["c"],
        "news": conn.execute("SELECT COUNT(*) c FROM news").fetchone()["c"],
        "messages": conn.execute(
            "SELECT COUNT(*) c FROM messages").fetchone()["c"],
    }
    messages = conn.execute(
        "SELECT * FROM messages ORDER BY id DESC LIMIT 6").fetchall()
    conn.close()
    s = db.get_settings()
    repos, login = [], ""
    token = s.get("github_token", "")
    if token:
        st, me = _gh_call("GET", "https://api.github.com/user", token)
        if st == 200:
            login = me.get("login", "")
        st, rl = _gh_call("GET", "https://api.github.com/user/repos"
                          "?per_page=100&sort=pushed", token)
        if st == 200:
            repos = [r["full_name"] for r in rl
                     if (r.get("permissions") or {}).get("push")]
    return render_template("admin/dashboard.html", stats=stats, messages=messages,
                           s=s, repos=repos, login=login, has_token=bool(token))


@app.route("/admin/fichier-unique")
@require_admin
def admin_mono():
    """Télécharge la page unique (index.html) prête pour GitHub Pages —
    voie de secours sans clé : Add file → Upload files sur github.com."""
    try:
        import build_standalone
        html = build_standalone.build_html()
    except Exception as e:
        flash(f"Impossible de générer la page unique : {e}", "error")
        return redirect(url_for("admin_home"))
    return Response(html, mimetype="text/html; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=index.html"})


# ---------------------------------------- publication multi-fichiers
# Site public exporté en fichiers séparés : accueil léger, images chargées
# à la demande — la version « rapide » du site pour les visiteurs.
import threading  # noqa: E402

_PUB = {"state": "idle", "phase": "", "done": 0, "total": 0, "current": "",
        "error": "", "log": []}

# chemins que nous gérons sur le dépôt (jamais touchés : CNAME, .gitignore…)
_MANAGED = ("galerie/", "evenements/", "uploads/", "static/", "index.html",
            "404.html", "sitemap.xml", "robots.txt", "sw.js", "artiste",
            "atelier", "contact", "demande-specifique", "mentions-legales",
            "confidentialite")


def _git_blob_sha(data):
    """Empreinte Git d'un contenu — pour n'envoyer que les fichiers changés."""
    import hashlib
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def _publish_site_thread(repo, branch, token):
    api = f"https://api.github.com/repos/{repo}"
    try:
        _PUB.update(state="running", phase="Fabrication du site rapide…",
                    done=0, total=0, current="", error="", log=[])
        from tools.export_static import export
        dist = export(progress=_PUB)
        files = {}
        for root, _dirs, fnames in os.walk(dist):
            for fn in fnames:
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, dist).replace(os.sep, "/")
                files[rel] = open(p, "rb").read()
        _PUB.update(phase="Lecture du dépôt GitHub…", total=len(files), done=0)

        st, ref = _gh_call("GET", f"{api}/git/ref/heads/{branch}", token)
        if st != 200:
            raise RuntimeError(f"dépôt ou branche introuvable ({st}) : "
                               f"{(ref or {}).get('message', '')}")
        head = ref["object"]["sha"]
        st, tree = _gh_call("GET", f"{api}/git/trees/{head}?recursive=1", token)
        remote = {}
        if st == 200:
            remote = {e["path"]: e.get("sha") for e in tree.get("tree", [])
                      if e.get("type") == "blob"}

        entries = []
        for rel in sorted(files):
            data = files[rel]
            if remote.get(rel) == _git_blob_sha(data):
                continue  # déjà en ligne, à l'identique
            _PUB.update(phase="Envoi des fichiers…", current=rel,
                        done=len(entries))
            st, blob = _gh_call("POST", f"{api}/git/blobs", token,
                                {"content": base64.b64encode(data).decode(),
                                 "encoding": "base64"})
            if st not in (200, 201):
                raise RuntimeError(f"échec de l'envoi de {rel} ({st}) : "
                                   f"{(blob or {}).get('message', '')}")
            entries.append({"path": rel, "mode": "100644",
                            "type": "blob", "sha": blob["sha"]})
        _PUB["done"] = len(entries)

        # retraits : fichiers présents sur le dépôt mais plus dans l'export
        gone = 0
        for path in remote:
            if path not in files and any(path == m or path.startswith(m)
                                         for m in _MANAGED):
                entries.append({"path": path, "mode": "100644",
                                "type": "blob", "sha": None})
                gone += 1

        if not entries:
            _PUB.update(state="done", phase="Le site en ligne est déjà à jour "
                        "— rien à envoyer.", current="")
            return
        _PUB.update(phase="Finalisation de la publication…",
                    current=f"{len(entries)} fichier(s) modifié(s), {gone} retiré(s)")
        st, newtree = _gh_call("POST", f"{api}/git/trees", token,
                               {"base_tree": head, "tree": entries})
        if st not in (200, 201):
            raise RuntimeError(f"arbre refusé ({st}) : {(newtree or {}).get('message', '')}")
        st, commit = _gh_call("POST", f"{api}/git/commits", token,
                              {"message": "Site mis à jour (version rapide)",
                               "tree": newtree["sha"], "parents": [head]})
        if st not in (200, 201):
            raise RuntimeError(f"commit refusé ({st}) : {(commit or {}).get('message', '')}")
        st, res = _gh_call("PATCH", f"{api}/git/refs/heads/{branch}", token,
                           {"sha": commit["sha"]})
        if st not in (200, 201):
            raise RuntimeError(f"mise à jour de la branche refusée ({st}) : "
                               f"{(res or {}).get('message', '')} — "
                               "retentez dans une minute")
        _PUB.update(state="done",
                    phase=f"Publié ✔ {len(entries) - gone} fichier(s) envoyé(s), "
                    f"{gone} retiré(s) — commit {commit['sha'][:7]}. "
                    "GitHub Pages se met à jour dans une à deux minutes.",
                    current="")
    except Exception as e:  # noqa: BLE001
        _PUB.update(state="error", error=str(e), phase="")


@app.route("/admin/publier/etat")
@require_admin
def admin_publish_state():
    return jsonify(_PUB)


# ---------------------------------------------------------- œuvres

@app.route("/admin/oeuvres")
@require_admin
def admin_works():
    conn = db.connect()
    vif = conn.execute("SELECT * FROM atelier WHERE kind='vif' "
                       "ORDER BY position, id").fetchall()
    conn.close()
    return render_template("admin/works.html",
                           works=get_works(only_published=False), vif=vif)


@app.route("/admin/oeuvres/nouvelle", methods=["GET", "POST"])
@require_admin
def admin_work_new():
    if request.method == "POST":
        if not auth.csrf_ok(request):
            abort(400)
        errors, data = validate_work_form(request)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("admin/work_edit.html", w=data, new=True)
        try:
            folder = None
            if request.files.get("image"):
                up = request.files["image"]
                folder, w, h = imaging.store_image(up, up.filename, WORKS_DIR)
                data["folder"], data["img_w"], data["img_h"] = folder, w, h
                data["tonality"], data["chroma"] = imaging.compute_tonality(
                    os.path.join(WORKS_DIR, folder))
        except imaging.ImageError as e:
            flash(str(e), "error")
            return render_template("admin/work_edit.html", w=data, new=True)

        if not data.get("folder"):
            flash("Merci de choisir une photographie de l'aquarelle.", "error")
            return render_template("admin/work_edit.html", w=data, new=True)

        conn = db.connect()
        pos = conn.execute("SELECT COALESCE(MAX(position),0)+1 p FROM works").fetchone()["p"]
        data["slug"] = unique_slug(conn, "works", slugify(data["title"], "aquarelle"))
        conn.execute(
            "INSERT INTO works(title,slug,description,category,technique,dimensions,"
            "sujet,ambiance,year,folder,img_w,img_h,position,published,"
            "tonality,chroma,created_at) "
            "VALUES(:title,:slug,:description,:category,:technique,:dimensions,"
            ":sujet,:ambiance,:year,:folder,:img_w,:img_h,:position,:published,"
            ":tonality,:chroma,:created_at)",
            {**data, "position": pos, "created_at": db.now_iso()})
        nid = conn.execute(
            "SELECT last_insert_rowid() i").fetchone()["i"]
        save_work_images(conn, nid, request)
        conn.commit()
        conn.close()
        if data.get("published") == 1:
            _n = _push_new_work()
            flash(("Œuvre ajoutée à la galerie — notification envoyée à %d abonné(s)."
                   % _n) if _n else "Œuvre ajoutée à la galerie.", "ok")
        else:
            flash("Œuvre ajoutée à la galerie.", "ok")
        return redirect(url_for("admin_works"))

    empty = {"title": "", "description": "", "category": "", "technique": "",
             "dimensions": "", "year": "", "published": 1}
    return render_template("admin/work_edit.html", w=empty, new=True)


@app.route("/admin/oeuvres/<int:wid>", methods=["GET", "POST"])
@require_admin
def admin_work_edit(wid):
    conn = db.connect()
    w = conn.execute("SELECT * FROM works WHERE id=?", (wid,)).fetchone()
    conn.close()
    if w is None:
        abort(404)
    if request.method == "POST":
        if not auth.csrf_ok(request):
            abort(400)
        action = request.form.get("action")
        if action == "img_add":
            conn = db.connect()
            save_work_images(conn, wid, request)
            conn.commit(); conn.close()
            flash("Image ajoutée à l’œuvre.", "ok")
            return redirect(url_for("admin_work_edit", wid=wid))
        if action == "img_move":
            delta = -1 if request.form.get("dir") == "up" else 1
            conn = db.connect()
            ids = [r["id"] for r in conn.execute(
                "SELECT id FROM works_images WHERE work_id=? ORDER BY position, id",
                (wid,))]
            try:
                iid = int(request.form.get("iid", "0") or 0)
            except ValueError:
                iid = 0
            if iid in ids:
                i = ids.index(iid)
                j = max(0, min(len(ids) - 1, i + delta))
                if i != j:
                    ids[i], ids[j] = ids[j], ids[i]
                    for k, rid in enumerate(ids, 1):
                        conn.execute("UPDATE works_images SET position=? WHERE id=?",
                                     (k, rid))
            conn.commit(); conn.close()
            return redirect(url_for("admin_work_edit", wid=wid))
        if action == "img_del":
            conn = db.connect()
            rowi = conn.execute("SELECT * FROM works_images WHERE id=? AND work_id=?",
                                (request.form.get("iid", "0") or 0, wid)).fetchone()
            if rowi:
                imaging.delete_image_folder(WORKS_DIR, rowi["image"])
                conn.execute("DELETE FROM works_images WHERE id=?", (rowi["id"],))
                for k, r in enumerate(conn.execute(
                        "SELECT id FROM works_images WHERE work_id=? "
                        "ORDER BY position, id", (wid,)), 1):
                    conn.execute("UPDATE works_images SET position=? WHERE id=?",
                                 (k, r["id"]))
            conn.commit(); conn.close()
            flash("Image retirée.", "ok")
            return redirect(url_for("admin_work_edit", wid=wid))
        if action == "toggle":
            conn = db.connect()
            conn.execute("UPDATE works SET published = 1 - published WHERE id=?", (wid,))
            now_pub = conn.execute("SELECT published p FROM works WHERE id=?",
                                   (wid,)).fetchone()["p"]
            conn.commit(); conn.close()
            if now_pub == 1:
                _n = _push_new_work()
                flash(("Œuvre rendue visible — notification envoyée à %d abonné(s)."
                       % _n) if _n else "Visibilité de l'œuvre mise à jour.", "ok")
            else:
                flash("Visibilité de l'œuvre mise à jour.", "ok")
            return redirect(url_for("admin_works"))
        if action == "delete":
            imaging.delete_image_folder(WORKS_DIR, w["folder"])
            conn = db.connect()
            # œuvre « sur le vif » : la même image vit aussi à l'atelier —
            # on la retire des deux côtés pour ne laisser aucun fantôme
            vif_row = conn.execute("SELECT id FROM atelier WHERE kind='vif' AND folder=?",
                                   (w["folder"],)).fetchone()
            if vif_row:
                imaging.delete_image_folder(ATELIER_DIR, w["folder"])
                conn.execute("DELETE FROM atelier WHERE id=?", (vif_row["id"],))
                for k, r in enumerate(conn.execute(
                        "SELECT id FROM atelier WHERE kind='vif' ORDER BY position, id"), 1):
                    conn.execute("UPDATE atelier SET position=? WHERE id=?", (k, r["id"]))
            for r in conn.execute("SELECT image FROM works_images WHERE work_id=?",
                                  (wid,)).fetchall():
                imaging.delete_image_folder(WORKS_DIR, r["image"])
            conn.execute("DELETE FROM works_images WHERE work_id=?", (wid,))
            conn.execute("DELETE FROM works WHERE id=?", (wid,))
            conn.commit(); conn.close()
            flash("Œuvre supprimée.", "ok")
            return redirect(url_for("admin_works"))
        if action == "move":
            delta = -1 if request.form.get("dir") == "up" else 1
            conn = db.connect()
            allw = conn.execute(
                "SELECT id FROM works ORDER BY position, id").fetchall()
            ids = [r["id"] for r in allw]
            i = ids.index(wid)
            j = max(0, min(len(ids) - 1, i + delta))
            if i != j:
                ids[i], ids[j] = ids[j], ids[i]
                for k, rid in enumerate(ids, start=1):
                    conn.execute("UPDATE works SET position=? WHERE id=?", (k, rid))
                conn.commit()
            conn.close()
            return redirect(url_for("admin_works"))

        errors, data = validate_work_form(request)
        if errors:
            for e in errors:
                flash(e, "error")
            data["id"] = wid
            return render_template("admin/work_edit.html", w=data, new=False)
        if request.files.get("image"):
            try:
                up = request.files["image"]
                folder, wpx, hpx = imaging.store_image(up, up.filename, WORKS_DIR)
                imaging.delete_image_folder(WORKS_DIR, w["folder"])
                data["folder"], data["img_w"], data["img_h"] = folder, wpx, hpx
                data["tonality"], data["chroma"] = imaging.compute_tonality(
                    os.path.join(WORKS_DIR, folder))
            except imaging.ImageError as e:
                flash(str(e), "error")
                data["id"] = wid
                return render_template("admin/work_edit.html", w=data, new=False)
        else:
            data["folder"], data["img_w"], data["img_h"] = w["folder"], w["img_w"], w["img_h"]
            data["tonality"], data["chroma"] = w["tonality"] or "", w["chroma"] or 0

        conn = db.connect()
        if data["title"] == w["title"]:
            data["slug"] = w["slug"]  # slug stable tant que le titre ne change pas
        else:
            data["slug"] = unique_slug(conn, "works",
                                       slugify(data["title"], "aquarelle"), exclude_id=wid)
        conn.execute(
            "UPDATE works SET title=:title, slug=:slug, description=:description, "
            "category=:category, technique=:technique, dimensions=:dimensions, "
            "sujet=:sujet, ambiance=:ambiance, "
            "year=:year, folder=:folder, img_w=:img_w, img_h=:img_h, published=:published, "
            "tonality=:tonality, chroma=:chroma WHERE id=:id",
            {**data, "id": wid})
        conn.commit(); conn.close()
        if data["published"] == 1 and w["published"] == 0:
            _n = _push_new_work()
            flash(("Œuvre mise à jour — notification envoyée à %d abonné(s)."
                   % _n) if _n else "Œuvre mise à jour.", "ok")
        else:
            flash("Œuvre mise à jour.", "ok")
        return redirect(url_for("admin_works"))

    conn = db.connect()
    wimgs = conn.execute("SELECT * FROM works_images WHERE work_id=? "
                         "ORDER BY position, id", (wid,)).fetchall()
    conn.close()
    return render_template("admin/work_edit.html", w=w, new=False, wimgs=wimgs)


def validate_work_form(request):
    data = {
        "title": clean(request.form.get("title", ""), 160) or "Sans titre",
        "description": clean(request.form.get("description", ""), 3000),
        "category": clean(request.form.get("category", ""), 80),
        "technique": clean(request.form.get("technique", ""), 120),
        "dimensions": clean(request.form.get("dimensions", ""), 60),
        "sujet": clean(request.form.get("sujet", ""), 160),
        "ambiance": clean(request.form.get("ambiance", ""), 160),
        "year": clean(request.form.get("year", ""), 20),
        "published": 1 if request.form.get("published") else 0,
        "folder": None, "img_w": 0, "img_h": 0, "tonality": "", "chroma": 0,
    }
    errors = []
    if request.files.get("image"):
        try:
            pass  # la validation réelle se fait à l'enregistrement
        except Exception:
            errors.append("Image illisible.")
    return errors, data


# ---------------------------------------------------------- actualités

def save_work_images(conn, wid, request):
    """Ajoute des images complémentaires (max 5 par œuvre)."""
    for f in request.files.getlist("images_add"):
        if not f or not f.filename:
            continue
        n = conn.execute("SELECT COUNT(*) c FROM works_images WHERE work_id=?",
                         (wid,)).fetchone()["c"]
        if n >= 5:
            break
        try:
            folder, _, _ = imaging.store_image(f, f.filename, WORKS_DIR)
        except Exception:
            continue
        conn.execute("INSERT INTO works_images(work_id,image,position) VALUES(?,?,?)",
                     (wid, folder, n + 1))


@app.route("/admin/actualites")
@require_admin
def admin_news():
    conn = db.connect()
    items = conn.execute(
        "SELECT n.*, (SELECT COUNT(*) FROM news_images i WHERE i.news_id=n.id) imgs "
        "FROM news n ORDER BY COALESCE(NULLIF(event_date,''), created_at) DESC, id DESC"
    ).fetchall()
    conn.close()
    return render_template("admin/news.html", items=items)


@app.route("/admin/actualites/nouvelle", methods=["GET", "POST"])
@require_admin
def admin_news_new():
    if request.method == "POST":
        if not auth.csrf_ok(request):
            abort(400)
        data, errors = validate_news_form(request)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("admin/news_edit.html", n=data, new=True, images=[])
        conn = db.connect()
        data["slug"] = unique_slug(conn, "news", slugify(data["title"], "actualite"))
        conn.execute(
            "INSERT INTO news(title,slug,event_date,event_time,place,body,link,cover,"
            "published,position,created_at) "
            "VALUES(:title,:slug,:event_date,:event_time,:place,:body,:link,:cover,"
            ":published,:position,:created_at)",
            {**data, "position": 0, "created_at": db.now_iso()})
        nid = conn.execute("SELECT last_insert_rowid() i").fetchone()["i"]
        save_news_images(conn, nid, request)
        conn.commit(); conn.close()
        if data["published"] == 1:
            _d = (data["event_date"] or "")[:10]
            _titre = ("Nouvel événement à venir"
                      if len(_d) == 10 and _d >= db.now_iso()[:10] else "Nouvel événement")
            try:
                _n = push_send_all(_titre, data["title"], url="/evenements")[0]
            except Exception:
                _n = 0
            flash(("Événement publié — notification envoyée à %d abonné(s)."
                   % _n) if _n else "Événement publié.", "ok")
        else:
            flash("Événement enregistré (masqué).", "ok")
        return redirect(url_for("admin_news"))
    empty = {"title": "", "event_date": "", "body": "", "link": "", "cover": "",
             "published": 1}
    return render_template("admin/news_edit.html", n=empty, new=True, images=[])


@app.route("/admin/actualites/<int:nid>", methods=["GET", "POST"])
@require_admin
def admin_news_edit(nid):
    conn = db.connect()
    n = conn.execute("SELECT * FROM news WHERE id=?", (nid,)).fetchone()
    if n is None:
        conn.close()
        abort(404)
    images = conn.execute("SELECT * FROM news_images WHERE news_id=? ORDER BY position, id",
                          (nid,)).fetchall()
    if request.method == "POST":
        if not auth.csrf_ok(request):
            abort(400)
        action = request.form.get("action")
        if action == "toggle":
            conn.execute("UPDATE news SET published = 1 - published WHERE id=?", (nid,))
            conn.commit(); conn.close()
            flash("Visibilité mise à jour.", "ok")
            return redirect(url_for("admin_news"))
        if action == "delete":
            delete_news(conn, nid)
            conn.commit(); conn.close()
            flash("Actualité supprimée.", "ok")
            return redirect(url_for("admin_news"))
        if "delete_image" in request.form:
            img_id = request.form.get("delete_image", "0")
            img = conn.execute("SELECT * FROM news_images WHERE id=? AND news_id=?",
                               (img_id, nid)).fetchone()
            if img:
                imaging.delete_image_folder(NEWS_DIR, img["image"])
                conn.execute("DELETE FROM news_images WHERE id=?", (img["id"],))
                conn.commit(); conn.close()
                flash("Image retirée.", "ok")
            return redirect(url_for("admin_news_edit", nid=nid))
        if action == "delete_image":
            img = conn.execute("SELECT * FROM news_images WHERE id=? AND news_id=?",
                               (request.form.get("image_id", "0"), nid)).fetchone()
            if img:
                imaging.delete_image_folder(NEWS_DIR, img["image"])
                conn.execute("DELETE FROM news_images WHERE id=?", (img["id"],))
            conn.commit(); conn.close()
            return redirect(url_for("admin_news_edit", nid=nid))

        data, errors = validate_news_form(request)
        if errors:
            for e in errors:
                flash(e, "error")
            data["id"] = nid
            return render_template("admin/news_edit.html", n=data, new=False, images=images)
        # sans nouvelle image principale, on conserve l'actuelle
        if not data["cover"]:
            data["cover"] = n["cover"]
        # slug stable : il ne change que si le titre change
        if data["title"] == n["title"]:
            data["slug"] = n["slug"]
        else:
            data["slug"] = unique_slug(conn, "news", slugify(data["title"], "actualite"),
                                       exclude_id=nid)
        if data["cover"] != n["cover"] and n["cover"]:
            imaging.delete_image_folder(NEWS_DIR, n["cover"])
        conn.execute(
            "UPDATE news SET title=:title, slug=:slug, event_date=:event_date, "
            "event_time=:event_time, place=:place, body=:body, "
            "link=:link, cover=:cover, published=:published WHERE id=:id",
            {**data, "id": nid})
        save_news_images(conn, nid, request)
        conn.commit(); conn.close()
        flash("Actualité mise à jour.", "ok")
        return redirect(url_for("admin_news"))

    conn.close()
    return render_template("admin/news_edit.html", n=n, new=False, images=images)


def delete_news(conn, nid):
    n = conn.execute("SELECT cover FROM news WHERE id=?", (nid,)).fetchone()
    if n and n["cover"]:
        imaging.delete_image_folder(NEWS_DIR, n["cover"])
    for img in conn.execute("SELECT image FROM news_images WHERE news_id=?", (nid,)):
        imaging.delete_image_folder(NEWS_DIR, img["image"])
    conn.execute("DELETE FROM news_images WHERE news_id=?", (nid,))
    conn.execute("DELETE FROM news WHERE id=?", (nid,))


def validate_news_form(request):
    data = {
        "title": clean(request.form.get("title", ""), 200),
        "event_date": clean(request.form.get("event_date", ""), 20),
        "event_time": clean(request.form.get("event_time", ""), 40),
        "place": clean(request.form.get("place", ""), 200),
        "body": clean(request.form.get("body", ""), 20000),
        "link": clean(request.form.get("link", ""), 300),
        "published": 1 if request.form.get("published") else 0,
        "cover": "",
    }
    errors = []
    if len(data["title"]) < 3:
        errors.append("Merci de donner un titre à l'actualité.")
    if data["event_date"]:
        import re as _re
        if not _re.match(r"^\d{4}(-\d{2})?(-\d{2})?$", data["event_date"]):
            errors.append("Date : format attendu AAAA, AAAA-MM ou AAAA-MM-JJ.")
    if data["link"] and not data["link"].startswith(("http://", "https://")):
        errors.append("Le lien doit commencer par http:// ou https://")
    if request.files.get("cover"):
        try:
            up = request.files["cover"]
            folder, _, _ = imaging.store_image(up, up.filename, NEWS_DIR)
            data["cover"] = folder
        except imaging.ImageError as e:
            errors.append(str(e))
    return data, errors


def save_news_images(conn, nid, request):
    files = request.files.getlist("images")
    pos = conn.execute("SELECT COALESCE(MAX(position),0) p FROM news_images WHERE news_id=?",
                       (nid,)).fetchone()["p"]
    for f in files:
        if not f or not f.filename:
            continue
        try:
            folder, _, _ = imaging.store_image(f, f.filename, NEWS_DIR)
            pos += 1
            conn.execute("INSERT INTO news_images(news_id,image,position) VALUES(?,?,?)",
                         (nid, folder, pos))
        except imaging.ImageError as e:
            flash(f"Image ignorée : {e}", "error")


# ---------------------------------------------------------- réglages & mot de passe

# ---------------------------------------------------------- atelier (photos)

@app.route("/admin/atelier", methods=["GET", "POST"])
@require_admin
def admin_atelier():
    if request.method == "POST":
        if not auth.csrf_ok(request):
            abort(400)
        action = request.form.get("action")
        kind = request.form.get("kind", "palette")
        if kind not in ("palette", "materiel"):
            kind = "palette"
        conn = db.connect()
        if action == "upload":
            up = request.files.get("image")
            if not up or not up.filename:
                conn.close()
                flash("Choisissez d’abord une image.", "error")
                return redirect(url_for("admin_atelier"))
            try:
                folder, w, h = imaging.store_image(up, up.filename, ATELIER_DIR)
            except Exception:
                conn.close()
                flash("Image illisible ou trop lourde (26 Mo maximum).", "error")
                return redirect(url_for("admin_atelier"))
            pos = conn.execute(
                "SELECT COALESCE(MAX(position),0)+1 p FROM atelier").fetchone()["p"]
            conn.execute("INSERT INTO atelier(folder,img_w,img_h,position,kind) "
                         "VALUES(?,?,?,?,?)", (folder, w, h, pos, kind))
            conn.commit(); conn.close()
            flash("Photo ajoutée à la palette." if kind == "palette"
                  else "Photo du matériel ajoutée.", "ok")
            return redirect(url_for("admin_atelier"))
        pid = request.form.get("id", "")
        row = (conn.execute("SELECT * FROM atelier WHERE id=? AND kind=?",
                            (pid, kind)).fetchone() if pid.isdigit() else None)
        if row is None:
            conn.close()
            abort(404)
        if action == "replace":
            up = request.files.get("image")
            if not up or not up.filename:
                flash("Choisissez d’abord une image.", "error")
            else:
                try:
                    folder, w, h = imaging.store_image(up, up.filename, ATELIER_DIR)
                except Exception:
                    folder = None
                    flash("Image illisible ou trop lourde (26 Mo maximum).", "error")
                if folder:
                    imaging.delete_image_folder(ATELIER_DIR, row["folder"])
                    conn.execute("UPDATE atelier SET folder=?, img_w=?, img_h=? "
                                 "WHERE id=?", (folder, w, h, row["id"]))
                    flash("Photo remplacée.", "ok")
        elif action == "move":
            delta = -1 if request.form.get("dir") == "up" else 1
            ids = [r["id"] for r in conn.execute(
                "SELECT id FROM atelier WHERE kind=? ORDER BY position, id", (kind,))]
            i = ids.index(row["id"])
            j = max(0, min(len(ids) - 1, i + delta))
            if i != j:
                ids[i], ids[j] = ids[j], ids[i]
                for k, rid in enumerate(ids, 1):
                    conn.execute("UPDATE atelier SET position=? WHERE id=?", (k, rid))
            flash("Ordre mis à jour.", "ok")
        elif action == "delete":
            imaging.delete_image_folder(ATELIER_DIR, row["folder"])
            conn.execute("DELETE FROM atelier WHERE id=?", (row["id"],))
            for k, r in enumerate(conn.execute(
                    "SELECT id FROM atelier WHERE kind=? "
                    "ORDER BY position, id", (kind,)), 1):
                conn.execute("UPDATE atelier SET position=? WHERE id=?", (k, r["id"]))
            flash("Photo supprimée.", "ok")
        else:
            flash("Action inconnue.", "error")
        conn.commit(); conn.close()
        return redirect(url_for("admin_atelier"))
    conn = db.connect()
    photos = conn.execute("SELECT * FROM atelier WHERE kind='palette' "
                          "ORDER BY position, id").fetchall()
    materiel = conn.execute("SELECT * FROM atelier WHERE kind='materiel' "
                            "ORDER BY position, id").fetchall()
    conn.close()
    return render_template("admin/atelier.html", photos=photos, materiel=materiel)


# ---------------------------------------------------------- sur le vif

def _vif_create_work(conn, folder, w, h):
    """Crée l'œuvre galerie « Sur le vif » liée à une photo de l'atelier.

    L'image reste stockée à l'atelier (dossier unique) et la galerie la sert
    par le repli works→atelier — exactement comme les œuvres d'origine."""
    k = conn.execute("SELECT COUNT(*) c FROM works WHERE technique='Sur le vif'"
                     ).fetchone()["c"] + 1
    while conn.execute("SELECT 1 FROM works WHERE slug=?",
                       ("sur-le-vif-%d" % k,)).fetchone():
        k += 1
    pos = conn.execute("SELECT COALESCE(MAX(position),0)+1 p FROM works"
                       ).fetchone()["p"]
    conn.execute(
        "INSERT INTO works(title,slug,description,category,technique,dimensions,"
        "year,folder,img_w,img_h,position,published,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,1,?)",
        ("Sur le vif %d" % k, "sur-le-vif-%d" % k, "", "", "Sur le vif", "", "",
         folder, w, h, pos, db.now_iso()))


@app.route("/admin/vif", methods=["GET", "POST"])
@require_admin
def admin_vif():
    if request.method == "POST":
        if not auth.csrf_ok(request):
            abort(400)
        action = request.form.get("action")
        conn = db.connect()
        if action == "upload":
            up = request.files.get("image")
            if not up or not up.filename:
                conn.close()
                flash("Choisissez d’abord une image.", "error")
                return redirect(url_for("admin_vif"))
            try:
                folder, w, h = imaging.store_image(up, up.filename, ATELIER_DIR)
            except Exception:
                conn.close()
                flash("Image illisible ou trop lourde (26 Mo maximum).", "error")
                return redirect(url_for("admin_vif"))
            pos = conn.execute(
                "SELECT COALESCE(MAX(position),0)+1 p FROM atelier").fetchone()["p"]
            conn.execute("INSERT INTO atelier(folder,img_w,img_h,position,kind) "
                         "VALUES(?,?,?,?,'vif')", (folder, w, h, pos))
            # même image dans la galerie : œuvre « Sur le vif »
            # (image stockée une seule fois, à l'atelier, servie par repli)
            _vif_create_work(conn, folder, w, h)
            conn.commit(); conn.close()
            flash("Aquarelle sur le vif ajoutée à la galerie et sur la page L’atelier.", "ok")
            return redirect(url_for("admin_vif"))
        if action == "sync":
            # photos ajoutées avec une ancienne version, présentes à l'atelier
            # mais jamais intégrées à la galerie : on crée les œuvres manquantes
            # (aucune image n'est modifiée ni supprimée)
            created = 0
            for r in conn.execute("SELECT folder, img_w, img_h FROM atelier "
                                  "WHERE kind='vif' ORDER BY position, id").fetchall():
                if conn.execute("SELECT 1 FROM works WHERE folder=?",
                                (r["folder"],)).fetchone():
                    continue
                _vif_create_work(conn, r["folder"], r["img_w"], r["img_h"])
                created += 1
            conn.commit(); conn.close()
            flash(("%d aquarelle(s) sur le vif intégrée(s) à la galerie." % created)
                  if created else
                  "Toutes les aquarelles sur le vif sont déjà dans la galerie.", "ok")
            return redirect(url_for("admin_vif"))
        vid = request.form.get("id", "")
        row = (conn.execute("SELECT * FROM atelier WHERE id=? AND kind='vif'",
                            (vid,)).fetchone() if vid.isdigit() else None)
        if row is None:
            conn.close()
            abort(404)
        if action == "move":
            delta = -1 if request.form.get("dir") == "up" else 1
            rows = conn.execute("SELECT id, folder FROM atelier WHERE kind='vif' "
                                "ORDER BY position, id").fetchall()
            ids = [r["id"] for r in rows]
            i = ids.index(row["id"])
            j = max(0, min(len(ids) - 1, i + delta))
            if i != j:
                fi, fj = rows[i]["folder"], rows[j]["folder"]
                ids[i], ids[j] = ids[j], ids[i]
                for k, rid in enumerate(ids, 1):
                    conn.execute("UPDATE atelier SET position=? WHERE id=?", (k, rid))
                # la galerie suit le même ordre (œuvres liées par le dossier)
                wi = conn.execute("SELECT id, position FROM works WHERE folder=?",
                                  (fi,)).fetchone()
                wj = conn.execute("SELECT id, position FROM works WHERE folder=?",
                                  (fj,)).fetchone()
                if wi and wj and wi["position"] != wj["position"]:
                    conn.execute("UPDATE works SET position=? WHERE id=?",
                                 (wj["position"], wi["id"]))
                    conn.execute("UPDATE works SET position=? WHERE id=?",
                                 (wi["position"], wj["id"]))
            flash("Ordre mis à jour.", "ok")
        elif action == "delete":
            imaging.delete_image_folder(ATELIER_DIR, row["folder"])
            conn.execute("DELETE FROM atelier WHERE id=?", (row["id"],))
            # retirer aussi l'œuvre liée dans la galerie (même image, même dossier)
            for wr in conn.execute("SELECT id, folder FROM works WHERE folder=?",
                                   (row["folder"],)).fetchall():
                for im in conn.execute("SELECT image FROM works_images WHERE work_id=?",
                                       (wr["id"],)).fetchall():
                    imaging.delete_image_folder(WORKS_DIR, im["image"])
                conn.execute("DELETE FROM works_images WHERE work_id=?", (wr["id"],))
                conn.execute("DELETE FROM works WHERE id=?", (wr["id"],))
            for k, r in enumerate(conn.execute(
                    "SELECT id FROM atelier WHERE kind='vif' ORDER BY position, id"), 1):
                conn.execute("UPDATE atelier SET position=? WHERE id=?", (k, r["id"]))
            flash("Aquarelle sur le vif supprimée (galerie et atelier).", "ok")
        else:
            flash("Action inconnue.", "error")
        conn.commit(); conn.close()
        return redirect(url_for("admin_vif"))
    conn = db.connect()
    items = conn.execute("SELECT * FROM atelier WHERE kind='vif' "
                         "ORDER BY position, id").fetchall()
    gfolders = {r["folder"] for r in conn.execute(
        "SELECT folder FROM works WHERE technique='Sur le vif'")}
    conn.close()
    return render_template("admin/vif.html", items=items, gfolders=gfolders,
                           n_missing=sum(1 for a in items if a["folder"] not in gfolders))


# ------------------------------------------------- publication GitHub

def _gh_call(method, url, token, payload=None):
    """Appel à l'API GitHub (urllib, aucune dépendance). Retourne (statut, json)."""
    import json as _json, urllib.request, urllib.error
    req = urllib.request.Request(
        url, method=method,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "hilaire-legentil-site",
                 "X-GitHub-Api-Version": "2022-11-28"})
    body = _json.dumps(payload).encode() if payload is not None else None
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, body, timeout=30) as r:
            return r.status, _json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            detail = _json.loads(e.read().decode()).get("message", "")
        except Exception:
            detail = ""
        return e.code, {"message": detail or str(e.reason)}


SETTING_GROUPS = [
    ("Accueil — grand bandeau", [
        ("hero_baseline", "Petite ligne au-dessus du nom"),
        ("hero_title", "Nom affiché en grand"),
        ("hero_sub", "Ligne sous le nom"),
        ("home_intro", "Phrase d'accroche de la page d'accueil"),
    ]),
    ("Page « La démarche de l'artiste »", [
        ("artist_intro", "Premier paragraphe (Parcours)"),
        ("regard_art", "Encadré « En un regard » — Art"),
        ("regard_sujet", "Encadré « En un regard » — Sujet"),
        ("regard_univers", "Encadré « En un regard » — Univers"),
        ("regard_support", "Encadré « En un regard » — Support"),
        ("regard_region", "Encadré « En un regard » — Région"),
    ]),
    ("Sous-titres des pages", [
        ("gallery_sub", "Page Galerie — sous-titre"),
        ("events_sub", "Page Événements — sous-titre"),
        ("contact_sub", "Page Contacts — sous-titre"),
        ("atelier_sub", "Page Cahier technique — sous-titre"),
    ]),
    ("Coordonnées & réseaux", [
        ("contact_phone", "Téléphone affiché sur le site"),
        ("contact_email", "Adresse e-mail affichée sur le site"),
        ("instagram", "Compte Instagram (sans @)"),
        ("facebook", "Page Facebook — adresse complète (facultatif)"),
    ]),
    ("Pied de page", [
        ("footer_job", "Métier (première ligne)"),
        ("footer_tag", "Deuxième ligne"),
    ]),
    ("Référencement — nom de domaine", [
        ("site_domain", "Adresse complète du site (ex. https://www.hilaire-legentil.fr — vide tant qu'il n'y a pas de domaine)"),
    ]),
    ("Mesure d'audience", [
        ("ga_id", "ID Google Analytics (ex. G-XXXXXXXXXX — vide = désactivé)"),
    ]),
]


@app.route("/admin/notifications", methods=["GET", "POST"])
@require_admin
def admin_notifications():
    conn = db.connect()
    n_subs = conn.execute("SELECT COUNT(*) c FROM push_subs").fetchone()["c"]
    last = conn.execute("SELECT created_at FROM push_subs "
                        "ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if request.method == "POST":
        if not auth.csrf_ok(request):
            abort(400)
        title = (request.form.get("title") or "").strip() or "Nouvelle aquarelle en ligne"
        body = (request.form.get("body") or "").strip() or \
            "Une nouvelle aquarelle vient d'être ajoutée à la galerie."
        if not PUSH_ENABLED:
            flash("Les notifications navigateur ne sont pas actives sur ce serveur "
                  "(module pywebpush absent).", "error")
        elif not n_subs:
            flash("Aucun abonné pour le moment — les visiteurs s'inscrivent depuis "
                  "le bouton « M'alerter » en bas du site.", "error")
        else:
            sent, failed, gone = push_send_all(title, body)
            msg = "Notification envoyée à %d abonné(s)." % sent
            if gone:
                msg += " %d abonnement(s) obsolète(s) retiré(s)." % gone
            if failed:
                msg += " %d échec(s) temporaire(s)." % failed
            flash(msg, "ok" if sent else "error")
        return redirect(url_for("admin_notifications"))
    return render_template("admin/notifications.html", n_subs=n_subs,
                           last=last, push_enabled=PUSH_ENABLED)


@app.route("/admin/reglages", methods=["GET", "POST"])
@require_admin
def admin_settings():
    keys = [k for _, items in SETTING_GROUPS for k, _ in items]
    if request.method == "POST":
        if not auth.csrf_ok(request):
            abort(400)
        action = request.form.get("action")
        if action == "password":
            current = request.form.get("current_password", "")
            new = request.form.get("new_password", "")
            from werkzeug.security import check_password_hash
            conn = db.connect()
            row = conn.execute("SELECT password_hash FROM admin WHERE username=?",
                               (auth.current_admin(),)).fetchone()
            conn.close()
            if not row or not check_password_hash(row["password_hash"], current):
                flash("Mot de passe actuel incorrect.", "error")
            elif len(new) < 10:
                flash("Le nouveau mot de passe doit contenir au moins 10 caractères.", "error")
            else:
                auth.set_password(auth.current_admin(), new)
                flash("Mot de passe mis à jour.", "ok")
            return redirect(url_for("admin_settings"))
        for key in keys:
            db.set_setting(key, clean(request.form.get(key, ""), 2000))
        flash("Réglages enregistrés.", "ok")
        return redirect(url_for("admin_settings"))
    s = db.get_settings()
    return render_template("admin/settings.html", groups=SETTING_GROUPS, s=s)


@app.route("/admin/accueil", methods=["GET", "POST"])
@require_admin
def admin_homepage():
    """Photo principale de la page d'accueil (remplaçable)."""
    import subprocess, sys
    from PIL import Image
    if request.method == "POST":
        if not auth.csrf_ok(request):
            abort(400)
        slot = request.form.get("slot", "")
        up = request.files.get("image")
        if slot != "1":
            flash("Emplacement inconnu.", "error")
            return redirect(url_for("admin_homepage"))
        if not up or not up.filename:
            flash("Choisissez d'abord une image.", "error")
            return redirect(url_for("admin_homepage"))
        try:
            im = Image.open(up.stream).convert("RGB")
        except Exception:
            flash("Image illisible ou trop lourde (26 Mo maximum).", "error")
            return redirect(url_for("admin_homepage"))
        if im.width > 1600:
            im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
        path = os.path.join(BASE_DIR, "static", "img", "carousel", "c%s.webp" % slot)
        im.save(path, "WEBP", quality=80, method=6)
        r = subprocess.run([sys.executable, "build_standalone.py"],
                           cwd=BASE_DIR, capture_output=True, text=True)
        if r.returncode == 0:
            flash("Photo de l'accueil mise à jour.", "ok")
        else:
            flash("Image mise à jour — la version « fichier unique » sera "
                  "régénérée à la prochaine publication.", "ok")
        return redirect(url_for("admin_homepage"))
    return render_template("admin/homepage.html")


# ------------------------------------------------- publication GitHub

@app.route("/admin/messages")
@require_admin
def admin_messages():
    conn = db.connect()
    messages = conn.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 200").fetchall()
    conn.close()
    return render_template("admin/messages.html", messages=messages)


# =================================================================

def clean(value, maxlen):
    return str(value or "").strip()[:maxlen]


def time_now():
    import time
    return int(time.time())


db.init_db()

SETTING_DEFAULTS = {
    "hero_baseline": "Aquarelles — mer & paysage",
    "hero_title": "Hilaire Legentil",
    "hero_sub": "Artiste auteur",
    "home_intro": "Onirique résumerait assez bien mon approche de l’aquarelle.",
    "artist_intro": "Derrière ces paysages, ces couleurs et ces formes en mouvement, "
                    "il y a une énergie, quelque chose de profond qui me bouleverse.",
    "regard_art": "Aquarelle",
    "regard_sujet": "Mer & paysage",
    "regard_univers": "calme · onirique · puissance",
    "regard_support": "Papier 100 % coton",
    "regard_region": "Normandie — Yvetot-Bocage (Manche)",
    "gallery_sub": "Aquarelles — mer & paysage, sur papier 100 % coton",
    "events_sub": "J’espère que cette nouvelle saison d’exposition vous inspirera, "
                  "vous permettra d’accéder à l’univers sensible du paysage et de l’aquarelle.",
    "contact_sub": "Et nous aurons peut-être le plaisir d’échanger, "
                   "c’est toujours un moment d’humanité privilégié.",
    "atelier_sub": "Les étapes d’une aquarelle · Des aquarelles montées sur châssis · "
                   "Fabrication des cadres",
    "footer_job": "Artiste auteur",
    "footer_tag": "Aquarelles — mer & paysage",
}


def _ensure_setting_defaults():
    current = db.get_settings()
    for k, v in SETTING_DEFAULTS.items():
        if k not in current:
            db.set_setting(k, v)


_ensure_setting_defaults()


def ensure_admin():
    """Crée un compte administrateur au premier lancement (dépôt GitHub,
    base vierge) : identifiant hilaire + mot de passe aléatoire écrit dans
    data/admin_password.txt."""
    conn = db.connect()
    has = conn.execute("SELECT COUNT(*) c FROM admin").fetchone()["c"]
    conn.close()
    if has:
        return
    import secrets as _secrets
    import string as _string
    pwd = "".join(_secrets.choice(_string.ascii_letters + _string.digits)
                  for _ in range(14))
    auth.create_admin("hilaire", pwd)
    with open(os.path.join(db.DATA_DIR, "admin_password.txt"), "w") as f:
        f.write("Identifiant : hilaire\nMot de passe : " + pwd + "\n")
    print("* Compte administrateur créé — mot de passe initial : data/admin_password.txt")


ensure_admin()


# ------------------------------------------------------- en-têtes HTTP

@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    return resp


def _restore_first_run():
    """Premier lancement (base vide + fichier unique présent) : restaure
    automatiquement œuvres, images, actualités et réglages depuis index.html.
    Ne s'exécute JAMAIS si la base contient déjà des œuvres."""
    try:
        conn = db.connect()
        n = conn.execute("SELECT COUNT(*) c FROM works").fetchone()["c"]
        conn.close()
        if n or not os.path.exists(os.path.join(BASE_DIR, "index.html")):
            return
        from tools.restaure import restore_all, DEFAULT_PASSWORD
        r = restore_all()
        print(f"* Premier lancement : {r['works']} œuvres, {r['news']} actualités "
              f"restaurées depuis le fichier unique.")
        print(f"* Connexion administrateur : hilaire / {DEFAULT_PASSWORD}")
    except Exception as e:
        print(f"* Restauration automatique ignorée : {e}")


if __name__ == "__main__":
    _restore_first_run()
    from waitress import serve
    port = int(os.environ.get("PORT", "8000"))
    print(f"* Site d'Hilaire Legentil — http://0.0.0.0:{port}")
    serve(app, host="0.0.0.0", port=port, threads=6)
