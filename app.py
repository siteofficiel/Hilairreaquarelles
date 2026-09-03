"""Hilaire Legentil — Artiste aquarelliste · Aquarelles mer & paysage.

Site public (galerie, actualités, contact, carte) + espace administrateur
(gestion des œuvres, des actualités, des réglages, des messages).
"""
import os
import sys
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
VENDOR = os.path.join(BASE_DIR, "vendor")
if VENDOR not in sys.path:
    sys.path.insert(0, VENDOR)

from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_from_directory, session, url_for)
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
    return {
        "SITE": SITE,
        "S": s,
        "admin_user": auth.current_admin(),
        "csrf": auth.csrf_token(),
        "year": date.today().year,
        "map_center": [49.4894, -1.5048],   # Yvetot-Bocage (Normandie)
        "map_radius": 75000,                # 75 km
    }


def site_url(path="/"):
    domain = SITE["domain"].rstrip("/")
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
    cand = [w for w in works if w["chroma"]]
    vivid = max(cand, key=lambda w: w["chroma"]) if cand else None
    mute = min(cand, key=lambda w: w["chroma"]) if cand else None
    return render_template("index.html", works=works[:6], news=get_news(limit=3),
                           hero_works=works[:5], vivid=vivid, mute=mute)


@app.route("/artiste")
def artist():
    return render_template("artist.html", expositions=get_news(limit=12))


@app.route("/atelier")
def atelier():
    conn = db.connect()
    photos = conn.execute(
        "SELECT folder, img_w, img_h FROM atelier "
        "WHERE kind='palette' ORDER BY position, id").fetchall()
    conn.close()
    return render_template("atelier.html", photos=photos)


@app.route("/aquarelles")
def gallery():
    works = get_works()
    cats = []
    for w in works:
        if w["category"] and w["category"] not in cats:
            cats.append(w["category"])
    conn = db.connect()
    vif = conn.execute("SELECT folder, img_w, img_h FROM atelier "
                       "WHERE kind='vif' ORDER BY position, id").fetchall()
    conn.close()
    return render_template("gallery.html", works=works, categories=cats, vif=vif)


@app.route("/aquarelles/<slug>")
def work(slug):
    works = get_works()
    row = next((w for w in works if w["slug"] == slug), None)
    if row is None:
        abort(404)
    idx = works.index(row)
    prev = works[idx - 1] if idx > 0 else (works[-1] if works else None)
    nxt = works[idx + 1] if idx < len(works) - 1 else (works[0] if works else None)
    return render_template("work.html", w=row, prev=prev, next=nxt,
                           index=idx + 1, total=len(works))


@app.route("/actualites")
def news_list():
    return render_template("news.html", items=get_news())


@app.route("/actualites/<slug>")
def news_item(slug):
    row, images = get_news_item(slug)
    if row is None or (not row["published"] and not auth.current_admin()):
        abort(404)
    others = [n for n in get_news(limit=4) if n["id"] != row["id"]][:3]
    return render_template("news_item.html", n=row, images=images, others=others)


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
    return send_from_directory(os.path.join(root, folder), filename,
                               max_age=31536000)


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
    if SITE["domain"]:
        body += f"Sitemap: {SITE['domain']}/sitemap.xml\n"
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
            import base64 as _b64
            api = f"https://api.github.com/repos/{repo}/contents/index.html"
            st, cur = _gh_call("GET", f"{api}?ref={branch}", token)
            payload = {"message": "Site mis à jour depuis l'espace d'administration",
                       "content": _b64.b64encode(html.encode()).decode(),
                       "branch": branch}
            if st == 200 and cur.get("sha"):
                payload["sha"] = cur["sha"]
            st, res = _gh_call("PUT", api, token, payload)
            if st in (200, 201):
                sha = (res.get("commit") or {}).get("sha", "")[:7]
                flash(f"Site publié sur GitHub ✔ (commit {sha}). GitHub Pages se met "
                      "à jour dans une à deux minutes.", "ok")
            else:
                hint = {401: "clé invalide", 403: "clé sans droit d’écriture",
                        404: "dépôt ou branche introuvable",
                        409: "conflit — réessayez"}.get(st, res.get("message", ""))
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
            "year,folder,img_w,img_h,position,published,tonality,chroma,created_at) "
            "VALUES(:title,:slug,:description,:category,:technique,:dimensions,"
            ":year,:folder,:img_w,:img_h,:position,:published,:tonality,:chroma,:created_at)",
            {**data, "position": pos, "created_at": db.now_iso()})
        conn.commit()
        conn.close()
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
        if action == "toggle":
            conn = db.connect()
            conn.execute("UPDATE works SET published = 1 - published WHERE id=?", (wid,))
            conn.commit(); conn.close()
            flash("Visibilité de l'œuvre mise à jour.", "ok")
            return redirect(url_for("admin_works"))
        if action == "delete":
            imaging.delete_image_folder(WORKS_DIR, w["folder"])
            conn = db.connect()
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
            "year=:year, folder=:folder, img_w=:img_w, img_h=:img_h, published=:published, "
            "tonality=:tonality, chroma=:chroma WHERE id=:id",
            {**data, "id": wid})
        conn.commit(); conn.close()
        flash("Œuvre mise à jour.", "ok")
        return redirect(url_for("admin_works"))

    return render_template("admin/work_edit.html", w=w, new=False)


def validate_work_form(request):
    data = {
        "title": clean(request.form.get("title", ""), 160) or "Sans titre",
        "description": clean(request.form.get("description", ""), 3000),
        "category": clean(request.form.get("category", ""), 80),
        "technique": clean(request.form.get("technique", ""), 120),
        "dimensions": clean(request.form.get("dimensions", ""), 60),
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
            "INSERT INTO news(title,slug,event_date,body,link,cover,published,position,"
            "created_at) VALUES(:title,:slug,:event_date,:body,:link,:cover,:published,"
            ":position,:created_at)",
            {**data, "position": 0, "created_at": db.now_iso()})
        nid = conn.execute("SELECT last_insert_rowid() i").fetchone()["i"]
        save_news_images(conn, nid, request)
        conn.commit(); conn.close()
        flash("Actualité publiée." if data["published"] else "Actualité enregistrée (masquée).", "ok")
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
            "UPDATE news SET title=:title, slug=:slug, event_date=:event_date, body=:body,"
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
                         "VALUES(?,?,?,?,'palette')", (folder, w, h, pos))
            conn.commit(); conn.close()
            flash("Photo ajoutée à la page L’atelier.", "ok")
            return redirect(url_for("admin_atelier"))
        pid = request.form.get("id", "")
        row = (conn.execute("SELECT * FROM atelier WHERE id=? AND kind='palette'",
                            (pid,)).fetchone() if pid.isdigit() else None)
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
                "SELECT id FROM atelier WHERE kind='palette' ORDER BY position, id")]
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
                    "SELECT id FROM atelier WHERE kind='palette' "
                    "ORDER BY position, id"), 1):
                conn.execute("UPDATE atelier SET position=? WHERE id=?", (k, r["id"]))
            flash("Photo supprimée.", "ok")
        else:
            flash("Action inconnue.", "error")
        conn.commit(); conn.close()
        return redirect(url_for("admin_atelier"))
    conn = db.connect()
    photos = conn.execute("SELECT * FROM atelier WHERE kind='palette' "
                          "ORDER BY position, id").fetchall()
    conn.close()
    return render_template("admin/atelier.html", photos=photos)


# ---------------------------------------------------------- sur le vif

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
            conn.commit(); conn.close()
            flash("Aquarelle sur le vif ajoutée à la galerie.", "ok")
            return redirect(url_for("admin_vif"))
        vid = request.form.get("id", "")
        row = (conn.execute("SELECT * FROM atelier WHERE id=? AND kind='vif'",
                            (vid,)).fetchone() if vid.isdigit() else None)
        if row is None:
            conn.close()
            abort(404)
        if action == "move":
            delta = -1 if request.form.get("dir") == "up" else 1
            ids = [r["id"] for r in conn.execute(
                "SELECT id FROM atelier WHERE kind='vif' ORDER BY position, id")]
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
                    "SELECT id FROM atelier WHERE kind='vif' ORDER BY position, id"), 1):
                conn.execute("UPDATE atelier SET position=? WHERE id=?", (k, r["id"]))
            flash("Aquarelle sur le vif supprimée.", "ok")
        else:
            flash("Action inconnue.", "error")
        conn.commit(); conn.close()
        return redirect(url_for("admin_vif"))
    conn = db.connect()
    items = conn.execute("SELECT * FROM atelier WHERE kind='vif' "
                         "ORDER BY position, id").fetchall()
    conn.close()
    return render_template("admin/vif.html", items=items)


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


@app.route("/admin/reglages", methods=["GET", "POST"])
@require_admin
def admin_settings():
    keys = [
        ("home_intro", "Phrase d'accroche de la page d'accueil"),
        ("artist_intro", "Présentation — page L'artiste (premier paragraphe)"),
        ("contact_phone", "Téléphone affiché sur le site"),
        ("contact_email", "Adresse e-mail affichée sur le site"),
        ("instagram", "Compte Instagram (sans @)"),
    ]
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
        for key, _ in keys:
            db.set_setting(key, clean(request.form.get(key, ""), 2000))
        flash("Réglages enregistrés.", "ok")
        return redirect(url_for("admin_settings"))
    s = db.get_settings()
    return render_template("admin/settings.html", keys=keys, s=s)


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


if __name__ == "__main__":
    from waitress import serve
    port = int(os.environ.get("PORT", "8000"))
    print(f"* Site d'Hilaire Legentil — http://0.0.0.0:{port}")
    serve(app, host="0.0.0.0", port=port, threads=6)
