"""Génère une version monofichier du site : un seul HTML autonome.

Tout est intégré : styles, scripts, polices (base64), images des œuvres et
des actualités (base64), Leaflet et ses données. Le fichier s'ouvre d'un
double-clic, sans serveur — navigation interne de type galerie.
"""
import base64
import json
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "vendor"))

import db  # noqa: E402
from utils import parse_date  # noqa: E402

OUT = os.path.join(os.path.dirname(BASE), "hilaire-legentil", "index.html")


def b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def img_uri(folder, area="works", prefer="medium"):
    """Data URI de l'image la plus légère disponible (WebP d'abord)."""
    root = os.path.join(BASE, "uploads", area, folder)
    for name in (f"{prefer}.webp", f"{prefer}.jpg"):
        p = os.path.join(root, name)
        if os.path.exists(p):
            mime = "image/webp" if name.endswith(".webp") else "image/jpeg"
            return f"data:{mime};base64," + b64(p), name
    return "", ""


def font_face(family, style, weight, filename):
    return ("@font-face{font-family:'%s';font-style:%s;font-weight:%d;"
            "src:url(data:font/woff2;base64,%s) format('woff2');}"
            % (family, style, weight,
               b64(os.path.join(BASE, "static", "fonts", filename))))


def build_html():
    conn = sqlite3.connect(os.path.join(BASE, "data", "hilaire.sqlite3"))
    conn.row_factory = sqlite3.Row
    S = {r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings")}

    # ------------------------------------------------------------- œuvres
    works = []
    for w in conn.execute("SELECT * FROM works WHERE published=1 ORDER BY position, id"):
        uri, _ = img_uri(w["folder"], "works")
        if not uri:
            continue
        wims = [img_uri(r["image"], "works")[0] for r in conn.execute(
            "SELECT image FROM works_images WHERE work_id=? ORDER BY position, id",
            (w["id"],))]
        works.append({
            "t": w["title"], "s": w["slug"], "c": w["category"] or "",
            "y": w["year"] or "", "d": w["description"] or "",
            "i": uri, "w": w["img_w"], "h": w["img_h"],
            "tn": w["tonality"] or "", "cf": w["chroma"] or 0,
            "sj": w["sujet"] or "", "am": w["ambiance"] or "",
            "tc": w["technique"] or "",
            "im": [u for u in wims if u],
        })

    # --------------------------------------------------------- actualités
    news = []
    for n in conn.execute("SELECT * FROM news WHERE published=1 "
                          "ORDER BY COALESCE(NULLIF(event_date,''),created_at) DESC, id DESC"):
        cover, _ = img_uri(n["cover"], "news") if n["cover"] else ("", "")
        imgs = []
        for im in conn.execute("SELECT * FROM news_images WHERE news_id=? "
                               "ORDER BY position, id", (n["id"],)):
            u, _ = img_uri(im["image"], "news")
            if u:
                imgs.append(u)
        date_fr, _ = parse_date(n["event_date"])
        paras = [p.strip() for p in (n["body"] or "").split("\n\n") if p.strip()]
        news.append({"t": n["title"], "s": n["slug"], "dt": date_fr,
                     "rd": n["event_date"] or "",
                     "tm": n["event_time"] or "", "pl": n["place"] or "",
                     "p": paras, "cov": cover, "img": imgs,
                     "l": n["link"] or ""})

    # ------------------------------------------------------------- atelier
    atelier, photos = [], []
    for a in conn.execute("SELECT folder, img_w, img_h, kind FROM atelier "
                          "ORDER BY position, id"):
        uri, _ = img_uri(a["folder"], "atelier")
        if not uri:
            continue
        if a["kind"] == "palette":
            photos.append({"i": uri, "w": a["img_w"], "h": a["img_h"]})
        else:
            atelier.append({"i": uri, "w": a["img_w"], "h": a["img_h"]})
    conn.close()

    data = {
        "works": works, "news": news, "pin": "aquarelles_2026",
        "homeIntro": S.get("home_intro", ""),
        "artistIntro": S.get("artist_intro", ""),
        "heroB": S.get("hero_baseline", "Aquarelles — mer & paysage"),
        "heroT": S.get("hero_title", "Hilaire Legentil"),
        "heroS": S.get("hero_sub", "Artiste auteur"),
        "gallerySub": S.get("gallery_sub", "Aquarelles — mer & paysage, sur papier 100 % coton"),
        "eventsSub": S.get("events_sub", "J’espère que cette nouvelle saison d’exposition vous inspirera, vous permettra d’accéder à l’univers sensible du paysage et de l’aquarelle."),
        "contactSub": S.get("contact_sub", "Et nous aurons peut-être le plaisir d’échanger, c’est toujours un moment d’humanité privilégié."),
        "atelierSub": S.get("atelier_sub", "Les étapes d’une aquarelle · Des aquarelles montées sur châssis · Fabrication des cadres"),
        "footerJob": S.get("footer_job", "Artiste auteur"),
        "footerTag": S.get("footer_tag", "Aquarelles — mer & paysage"),
        "rA": S.get("regard_art", "Aquarelle"),
        "rS": S.get("regard_sujet", "Mer & paysage"),
        "rU": S.get("regard_univers", "calme · onirique · puissance"),
        "rP": S.get("regard_support", "Papier 100 % coton"),
        "rR": S.get("regard_region", "Normandie — Yvetot-Bocage (Manche)"),
        "phone": S.get("contact_phone", ""),
        "email": S.get("contact_email", ""),
        "instagram": S.get("instagram", ""),
        "fb": S.get("facebook", ""), "ga": S.get("ga_id", ""),
        "atelier": atelier,
        "photos": photos,
        "portrait": "data:image/jpeg;base64,"
                    + b64(os.path.join(BASE, "static", "img", "portrait.jpg")),
    }
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    data_json = data_json.replace("</", "<\\/")  # sécurité balise <script>

    fonts = "\n".join([
        font_face("Cormorant Garamond", "normal", 500, "CormorantGaramond-500.woff2"),
        font_face("Cormorant Garamond", "normal", 600, "CormorantGaramond-600.woff2"),
        font_face("Cormorant Garamond", "italic", 400, "CormorantGaramond-400i.woff2"),
        font_face("Jost", "normal", 400, "Jost-400.woff2"),
        font_face("Jost", "normal", 500, "Jost-500.woff2"),
    ])

    with open(os.path.join(BASE, "static", "css", "main.css")) as f:
        main_css = f.read()
    # la feuille fusionnée commence par la portion Leaflet
    _start = main_css.index("/* --- Leaflet")
    _end = main_css.index("/* ============================================================")
    leaflet_css = main_css[_start:_end]
    with open(os.path.join(BASE, "static", "js", "leaflet.js")) as f:
        leaflet_js = f.read()

    favicon = ("data:image/svg+xml;base64,"
               + base64.b64encode(open(os.path.join(BASE, "static/img/favicon.svg"), "rb").read()).decode())

    html = TEMPLATE.replace("__FONTS__", fonts) \
                   .replace("__LEAFLET_CSS__", leaflet_css) \
                   .replace("__LEAFLET_JS__", leaflet_js) \
                   .replace("__FAVICON__", favicon) \
                   .replace("__WASHCARD__", "data:image/webp;base64," + b64(os.path.join(BASE, "static", "img", "wash-card.webp"))) \
                   .replace("__FJOB__", S.get("footer_job", "Artiste auteur")) \
                   .replace("__FTAG__", S.get("footer_tag", "Aquarelles — mer & paysage")) \
                   .replace("__HC1__", "data:image/webp;base64," + b64(os.path.join(BASE, "static", "img", "carousel", "c1.webp"))) \
                   .replace("__HC2__", "data:image/webp;base64," + b64(os.path.join(BASE, "static", "img", "carousel", "c2.webp"))) \
                   .replace("__HC3__", "data:image/webp;base64," + b64(os.path.join(BASE, "static", "img", "carousel", "c3.webp"))) \
                   .replace("__HC4__", "data:image/webp;base64," + b64(os.path.join(BASE, "static", "img", "carousel", "c4.webp"))) \
                   .replace("__HC5__", "data:image/webp;base64," + b64(os.path.join(BASE, "static", "img", "carousel", "c5.webp"))) \
                   .replace("__DATA__", data_json)
    return html


def main():
    html = build_html()
    with open(OUT, "w") as f:
        f.write(html)

    # 404.html : sur GitHub Pages, rattrape « …/admin » vers « …/#/admin »
    page404 = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hilaire Legentil — Artiste auteur · Aquarelles — mer &amp; paysage</title>
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:radial-gradient(60% 80% at 80% 0%,rgba(34,155,117,0.280),transparent 60%),#faf8f3;
font-family:Georgia,serif;color:#263a40;text-align:center;padding:2rem}
.box{max-width:520px}
p{line-height:1.7}
a{color:#097380}
small{font-family:system-ui,sans-serif;color:#5a6a68}

</style>
</head>
<body>
<div class="box">
<p style="letter-spacing:.25em;text-transform:uppercase;font-size:.8rem;color:#097380;font-family:system-ui,sans-serif">Hilaire Legentil</p>
<h1 style="font-size:2rem;margin:.4rem 0 1rem">Cette page n’existe pas.</h1>
<p id="msg">Vous serez ramené à la galerie dans un instant.</p>
<p><a href="./">← Revenir à l’accueil</a></p>
<small>Espace administrateur : <a href="./#/admin">cette adresse</a></small>
</div>
<script>
var p=location.pathname;
if(/\/admin\/?$/.test(p)){location.replace(p.replace(/admin\/?$/,"")+"#/admin");}
else if(document.getElementById("msg")){document.getElementById("msg").style.display="none";}
</script>
</body>
</html>
"""
    out404 = os.path.join(os.path.dirname(OUT), "404.html")
    with open(out404, "w") as f:
        f.write(page404)
    print(f"→ {out404}")
    print(f"→ {OUT}  ({len(html)/1e6:.2f} Mo)")


# ══════════════════════════════════════════════════════════════════════
#  GABARIT DU FICHIER UNIQUE
# ══════════════════════════════════════════════════════════════════════
TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hilaire Legentil — Artiste auteur · Aquarelles — mer &amp; paysage</title>
<meta name="description" content="Hilaire LEGENTIL, artiste auteur. Aquarelles — mer &amp; paysage, sur papier 100 % coton.">
<meta property="og:title" content="Hilaire Legentil — Aquarelles mer &amp; paysage">
<meta property="og:description" content="Aquarelles originales sur papier 100 % coton — mer &amp; paysage de Normandie.">
<meta property="og:locale" content="fr_FR">
<meta name="theme-color" content="#0a7d85">
<link rel="icon" href="__FAVICON__">
<style>__LEAFLET_CSS__</style>
<style>
__FONTS__
:root{--paper:#faf8f3;--paper2:#f3efe7;--card:#fffdf9;--ink:#0e2a32;--text:#263a40;
--muted:#5a6a68;--teal:#38a888;--tealInk:#097380;--tealDeep:#0a7d85;--tealSoft:#e7f2f0;
--tealWash:#d9ebe8;--hair:#d2c9b6;--sh:0 18px 40px -18px rgba(28,58,65,.22);
--shs:0 10px 26px -14px rgba(28,58,65,.18);
--serif:"Cormorant Garamond","Times New Roman",Georgia,serif;
--sans:"Jost","Segoe UI",system-ui,-apple-system,sans-serif}
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--text);font:400 17px/1.72 var(--sans);
-webkit-font-smoothing:antialiased}
img{max-width:100%;height:auto;display:block}
a{color:var(--tealInk);text-decoration:none}a:hover{color:var(--tealDeep)}
:focus-visible{outline:2px solid var(--teal);outline-offset:3px;border-radius:2px}
h1,h2,h3{font-family:var(--serif);font-weight:500;color:var(--ink);margin:0 0 .55em;line-height:1.14}
p{margin:0 0 1.1em}
.container{width:min(1180px,92vw);margin-inline:auto}.narrow{width:min(760px,92vw);margin-inline:auto}
.center{text-align:center}.muted{color:var(--muted)}.small{font-size:.95rem}
.skip-link{position:absolute;left:1rem;top:-4rem;z-index:200;background:var(--ink);color:#fff;
padding:.7rem 1.2rem;border-radius:4px;transition:top .2s}
.skip-link:focus{top:1rem;color:#fff}
.label{font-weight:600;font-size:.74rem;letter-spacing:.22em;text-transform:uppercase;color:var(--tealInk);
margin:0 0 1.1rem;display:flex;align-items:center;gap:.8rem}
.label::before{content:"";width:2rem;height:1px;background:var(--teal);opacity:.65}
.center .label{justify-content:center}
.h2{font-size:clamp(1.9rem,3.6vw,2.9rem)}.h3{font-size:clamp(1.4rem,2.6vw,1.9rem)}
.lead{font-size:1.13rem;line-height:1.75;color:#2e4247}
/* en-tête */
.site-header{position:fixed;inset:0 0 auto 0;z-index:100;padding:1.05rem 0;
transition:background .35s,box-shadow .35s,padding .35s}
.site-header.scrolled{background:rgba(250,248,243,.95);backdrop-filter:blur(10px);
box-shadow:0 1px 0 var(--hair);padding:.62rem 0}
.header-inner{width:min(1180px,92vw);margin-inline:auto;display:flex;align-items:center;
justify-content:space-between;gap:1.5rem}
.brand{display:flex;flex-direction:column;gap:.14rem}
.brand-name{font-family:var(--serif);font-weight:600;font-size:1.32rem;color:var(--ink);line-height:1}
.brand-baseline{font-size:.62rem;letter-spacing:.26em;text-transform:uppercase;color:var(--teal)}
.site-nav ul{display:flex;gap:2rem;list-style:none;margin:0;padding:0}
@media (max-width:1240px){.site-nav ul{gap:1.1rem}}
@media (max-width:1080px){.site-nav a:not(.nav-close){font-size:.72rem;letter-spacing:.09em}}
.site-nav a:not(.nav-close){font-size:.8rem;letter-spacing:.14em;text-transform:uppercase;
color:var(--ink);padding:.4rem 0;position:relative}
.site-nav a:not(.nav-close)::after{content:"";position:absolute;left:0;right:100%;bottom:0;
height:1px;background:var(--teal);transition:right .3s}
.site-nav a:not(.nav-close):hover::after,.site-nav a.on::after{right:0}
.site-nav a.on{color:var(--tealInk)}
.nav-toggle{display:none;background:none;border:0;cursor:pointer;padding:.6rem}
.nav-toggle span{display:block;width:26px;height:1.6px;background:var(--ink);margin:.42rem 0}
@media(max-width:900px){
.nav-toggle{display:block}
.site-nav{position:fixed;inset:0;background:rgba(250,248,243,.985);display:flex;
align-items:center;justify-content:center;opacity:0;visibility:hidden;transition:.35s;z-index:99}
.site-nav.open{opacity:1;visibility:visible}
.site-nav ul{flex-direction:column;gap:1.9rem;text-align:center}
.site-nav ul a:not(.nav-close){font-size:1.05rem;letter-spacing:.2em}
body.nav-open{overflow:hidden}}
/* héros */
.hero{position:relative;padding:0;display:grid;grid-template-columns:100%;grid-template-rows:auto auto}
.hero-wash{position:relative;z-index:0;grid-column:1;grid-row:1;align-self:start}.hero-wash img{width:100%;height:auto;display:block}.hero::before{content:"";position:absolute;inset:0;z-index:1;pointer-events:none;background:radial-gradient(62% 78% at 50% 24%,rgba(250,248,243,.70),rgba(250,248,243,.30) 55%,transparent 76%)}
.hero-inner{position:relative;grid-column:1;grid-row:1;align-self:start;justify-self:center;z-index:2;width:min(1180px,92vw);margin:clamp(4.6rem,13vh,8.5rem) auto 1.1rem;text-align:center}.hero-baseline,.hero-title,.hero-sub{text-shadow:0 1px 2px rgba(250,248,243,.95),0 0 16px rgba(250,248,243,.85),0 2px 28px rgba(250,248,243,.75)}.hero-after{position:relative;grid-column:1;grid-row:2;justify-self:center;z-index:2;width:min(1180px,92vw);margin:0 auto;padding:2rem 0 2.4rem;text-align:center}
.hero-baseline{font-size:.8rem;font-weight:600;letter-spacing:.3em;text-transform:uppercase;
color:var(--tealInk);margin-bottom:1.3rem}
.hero-title{font-size:clamp(3rem,8.6vw,6.6rem);font-weight:500;line-height:1.02;color:var(--ink);margin:0 0 1.1rem}
.hero-sub{font-family:var(--serif);font-style:italic;font-size:clamp(1.15rem,2.4vw,1.6rem);
color:var(--tealDeep);margin-bottom:1.4rem}
.hero-intro{max-width:34em;font-size:1.06rem;margin-bottom:2rem}
.hero-cta{display:flex;align-items:center;gap:2.2rem;flex-wrap:wrap;margin:0}
.btn{display:inline-block;font-weight:500;font-size:.8rem;letter-spacing:.18em;
text-transform:uppercase;color:#fff;border:1px solid var(--tealDeep);padding:.95rem 2.1rem;
border-radius:2px;transition:.3s;background:var(--tealDeep);cursor:pointer}
.btn:hover{background:var(--teal);color:#fff}
.btn.btn-outline{background:transparent;color:var(--tealInk);border-color:var(--teal)}
.btn.btn-outline:hover{background:var(--teal);color:#fff}
.btn-full{width:100%;text-align:center}
.link-arrow{font-family:var(--serif);font-style:italic;font-size:1.12rem;color:var(--tealInk);
display:inline-flex;align-items:center;gap:.55rem}
.link-arrow::after{content:"→";font-family:var(--sans);font-style:normal;transition:transform .3s}
.link-arrow:hover::after{transform:translateX(5px)}
.lnk{border-bottom:1px solid var(--tealWash);padding-bottom:1px}.lnk:hover{border-color:var(--teal)}
.frieze{position:relative;z-index:1;display:flex;align-items:flex-end;justify-content:center;
gap:2.4rem;width:min(1180px,94vw);margin:0 auto}
.frieze a{display:block}
.frieze img{background:var(--card);padding:.55rem .55rem 1.5rem;border:1px solid var(--hair);
box-shadow:var(--shs);transition:transform .5s}
.frieze a:hover img{transform:translateY(-6px)}
.f1 img{height:min(30vw,300px);width:auto;max-width:46vw}
.f2 img{height:min(38vw,400px);width:auto;max-width:46vw}
.f3 img{height:min(24vw,236px);width:auto;max-width:46vw}
.f1{transform:translateY(-1.4rem)}.f3{transform:translateY(-2.6rem)}
@media(max-width:760px){.frieze{gap:1rem}.f3{display:none}
.f1 img,.f2 img{height:34vw}.f1{transform:translateY(-1rem)}}
/* sections */
.section{padding:clamp(4rem,9vw,7.5rem) 0}
.section-head{display:flex;align-items:flex-end;justify-content:space-between;gap:2rem;
margin-bottom:2.6rem;flex-wrap:wrap}
.page-head{padding:clamp(9rem,16vw,12rem) 0 clamp(2.2rem,5vw,3.6rem);
background:radial-gradient(120% 90% at 85% -10%,rgba(34,155,117,0.300),transparent 55%),
linear-gradient(180deg,#f5f1e9,var(--paper))}
.page-title{font-size:clamp(2.5rem,6vw,4.3rem);margin-bottom:.35rem}
.page-sub{font-family:var(--serif);font-style:italic;color:var(--tealDeep);
font-size:clamp(1.05rem,2.2vw,1.35rem);margin:0}
.section-artist{background:linear-gradient(180deg,var(--paper),#f7f3eb)}
.artist-home{display:grid;grid-template-columns:1.25fr .85fr;gap:clamp(2.5rem,6vw,5.5rem);align-items:center}
.artist-home-figure{position:relative;transform:rotate(.6deg)}
.artist-home-figure img{background:var(--card);padding:.5rem .5rem 1.4rem;border:1px solid var(--hair);
box-shadow:var(--sh);max-height:560px;width:100%;object-fit:cover}
.figure-caption{position:absolute;left:0;bottom:-1.7rem;font-size:.8rem;color:var(--muted);
font-style:italic;font-family:var(--serif)}
.mini-quote{margin:1.8rem 0 .4rem;padding:1.4rem 0 .2rem;border-top:1px solid var(--hair);
font-family:var(--serif);font-style:italic;font-size:1.18rem;color:#2e4247;line-height:1.6}
.mini-quote cite,.big-quote cite{display:block;margin-top:.8rem;font-family:var(--sans);font-style:normal;
font-size:.72rem;letter-spacing:.2em;text-transform:uppercase;color:var(--muted)}
.quote-section{background:linear-gradient(180deg,#edf3f1,var(--tealSoft));border-top:1px solid var(--hair);border-bottom:1px solid var(--hair)}
.quote-mark{width:52px;margin:0 auto 1.6rem;display:block}
.big-quote{margin:0;font-family:var(--serif);font-style:italic;font-weight:400;
font-size:clamp(1.45rem,3.2vw,2.15rem);line-height:1.5;color:var(--ink)}
.big-quote cite{color:var(--teal);margin-top:1.6rem}
.wash-band{background:radial-gradient(60% 120% at 20% 50%,rgba(34,155,117,0.280),transparent 60%),
radial-gradient(50% 100% at 85% 40%,rgba(17,89,106,.12),transparent 60%)}
.contact-invitation{background:radial-gradient(70% 110% at 12% 0%,rgba(31,179,196,0.260),transparent 60%),radial-gradient(70% 110% at 88% 8%,rgba(34,155,117,0.260),transparent 60%),linear-gradient(180deg,var(--paper),var(--tealSoft) 320%);text-align:center}
.invitation-cta{display:flex;gap:2.2rem;align-items:center;justify-content:center;flex-wrap:wrap;margin-top:2.2rem}
/* galerie — filtres pro : menus déroulants + tri automatique */
.hl-filters{margin:-1.6rem auto 0;padding:clamp(.9rem,2.2vw,1.3rem) clamp(1rem,2.6vw,1.5rem);
background:rgba(252,250,246,.92);border:1px solid var(--hair);border-radius:var(--r-card);box-shadow:var(--shs)}
.hl-fbar{display:grid;grid-template-columns:repeat(4,minmax(0,1fr)) minmax(150px,auto);gap:.6rem}
.hl-dd{position:relative;min-width:0}
.hl-dd-btn{display:flex;width:100%;min-height:48px;align-items:center;gap:.55rem;text-align:left;
font-family:var(--sans);background:var(--card);color:var(--text);border:1px solid var(--hair);
border-radius:var(--r-btn);padding:.5rem .8rem;cursor:pointer;transition:border-color .25s,box-shadow .25s}
.hl-dd-btn:hover{border-color:var(--teal)}
.hl-dd-lab{flex:none;font-size:.62rem;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.hl-dd-val{flex:1;min-width:0;font-size:.92rem;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hl-dd-arr{flex:none;color:var(--teal);transition:transform .3s var(--t-soft)}
.hl-dd.is-set .hl-dd-val{color:var(--tealInk);font-weight:600}
.hl-dd.is-open .hl-dd-btn{border-color:var(--teal);box-shadow:0 0 0 3px rgba(10,125,133,.12)}
.hl-dd.is-open .hl-dd-arr{transform:rotate(180deg)}
.hl-dd-menu{position:absolute;top:calc(100% + 6px);left:0;z-index:40;min-width:100%;
max-width:min(88vw,20rem);max-height:min(60vh,22rem);overflow:auto;background:var(--card);
border:1px solid var(--hair);border-radius:var(--r-btn);box-shadow:var(--sh);padding:.3rem;
opacity:0;visibility:hidden;transform:translateY(-4px);
transition:opacity .22s var(--t-soft),transform .22s var(--t-soft),visibility .22s}
.hl-dd.is-open .hl-dd-menu{opacity:1;visibility:visible;transform:none}
.hl-dd-sort .hl-dd-menu{left:auto;right:0}
.hl-dd-opt{display:flex;width:100%;align-items:center;gap:.5rem;text-align:left;
font-family:var(--sans);font-size:.88rem;color:var(--text);background:none;border:0;
border-radius:4px;padding:.55rem .65rem;cursor:pointer;transition:background .2s}
.hl-dd-opt:hover{background:rgba(10,125,133,.08)}
.hl-dd-opt.is-sel{color:var(--tealInk);font-weight:600;background:rgba(10,125,133,.10)}
.hl-dd-n{margin-left:auto;flex:none;font-size:.72rem;color:var(--muted);
background:rgba(10,125,133,.08);border-radius:999px;padding:.08rem .5rem}
.hl-dd-opt.is-sel .hl-dd-n{background:var(--tealDeep);color:#fff}
.hl-dd-opt.is-sel::after{content:"✓";flex:none;margin-left:.1rem;color:var(--tealDeep);font-weight:700}
.hl-dd-opt[data-dot]::before{content:"";flex:none;width:9px;height:9px;border-radius:50%}
.hl-dd-opt[data-dot="Contraste coloré"]::before{background:#38a888}
.hl-dd-opt[data-dot="Doux"]::before{background:#c9a25e}
.hl-fstatus{display:flex;align-items:center;flex-wrap:wrap;gap:.55rem .9rem;margin-top:.85rem}
.hl-fcount{margin:0;font-family:var(--sans);font-size:.74rem;letter-spacing:.14em;
text-transform:uppercase;color:var(--muted)}
.hl-fcount.is-empty{text-transform:none;letter-spacing:0;font-family:var(--serif);
font-style:italic;font-size:1rem;color:var(--ink)}
.hl-fchips{display:flex;flex-wrap:wrap;gap:.45rem}
.hl-fchip{display:inline-flex;align-items:center;gap:.4rem;min-height:40px;
font-family:var(--sans);font-size:.78rem;color:var(--tealInk);background:rgba(10,125,133,.10);
border:1px solid rgba(10,125,133,.25);border-radius:999px;padding:.3rem .75rem;cursor:pointer;transition:all .25s}
.hl-fchip:hover{background:rgba(10,125,133,.18)}
.hl-fx{font-size:.95rem;line-height:1;color:var(--teal)}
.hl-freset{margin-left:auto;min-height:40px;font-family:var(--sans);font-size:.72rem;
letter-spacing:.12em;text-transform:uppercase;color:var(--tealInk);background:none;
border:1px solid var(--hair);border-radius:999px;padding:.4rem .95rem;cursor:pointer;transition:all .25s}
.hl-freset:hover{border-color:var(--teal);background:rgba(10,125,133,.06)}
@keyframes hlIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.work.hl-in{animation:hlIn .45s var(--t-soft) both}
@media(prefers-reduced-motion:reduce){.work.hl-in{animation:none}
.hl-dd-menu,.hl-dd-arr{transition:none}}
@media(max-width:1000px){.hl-fbar{grid-template-columns:repeat(2,minmax(0,1fr))}
.hl-dd-sort{grid-column:1/-1}}
@media(max-width:480px){.hl-fbar{grid-template-columns:1fr}
.hl-dd-val{font-size:.88rem}.hl-freset{margin-left:0;width:100%}}
/* notifications — nouvelles aquarelles mises en ligne */
.hl-new-badge{position:absolute;top:.75rem;left:.75rem;z-index:3;
font-family:var(--sans);font-size:.58rem;letter-spacing:.16em;text-transform:uppercase;
color:#fff;background:var(--tealDeep);border-radius:3px;padding:.28rem .55rem;
box-shadow:0 6px 14px -6px rgba(10,125,133,.55);white-space:nowrap}
.hl-toast{position:fixed;right:1.1rem;bottom:1.1rem;z-index:900;
width:min(340px,calc(100vw - 2.2rem));background:var(--card);border:1px solid var(--hair);
border-left:4px solid var(--teal);border-radius:var(--r-card);box-shadow:var(--sh);
padding:1.05rem 1.15rem 1.15rem;opacity:0;transform:translateY(12px);
transition:opacity .45s var(--t-soft),transform .45s var(--t-soft)}
.hl-toast.is-in{opacity:1;transform:none}
.hl-toast-label{margin:0 0 .35rem;font-family:var(--sans);font-size:.62rem;
letter-spacing:.18em;text-transform:uppercase;color:var(--teal)}
.hl-toast-title{margin:0 0 .3rem;font-family:var(--serif);font-size:1.14rem;color:var(--ink);line-height:1.25}
.hl-toast-sub{margin:0 0 .85rem;font-size:.85rem;color:var(--muted)}
.hl-toast-cta{display:inline-block;font-family:var(--sans);font-size:.76rem;letter-spacing:.12em;
text-transform:uppercase;color:var(--tealInk);text-decoration:none;border:1px solid var(--teal);
border-radius:var(--r-btn);padding:.55rem 1.05rem;transition:all .25s}
.hl-toast-cta:hover{background:var(--tealDeep);border-color:var(--tealDeep);color:#fff}
.hl-toast-x{position:absolute;top:.5rem;right:.5rem;background:none;border:0;cursor:pointer;
color:var(--muted);font-size:1.3rem;line-height:1;padding:.35rem;min-width:44px;min-height:44px}
.hl-toast-x:hover{color:var(--ink)}
@media(prefers-reduced-motion:reduce){.hl-toast{transition:none}}
@media(max-width:480px){.hl-toast{right:.6rem;left:.6rem;bottom:.6rem;width:auto}}
.gallery-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:clamp(1.4rem,3vw,2.6rem)
clamp(1.2rem,2.4vw,2rem);align-items:start;grid-auto-flow:dense}
.work{display:block;color:inherit;position:relative}
.work.s-std{grid-column:span 2}.work.s-big{grid-column:span 3}.work.s-wide{grid-column:span 4}
.work.s-tall{grid-column:span 2;grid-row:span 2;padding-top:1.6rem}
.work:nth-child(6n+3){margin-top:2.4rem}.work:nth-child(6n+5){margin-top:1.2rem}
.work-frame{display:block;background:var(--card);border:1px solid var(--hair);padding:.5rem;
box-shadow:var(--shs);transition:box-shadow .5s,transform .5s}
.work-frame img{width:100%;transition:transform .85s cubic-bezier(.19,1,.22,1)}
.work:hover .work-frame{transform:translateY(-5px);box-shadow:var(--sh)}
.work:hover .work-frame img{transform:scale(1.035)}
.work-caption{display:block;padding:.85rem .3rem 0}
.work-title{display:block;font-family:var(--serif);font-size:1.18rem;color:var(--ink);line-height:1.25}
.work-meta{display:block;font-size:.74rem;letter-spacing:.14em;text-transform:uppercase;
color:var(--muted);margin-top:.3rem}
@media(max-width:1000px){.gallery-grid{grid-template-columns:repeat(4,1fr)}.work.s-wide{grid-column:span 4}}
@media(max-width:700px){.gallery-grid{grid-template-columns:repeat(2,1fr)}
.work.s-std,.work.s-big,.work.s-tall{grid-column:span 1}.work.s-wide{grid-column:span 2}
.work:nth-child(6n+3),.work:nth-child(6n+5){margin-top:0}.work.s-tall{padding-top:0}
.work:nth-child(even){margin-top:1.6rem}}
/* page œuvre */
.work-layout{display:grid;grid-template-columns:minmax(0,1.75fr) minmax(280px,.85fr);
gap:clamp(2.4rem,5vw,4.6rem);align-items:start}
.work-figure{margin:0}
.work-figure img{width:100%;background:var(--card);border:1px solid var(--hair);
padding:clamp(.7rem,2vw,1.6rem);box-shadow:var(--sh)}
.work-tech{margin-top:.9rem;font-size:.78rem;letter-spacing:.1em;color:var(--muted);text-transform:uppercase}
.work-facts{margin:0 0 1.8rem;border-top:1px solid var(--hair)}
.work-facts div{display:flex;justify-content:space-between;gap:1.5rem;padding:.72rem 0;
border-bottom:1px solid var(--hair)}
.work-facts dt{font-size:.74rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.work-facts dd{margin:0;font-size:.95rem;color:var(--ink);text-align:right}
.work-nav{display:flex;flex-direction:column;gap:1rem;margin:2.2rem 0 1.2rem}
.work-nav-link{display:flex;flex-direction:column;gap:.15rem;border:1px solid var(--hair);
padding:.85rem 1.1rem;border-radius:2px;background:var(--card);color:inherit}
.work-nav-link:hover{border-color:var(--teal);color:inherit}
.wn-label{font-size:.68rem;letter-spacing:.18em;text-transform:uppercase;color:var(--tealInk)}
.wn-title{font-family:var(--serif);font-size:1.1rem;color:var(--ink)}
.is-next{text-align:right;align-items:flex-end}
.work-counter{font-size:.8rem;color:var(--muted);letter-spacing:.08em}
@media(max-width:1000px){.work-layout{grid-template-columns:1fr}}
.next-teaser{background:var(--paper2);border-top:1px solid var(--hair)}
.teaser-inner{display:flex;align-items:center;justify-content:space-between;gap:3rem}
.teaser-figure{flex:0 0 300px}.teaser-figure img{border:1px solid var(--hair);padding:.4rem;background:var(--card)}
@media(max-width:760px){.teaser-inner{flex-direction:column-reverse;align-items:flex-start}}
/* actualités */
.news-rows{display:flex;flex-direction:column}
.evt-label{margin:0 0 1.1rem}
.evt-divider{display:flex;align-items:center;gap:1.1rem;margin:2.7rem 0 .5rem}
.evt-divider::before,.evt-divider::after{content:"";flex:1;height:1px;background:var(--hair)}
.evt-divider span{font-family:var(--sans);font-size:.7rem;letter-spacing:.2em;
text-transform:uppercase;color:var(--muted);white-space:nowrap}
.news-row{display:flex;align-items:center;gap:clamp(1.4rem,3vw,2.6rem);padding:1.6rem .4rem;
border-bottom:1px solid var(--hair);color:inherit;transition:background .3s,padding .3s}
.news-row:first-child{border-top:1px solid var(--hair)}
.news-row:hover{background:#f5f1e8;color:inherit;padding-left:1rem}
.news-thumb{flex:0 0 clamp(96px,16vw,220px)}
.news-thumb img{width:100%;border:1px solid var(--hair);padding:.3rem;background:var(--card)}
.news-body{flex:1;display:flex;flex-direction:column;gap:.28rem}
.news-date{font-size:.73rem;font-weight:500;letter-spacing:.18em;text-transform:uppercase;color:var(--tealInk)}
.news-title{font-family:var(--serif);font-size:clamp(1.25rem,2.6vw,1.7rem);color:var(--ink);line-height:1.25}
.news-excerpt{color:var(--muted);font-size:.95rem}
.news-arrow{font-size:1.3rem;color:var(--teal)}
@media(max-width:760px){.news-arrow{display:none}}
.article{max-width:760px}
.article-cover{margin:0 0 2.6rem}
.article-cover img{width:100%;border:1px solid var(--hair);padding:.6rem;background:var(--card);box-shadow:var(--shs)}
.article-body{font-size:1.08rem}.article-body p{line-height:1.85}
.article-gallery{display:grid;grid-template-columns:1fr 1fr;gap:1.4rem;margin:2.6rem 0}
.article-gallery img{width:100%;border:1px solid var(--hair);padding:.35rem;background:var(--card)}
@media(max-width:640px){.article-gallery{grid-template-columns:1fr}}
.article-footer{margin-top:3rem;padding-top:1.4rem;border-top:1px solid var(--hair)}
/* contact */
.contact-layout{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(300px,.85fr);
gap:clamp(2.4rem,5vw,4.5rem);align-items:start}
.contact-form,.contact-card{background:var(--card);border:1px solid var(--hair);border-radius:3px;
padding:clamp(1.6rem,3.5vw,2.8rem);box-shadow:var(--shs);text-align:left}
.field{margin-bottom:1.5rem}
.field-row{display:grid;grid-template-columns:1fr 1fr;gap:1.4rem}
label{display:block;font-size:.74rem;letter-spacing:.16em;text-transform:uppercase;
color:var(--ink);margin-bottom:.5rem;font-weight:500}
.req{color:var(--teal)}.opt{color:var(--muted);text-transform:none;letter-spacing:.04em}
input[type=text],input[type=email],input[type=tel],select,textarea{width:100%;font:inherit;
font-size:1rem;color:var(--ink);background:var(--paper);border:0;border-bottom:1px solid var(--hair);
padding:.65rem .2rem;border-radius:0}
textarea{resize:vertical;min-height:130px;border:1px solid var(--hair);padding:.8rem}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--teal)}
select{appearance:none;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='8'><path d='M1 1l5 5 5-5' fill='none' stroke='%2338a888' stroke-width='1.6'/></svg>");
background-repeat:no-repeat;background-position:right .4rem center;padding-right:1.6rem}
.form-note{font-size:.8rem;color:var(--muted);margin:1.1rem 0 0}
.form-success{background:var(--tealSoft);border:1px solid var(--tealWash);border-radius:3px;
padding:1.3rem 1.5rem;margin-bottom:1.8rem;color:var(--tealDeep)}
.contact-aside{display:flex;flex-direction:column;gap:1.6rem}
.contact-list{list-style:none;margin:0;padding:0}
.contact-list li{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;
padding:.6rem 0;border-bottom:1px solid var(--hair);font-size:.95rem}
.contact-list li span:first-child{color:var(--muted);font-size:.78rem;letter-spacing:.14em;
text-transform:uppercase;padding-top:.2rem}
@media(max-width:900px){.contact-layout{grid-template-columns:1fr}.field-row{grid-template-columns:1fr;gap:0}}
.map-section{background:var(--paper2);border-top:1px solid var(--hair)}
.map-note{max-width:640px}
.map-wrap{position:relative;border:1px solid var(--hair);background:var(--card);box-shadow:var(--shs)}
#map{height:clamp(340px,55vw,520px);width:100%;z-index:1}
.map-credit{margin:.6rem 1rem .8rem;font-size:.74rem;color:var(--muted)}
/* l'artiste */
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:clamp(2.4rem,6vw,5.5rem)}
@media(max-width:900px){.two-col{grid-template-columns:1fr}}
.fact-card{background:var(--card);border:1px solid var(--hair);padding:1.8rem 1.9rem;
border-radius:3px;box-shadow:var(--shs)}
.fact-title{font-size:1.35rem;margin-bottom:1.1rem}
.fact-list{margin:0}.fact-list div{display:flex;gap:1.4rem;padding:.6rem 0;
border-bottom:1px solid var(--hair);justify-content:space-between}
.fact-list div:last-child{border-bottom:0}
.fact-list dt{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:var(--tealInk);padding-top:.25rem}
.fact-list dd{margin:0;text-align:right;color:var(--ink);font-size:.98rem}
.section-expos{background:var(--paper2);border-top:1px solid var(--hair)}
.timeline{list-style:none;margin:0;padding:0}
.timeline li{border-bottom:1px solid var(--hair)}.timeline li:first-child{border-top:1px solid var(--hair)}
.timeline a{display:flex;align-items:baseline;gap:1.8rem;padding:1.35rem .4rem;color:inherit;transition:.3s}
.timeline a:hover{background:#f5f1e8;padding-left:1rem;color:inherit}
.tl-date{flex:0 0 170px;font-size:.74rem;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:var(--tealInk)}
.tl-title{font-family:var(--serif);font-size:1.3rem;color:var(--ink);flex:1}
.tl-arrow{color:var(--teal)}
@media(max-width:700px){.tl-date{flex-basis:110px}.tl-arrow{display:none}}
/* footer */
.site-footer{background:#0f2e35;color:#c9d8d6;margin-top:4rem}
.footer-inner{width:min(1180px,92vw);margin-inline:auto;display:grid;
grid-template-columns:1.3fr 1fr 1fr;gap:2.6rem;padding:clamp(3rem,6vw,4.5rem) 0 2.4rem}
.footer-col .brand-name{color:#f4efe6;font-size:1.5rem}
.footer-baseline{font-family:var(--serif);font-style:italic;color:#9db8b4;font-size:1.02rem}
.footer-loc{color:#7fa19c;font-size:.85rem;letter-spacing:.1em}
.footer-title{font-weight:500;font-size:.72rem;letter-spacing:.22em;text-transform:uppercase;
color:var(--teal);margin-bottom:1.1rem}
.footer-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:.55rem}
.footer-list a{color:#c9d8d6}.footer-list a:hover{color:#fff}
.footer-legal{border-top:1px solid rgba(255,255,255,.09)}
.footer-legal p{width:min(1180px,92vw);margin:0 auto;padding:1.2rem 0;font-size:.78rem;color:#7fa19c}
.footer-legal a{color:#a9c3bf}
@media(max-width:800px){.footer-inner{grid-template-columns:1fr 1fr}}
@media(max-width:560px){.footer-inner{grid-template-columns:1fr}}
/* animations */
.reveal{opacity:0;transform:translateY(16px);transition:opacity .9s,transform .9s}
.reveal.vis{opacity:1;transform:none}
.d1{transition-delay:.12s}.d2{transition-delay:.24s}.d3{transition-delay:.36s}.d4{transition-delay:.5s}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}
.reveal{opacity:1;transform:none;transition:none}*{transition-duration:.01ms!important}}
.fade-in{animation:fadein .5s ease both}
@keyframes fadein{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}

/* ═══════════════════════ DÉCOR AQUARELLE (DA carte de visite) ═══════════════════════
   Vaguelettes signature, lavis derrière les œuvres, houle du pied de page. */

/* — vague signature sous les labels — */
.label::before{
  width:34px;height:8px;min-width:34px;background:var(--teal);opacity:1;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='34' height='8' viewBox='0 0 34 8'><path d='M1 5c4-4 8-4 12 0s8 4 12 0 6-3 8-1' fill='none' stroke='%2338a888' stroke-width='1.7' stroke-linecap='round'/></svg>") center/34px 8px no-repeat;
}

/* — en-têtes de page : lavis aux coins + vague sous le titre — */
.page-head{position:relative;}
.page-head::before{
  content:"";position:absolute;inset:0;pointer-events:none;
  background:
    radial-gradient(42% 62% at 7% 10%, rgba(34,155,117,0.300), transparent 66%),
    radial-gradient(36% 56% at 93% 26%, rgba(17,89,106,.12), transparent 66%),
    radial-gradient(34% 52% at 68% 0%, rgba(34,155,117,0.260), transparent 66%),
    radial-gradient(30% 46% at 96% 92%, rgba(31,179,196,0.220), transparent 66%),
    radial-gradient(30% 46% at 18% 96%, rgba(34,155,117,0.180), transparent 64%);
}
.page-head::after{
  content:"";position:absolute;left:50%;bottom:.9rem;transform:translateX(-50%);
  width:132px;height:10px;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='132' height='10' viewBox='0 0 132 10'><path d='M2 6c14-6 28-6 42 0s28 6 42 0 28-6 44-2' fill='none' stroke='%2338a888' stroke-width='1.7' stroke-linecap='round' opacity='.85'/><circle cx='124' cy='3.4' r='1.5' fill='%230a7d85' opacity='.55'/></svg>") center/contain no-repeat;
}
.page-head .container{position:relative;}

/* — tache d'aquarelle derrière chaque œuvre (comme un fond d'atelier) — */
.work{position:relative;z-index:0;}
.work-frame{position:relative;}
.work-frame::before{
  content:"";position:absolute;inset:-16px 12px -20px -16px;z-index:-1;
  opacity:.6;transition:opacity .5s ease;
  background:
    radial-gradient(55% 60% at 30% 28%, rgba(34,155,117,0.300), transparent 70%),
    radial-gradient(46% 50% at 72% 78%, rgba(17,89,106,.10), transparent 72%);
}
.work:hover .work-frame::before{opacity:1;}
.frieze a{position:relative;z-index:0;}
.frieze a::before{
  content:"";position:absolute;inset:-14px 8px -18px -12px;z-index:-1;
  background:
    radial-gradient(55% 60% at 32% 30%, rgba(34,155,117,0.300), transparent 70%),
    radial-gradient(46% 50% at 70% 76%, rgba(17,89,106,.11), transparent 72%);
}
.artist-home-figure{z-index:0;}
.artist-home-figure::before{
  content:"";position:absolute;inset:-22px 14px -26px -20px;z-index:-1;
  background:
    radial-gradient(50% 58% at 30% 26%, rgba(34,155,117,0.300), transparent 70%),
    radial-gradient(44% 50% at 72% 80%, rgba(17,89,106,.10), transparent 72%);
}
.work-figure{position:relative;z-index:0;}
.work-figure::before{
  content:"";position:absolute;inset:-18px 14px -22px -18px;z-index:-1;
  background:
    radial-gradient(50% 58% at 30% 26%, rgba(34,155,117,0.280), transparent 70%),
    radial-gradient(44% 50% at 72% 80%, rgba(17,89,106,.10), transparent 72%);
}

/* — citation : nuage d'aquarelle organique derrière le texte — */
.quote-section .narrow{position:relative;}
.quote-section .narrow::before{
  content:"";position:absolute;inset:-34px -48px;z-index:0;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='560' height='300' viewBox='0 0 560 300'><filter id='w'><feTurbulence type='fractalNoise' baseFrequency='0.013 0.02' numOctaves='3' seed='11'/><feDisplacementMap in='SourceGraphic' scale='70'/><feColorMatrix type='saturate' values='1.45'/><feGaussianBlur stdDeviation='5'/></filter><g filter='url(%23w)'><ellipse cx='280' cy='150' rx='225' ry='105' fill='%231a9d9a' opacity='0.34'/><ellipse cx='330' cy='120' rx='150' ry='78' fill='%231fb3c4' opacity='0.26'/><ellipse cx='215' cy='185' rx='120' ry='64' fill='%2362c4a3' opacity='0.28'/></g></svg>") center/100% 100% no-repeat;
}
.quote-section .narrow > *{position:relative;z-index:1;}

/* — houle au-dessus du pied de page — */
.site-footer{position:relative;}
.site-footer::before{
  content:"";position:absolute;left:0;right:0;top:-52px;height:54px;pointer-events:none;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='620' height='54' viewBox='0 0 620 54' preserveAspectRatio='none'><path d='M0 34 C 80 16, 160 50, 240 34 S 400 16, 480 34 S 570 48, 620 30' fill='none' stroke='%2338a888' stroke-width='2' opacity='.55'/><path d='M0 24 C 90 8, 190 36, 290 24 S 470 8, 570 22 S 610 26, 620 20' fill='none' stroke='%2338a888' stroke-width='1.6' opacity='.42'/><path d='M0 46 C 100 30, 200 58, 300 46 S 500 30, 620 44' fill='none' stroke='%230a7d85' stroke-width='1.6' opacity='.4'/><circle cx='95' cy='24' r='2' fill='%2338a888' opacity='.55'/><circle cx='410' cy='16' r='2.4' fill='%230a7d85' opacity='.6'/><circle cx='540' cy='40' r='2' fill='%23229b75' opacity='.55'/></svg>") repeat-x bottom;background-size:620px 54px;
}

/* — invitation contact : ligne de rivage en tête de section — */
.contact-invitation{position:relative;overflow:hidden;}
.contact-invitation::before{
  content:"";position:absolute;left:0;right:0;top:0;height:44px;opacity:.75;pointer-events:none;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='520' height='44' viewBox='0 0 520 44'><path d='M0 16 C 65 4, 130 28, 195 16 S 325 4, 390 16 S 485 26, 520 12' fill='none' stroke='%2338a888' stroke-width='1.8' stroke-linecap='round' opacity='.8'/><path d='M0 30 C 70 18, 140 40, 210 30 S 350 18, 420 30 S 490 38, 520 26' fill='none' stroke='%230a7d85' stroke-width='1.4' stroke-linecap='round' opacity='.5'/></svg>") repeat-x top;background-size:520px 44px;
}

/* — transition douce sous le héros — */
.section-artist{position:relative;}
.section-artist::before{
  content:"";position:absolute;top:1.6rem;left:8vw;right:8vw;height:12px;opacity:.5;pointer-events:none;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='90' height='12' viewBox='0 0 90 12'><path d='M2 7c12-6 24-6 36 0s24 6 36 0 10-4 14-2' fill='none' stroke='%2338a888' stroke-width='1.5' stroke-linecap='round'/></svg>") repeat-x center/auto 12px;
}

/* — signature discrète dans les cartes — */
.contact-card,.fact-card{position:relative;}
.contact-card::after{
  content:"";position:absolute;bottom:.9rem;right:1rem;width:30px;height:7px;opacity:.55;pointer-events:none;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='30' height='7' viewBox='0 0 30 7'><path d='M1 4.5c4-4 7-4 11 0s7 4 11 0 4-2.5 6-1.5' fill='none' stroke='%2338a888' stroke-width='1.4' stroke-linecap='round'/></svg>") center/contain no-repeat;
}

/* ═══════ DUO — tantôt couleur, tantôt silence ═══════ */

/* ════════════════ SYMPHONIE DE COULEURS — aquarelle enrichie ════════════════ */
/* teintes réelles des aquarelles : céruléen, ocre, sauge, terre */
.tint-sand{background:linear-gradient(180deg,#f8f4ea,#f3ebd9);}
.tint-sky{background:linear-gradient(180deg,#edf4fb,#e1ecf8);}
.tint-sage{background:linear-gradient(180deg,#f0f4ec,#e7efdd);}
.tint-sand .label{color:#0a7d85;}
.tint-sky .label{color:#0a7d85;}
.tint-sage .label{color:#38a888;}

/* spectre aquarelle au-dessus du pied de page */
.spectrum{height:7px;background:linear-gradient(90deg,#0a7d85 0%,#38a888 100%);}

/* lavis derrière chaque œuvre selon sa tonalité */
.work[data-tn="Contraste coloré"] .work-frame::before{background:
  radial-gradient(55% 60% at 30% 28%, rgba(34,155,117,0.300), transparent 70%),
  radial-gradient(46% 50% at 72% 78%, rgba(34,155,117,0.300), transparent 72%);}
.work[data-tn="Doux"] .work-frame::before{background:
  radial-gradient(55% 60% at 30% 28%, rgba(31,179,196,0.300), transparent 70%),
  radial-gradient(46% 50% at 72% 78%, rgba(143,120,90,.14), transparent 72%);}

/* point de tonalité à côté du titre */
.work-title::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;
  margin-right:.5rem;vertical-align:2px;background:#38a888;}
.work[data-tn="Doux"] .work-title::before{background:#0a7d85;}

/* dates qui alternent les teintes de la palette */
.timeline li:nth-child(5n+1) .tl-date{color:#097380;}
.timeline li:nth-child(5n+2) .tl-date{color:#0a7d85;}
.timeline li:nth-child(5n+3) .tl-date{color:#0a7d85;}
.timeline li:nth-child(5n+4) .tl-date{color:#38a888;}
.timeline li:nth-child(5n+5) .tl-date{color:#38a888;}
.news-rows .news-row:nth-child(5n+2) .news-date{color:#0a7d85;}
.news-rows .news-row:nth-child(5n+3) .news-date{color:#0a7d85;}
.news-rows .news-row:nth-child(5n+4) .news-date{color:#38a888;}
.news-rows .news-row:nth-child(5n+5) .news-date{color:#38a888;}

/* ═══════════════════ HYPER-AQUARELLE — toute la page en lavis ═══════════════════ */
/* parcours coloré du fond : le papier se teinte au fil du défilement */
body{
  background:
    radial-gradient(52% 38% at 8% 2%,  rgba(34,155,117,0.150), transparent 70%),
    radial-gradient(46% 34% at 94% 14%, rgba(34,155,117,0.140), transparent 70%),
    radial-gradient(50% 36% at 6% 46%,  rgba(31,179,196,0.120), transparent 70%),
    radial-gradient(48% 34% at 95% 66%, rgba(34,155,117,0.120), transparent 70%),
    radial-gradient(50% 36% at 10% 96%, rgba(34,155,117,0.110), transparent 70%),
    var(--paper);
}
/* labels en dégradé d'encres (fallback solide conservé) */
.label{color:#097380;}
@supports (-webkit-background-clip: text){
  .label{background:linear-gradient(90deg,#097380 0%,#0a7d85 100%);
    -webkit-background-clip:text;background-clip:text;color:transparent;}
}
/* signature du nom : filet d'aquarelle sous la marque */
.brand-name{position:relative;}
.brand-name::after{content:"";position:absolute;left:.02em;right:.35em;bottom:-.28rem;height:5px;
  border-radius:3px;opacity:.85;
  background:linear-gradient(90deg,#0a7d85,#38a888);}
/* menu : soulignements arc-en-ciel, une teinte par rubrique */
.site-nav ul li:nth-child(1) a:not(.nav-close)::after{background:linear-gradient(90deg,#0a7d85,#38a888);}
.site-nav ul li:nth-child(2) a:not(.nav-close)::after{background:linear-gradient(90deg,#38a888,#0a7d85);}
.site-nav ul li:nth-child(3) a:not(.nav-close)::after{background:linear-gradient(90deg,#0a7d85,#38a888);}
.site-nav ul li:nth-child(4) a:not(.nav-close)::after{background:linear-gradient(90deg,#38a888,#0a7d85);}
.site-nav ul li:nth-child(5) a:not(.nav-close)::after{background:linear-gradient(90deg,#0a7d85,#38a888);}
/* bouton principal : aplat dégradé + halo d'aquarelle au survol */
.btn{
  background:linear-gradient(135deg,#0a7d85 0%,#38a888 100%);
  color:#fff;border-color:transparent;
  box-shadow:0 10px 26px -14px rgba(17,89,106,.55);
}
.btn:hover{filter:brightness(1.12);box-shadow:0 16px 34px -14px rgba(56,168,136,.65);}
.btn-outline{background:transparent;color:var(--teal-ink);border-color:var(--teal);
  box-shadow:none;}
.btn-outline:hover{background:var(--teal);color:#fff;}
/* filets d'aquarelle : les lignes plates deviennent des fils colorés */
.page-head{border-bottom:2px solid transparent;
  border-image:linear-gradient(90deg,#0a7d85,#38a888) 1;}
.section-artist,.section-expos,.map-section{border-top:2px solid transparent;
  border-image:linear-gradient(90deg,#0a7d85,#38a888) 1;}
.spectrum{height:10px;
  box-shadow:0 6px 22px -8px rgba(56,168,136,.5);}
/* lavis propres à chaque rubrique */
.pg-artist .page-head,.pg-artiste .page-head{background:
  radial-gradient(60% 80% at 12% 0%,rgba(31,179,196,0.300),transparent 60%),
  radial-gradient(55% 75% at 90% 15%,rgba(34,155,117,0.240),transparent 60%),
  linear-gradient(180deg,#f7f1e4,var(--paper));}
.pg-gallery .page-head,.pg-work .page-head,.pg-aquarelles .page-head,.pg-oeuvre .page-head{background:
  radial-gradient(55% 78% at 85% -5%,rgba(34,155,117,0.300),transparent 62%),
  radial-gradient(50% 72% at 8% 20%,rgba(34,155,117,0.280),transparent 60%),
  radial-gradient(45% 60% at 92% 95%,rgba(31,179,196,0.220),transparent 65%),
  linear-gradient(180deg,#f2f6fb,var(--paper));}
.pg-news_list .page-head,.pg-news_item .page-head,.pg-actualites .page-head,.pg-actualite .page-head{background:
  radial-gradient(58% 80% at 10% 0%,rgba(34,155,117,0.280),transparent 62%),
  radial-gradient(50% 70% at 92% 30%,rgba(34,155,117,0.220),transparent 62%),
  linear-gradient(180deg,#eef5fb,var(--paper));}
.pg-contact .page-head{background:
  radial-gradient(55% 78% at 88% -5%,rgba(34,155,117,0.300),transparent 60%),
  radial-gradient(50% 70% at 8% 25%,rgba(34,155,117,0.240),transparent 60%),
  linear-gradient(180deg,#f0f5ef,var(--paper));}
/* cadres : passe-partouts teintés qui alternent + halo coloré au survol */
.work-frame{background:#fffdf9;}
.work:nth-child(3n) .work-frame{background:#f8fcfb;}
.work:nth-child(3n+1) .work-frame{background:#fdfbf6;}
.work:nth-child(3n+2) .work-frame{background:#f9faf6;}
.work:hover .work-frame{box-shadow:0 22px 46px -18px rgba(56,168,136,.45);}
.work[data-tn="Doux"]:hover .work-frame{box-shadow:0 22px 46px -18px rgba(10,125,133,.45);}
.work-figure picture{box-shadow:0 24px 52px -20px rgba(17,89,106,.4);}
/* cartes & encadrés : liseré d'aquarelle en tête */
.contact-card,.fact-card{border-top:3px solid transparent;
  border-image:linear-gradient(90deg,#0a7d85,#38a888) 1;}
/* pied de page : lueur d'aquarelle sur le bleu nuit */
.site-footer{background:
  radial-gradient(70% 90% at 15% 0%,rgba(34,155,117,0.300),transparent 60%),
  radial-gradient(60% 80% at 85% 10%,rgba(34,155,117,0.200),transparent 60%),
  #0f2e35;}

/* ═══════════════════ RESPONSIVE+ — du 320 px au grand écran ═══════════════════ */
/* cibles tactiles confortables (doigt ≈ 44 px) */
@media (hover:none){
  .btn,.work-nav-link{min-height:46px;}
  .site-nav ul a:not(.nav-close){padding:.7rem .4rem;}
}
/* très petits téléphones (≤ 400 px) */
@media (max-width:400px){
  body{font-size:16px;}
  .hero-title{font-size:clamp(2.3rem,11vw,3rem);}
  .hero-cta{flex-direction:column;align-items:flex-start;gap:1.1rem;}
  .gallery-grid{gap:1rem .9rem;}
  .work-title{font-size:1.02rem;}
  .work-meta{font-size:.66rem;}
  .cookie-actions{width:100%;flex-direction:column;}
  .cookie-actions .btn{width:100%;}
  .footer-legal p{font-size:.7rem;}
}
/* téléphones (≤ 600 px) : respiration et empilement */
@media (max-width:600px){
  .hero-inner{margin-top:4.4rem;}
  .page-head{padding-top:clamp(7.2rem,18vw,9rem);}
  .section-head{flex-direction:column;align-items:flex-start;gap:.9rem;}
  .news-row{align-items:flex-start;}
  .news-title{font-size:1.18rem;}
  .timeline a{flex-wrap:wrap;gap:.45rem 1rem;}
  .tl-date{flex-basis:100%;}
  .invitation-cta{flex-direction:column;gap:1.2rem;}
  .work-facts div{flex-wrap:wrap;}
  .work-facts dd{text-align:left;flex:1;}
  .map-consent{min-height:240px;}
  .cookie-bar{left:.5rem;right:.5rem;transform:none;width:auto;}
  .cookie-inner{flex-direction:column;align-items:flex-start;gap:.9rem;}
  .article-gallery{gap:.9rem;}
  .teaser-figure{flex-basis:auto;width:100%;}
}
/* tableau cookies lisible sur mobile */
@media (max-width:640px){
  .cookie-table thead{display:none;}
  .cookie-table,.cookie-table tbody,.cookie-table tr,.cookie-table td{display:block;width:100%;}
  .cookie-table tr{margin-bottom:1rem;border:1px solid var(--hair);border-radius:4px;overflow:hidden;}
  .cookie-table td{border:0;border-bottom:1px solid var(--hair);padding:.55rem .8rem;}
  .cookie-table td::before{content:attr(data-l);display:block;font-size:.68rem;
    letter-spacing:.14em;text-transform:uppercase;color:var(--teal-ink);margin-bottom:.2rem;}
}
/* tablettes (601–1000 px) */
@media (min-width:601px) and (max-width:1000px){
  .hero-title{font-size:clamp(3rem,9vw,5rem);}
}
/* écrans larges : la galerie respire davantage */
@media (min-width:1500px){
  :root{--w-container:1280px;}
  .gallery-grid{gap:3rem 2.6rem;}
}
/* mode impression : papier propre, œuvres avant tout */
@media print{
  .site-header,.site-footer,.spectrum,.cookie-bar,.map-wrap,.hero-wash,
  .contact-invitation,.next-teaser,.work-nav,.hl-filters,.hl-toast{display:none !important;}
  body{background:#fff;color:#000;font-size:12pt;}
  .work-frame,.work-figure picture{box-shadow:none;border:1px solid #999;}
  .reveal{opacity:1;transform:none;}
}

/* ═══════════════════ ATELIER — photos & visionneuse ═══════════════════ */
.pg-atelier .page-head{background:
  radial-gradient(60% 80% at 10% 0%,rgba(31,179,196,0.300),transparent 60%),
  radial-gradient(55% 75% at 92% 12%,rgba(34,155,117,0.300),transparent 60%),
  linear-gradient(180deg,#f6f1e3,var(--paper));}
.atelier-note{margin:0 0 1.6rem;color:var(--muted);font-size:.95rem}
.atelier-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:1.6rem}
.atelier-item{margin:0;background:var(--card);border:1px solid rgba(56,168,136,.16);
  border-radius:10px;padding:10px;box-shadow:var(--shadow-soft);
  transition:transform .35s ease,box-shadow .35s ease}
.atelier-item:nth-child(3n+2){background:#f3f4eb;border-color:rgba(56,168,136,.30)}
.atelier-item:nth-child(3n){background:#f8f1e2;border-color:rgba(10,125,133,.32)}
.atelier-item:hover{transform:translateY(-5px);
  box-shadow:0 18px 40px -18px rgba(56,168,136,.55)}
.atelier-btn{display:block;width:100%;padding:0;border:0;background:none;cursor:zoom-in;
  border-radius:6px;overflow:hidden}
.atelier-btn:focus-visible{outline:2px solid var(--teal);outline-offset:3px}
.atelier-btn img{display:block;width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:6px;
  transition:transform .5s ease}
.atelier-item:hover .atelier-btn img{transform:scale(1.04)}
.portrait-card{margin:0 0 1.4rem;background:var(--card);border:1px solid rgba(10,125,133,.35);
  border-radius:10px;padding:10px 10px 8px;box-shadow:var(--shadow);
  transform:rotate(-1.4deg)}
.portrait-card img{display:block;width:100%;max-width:280px;margin:0 auto;border-radius:6px}
.portrait-card figcaption{margin-top:.55rem;text-align:center;font-family:var(--sans);
  font-size:.7rem;letter-spacing:.18em;text-transform:uppercase;color:var(--muted)}
.hl-lightbox{position:fixed;inset:0;z-index:1200;display:flex;flex-direction:column;
  align-items:center;justify-content:center;background:rgba(10,19,27,.93);
  padding:1.2rem;-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px)}
.hl-lightbox[hidden]{display:none}
.hl-lightbox figure{margin:0;max-width:min(1200px,94vw);text-align:center}
.hl-lightbox img{max-width:100%;max-height:78vh;border:2px solid rgba(255,255,255,.55);
  border-radius:8px;box-shadow:0 30px 80px -20px rgba(0,0,0,.7)}
.hl-lightbox figcaption{margin-top:.8rem;color:#e8eef1;font-size:.85rem;letter-spacing:.08em}
.hl-lb-btn{position:absolute;top:50%;transform:translateY(-50%);min-width:46px;min-height:46px;
  border:1px solid rgba(255,255,255,.4);border-radius:50%;background:rgba(255,255,255,.12);
  color:#fff;font-size:1.3rem;line-height:1;cursor:pointer;
  display:flex;align-items:center;justify-content:center}
.hl-lb-btn:hover{background:rgba(56,168,136,.55)}
.hl-lb-prev{left:14px}.hl-lb-next{right:14px}
.hl-lb-close{position:absolute;top:14px;right:14px;min-width:46px;min-height:46px;
  border-radius:50%;border:1px solid rgba(255,255,255,.4);background:rgba(255,255,255,.12);
  color:#fff;font-size:1.05rem;cursor:pointer}
.hl-lb-close:hover{background:rgba(56,168,136,.55)}
@media (max-width:600px){
  .atelier-grid{grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:.9rem}
  .atelier-item{padding:6px}
  .hl-lb-btn{min-width:52px;min-height:52px}
  .portrait-card img{max-width:230px}
}
@media print{.hl-lightbox{display:none!important}.atelier-item{break-inside:avoid}}


/* ═══════════════════ COULEURS-MAXIMALES — le site en pleine aquarelle ═══════════════════ */
/* voile multicolore fixe : les 5 teintes des aquarelles traversent tout le site */
body::after{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background:
  radial-gradient(46rem 32rem at 50% 97%,rgba(26,157,154,0.08),transparent 62%);}
/* bandes alternées à peine teintées : la couleur monte à chaque section */
.main .section:nth-of-type(even):not([class*="tint-"]):not(.wash-band){background:
  linear-gradient(180deg,rgba(56,168,136,.05),rgba(56,168,136,.04) 55%,rgba(10,125,133,.05));}
.main .section:nth-of-type(odd):not([class*="tint-"]):not(.wash-band){background:
  linear-gradient(180deg,rgba(56,168,136,.035),rgba(56,168,136,.035) 60%,rgba(56,168,136,.045));}
/* titres en dégradé d'encre (encres toutes validées AA sur papier) */
@supports ((-webkit-background-clip:text) or (background-clip:text)){
  .page-title,.h2,.fact-title,.big-quote{
    background:linear-gradient(100deg,#0a7d85 0%,#38a888 100%);
    -webkit-background-clip:text;background-clip:text;
    -webkit-text-fill-color:transparent;}
  .site-footer .footer-title,.footer-col .brand-name{
    background:linear-gradient(90deg,#8be0d8,#7ecdf0 48%,#93e6b8);
    -webkit-background-clip:text;background-clip:text;
    -webkit-text-fill-color:transparent;}
}
/* en-têtes de rubrique : lavis plus généreux */
.page-head{background:
  radial-gradient(60% 85% at 8% 0%,rgba(34,155,117,0.300),transparent 62%),
  radial-gradient(55% 80% at 92% 8%,rgba(31,179,196,0.300),transparent 60%),
  radial-gradient(45% 65% at 50% 100%,rgba(34,155,117,0.200),transparent 65%),
  linear-gradient(180deg,#f6f4ec,var(--paper)) !important;}
.pg-artist .page-head,.pg-artiste .page-head{background:
  radial-gradient(60% 80% at 12% 0%,rgba(31,179,196,0.300),transparent 62%),
  radial-gradient(55% 75% at 90% 15%,rgba(34,155,117,0.300),transparent 60%),
  radial-gradient(40% 55% at 55% 100%,rgba(34,155,117,0.240),transparent 65%),
  linear-gradient(180deg,#f8f0dc,var(--paper)) !important;}
.pg-gallery .page-head,.pg-work .page-head,.pg-aquarelles .page-head,.pg-oeuvre .page-head{background:
  radial-gradient(55% 78% at 85% -5%,rgba(34,155,117,0.300),transparent 62%),
  radial-gradient(50% 72% at 8% 20%,rgba(34,155,117,0.300),transparent 60%),
  radial-gradient(45% 60% at 92% 95%,rgba(31,179,196,0.300),transparent 65%),
  linear-gradient(180deg,#eaf2fb,var(--paper)) !important;}
.pg-news_list .page-head,.pg-news_item .page-head,.pg-actualites .page-head,.pg-actualite .page-head{background:
  radial-gradient(58% 80% at 10% 0%,rgba(34,155,117,0.300),transparent 62%),
  radial-gradient(50% 70% at 92% 30%,rgba(34,155,117,0.300),transparent 62%),
  radial-gradient(42% 58% at 45% 100%,rgba(34,155,117,0.280),transparent 65%),
  linear-gradient(180deg,#e9f2fa,var(--paper)) !important;}
.pg-contact .page-head{background:
  radial-gradient(55% 78% at 88% -5%,rgba(34,155,117,0.300),transparent 60%),
  radial-gradient(50% 70% at 8% 25%,rgba(34,155,117,0.300),transparent 60%),
  linear-gradient(180deg,#eaf3ea,var(--paper)) !important;}
.pg-atelier .page-head{background:
  radial-gradient(60% 80% at 10% 0%,rgba(31,179,196,0.300),transparent 62%),
  radial-gradient(55% 75% at 92% 12%,rgba(34,155,117,0.300),transparent 60%),
  radial-gradient(42% 58% at 50% 100%,rgba(34,155,117,0.280),transparent 65%),
  linear-gradient(180deg,#f8f0dd,var(--paper)) !important;}
/* rubriques teintées : saturation doucement augmentée */
.tint-sand{background:linear-gradient(180deg,#f9f3e2,#f1e6cb);}
.tint-sky{background:linear-gradient(180deg,#e9f2fb,#dcebf9);}
.tint-sage{background:linear-gradient(180deg,#edf3e6,#e0ebd2);}
.wash-band{background:
  radial-gradient(60% 120% at 20% 50%,rgba(34,155,117,0.300),transparent 60%),
  radial-gradient(50% 100% at 85% 40%,rgba(34,155,117,0.300),transparent 62%),
  radial-gradient(45% 90% at 55% 110%,rgba(31,179,196,0.240),transparent 65%);}
/* spectre plus présent, avec lueur */
.spectrum{height:14px;
  box-shadow:0 -8px 22px -8px rgba(56,168,136,.5),0 8px 22px -8px rgba(10,125,133,.45);}
/* en-tête fixe : liseré arc-en-ciel dès qu'on défile */
.site-header.is-scrolled{border-bottom:2px solid transparent;
  border-image:linear-gradient(90deg,#0a7d85,#38a888) 1;
  box-shadow:0 12px 30px -20px rgba(56,168,136,.45);}
/* menu : chaque rubrique prend sa couleur d'encre (AA) */
.site-nav ul li:nth-child(1) a:not(.nav-close):hover,
.site-nav ul li:nth-child(1) a[aria-current="page"]{color:#097380;}
.site-nav ul li:nth-child(2) a:not(.nav-close):hover,
.site-nav ul li:nth-child(2) a[aria-current="page"]{color:#0a7d85;}
.site-nav ul li:nth-child(3) a:not(.nav-close):hover,
.site-nav ul li:nth-child(3) a[aria-current="page"]{color:#0a7d85;}
.site-nav ul li:nth-child(4) a:not(.nav-close):hover,
.site-nav ul li:nth-child(4) a[aria-current="page"]{color:#38a888;}
.site-nav ul li:nth-child(5) a:not(.nav-close):hover,
.site-nav ul li:nth-child(5) a[aria-current="page"]{color:#38a888;}
.site-nav ul li:nth-child(6) a:not(.nav-close):hover,
.site-nav ul li:nth-child(6) a[aria-current="page"]{color:#097380;}
/* boutons : double halo coloré, éclat au survol (dégradé AA inchangé) */
.btn{box-shadow:0 12px 32px -12px rgba(56,168,136,.6),0 8px 26px -14px rgba(56,168,136,.5);
  transition:background .3s,color .3s,border-color .3s,box-shadow .3s,transform .3s,filter .3s;}
.btn:hover{filter:saturate(1.18) brightness(1.05);transform:translateY(-2px);}
/* fiche « En un regard » : liseré d'aquarelle */
.fact-card{border-top:4px solid transparent;
  border-image:linear-gradient(90deg,#0a7d85,#38a888) 1;}
/* héros : voile multicolore au-dessus du lavis SVG */
/* effets latéraux retirés : l'aquarelle s'affiche pure, de bord à bord */
/* pied de page : nuit bleutée traversée de lueurs */
.site-footer{background:
  radial-gradient(50rem 20rem at 12% 0%,rgba(34,155,117,0.300),transparent 60%),
  radial-gradient(46rem 18rem at 88% 8%,rgba(34,155,117,0.300),transparent 62%),
  radial-gradient(40rem 16rem at 50% 112%,rgba(31,179,196,0.300),transparent 60%),
  linear-gradient(180deg,#123840,#0f2e35 45%,#0b2530);}
.footer-list a:hover{color:#9fd8d2;border-color:rgba(159,216,210,.5);}
/* détails */
::selection{background:rgba(56,168,136,.30);}
.lnk{border-bottom-color:rgba(10,125,133,.45);}
.lnk:hover{color:#0a7d85;}
.link-arrow:hover{color:#38a888;}
/* impression : on retire les effets pour un papier propre */
@media print{
  body::after,.hero::after{display:none;}
  .page-title,.h2,.fact-title,.big-quote,.hero-baseline{
    background:none;-webkit-text-fill-color:initial;color:var(--ink);}
  .site-footer .footer-title,.footer-col .brand-name{
    background:none;-webkit-text-fill-color:initial;color:#f4efe6;}
  .spectrum{height:6px;box-shadow:none;}
  .main .section:nth-of-type(even):not([class*="tint-"]):not(.wash-band),
  .main .section:nth-of-type(odd):not([class*="tint-"]):not(.wash-band){background:none;}
  .fact-card,.site-header.is-scrolled,.page-head{border-image:none;}
}


/* ═══════════════════ SUR LE VIF — définition encadrée & cadres d'œuvres ═══════════════════ */
.vif-def{position:relative;margin:0 0 1.6rem;padding:1.25rem 1.5rem 1.25rem 1.9rem;
  background:linear-gradient(180deg,#fffdf9,#faf5ea);border:1px solid rgba(10,125,133,.5);
  border-radius:6px;box-shadow:var(--shadow-soft)}
.vif-def::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;
  border-radius:6px 0 0 6px;
  background:linear-gradient(180deg,#0a7d85,#38a888)}
.vif-def-title{font-family:var(--sans);font-weight:600;font-size:.76rem;letter-spacing:.18em;
  text-transform:uppercase;color:#0a7d85;margin:0 0 .55rem}
.vif-def p:last-child{margin:0;color:var(--text);max-width:62ch}
/* les images deviennent des œuvres encadrées : passe-partout + cadre + tampon */
.atelier-item{padding:14px 14px 34px;background:#fffdf9;border:1px solid #cfc4a8;
  border-radius:4px;position:relative}
.atelier-item:nth-child(3n+2),.atelier-item:nth-child(3n){background:#fffdf9}
.atelier-item::after{content:"";position:absolute;inset:5px;border:1px solid rgba(14,42,50,.16);
  border-radius:2px;pointer-events:none}
.atelier-item:hover{border-color:#b9a97f}
.atelier-btn img{aspect-ratio:auto;object-fit:contain;max-height:24rem;background:#fff}
.vif-badge{position:absolute;left:50%;bottom:9px;transform:translateX(-50%);
  font-family:var(--sans);font-size:.62rem;letter-spacing:.22em;text-transform:uppercase;
  color:#0a7d85;white-space:nowrap}
.vif-badge::before,.vif-badge::after{content:"·";margin:0 .45em;color:#0a7d85}
@media (max-width:600px){
  .atelier-item{padding:8px 8px 26px}
  .vif-badge{bottom:6px;font-size:.56rem}
  .atelier-btn img{max-height:17rem}
}
@media print{.vif-def{break-inside:avoid}}


/* ═══ SUR LE VIF passe en galerie · la palette reste Ю l'atelier ═══ */
.atelier-grid.atelier-one{grid-template-columns:minmax(0,430px);justify-content:center}
.atelier-one .atelier-btn img{max-height:32rem}
.hl-lightbox.hl-lb-single .hl-lb-btn{display:none}
.wk-lightbox.hl-lb-single .hl-lb-btn{display:none}


/* ═══════════════ RYTHME & ULTRA-RESPONSIVE — espacements harmonisés ═══════════════ */
:root{--gap:clamp(1.15rem,2.6vw,1.9rem);}
html,body{overflow-x:clip;}
img,picture,svg,video{max-width:100%;}
.section{padding:clamp(3.4rem,8vw,6.4rem) 0;}
.section-head{margin-bottom:clamp(1.7rem,4vw,2.6rem);gap:1.2rem;}
.gallery-grid{gap:var(--gap);}
.atelier-grid{gap:var(--gap);}

.news-row{padding:clamp(1.15rem,3vw,1.65rem) .4rem;}
.timeline a{padding:clamp(1.05rem,2.6vw,1.4rem) .4rem;}
.atelier-note{margin:0 0 clamp(1.2rem,3vw,1.7rem);}
.vif-def{margin:0 0 clamp(1.1rem,2.6vw,1.5rem);}
.footer-inner{gap:clamp(1.8rem,4.5vw,2.6rem);padding:clamp(2.6rem,6vw,4.3rem) 0 2.1rem;}
@media (max-width:600px){
  .footer-inner{grid-template-columns:1fr;gap:1.7rem;}
  .section{padding:clamp(2.9rem,9vw,4rem) 0;}
  .page-head{padding-top:clamp(7.2rem,19vw,9rem);}
  .gallery-grid{grid-template-columns:repeat(auto-fill,minmax(148px,1fr));}
  .section-head{margin-bottom:1.5rem;}
  .news-thumb{flex-basis:86px;}
}
@media (max-width:360px){
  .container,.narrow{width:94vw;}
  .gallery-grid{grid-template-columns:repeat(auto-fill,minmax(126px,1fr));}
  .page-title{font-size:clamp(1.85rem,8.5vw,2.3rem);}
  .btn{width:100%;text-align:center;}
  .section-head{flex-direction:column;align-items:flex-start;}
}
@media (hover:none){
  .footer-list a,.site-nav a:not(.nav-close),.icon-btn,.btn-tiny{min-height:46px;}
  .work:hover .work-frame,.atelier-item:hover{transform:none;}
  .atelier-item:hover .atelier-btn img{transform:none;}
}
@media (orientation:landscape) and (max-height:540px){
  .hero-inner{margin-top:4.1rem;}
}
@media (min-width:1600px){:root{--w-container:1300px;}}


/* ═══════════ CADRAGES UNIFORMES — sur le vif, atelier & actualités ═══════════ */
/* vignettes « sur le vif » et photos d'atelier : cadres nets et alignés
   (miniature recadrée ; l'image entière s'affiche au clic dans la visionneuse) */
.atelier-grid .atelier-btn img{aspect-ratio:4/3;object-fit:cover;max-height:none;}
.atelier-grid.atelier-one .atelier-btn img{aspect-ratio:auto;object-fit:contain;max-height:32rem;}
/* actualités sur téléphone : rangées bien cadrées */
@media (max-width:600px){
  .news-row{gap:.95rem;padding:1.05rem 0;}
  .news-thumb{flex:0 0 104px;}
  .news-thumb img{width:100%;aspect-ratio:1/1;object-fit:cover;}
  .news-title{font-size:1.12rem;}
}


/* ═══════════ GALERIE PLEIN ÉCRAN SUR PC — les aquarelles occupent l'écran ═══════════ */
@media (min-width:1100px){
  .gallery-section .container{width:min(1760px,94vw);}
  .gallery-grid{grid-template-columns:repeat(8,1fr);}
  .hl-filters{width:min(1760px,94vw);}
}
@media (min-width:1600px){
  .gallery-section .container,.hl-filters{width:min(1920px,94vw);}
}


/* ═══════════ UNIFORMITÉ & FLUIDITÉ — un seul rythme pour tout le site ═══════════ */
:root{
  --r-card:10px; --r-img:6px; --r-btn:4px;
  --section-pad:clamp(3rem,7vw,6rem);
  --t-soft:cubic-bezier(.22,1,.36,1);
}
/* sections & conteneurs : une seule règle de respiration */
.section{padding:var(--section-pad) 0;}
.page-head{padding:clamp(7.5rem,14vw,11rem) 0 clamp(1.8rem,4vw,3.2rem);}
.section-head{margin-bottom:clamp(1.6rem,3.6vw,2.4rem);}
/* cartes : mêmes angles, mêmes ombres, mêmes bordilles partout */
.work-frame,.atelier-item,.fact-card,.portrait-card,.news-thumb picture,
.msg-card,.form-card{border-radius:var(--r-card);box-shadow:var(--shadow-soft);}
.atelier-btn img,.atelier-btn,.work-frame img,.news-thumb img,
.hl-lightbox img{border-radius:var(--r-img);}
.btn,.icon-btn,.btn-tiny,.btn-primary,.btn-secondary{border-radius:var(--r-btn);}
/* boutons : même gabarit, même geste */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.5rem;
  min-height:48px;padding:.85rem clamp(1.2rem,2.4vw,2rem);text-align:center;}
.btn,.work-frame,.atelier-item{transition:all .35s var(--t-soft);}
/* titres : même respiration */
h1,h2,h3{margin:0 0 .5em;}
/* focus unique et visible */
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,
textarea:focus-visible,[tabindex]:focus-visible{outline:2px solid var(--teal);
  outline-offset:2px;border-radius:var(--r-btn);}
/* grilles : écart unique */
.gallery-grid,.atelier-grid,.news-rows{gap:var(--gap);}
/* ── hyper responsive : fluide du 320 px au 4K ── */
@media (max-width:340px){
  html{font-size:15px;}
  .container,.narrow{width:94vw;}
  .page-title{font-size:clamp(1.7rem,9vw,2.1rem);}
  .page-sub{font-size:1rem;}
}
@media (min-width:2000px){
  :root{--w-container:1500px;}
  html{font-size:17.5px;}
}
@media (orientation:landscape) and (max-height:500px){
  .page-head{padding-top:clamp(5.6rem,12vh,7.5rem);}
  .section{padding:clamp(2.2rem,6vh,4rem) 0;}
}
@media (hover:none){
  .btn,.icon-btn,.btn-tiny,.hl-lb-btn,.hl-lb-close,
  .nav-toggle{min-height:48px;min-width:48px;}
}


/* ═══════ PORTE DE PUBLICATION — carte d'accueil de la clé ═══════ */
.gh-gate{max-width:780px;margin:0 auto 2.2rem;background:linear-gradient(180deg,#fffdf9,#f8f3e8);
  border:1px solid rgba(10,125,133,.4);border-top:4px solid;
  border-image:linear-gradient(90deg,#0a7d85,#38a888) 1;
  border-radius:10px;padding:clamp(1.4rem,4vw,2.4rem);box-shadow:var(--shadow);}
.gh-title{font-size:clamp(1.5rem,3.4vw,2.2rem);margin:0 0 .4em;}
.gh-title em{font-style:italic;color:var(--teal-ink);}
.gh-state{margin:.4rem 0 1.2rem;}
.gh-row{display:flex;gap:.7rem;flex-wrap:wrap;align-items:stretch;}
.gh-row input,.gh-row select{flex:1 1 240px;min-height:50px;}
.gh-actions{display:flex;gap:.7rem;flex-wrap:wrap;margin-top:1.1rem;}
.gh-help{margin-top:1.3rem;border-top:1px solid var(--hair);padding-top:1rem;}
.gh-help summary{cursor:pointer;font-weight:600;color:var(--teal-ink);min-height:46px;display:flex;align-items:center;}
.gh-help ol{margin:.7rem 0 0 1.2rem;display:grid;gap:.45rem;color:var(--text);}
@media (max-width:560px){.gh-row{flex-direction:column}.gh-row .btn{width:100%}}


/* ═══════════ MENU MOBILE OPAQUE + AUDIT TÉLÉPHONE ═══════════ */
@media (max-width:900px){
  .site-nav{background:
    radial-gradient(70% 40% at 15% 6%,rgba(34,155,117,0.200),transparent 60%),
    radial-gradient(60% 35% at 88% 18%,rgba(34,155,117,0.200),transparent 60%),
    radial-gradient(75% 45% at 50% 100%,rgba(31,179,196,0.240),transparent 65%),
    #faf8f3;
    padding-top:4.6rem;padding-bottom:2rem;overflow-y:auto;overscroll-behavior:contain;}
  body.nav-open .site-header{background:none!important;box-shadow:none!important;
    border-image:none!important;border-bottom-color:transparent!important;
    backdrop-filter:none!important;-webkit-backdrop-filter:none!important;
    filter:none!important;}
  .site-nav ul{gap:.55rem;}
  .site-nav ul a:not(.nav-close){display:inline-flex;align-items:center;justify-content:center;
    min-height:52px;padding:.7rem 1.5rem;font-weight:500;color:var(--ink);}
  .nav-close{top:calc(1rem + env(safe-area-inset-top,0px));right:.9rem;
    min-width:52px;min-height:52px;display:flex;align-items:center;justify-content:center;}
  body.nav-open{overflow:hidden;}
}
/* textes : aucun débordement, même pour les mots longs */
.work-title,.news-title,.tl-title,.page-title,.page-sub,.h2,.h3,.hero-title,.hero-sub,
.big-quote,.mini-quote,.footer-list a,.vif-def,.atelier-note{overflow-wrap:break-word;}
/* visionneuse : calibrée pour les téléphones (avec encoches) */
@media (max-width:600px){
  .hl-lightbox figure{max-width:96vw;}
  .hl-lightbox img{max-height:62vh;}
  .hl-lightbox figcaption{font-size:.78rem;padding:0 .5rem;}
  .hl-lb-prev{left:calc(6px + env(safe-area-inset-left,0px));}
  .hl-lb-next{right:calc(6px + env(safe-area-inset-right,0px));}
  .hl-lb-close{top:calc(8px + env(safe-area-inset-top,0px));right:calc(8px + env(safe-area-inset-right,0px));}
  .mat-figure{max-height:64vh;object-fit:contain;}
}
/* très petits écrans : tailles et bandeau cookies calés */
@media (max-width:380px){
  .hero-title{font-size:clamp(2.3rem,11vw,2.9rem);}
  .hero-sub{font-size:1rem;}
  .label{font-size:.68rem;letter-spacing:.16em;}
  .cookie-txt{font-size:.85rem;}
  .cookie-actions .btn{width:100%;}
}


/* ═══════════ MENU JAMAIS COUPÉ + CRÉDIT WEB&GO ═══════════ */
@media (max-width:900px){
  .site-nav{align-items:flex-start;}
  .site-nav ul{margin:auto 0;width:100%;padding-bottom:1.2rem;}
}
.footer-legal .footer-credit{margin-top:.5rem;}
.footer-credit a{color:#9fd8d2;border-bottom:1px solid rgba(159,216,210,.4);}
.footer-credit a:hover{border-bottom-color:#9fd8d2;}

/* ═══════════ GALERIE, UNIVERS, ATELIER, ÉVÉNEMENTS — composants ═══════════ */
/* nuage de mots — Mon univers */
.wordcloud{list-style:none;margin:2.4rem 0 3rem;padding:0;display:flex;flex-wrap:wrap;
  justify-content:center;align-items:center;gap:.4rem 1.6rem;max-width:820px;margin-inline:auto}
.wordcloud li{font-family:var(--serif);font-style:italic;line-height:1.1;color:var(--teal-ink);
  opacity:.92;transition:opacity .3s,transform .3s}
.wordcloud li:hover{opacity:1;transform:translateY(-2px)}
.w-xl{font-size:clamp(1.9rem,4.5vw,2.9rem)}
.w-lg{font-size:clamp(1.5rem,3.4vw,2.2rem)}
.w-md{font-size:clamp(1.15rem,2.5vw,1.6rem)}
.w-sm{font-size:clamp(.95rem,1.9vw,1.2rem)}
.wordcloud li:nth-child(3n){color:#0a7d85;transform:rotate(-2deg)}
.wordcloud li:nth-child(3n+1){color:#0a7d85}
.wordcloud li:nth-child(4n){transform:rotate(1.6deg)}
.wordcloud li:nth-child(5n+2){color:#38a888}
.wordcloud li:nth-child(7n){color:#38a888}
/* relations sujet / ambiance / technique / composition */
.rel-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--gap)}
.rel-card{background:var(--card);border:1px solid var(--hair);border-radius:var(--r-card);
  padding:clamp(1.1rem,2.6vw,1.7rem);box-shadow:var(--shadow-soft)}
.rel-num{font-family:var(--sans);font-size:.72rem;letter-spacing:.22em;color:var(--teal);margin:0 0 .5rem}
.rel-card h3{font-size:1.25rem;margin-bottom:.4rem}
.rel-card p{font-size:.92rem;color:var(--muted);margin:0}
/* matériel atelier */
.mat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:var(--gap);margin:1.8rem 0 2.2rem}
.mat-card{background:var(--card);border:1px solid var(--hair);border-radius:var(--r-card);
  padding:clamp(1.1rem,2.6vw,1.6rem);box-shadow:var(--shadow-soft);text-align:left}
.mat-ico{font-size:1.6rem;display:block;margin-bottom:.55rem}
.mat-card h3{font-size:1.2rem;margin-bottom:.35rem}
.mat-card p{font-size:.9rem;color:var(--muted);margin:0}
/* galerie à feuilleter (accueil) */
.flip-row{display:flex;gap:var(--gap);overflow-x:auto;scroll-snap-type:x mandatory;
  padding:.4rem .2rem 1.2rem;-webkit-overflow-scrolling:touch;scrollbar-width:thin}
.flip-card{flex:0 0 min(300px,72vw);scroll-snap-align:center;text-decoration:none;color:inherit}
.flip-figure{display:block;background:var(--card);border:1px solid var(--hair);
  border-radius:var(--r-card);padding:12px 12px 30px;box-shadow:var(--shadow-soft);
  transition:transform .35s var(--t-soft),box-shadow .35s var(--t-soft)}
.flip-card:hover .flip-figure{transform:translateY(-5px);
  box-shadow:0 18px 40px -18px rgba(56,168,136,.5)}
.flip-img{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:var(--r-img)}
.flip-cap{display:block;text-align:center;margin-top:.6rem}
.flip-cap strong{display:block;font-family:var(--serif);font-size:1.02rem}
.flip-cap em{font-size:.78rem;color:var(--muted)}
.flip-nav{display:flex;gap:.6rem}
.flip-btn{min-width:48px;min-height:48px;border-radius:50%;border:1px solid var(--hair);
  background:var(--card);color:var(--ink);font-size:1.15rem;cursor:pointer}
.flip-btn:hover{border-color:var(--teal);color:var(--teal-ink)}
/* carrousel d'œuvre (page détail) */
.wk-carousel{position:relative;margin:0}
.wk-track{display:flex;transition:transform .5s var(--t-soft);border-radius:var(--r-img)}
.wk-img{flex:0 0 100%;width:100%;object-fit:contain}
.wk-btn{position:absolute;top:50%;transform:translateY(-50%);min-width:48px;min-height:48px;
  border-radius:50%;border:1px solid rgba(14,42,50,.25);background:rgba(255,253,249,.92);
  color:var(--ink);font-size:1.5rem;line-height:1;cursor:pointer;z-index:2}
.wk-prev{left:10px}.wk-next{right:10px}
.wk-btn:hover{background:var(--teal);color:#fff;border-color:var(--teal)}
.wk-dots{position:absolute;left:0;right:0;bottom:.7rem;display:flex;justify-content:center;
  gap:.45rem;z-index:2}
.wk-dots{bottom:.8rem}
.wk-dot{width:34px;height:26px;border-radius:3px;overflow:hidden;cursor:pointer;
  background:rgba(255,253,249,.92) center/cover no-repeat;
  border:1px solid rgba(14,42,50,.28);padding:0;margin:0;
  box-shadow:0 1px 3px rgba(14,42,50,.18);transition:transform .25s,border-color .25s}
.wk-dot:hover{transform:translateY(-2px)}
.wk-dot.on{border:2px solid var(--teal);transform:scale(1.08)}
.wk-dot:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
.wk-zoom{position:absolute;top:12px;right:12px;z-index:3;min-width:44px;min-height:44px;
  border-radius:50%;background:rgba(255,253,249,.92);border:1px solid rgba(14,42,50,.25);
  color:var(--ink);font-size:1.15rem;line-height:1;cursor:pointer;
  box-shadow:0 2px 6px rgba(14,42,50,.22);transition:background .25s,color .25s,transform .25s}
.wk-zoom:hover{background:var(--teal);color:#fff;transform:scale(1.06)}
.wk-zoom:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
.wk-carousel{outline:none}
.wk-carousel:focus-visible{outline:2px solid var(--teal);outline-offset:4px;border-radius:var(--r-img)}
.wk-img{cursor:zoom-in}
.wk-lightbox{position:fixed;inset:0;z-index:1200;display:flex;flex-direction:column;
  align-items:center;justify-content:center;background:rgba(10,22,26,.92)}
.wk-lightbox[hidden]{display:none}
.wk-lightbox figure{margin:0;max-width:min(1200px,94vw);text-align:center}
.wk-lightbox img{max-width:100%;max-height:78vh;border:2px solid rgba(255,255,255,.55);
  background:#fffdf9;padding:.4rem}
.artist-socials{margin:.9rem 0 0;font-family:var(--sans);font-size:.82rem;
  letter-spacing:.06em;color:var(--text)}
.artist-socials a{color:var(--tealInk);text-decoration:none;
  border-bottom:1px solid rgba(56,168,136,.35)}
.artist-socials a:hover{border-bottom-color:var(--tealInk)}
.artist-socials a+a{margin-left:.8rem}
.artist-socials a:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
@media(max-width:700px){.wk-dot{width:26px;height:20px}}
/* badge événement à venir */
.evt-badge{display:inline-block;margin-left:.5rem;padding:.14rem .55rem;border-radius:99px;
  background:var(--teal);color:#fff;font-size:.62rem;letter-spacing:.14em;
  text-transform:uppercase;vertical-align:1px}
/* responsive */
@media (max-width:900px){.rel-grid{grid-template-columns:repeat(2,1fr)}.mat-grid{grid-template-columns:repeat(2,1fr)}}
@media (max-width:560px){.rel-grid,.mat-grid{grid-template-columns:1fr}
  .wordcloud{gap:.3rem 1rem}}
@media print{.flip-nav,.wk-btn,.wk-dots{display:none}.flip-row{flex-wrap:wrap}}

/* conformité cookies & porte carte */
.cookie-bar{position:fixed;left:50%;bottom:1.1rem;transform:translateX(-50%);z-index:160;
width:min(860px,94vw);background:var(--card);border:1px solid var(--hair);
border-top:2px solid var(--teal);border-radius:4px;box-shadow:var(--sh);padding:1rem 1.3rem}
.cookie-inner{display:flex;gap:1.4rem;align-items:center;justify-content:space-between;flex-wrap:wrap}
.cookie-txt{margin:0;font-size:.92rem;max-width:52em;color:var(--text)}
.cookie-actions{display:flex;gap:.8rem;margin:0}
.cookie-actions .btn{padding:.68rem 1.3rem;font-size:.74rem}
.cookie-main{flex:1 1 340px;min-width:0}
.cookie-opts{border-top:1px solid var(--hair);margin-top:.9rem;padding-top:.9rem;width:100%}
.ck-title{margin:0 0 .55rem;font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.ck-opt{display:flex;gap:.65rem;align-items:flex-start;margin:.45rem 0;font-size:.88rem;cursor:pointer}
.ck-opt input{margin-top:.22rem;accent-color:var(--teal);flex:none;width:16px;height:16px}
.ck-opt.ck-tech{cursor:default;color:var(--muted)}
.map-consent{min-height:300px;display:flex;align-items:center;justify-content:center;text-align:center;
background:radial-gradient(70% 90% at 50% 110%,rgba(34,155,117,0.200),transparent 70%),var(--paper)}
.map-consent-inner{max-width:520px;padding:2rem 1.4rem;color:var(--text)}
.map-consent-inner .label{justify-content:center}
.map-consent-inner p{margin-bottom:1rem}
/* administration (monofichier) */
.adm-bar{display:flex;gap:.8rem;flex-wrap:wrap;margin-bottom:1.4rem}
.adm-status{font-size:.85rem;color:var(--tealInk);min-height:1.3em;margin-bottom:1.2rem}
.adm-status.err{color:#b3552d}
.adm-row{display:grid;grid-template-columns:96px minmax(0,1fr) auto;gap:1rem;
padding:1rem 0;border-bottom:1px solid var(--hair);align-items:start}
.adm-thumb{width:96px;height:70px;object-fit:cover;border:1px solid var(--hair);
padding:2px;background:var(--card)}
.adm-noimg{display:flex;align-items:center;justify-content:center;color:var(--muted);
border-style:dashed}
.adm-fields input,.adm-fields textarea{width:100%;font:inherit;font-size:.95rem;
border:1px solid var(--hair);background:#fff;padding:.45rem .6rem;border-radius:3px;color:var(--ink)}
.adm-fields input:focus,.adm-fields textarea:focus{outline:none;border-color:var(--teal)}
.adm-fields textarea{min-height:60px;resize:vertical}
.adm-inline{display:grid;grid-template-columns:minmax(0,1fr) 120px;gap:.6rem;margin-top:.45rem}
.adm-fields>.adm-inline:first-child{margin-top:0}
.adm-fields input+textarea,.adm-fields .adm-inline+textarea{margin-top:.45rem}
.adm-actions{display:flex;flex-direction:column;gap:.4rem}
.adm-actions button,.adm-actions label{font:500 .74rem/1 var(--sans);letter-spacing:.05em;
padding:.5rem .75rem;border:1px solid var(--hair);background:var(--card);border-radius:3px;
cursor:pointer;text-align:center;color:var(--ink)}
.adm-actions button:hover,.adm-actions label:hover{border-color:var(--teal);color:var(--tealInk)}
.adm-actions .danger{color:#b3552d}
.adm-actions .danger:hover{border-color:#b3552d;color:#b3552d;background:#fdf6f2}
.adm-add{background:var(--card);border:1px solid var(--hair);border-radius:4px;
padding:1.3rem 1.5rem;margin:1.3rem 0 2.6rem}
.adm-add h3{margin-bottom:.9rem}
.adm-grid2{display:grid;grid-template-columns:1fr 1fr;gap:.9rem}
@media(max-width:700px){.adm-row{grid-template-columns:74px minmax(0,1fr)}
.adm-thumb{width:74px}.adm-actions{grid-column:1/-1;flex-direction:row;flex-wrap:wrap}
.adm-grid2{grid-template-columns:1fr}}
.edit[contenteditable]{outline:1px dashed rgba(56,168,136,.55);outline-offset:4px;
cursor:text;border-radius:2px}
.edit[contenteditable]:focus{outline:2px solid var(--teal);background:rgba(56,168,136,.05)}
.hero-title,.page-title,.h2,.h3{color:#0a7d85}

/* — duo carte de visite : #0a7d85 (bleu) · #38a888 (vert) — survols lisibles — */
.btn:hover,.btn.btn-outline:hover,.wk-btn:hover,.wk-zoom:hover{background:#0c6e77;border-color:#0c6e77}
.lnk:hover{color:#0c6e77}
.hl-lb-btn:hover,.hl-lb-close:hover{background:rgba(12,110,119,.62)}
a:focus-visible,button:focus-visible{outline-color:#0a7d85}


/* — motif exact de la carte de visite en tête de chaque page — */
.page-head,
.pg-artist .page-head,.pg-artiste .page-head,.pg-atelier .page-head,
.pg-gallery .page-head,.pg-galerie .page-head,.pg-work .page-head,.pg-oeuvre .page-head,
.pg-news_list .page-head,.pg-evenements .page-head,.pg-news_item .page-head,.pg-evenement .page-head,
.pg-contact .page-head{background:linear-gradient(180deg,rgba(250,248,243,.62) 0%,rgba(250,248,243,.92) 70%,var(--paper) 100%),url("__WASHCARD__") center/cover no-repeat!important}

/* démarche de l'auteur — carnet d'inspiration */
.poem-card{max-width:34em;margin:2.2rem auto 0;padding:1.6rem 1.4rem;background:linear-gradient(180deg,rgba(255,253,249,.92),rgba(250,248,243,.86));border:1px solid rgba(14,42,50,.10);border-radius:var(--r-img);font-family:var(--serif);font-style:italic;font-size:1.05rem;line-height:2;color:var(--ink);text-align:center;box-shadow:var(--shadow-soft)}
.poem-card p{margin:0}
.poem-gap{display:block;height:1.1rem}
.big-quote cite a{color:inherit}
.lead.center{text-align:center}
.tint-sage .fact-card{margin-top:1.4rem}
/* atelier — cahier technique */
.tech-card{background:var(--card);border:1px solid var(--hair);border-radius:var(--r-card);padding:clamp(1.1rem,2.6vw,1.6rem);box-shadow:var(--shadow-soft)}
.tech-card h4{font-family:var(--sans);font-size:.78rem;letter-spacing:.18em;text-transform:uppercase;color:var(--teal);margin:0 0 .7rem}
.tech-list{list-style:none;margin:0;padding:0}
.tech-list li{position:relative;padding-left:1.1rem;font-size:.93rem;color:var(--muted);line-height:1.55;margin-bottom:.45rem}
.tech-list li::before{content:"";position:absolute;left:0;top:.62em;width:.45rem;height:2px;background:var(--teal)}
.chip-list{display:flex;flex-wrap:wrap;gap:.5rem;margin:0;padding:0;list-style:none}
.chip{font-family:var(--serif);font-style:italic;font-size:.92rem;color:var(--teal-ink);background:rgba(26,157,154,.07);border:1px solid rgba(10,125,133,.22);border-radius:999px;padding:.32rem .8rem}
.step-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem;margin-top:1.6rem}
.step-card{background:var(--card);border:1px solid var(--hair);border-radius:var(--r-card);padding:1.2rem 1.2rem 1.3rem;box-shadow:var(--shadow-soft)}
.step-num{font-family:var(--sans);font-size:.72rem;letter-spacing:.22em;color:var(--teal);margin:0 0 .6rem}
.step-card p{font-size:.93rem;color:var(--muted);margin:0}
.tech-note{max-width:44em;margin:1.8rem auto 0;padding:1rem 1.2rem;border-left:3px solid var(--teal);background:rgba(26,157,154,.06);border-radius:0 var(--r-card) var(--r-card) 0;font-size:.92rem;color:var(--muted)}
/* carrousel — sur l'aquarelle, sous le nom ; passe-partout, formule fluide unique */
.hc-carousel{position:relative;width:min(760px,78vw);margin:clamp(1rem,2.2vw,1.6rem) auto 0;aspect-ratio:2.6/1;overflow:hidden;border:6px solid rgba(252,250,246,.95);border-radius:14px;background:#fcfaf6;box-shadow:0 10px 30px rgba(14,42,50,.18),0 3px 8px rgba(14,42,50,.10);outline:none}
.hc-carousel:focus-visible{outline:2px solid var(--teal);outline-offset:4px}
.hc-img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center;opacity:0;transform:scale(1);transition:opacity .9s ease,transform .9s ease}
.hc-img.on{opacity:1;transform:scale(1.07);transition:opacity .9s ease,transform 8s linear}
.hc-carousel::after{content:"";position:absolute;inset:auto 0 0 0;height:24%;z-index:2;pointer-events:none;background:linear-gradient(180deg,transparent,rgba(10,40,45,.30))}
.hc-carousel .wk-btn{position:absolute;top:50%;transform:translateY(-50%);z-index:3;width:52px;height:52px;min-width:0;min-height:0;padding:0;display:flex;align-items:center;justify-content:center;border-radius:50%;border:1px solid rgba(250,248,243,.55);background:rgba(10,40,45,.32);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);color:#faf8f3;font-family:inherit;font-size:1.9rem;line-height:1;cursor:pointer;opacity:0;transition:opacity .3s ease,background .25s ease,border-color .25s ease}
.hc-carousel:hover .wk-btn,.hc-carousel:focus-within .wk-btn{opacity:1}
.hc-carousel .wk-btn:hover{background:rgba(10,60,66,.58);border-color:#faf8f3}
.hc-carousel .wk-prev{left:14px}
.hc-carousel .wk-next{right:14px}
@media (hover:none){.hc-carousel .wk-btn{opacity:1}}
.hc-carousel .wk-dots{position:absolute;left:50%;right:auto;transform:translateX(-50%);bottom:14px;z-index:3;display:flex;justify-content:center;gap:9px;padding:6px 9px;border-radius:999px;background:rgba(10,40,45,.34);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px)}
.hc-carousel .wk-dot{width:46px;height:30px;padding:0;border-radius:6px;cursor:pointer;background-size:cover;background-position:center;border:1px solid rgba(250,248,243,.40);opacity:.55;transition:opacity .25s ease,transform .25s ease,border-color .25s ease}
.hc-carousel .wk-dot:hover{opacity:.85}
.hc-carousel .wk-dot.on{opacity:1;border-color:#faf8f3;transform:scale(1.1)}
@media (max-width:760px){.hero-title{margin-bottom:.8rem}.hero-sub{margin-bottom:.9rem}.hero-after{padding-top:1rem}.hc-carousel{margin-top:.75rem}.hc-carousel .wk-btn{width:42px;height:42px;font-size:1.6rem}.hc-carousel .wk-dots{gap:6px;padding:5px 7px;bottom:10px}.hc-carousel .wk-dot{width:36px;height:24px;border-radius:5px}}
</style>
</head>
<body class="pg-home">
<a class="skip-link" href="#contenu">Aller au contenu</a>
<header class="site-header" id="site-header">
  <div class="header-inner">
    <a class="brand" href="#/accueil" aria-label="Hilaire Legentil — accueil">
      <span class="brand-name">Hilaire&nbsp;Legentil</span>
      <span class="brand-baseline">Aquarelles — mer &amp; paysage</span>
    </a>
    <nav class="site-nav" id="site-nav" aria-label="Navigation principale">
      <ul>
        <li><a href="#/accueil" data-r="accueil">Accueil</a></li>
        <li><a href="#/artiste" data-r="artiste">La démarche de l’artiste</a></li>
        <li><a href="#/atelier" data-r="atelier">L’atelier</a></li>
        <li><a href="#/galerie" data-r="galerie">Galerie</a></li>
        <li><a href="#/evenements" data-r="evenements">Événements</a></li>
        <li><a href="#/contact" data-r="contact">Contacts</a></li>
      </ul>
    </nav>
    <button class="nav-toggle" id="nav-toggle" aria-expanded="false"
            aria-controls="site-nav" aria-label="Ouvrir le menu"><span></span><span></span></button>
  </div>
</header>
<main id="contenu"></main>
<div class="spectrum" aria-hidden="true"></div>
<footer class="site-footer">
  <div class="footer-inner">
    <div class="footer-col">
      <p class="brand-name">Hilaire&nbsp;Legentil</p>
      <p class="footer-baseline">__FJOB__<br>__FTAG__</p>
      <p class="footer-loc">Yvetot-Bocage · Normandie</p>
    </div>
    <div class="footer-col">
      <h2 class="footer-title">Contacts</h2>
      <ul class="footer-list" id="footer-contact"></ul>
    </div>
    <div class="footer-col">
      <h2 class="footer-title">Le site</h2>
      <ul class="footer-list">
        <li><a href="#/artiste">La démarche de l’artiste</a></li>
        <li><a href="#/atelier">L’atelier</a></li>
        <li><a href="#/galerie">La galerie</a></li>
        <li><a href="#/evenements">Événements &amp; expositions</a></li>
        <li><a href="#/contact">Contact &amp; demande spécifique</a></li>
        <li><a href="#/admin" rel="nofollow">✎ Espace administrateur</a></li>
      </ul>
    </div>
  </div>
  <div class="footer-legal">
    <p>© <span id="year"></span> Hilaire Legentil · SIREN 927 753 780 —
       Aquarelles originales, photographies et textes protégés. —
       <a href="#/confidentialite">Confidentialité &amp; mentions légales</a></p>
    <p class="footer-credit">Site réalisé par <a href="http://webetgo.fr" target="_blank" rel="noopener">Web&amp;Go</a></p>
  </div>
</footer>
<aside class="cookie-bar" id="cookie-bar" role="region" aria-label="Gestion des cookies" hidden>
  <div class="cookie-inner">
    <div class="cookie-main">
      <p class="cookie-txt">Ce fichier ne dépose aucun cookie. La carte de la page Contact
         (tuiles OpenStreetMap) ne se charge qu’avec votre accord.<span id="ck-ga-txt"></span>
         <a class="lnk" href="#/confidentialite">En savoir plus</a></p>
      <p class="cookie-actions">
        <button class="btn" id="ck-accept" type="button">Tout accepter</button>
        <button class="btn btn-outline" id="ck-refuse" type="button">Tout refuser</button>
        <button class="btn btn-outline" id="ck-custom" type="button" aria-expanded="false" aria-controls="cookie-opts">Personnaliser</button>
      </p>
    </div>
    <div class="cookie-opts" id="cookie-opts" hidden>
      <p class="ck-title">Choix par usage</p>
      <label class="ck-opt ck-tech"><input type="checkbox" checked disabled>
        <span><strong>Stockage local technique</strong> (vos choix) — indispensable, conservé dans votre navigateur, jamais transmis.</span></label>
      <label class="ck-opt"><input type="checkbox" id="ck-map">
        <span><strong>Carte interactive</strong> (page Contact) — tuiles OpenStreetMap, chargées seulement si vous l’acceptez.</span></label>
      <label class="ck-opt" id="ck-ga-row" hidden><input type="checkbox" id="ck-ga">
        <span><strong>Mesure d’audience</strong> — anonymisée, aucun profilage.</span></label>
      <p class="cookie-actions"><button class="btn" id="ck-save" type="button">Enregistrer mes choix</button></p>
    </div>
  </div>
</aside>
<script>__LEAFLET_JS__</script>
<script>
"use strict";
var DATA = /*HLDATA*/__DATA__/*HLDATA-END*/;
var PRISTINE="<!DOCTYPE html>\n"+document.documentElement.outerHTML;
try{var SAVED=JSON.parse(localStorage.getItem("hl_data")||"null");
    if(SAVED&&SAVED.data){DATA=SAVED.data;if(!DATA.atelier)DATA.atelier=[];if(!DATA.photos)DATA.photos=DATA.palette?[DATA.palette]:[];
  DATA.works.forEach(function(w){if(!w.im)w.im=[];});}
hlGaInit();}catch(e){}
function hlGaInit(){try{
  if(!DATA.ga||window.__hlGaDone)return;var C=hlGet();if(!C.done||!C.ga)return;
  window.__hlGaDone=true;
  var s=document.createElement("script");s.async=true;
  s.src="https://www.googletagmanager.com/gtag/js?id="+encodeURIComponent(DATA.ga);
  document.head.appendChild(s);
  window.dataLayer=window.dataLayer||[];window.gtag=function(){dataLayer.push(arguments);};
  gtag("js",new Date());gtag("config",DATA.ga,{anonymize_ip:true});}catch(e){}}
var ADMIN=false;try{ADMIN=sessionStorage.getItem("hl_admin")==="1";}catch(e){}

/* --------------------------------------------------- utilitaires ------- */
function esc(s){var d=document.createElement("div");d.textContent=s||"";return d.innerHTML;}
function escA(s){return (s||"").replace(/&/g,"&amp;").replace(/"/g,"&quot;")
  .replace(/'/g,"&#39;").replace(/</g,"&lt;");}
function slugJs(t){t=(t||"").replace(/[\u0152\u0153]/g,"oe").replace(/[\u00c6\u00e6]/g,"ae");
  t=t.normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/[^a-zA-Z0-9]+/g,"-")
  .replace(/^-+|-+$/g,"").toLowerCase();return t||"sans-titre";}
function jsDateFr(v){var m=/^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$/.exec(v||"");if(!m)return v||"";
  var mo=["","janvier","février","mars","avril","mai","juin","juillet","août",
  "septembre","octobre","novembre","décembre"];
  var p=[];if(m[3])p.push(+m[3]);if(m[2]&&+m[2]>=1&&+m[2]<=12)p.push(mo[+m[2]]);p.push(m[1]);
  return p.join(" ");}
function workBySlug(s){for(var i=0;i<DATA.works.length;i++)if(DATA.works[i].s===s)return DATA.works[i];return null;}
function newsBySlug(s){for(var i=0;i<DATA.news.length;i++)if(DATA.news[i].s===s)return DATA.news[i];return null;}
function meta(w){var m=[w.c,w.y].filter(Boolean).join(" · ");return m||"Aquarelle";}
function spanClass(w,i){var r=w.h?w.w/w.h:1;
  if(r>=1.75)return"s-wide";if(r<=0.85)return"s-tall";if(i%5===2)return"s-big";return"s-std";}
function workCard(w,i){return '<a class="work '+spanClass(w,i)+'" href="#/oeuvre/'+w.s+
  '" data-cat="'+esc(w.c)+'" data-tn="'+esc(w.tn||"")+
  '" data-sujet="'+esc(w.sj||"")+'" data-amb="'+esc(w.am||"")+'" data-tech="'+esc(w.tc||"")+
  '" data-year="'+esc(w.y||"")+'"><span class="work-frame"><img loading="lazy" alt="Aquarelle — '+
  esc(w.t)+(w.c?" — "+esc(w.c):"")+'" src="'+w.i+'"></span><span class="work-caption">'+
  '<span class="work-title">'+esc(w.t)+'</span><span class="work-meta">'+esc(meta(w))+
  '</span></span></a>';}
function newsRow(n,excerpt,upcoming){return '<a class="news-row" href="#/evenement/'+n.s+'">'+
  (n.cov?'<span class="news-thumb"><img loading="lazy" alt="'+esc(n.t)+'" src="'+n.cov+'"></span>':"")+
  '<span class="news-body">'+(n.dt?'<span class="news-date">'+esc(n.dt)+(n.tm?' · '+esc(n.tm):'')+(n.pl?' · '+esc(n.pl):'')+'</span>'+((upcoming)?' <span class="evt-badge">à venir</span>':''):'')+
  '<span class="news-title">'+esc(n.t)+'</span>'+
  (excerpt&&n.p[0]?'<span class="news-excerpt">'+esc(n.p[0].slice(0,160))+
   (n.p[0].length>160?"…":"")+'</span>':"")+
  '</span><span class="news-arrow" aria-hidden="true">→</span></a>';}
var QUOTE='<svg class="quote-mark" viewBox="0 0 72 48" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">'+
'<path d="M8 40c10-4 16-12 16-24-7 1-12-3-12-9S17-2 23-2c8 0 13 6 13 14 0 16-10 26-24 30z" transform="translate(8 4)" fill="#38a888" opacity=".45"/>'+
'<path d="M8 40c10-4 16-12 16-24-7 1-12-3-12-9S17-2 23-2c8 0 13 6 13 14 0 16-10 26-24 30z" transform="translate(34 4)" fill="#38a888" opacity=".28"/></svg>';
var WASH='<div class="hero-wash" aria-hidden="true"><img src="__WASHCARD__" alt="" decoding="async"></div>';

/* ------------------------------------------------------- pages --------- */
var CAR='<div class="hc-carousel reveal d2" id="hc-carousel" role="region" aria-label="Carrousel de photographies">'+
  '<img class="hc-img on" src="__HC1__" alt="Photographie de l\u2019univers d\u2019Hilaire Legentil" decoding="async">'+
  '<img class="hc-img" src="__HC2__" alt="Photographie de l\u2019univers d\u2019Hilaire Legentil" loading="lazy" decoding="async">'+
  '<img class="hc-img" src="__HC3__" alt="Photographie de l\u2019univers d\u2019Hilaire Legentil" loading="lazy" decoding="async">'+
  '<img class="hc-img" src="__HC4__" alt="Photographie de l\u2019univers d\u2019Hilaire Legentil" loading="lazy" decoding="async">'+
  '<img class="hc-img" src="__HC5__" alt="Photographie de l\u2019univers d\u2019Hilaire Legentil" loading="lazy" decoding="async">'+
  '<button class="wk-btn wk-prev" type="button" aria-label="Image précédente">\u2039</button>'+
  '<button class="wk-btn wk-next" type="button" aria-label="Image suivante">\u203a</button>'+
  '<span class="wk-dots" id="hc-dots"></span></div>';
function pageHome(){
  var _td=new Date().toISOString().slice(0,10);
  var _up=DATA.news.filter(function(n){return (n.rd||"")>=_td;}),
      _pa=DATA.news.filter(function(n){return (n.rd||"")<_td;});
  var news=_up.concat(_pa).slice(0,3).map(function(n){return newsRow(n,false);}).join("");
  var fig=DATA.works[0];
  return '<section class="hero">'+WASH+
  '<div class="hero-inner"><p class="hero-baseline reveal">'+esc(DATA.heroB)+'</p>'+
  '<h1 class="hero-title reveal d1">'+esc(DATA.heroT)+'</h1>'+
  '<p class="hero-sub reveal d2">'+esc(DATA.heroS)+'</p>'+
  CAR+
  '</div>'+
  '<div class="hero-after"><p class="hero-intro reveal d3">'+esc(DATA.homeIntro)+'</p>'+
  '<p class="hero-cta reveal d3"><a class="btn" href="#/artiste">Découvrir la démarche</a></p></div>'+
  '</section>'+
  '<section class="section section-artist tint-sand"><div class="container artist-home">'+
  '<div class="reveal"><p class="label">La démarche de l’artiste</p>'+
  '<h2 class="h2">Traduire quelque chose<br>de profond</h2>'+
  '<p class="lead">'+esc(DATA.artistIntro)+'</p>'+
  '<blockquote class="mini-quote">«&nbsp;Mes aquarelles sont sur papier 100&nbsp;% coton, cette matière apporte une tonalité douce à la couleur et permet des superpositions qui n’altèrent pas les lavis.&nbsp;»<cite>— Hilaire Legentil</cite></blockquote>'+
  '<a class="link-arrow" href="#/artiste">La démarche de l’artiste</a></div>'+
  (fig?'<div class="artist-home-figure reveal"><img src="'+fig.i+'" alt="Aquarelle — '+esc(fig.t)+'">'+
   '<span class="figure-caption">'+esc(fig.t)+'</span></div>':"")+
  '</div></section>'+
  '<section class="section quote-section"><div class="container narrow center reveal">'+QUOTE+
  '<blockquote class="big-quote">Peindre, c’est voyager, peindre c’est aussi une façon de pouvoir méditer. J’ai choisi d’être paysagiste marine car la mer, les ports, la côte et les nuages m’apaisent et me recentrent.<cite>Hilaire Legentil</cite></blockquote></div></section>'+
  '<section class="section tint-sky"><div class="container"><div class="section-head reveal">'+
  '<div><p class="label">Événements</p><h2 class="h2">Événements &amp; expositions</h2></div>'+
  '<a class="link-arrow" href="#/evenements">Tous les événements</a></div>'+
  '<div class="news-rows">'+news+'</div></div></section>'+
  '<section class="section contact-invitation"><div class="container narrow reveal">'+
  '<p class="label">Prendre contact</p><h2 class="h2">Exposition et vente</h2>'+
  '<p class="lead">Aquarelles sur commandes.</p>'+
  '<p class="invitation-cta"><a class="btn" href="#/contact">Contacter l’artiste</a>'+
  '<a class="link-arrow" href="#/contact?sujet=Demande%20sp%C3%A9cifique">Faire une demande spécifique</a></p></div></section>';
}

function pageArtist(){
  var tl=DATA.news.map(function(n){
    return '<li><a href="#/evenement/'+n.s+'"><span class="tl-date">'+esc(n.dt)+'</span>'+
    '<span class="tl-title">'+esc(n.t)+'</span><span class="tl-arrow" aria-hidden="true">→</span></a></li>';}).join("");
  return '<header class="page-head"><div class="container reveal"><p class="label">La démarche de l’artiste</p>'+
  '<h1 class="page-title">Hilaire Legentil</h1>'+
  '<p class="page-sub">Artiste auteur</p></div></header>'+

  '<section class="section artist-intro"><div class="container two-col">'+
  '<div class="artist-text reveal"><p class="label">Quelques mots</p>'+
  '<h2 class="h2">Parcours</h2>'+
  '<p class="lead">'+esc(DATA.artistIntro)+'</p>'+
  '<p>Je dessine et je peins depuis mon plus jeune âge, mes parents n’étaient pas artistes, ils tenaient une boutique de tissu sur les marchés. Ma maman, très demandée par les clients pour ses conseils, sans le savoir, m’a finalement éveillé à l’association des couleurs.</p>'+
  '<p>Ayant suivi un parcours technique, je n’ai pas fait d’école d’arts, puis, à 25 ans j’ai pris quelques cours avec Kasuo Iwamura (Valognes).</p>'+
  '<p>Avec mon épouse, nous avons ensuite élevé nos enfants puis déménagé à Paris pour le travail. Pendant ces 25 ans, j’ai rarement repris les pinceaux mais j’ai continué à fréquenter les galeries d’arts et les musées.</p>'+
  '<p>Le confinement a eu raison de beaucoup de nos certitudes. À ce moment, l’aquarelle s’est imposée à moi comme une nécessité. J’ai eu l’immense privilège de rencontrer Alain Meyer, professeur expérimenté avec qui j’ai commencé des cours en visio pendant le confinement&nbsp;! Pendant 2 ans, il a été mon maître, il m’a transmis le bagage technique et la méthode que je recherchais. L’aquarelle est très exigeante et ne s’improvise pas. La technique est incontournable pour se libérer et s’exprimer.</p></div>'+

  '<aside class="reveal"><figure class="portrait-card">'+
  '<img src="'+DATA.portrait+'" alt="Portrait de Hilaire Legentil" width="302" height="452" loading="lazy">'+
  '<figcaption>Hilaire Legentil</figcaption></figure>'+
  ((DATA.instagram||DATA.fb)?'<p class="artist-socials">Suivre l’artiste —'+
    (DATA.instagram?' <a href="https://www.instagram.com/'+DATA.instagram+'/" rel="me noopener" target="_blank">Instagram</a>':"")+
    (DATA.fb?' <a href="'+DATA.fb+'" rel="me noopener" target="_blank">Facebook</a>':"")+
    '</p>':"")+
  '<div class="fact-card"><h2 class="fact-title">En un regard</h2>'+
  '<dl class="fact-list"><div><dt>Art</dt><dd>'+esc(DATA.rA)+'</dd></div>'+
  '<div><dt>Sujet</dt><dd>'+esc(DATA.rS)+'</dd></div>'+
  '<div><dt>Univers</dt><dd>'+esc(DATA.rU)+'</dd></div>'+
  '<div><dt>Support</dt><dd>'+esc(DATA.rP)+'</dd></div>'+
  '<div><dt>Région</dt><dd>'+esc(DATA.rR)+'</dd></div></dl></div>'+
  '</aside></div></section>'+

  '<section class="section tint-sky"><div class="container narrow reveal">'+
  '<h2 class="h2">Traduire quelque chose de profond</h2>'+
  '<p>L’«&nbsp;art figuratif&nbsp;» que je pratique n’est pas copier le sujet, ce qui a peu d’intérêt en effet. J’essaie modestement de synthétiser, de trouver le chemin qui fera voyager le regardant. L’abstrait ou le figuratif pour moi ne font pas débat, l’essentiel étant de faire rêver.</p>'+
  '<p>Peindre, c’est voyager, peindre c’est aussi une façon de pouvoir méditer. J’ai choisi d’être paysagiste marine car la mer, les ports, la côte et les nuages m’apaisent et me recentrent. Onirique résumerait assez bien mon approche de l’aquarelle. Derrière ces paysages, ces couleurs et ces formes en mouvement, il y a une énergie, quelque chose de profond qui me bouleverse. Un ciel ombrageux, une vague verte éclairée dans un soleil d’hiver, un vol planant de Goéland engendrent une impression que j’aime explorer et faire grandir en moi. C’est probablement cela que je tente de traduire et de partager.</p></div></section>'+

  '<section class="section"><div class="container narrow reveal">'+
  '<h2 class="h2">La technique</h2>'+
  '<p>Je compose mes aquarelles à partir de matériaux multiples&nbsp;: observation et croquis sur le vif, photos formant un carnet de notes de couleurs et de formes. Pour pouvoir exprimer ce qui m’a ému dans un paysage, j’adapte le sujet&nbsp;: je supprime un élément, ajuste une ligne d’horizon, complète un élément important au premier plan…</p>'+
  '<p>Mes aquarelles sont sur papier 100&nbsp;% coton, cette matière apporte une tonalité douce à la couleur et permet des superpositions qui n’altèrent pas les lavis.</p>'+
  '<p>Ma couleur de prédilection est le bleu&nbsp;: en particulier l’Outremer qui apporte une granulation si belle sur le papier. Pour la mer, j’associe des bleus tirant sur le vert (Bleu Winsor, Bleu de prusse) que je mélange en quantité variable à des terres ou à des verts (vert d’eau). Ces couleurs forment la trame de mes compositions.</p>'+
  '<p>J’utilise assez régulièrement le Marron de Pérylène (plus transparent que le rouge indien et tirant sur le gris). Associé au bleu d’Indanthrène, il forme de magnifiques violets pour les nuages sombres.</p>'+
  '<p>Les gris enfin, le gris chaud pour le sable humide et le gris froid très utile pour contrôler la profondeur du paysage.</p></div></section>'+

  '<section class="section tint-sand"><div class="container narrow reveal">'+
  '<h2 class="h2">L’expo</h2>'+
  '<p>J’espère que cette nouvelle saison d’exposition vous inspirera, vous permettra d’accéder à l’univers sensible du paysage et de l’aquarelle. Et nous aurons peut-être le plaisir d’échanger, c’est toujours un moment d’humanité privilégié.</p>'+
  '<p>Pour un court séjour dans le Cotentin, ou habitant cette région, je souhaite aussi de tout cœur que cette exposition vous donne envie — quel que soit votre parcours, de peindre, d’utiliser vos mains ou votre corps pour exprimer ce qui vibre en vous (peinture, sculpture, chant, danse, méditation…).</p></div></section>'+

  '<section class="section"><div class="container narrow reveal">'+
  '<h2 class="h2">L’art comme thérapie.</h2>'+
  '<p>Plusieurs études ont démontré que le fait d’être exposé à l’art présentait des vertus pour la santé mentale&nbsp;! Une étude londonienne parle même de baisse de mortalité, une autre du Japon met en avant la réduction de l’anxiété et de la pression artérielle. L’OMS a enfin validé l’effet thérapeutique de l’art sur le cerveau et le bien-être. On parle aujourd’hui de «&nbsp;muséothérapie&nbsp;», et de prendre soin de soi par la culture.</p>'+
  '<p>Je suis parfois surpris de constater nombre de personnes sans formation, sans aptitude apparente, sans parcours dans les arts, se révèlent pleines de ressources et de talent dans la pratique artistique.</p>'+
  '<p class="lead center">À vos pinceaux</p></div></section>'+

  '<section class="section tint-sage"><div class="container reveal">'+
  '<h2 class="h2">La société&nbsp;: Marine Normandie aquarelle</h2>'+
  '<div class="rel-grid">'+
  '<div class="rel-card reveal"><h3 class="h3">Exposition et vente</h3></div>'+
  '<div class="rel-card reveal"><h3 class="h3">Aquarelles sur commandes</h3></div></div>'+
  '<div class="fact-card"><dl class="fact-list">'+
  '<div><dt>Non commercial</dt><dd>Marine Normandie Aquarelle</dd></div>'+
  '<div><dt>SIRET</dt><dd>927753780 00018</dd></div>'+
  '<div><dt>Activité</dt><dd>création artistique relevant des arts plastiques, artiste auteur</dd></div>'+
  '<div><dt>Adresse</dt><dd>50700 YVETOT-BOCAGE</dd></div>'+
  '<div><dt>Création</dt><dd>01/04/2024</dd></div>'+
  (DATA.instagram?'<div><dt>Instagram</dt><dd><a href="https://www.instagram.com/'+DATA.instagram+'/" rel="me noopener" target="_blank">Instagram</a></dd></div>':"")+
  '</dl></div></div></section>'+

  '<section class="section wash-band"><div class="container narrow center reveal">'+
  '<h2 class="h2">Carnet d’inspiration</h2>'+
  QUOTE+'<blockquote class="big-quote">…Sons et paysages côtiers nous transportent et nous bercent depuis l’enfance. Loin du tumulte du monde, nous sommes aptes à aimer et chérir ceux qui nous sont les plus chers…</blockquote>'+
  '<blockquote class="big-quote">La nature, le paysage détiennent cette faculté de pouvoir nous apaiser, nous recentrer…</blockquote>'+
  '<blockquote class="big-quote">S’inquiéter n’effacera pas les problèmes de demain, cela ne fera qu’enlever la paix d’aujourd’hui…'+
  '<cite><a href="https://www.atmosphere-citation.com/author/atmo" target="_blank" rel="noopener">atmosphere-citation.com</a></cite></blockquote>'+
  '<div class="poem-card">'+
  '<p>…Alors dans ma mémoire, je cherche les moments où je suis là…</p>'+
  '<span class="poem-gap" aria-hidden="true"></span>'+
  '<p>…Cri des goélands…<br>Ressac de la mer — bruit sourd — sur le sable…<br>“Piû” des gravelots…<br>Marée basse… [pause]…marée basse…</p>'+
  '<span class="poem-gap" aria-hidden="true"></span>'+
  '<p>Parfums d’herbes de dunes…<br>Cri d’enfants au loin, jouant sur la plage…<br>Pieds nus dans le sable…<br>Survol d’oies<br>grève froide…</p>'+
  '<span class="poem-gap" aria-hidden="true"></span>'+
  '<p>Ânes au silence du champ…<br>Peupliers, vent des arbres…<br>Cimes immobiles…</p>'+
  '<span class="poem-gap" aria-hidden="true"></span>'+
  '<p>Odeurs du quai…<br>Portes à flots…<br>Terrasse à la mer…<br>Terrasse tête à tête…</p>'+
  '<span class="poem-gap" aria-hidden="true"></span>'+
  '<p>Nuages, lointain…<br>Percer le mystère, aller plus loin…<br>S’y baigner, le rejoindre…&nbsp;»</p>'+
  '</div></div></section>'+

  '<section class="section section-expos"><div class="container">'+
  '<div class="section-head reveal"><div><p class="label">Événements</p>'+
  '<h2 class="h2">Expositions</h2></div>'+
  '<a class="link-arrow" href="#/evenements">Tous les événements</a></div>'+
  '<ol class="timeline">'+tl+'</ol></div></section>'+

  '<section class="section contact-invitation"><div class="container narrow center reveal">'+
  '<h2 class="h2">Exposition et vente</h2>'+
  '<p class="lead">Aquarelles sur commandes.</p>'+
  '<p class="invitation-cta"><a class="btn" href="#/contact">Contacter l’artiste</a></p></div></section>';
}

function pageGallery(){
  var cats=[];DATA.works.forEach(function(w){if(w.c&&cats.indexOf(w.c)<0)cats.push(w.c);});
  var vifSec=DATA.atelier.length?
    '<section class="section"><div class="container">'+
    '<div class="section-head reveal"><div><p class="label">Sur le vif</p><h2 class="h2">Un carnet de notes de couleurs et de formes</h2></div></div>'+
    '<aside class="vif-def reveal">'+
    '<p>Je compose mes aquarelles à partir de matériaux multiples&nbsp;: observation et croquis sur le vif, photos formant un carnet de notes de couleurs et de formes.</p>'+
    '</aside>'+
    '<p class="atelier-note reveal">Cliquez pour agrandir.</p>'+
    '<div class="atelier-grid" id="atelier-grid" data-cap="Aquarelle sur le vif">'+
    DATA.atelier.map(function(p,i){return '<figure class="atelier-item reveal"><span class="vif-badge" aria-hidden="true">sur le vif</span>'+
      '<button type="button" class="atelier-btn" aria-label="Agrandir l’aquarelle '+(i+1)+' sur '+DATA.atelier.length+'">'+
      '<img loading="lazy" decoding="async" src="'+p.i+'" alt="Aquarelle sur le vif — '+(i+1)+'"></button></figure>';}).join("")+
    '</div></div></section>':"";
  var tall=function(key){var o={};DATA.works.forEach(function(w){var v=w[key];if(v)o[v]=(o[v]||0)+1;});return o;};
  var sj=tall("sj"),am=tall("am"),tc=tall("tc"),ys=tall("y");
  var yk=Object.keys(ys).sort(function(a,b){return a<b?1:-1;});
  var ARR='<svg class="hl-dd-arr" width="10" height="6" viewBox="0 0 10 6" aria-hidden="true"><path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  function dd(g,lab,allLab,keys,t,dots){
    var opts='<button type="button" class="hl-dd-opt is-sel" role="option" aria-selected="true" data-v="" data-l="Tous">'+allLab+'<span class="hl-dd-n">'+DATA.works.length+'</span></button>'+
    keys.map(function(v){return '<button type="button" class="hl-dd-opt" role="option" aria-selected="false" data-v="'+escA(v)+'" data-l="'+escA(v)+'"'+(dots?' data-dot="'+escA(v)+'"':'')+'>'+esc(v)+'<span class="hl-dd-n">'+t[v]+'</span></button>';}).join("");
    return '<div class="hl-dd" data-g="'+g+'"><button type="button" class="hl-dd-btn" aria-expanded="false" aria-haspopup="listbox">'+
    '<span class="hl-dd-lab">'+lab+'</span><span class="hl-dd-val">Tous</span>'+ARR+'</button>'+
    '<div class="hl-dd-menu" role="listbox" aria-label="'+lab+'">'+opts+'</div></div>';}
  var sdd='<div class="hl-dd hl-dd-sort" data-g="sort">'+
    '<button type="button" class="hl-dd-btn" aria-expanded="false" aria-haspopup="listbox">'+
    '<span class="hl-dd-lab">Trier</span><span class="hl-dd-val">Ordre de la galerie</span>'+ARR+'</button>'+
    '<div class="hl-dd-menu" role="listbox" aria-label="Trier les œuvres">'+
    '<button type="button" class="hl-dd-opt is-sel" role="option" aria-selected="true" data-v="gallery" data-l="Ordre de la galerie">Ordre de la galerie</button>'+
    '<button type="button" class="hl-dd-opt" role="option" aria-selected="false" data-v="recent" data-l="Plus récentes">Plus récentes d’abord</button>'+
    '<button type="button" class="hl-dd-opt" role="option" aria-selected="false" data-v="old" data-l="Plus anciennes">Plus anciennes d’abord</button>'+
    '</div></div>';
  var nW=DATA.works.length;
  var bar='<div class="container hl-filters reveal" id="hl-filters">'+
    '<div class="hl-fbar" role="group" aria-label="Filtrer et trier les œuvres">'+
    (Object.keys(sj).length?dd("sujet","Sujet","Tous les sujets",Object.keys(sj),sj,false):"")+
    (Object.keys(am).length?dd("ambiance","Ambiance","Toutes les ambiances",Object.keys(am),am,true):"")+
    (Object.keys(tc).length?dd("technique","Technique","Toutes les techniques",Object.keys(tc),tc,false):"")+
    (yk.length?dd("annee","Année","Toutes les années",yk,ys,false):"")+
    sdd+'</div>'+
    '<div class="hl-fstatus"><p class="hl-fcount" id="gcount" aria-live="polite">'+nW+(nW>1?" œuvres":" œuvre")+'</p>'+
    '<div class="hl-fchips" id="hl-chips"></div>'+
    '<button type="button" class="hl-freset" id="hl-reset" hidden>Réinitialiser</button></div></div>';
  return '<header class="page-head"><div class="container reveal"><p class="label">Galerie</p>'+
  '<h1 class="page-title">La galerie</h1>'+
  '<p class="page-sub">'+esc(DATA.gallerySub)+'</p></div></header>'+
  bar+
  '<section class="section gallery-section"><div class="container">'+
  '<div class="gallery-grid" id="grid">'+DATA.works.map(workCard).join("")+'</div></div></section>'+
  vifSec+
  '<section class="section contact-invitation"><div class="container narrow center reveal">'+
  '<h2 class="h2">Exposition et vente</h2>'+
  '<p class="lead">Aquarelles sur commandes.</p>'+
  '<p class="invitation-cta"><a class="btn" href="#/contact">Contacter l’artiste</a></p></div></section>';
}

function pageWork(slug){
  var idx=-1;DATA.works.forEach(function(w,i){if(w.s===slug)idx=i;});
  if(idx<0)return pageGallery();
  var w=DATA.works[idx];
  var prev=DATA.works[(idx-1+DATA.works.length)%DATA.works.length];
  var next=DATA.works[(idx+1)%DATA.works.length];
  var facts="";
  if(w.c)facts+='<div><dt>Catégorie</dt><dd>'+esc(w.c)+'</dd></div>';
  if(w.tn)facts+='<div><dt>Tonalité</dt><dd>'+esc(w.tn)+'</dd></div>';
  facts+='<div><dt>Technique</dt><dd>Aquarelle sur papier 100&nbsp;% coton</dd></div>';
  if(w.y)facts+='<div><dt>Année</dt><dd>'+esc(w.y)+'</dd></div>';
  if(w.sj)facts+='<div><dt>Sujet</dt><dd>'+esc(w.sj)+'</dd></div>';
  if(w.am)facts+='<div><dt>Ambiance</dt><dd>'+esc(w.am)+'</dd></div>';
  return '<header class="page-head"><div class="container reveal"><p class="label">Aquarelle</p>'+
  '<h1 class="page-title">'+esc(w.t)+'</h1><p class="page-sub">'+esc(meta(w))+'</p></div></header>'+
  '<section class="section"><div class="container work-layout">'+
  '<figure class="work-figure reveal wk-carousel" id="wk-carousel" tabindex="0" role="group" aria-roledescription="carrousel" aria-label="Images de l’œuvre — flèches pour naviguer, cliquer pour agrandir"><div class="wk-track">'+
  '<img class="wk-img" src="'+w.i+'" alt="Aquarelle « '+esc(w.t)+' » d’Hilaire Legentil">'+
  (w.im||[]).map(function(u){return '<img class="wk-img" loading="lazy" src="'+u+'" alt="Aquarelle (vue complémentaire) — '+esc(w.t)+'">';}).join("")+
  '</div>'+
  '<button class="wk-zoom" type="button" aria-label="Agrandir l’image">⤢</button>'+
  ((w.im&&w.im.length)?'<button class="wk-btn wk-prev" type="button" aria-label="Image précédente">‹</button>'+
  '<button class="wk-btn wk-next" type="button" aria-label="Image suivante">›</button>'+
  '<span class="wk-dots" id="wk-dots"></span>':"")+
  '<figcaption class="work-tech">Aquarelle sur papier 100&nbsp;% coton</figcaption></figure>'+
  '<aside class="reveal"><dl class="work-facts">'+facts+'</dl>'+
  (w.d?'<div class="article-body">'+w.d.split("\n").map(function(p){return '<p>'+esc(p)+'</p>';}).join("")+'</div>':"")+
  (ADMIN?'<a class="btn btn-outline btn-full" style="margin-bottom:1rem" href="#/admin">✎ Modifier titre, description…</a>':"")+
  '<a class="btn btn-full" href="#/contact?sujet='+encodeURIComponent("Demande d’information — aquarelle « "+w.t+" »")+'">Demander des informations</a>'+
  '<nav class="work-nav" aria-label="Navigation entre les œuvres">'+
  '<a class="work-nav-link" href="#/oeuvre/'+prev.s+'"><span class="wn-label">Œuvre précédente</span>'+
  '<span class="wn-title">'+esc(prev.t)+'</span></a>'+
  '<a class="work-nav-link is-next" href="#/oeuvre/'+next.s+'"><span class="wn-label">Œuvre suivante</span>'+
  '<span class="wn-title">'+esc(next.t)+'</span></a></nav>'+
  '<p class="work-counter">'+(idx+1)+' / '+DATA.works.length+' — <a class="lnk" href="#/galerie">retour à la galerie</a></p></aside>'+
  '</div></section>'+
  '<section class="section next-teaser"><div class="container teaser-inner">'+
  '<div class="reveal"><p class="label">Œuvre suivante</p><h2 class="h3">'+esc(next.t)+'</h2>'+
  '<a class="link-arrow" href="#/oeuvre/'+next.s+'">Voir l’œuvre suivante</a></div>'+
  '<a class="teaser-figure reveal" href="#/oeuvre/'+next.s+'"><img loading="lazy" src="'+next.i+'" alt=""></a>'+
  '</div></section>';
}

function pageNews(){
  var today=new Date().toISOString().slice(0,10);
  var up=DATA.news.filter(function(n){return (n.rd||"")>=today;})
    .sort(function(a,b){return (a.rd||"")<(b.rd||"")?-1:1;});
  var past=DATA.news.filter(function(n){return (n.rd||"")<today;})
    .sort(function(a,b){return (a.rd||"")>(b.rd||"")?-1:1;});
  var html="";
  if(up.length)html+='<p class="label evt-label reveal">À venir</p>'+
    '<div class="news-rows">'+up.map(function(n){return newsRow(n,true,true);}).join("")+'</div>';
  if(past.length)html+=(up.length?
    '<div class="evt-divider reveal" role="separator"><span>Événements passés</span></div>':
    '<p class="label evt-label reveal">Événements passés</p>')+
    '<div class="news-rows">'+past.map(function(n){return newsRow(n,true,false);}).join("")+'</div>';
  return '<header class="page-head"><div class="container reveal"><p class="label">Événements</p>'+
  '<h1 class="page-title">Événements &amp; expositions</h1>'+
  '<p class="page-sub">'+esc(DATA.eventsSub)+'</p></div></header>'+
  (ADMIN?'<section class="section" style="padding:0 0 1rem"><div class="container adm-bar">'+
  '<a class="btn" href="#/admin">+ Ajouter un événement</a></div></section>':"")+
  '<section class="section"><div class="container">'+
  (html||'<p class="muted">Aucune actualité pour le moment. Les expositions seront annoncées ici.</p>')+
  '</div></section>'+
  '<section class="section contact-invitation"><div class="container narrow center reveal">'+
  '<h2 class="h2">Exposition et vente</h2>'+
  '<p class="lead">Aquarelles sur commandes.</p>'+
  '<p class="invitation-cta"><a class="btn" href="#/contact">Contacter l’artiste</a></p></div></section>';
}

function pageNewsItem(slug){
  var n=null;DATA.news.forEach(function(x){if(x.s===slug)n=x;});
  if(!n)return pageNews();
  var others=DATA.news.filter(function(x){return x.s!==slug;}).slice(0,3);
  return '<header class="page-head"><div class="container reveal">'+
  '<p class="label">'+(n.dt?esc(n.dt)+(n.tm?" — "+esc(n.tm):"")+(n.pl?" — "+esc(n.pl):""):"Événement")+'</p><h1 class="page-title">'+esc(n.t)+'</h1></div></header>'+
  '<article class="section"><div class="container article">'+
  (n.cov?'<figure class="article-cover reveal"><img src="'+n.cov+'" alt="'+esc(n.t)+'"></figure>':"")+
  '<div class="article-body reveal">'+n.p.map(function(p){return '<p>'+esc(p)+'</p>';}).join("")+'</div>'+
  (n.img.length?'<div class="article-gallery reveal">'+n.img.map(function(u,i){
    return '<img loading="lazy" src="'+u+'" alt="'+esc(n.t)+' — image '+(i+1)+'">';}).join("")+'</div>':"")+
  (n.l?'<p><a class="link-arrow" href="'+esc(n.l)+'" rel="noopener" target="_blank">En savoir plus ↗</a></p>':"")+
  '<div class="article-footer"><a class="lnk" href="#/evenements">← Tous les événements</a></div>'+
  '</div></article>'+
  (others.length?'<section class="section" style="padding-top:0"><div class="container">'+
  '<p class="label reveal">À lire également</p><div class="news-rows">'+
  others.map(function(n2){return newsRow(n2,false);}).join("")+'</div></div></section>':"");
}

function pageContact(q){
  var sujet=(q&&q.sujet)||"";
  return '<header class="page-head"><div class="container reveal"><p class="label">Contacts</p>'+
  '<h1 class="page-title">Contacts</h1><p class="page-sub">'+esc(DATA.contactSub)+'</p></div></header>'+
  '<section class="section"><div class="container contact-layout">'+
  '<div class="reveal"><div id="form-ok" hidden class="form-success" role="status">'+
  '<p style="font-family:var(--serif);font-size:1.3rem;color:var(--ink);margin:0 0 .3rem">Votre message est prêt.</p>'+
  '<p>Votre logiciel de messagerie s’est ouvert avec le message pré-rempli&nbsp;; il ne reste qu’à cliquer sur «&nbsp;Envoyer&nbsp;».</p></div>'+
  '<form id="contact-form" class="contact-form" novalidate>'+
  '<div class="field"><label for="f-name">Nom / prénom <span class="req">*</span></label>'+
  '<input id="f-name" type="text" required maxlength="120" autocomplete="name"></div>'+
  '<div class="field-row"><div class="field"><label for="f-email">Votre adresse e-mail <span class="req">*</span></label>'+
  '<input id="f-email" type="email" required maxlength="160" autocomplete="email"></div>'+
  '<div class="field"><label for="f-phone">Téléphone <span class="opt">(facultatif)</span></label>'+
  '<input id="f-phone" type="tel" maxlength="40" autocomplete="tel"></div></div>'+
  '<div class="field"><label for="f-cat">Votre demande concerne</label><select id="f-cat">'+
  '<option>Une information sur une œuvre</option><option>Une demande spécifique</option>'+
  '<option>Une commande</option><option>Une exposition</option><option>Autre chose</option></select></div>'+
  '<div class="field"><label for="f-subject">Objet <span class="req">*</span></label>'+
  '<input id="f-subject" type="text" required maxlength="160" value="'+esc(sujet)+'"></div>'+
  '<div class="field"><label for="f-message">Message <span class="req">*</span></label>'+
  '<textarea id="f-message" required maxlength="4000" rows="6"></textarea></div>'+
  '<button class="btn btn-full" type="submit">Préparer le message</button>'+
  '<p class="form-note">Ce fichier fonctionne sans serveur&nbsp;: le bouton ouvre votre messagerie avec le message pré-rempli, à destination d’Hilaire.</p>'+
  '</form></div>'+
  '<aside class="contact-aside reveal">'+
  '<div class="contact-card"><h2 class="h3">Contacts</h2><ul class="contact-list">'+
  '<li><span>Téléphone</span><a class="lnk" href="tel:'+DATA.phone.replace(/\s/g,"")+'">'+esc(DATA.phone)+'</a></li>'+
  '<li><span>E-mail</span><a class="lnk" href="mailto:'+DATA.email+'">'+esc(DATA.email)+'</a></li>'+
  '<li><span>Instagram</span><a class="lnk" href="https://www.instagram.com/'+DATA.instagram+'/" rel="me noopener" target="_blank">'+esc(DATA.instagram)+'</a></li>'+
  '<li><span>Atelier</span><span>Yvetot-Bocage · Manche · Normandie</span></li></ul></div>'+
  '<div class="contact-card"><h2 class="h3">Demande spécifique</h2>'+
  '<p class="small">Aquarelles sur commandes.</p></div>'+
  '</aside></div></section>'+
  '<section class="section map-section tint-sky"><div class="container">'+
  '<div class="section-head reveal"><div><p class="label">La région</p>'+
  '<h2 class="h2">Pour un court séjour dans le Cotentin</h2></div></div>'+
  '<p class="map-note reveal">Yvetot-Bocage (Manche). La zone entourée ci-dessous correspond à un rayon d’environ 75&nbsp;km.</p>'+
  '<div class="map-wrap reveal"><div id="map" hidden role="application" aria-label="Carte : zone d’environ 75 kilomètres autour d’Yvetot-Bocage en Normandie"></div>'+
  '<div id="map-consent" class="map-consent" hidden><div class="map-consent-inner">'+
  '<p class="label">Carte interactive</p>'+
  '<p>La carte est servie par OpenStreetMap, un service tiers susceptible de déposer des cookies. Elle ne se charge qu’avec votre accord.</p>'+
  '<p><button class="btn" id="map-load" type="button">Charger la carte</button></p>'+
  '</div></div>'+
  '<p class="map-credit">Carte © les contributeurs d’<a href="https://www.openstreetmap.org/copyright" rel="noopener" target="_blank">OpenStreetMap</a> — tuiles chargées en ligne si une connexion est disponible.</p></div>'+
  '</div></section>';
}

/* ------------------------------------------------------- routeur ------- */
var main=document.getElementById("contenu");
function parseHash(){
  var h=location.hash.replace(/^#\/?/,""),parts=h.split("?"),q={};
  if(parts[1])parts[1].split("&").forEach(function(kv){
    var p=kv.split("=");q[decodeURIComponent(p[0])]=decodeURIComponent(p[1]||"");});
  return {route:parts[0]||"accueil",q:q};
}
function pageAtelier(){
  var g=DATA.photos.map(function(p,i){
    return '<figure class="atelier-item reveal">'+
    '<button type="button" class="atelier-btn" aria-label="Agrandir la photo '+(i+1)+' sur '+DATA.photos.length+'">'+
    '<img loading="lazy" decoding="async" src="'+p.i+'" alt="L\u2019atelier d\u2019Hilaire Legentil — photo '+(i+1)+'"></button></figure>';
  }).join("");
  if(!g)g='<p class="muted">Les photos arriveront prochainement.</p>';
  return '<header class="page-head"><div class="container reveal"><p class="label">L\u2019atelier</p>'+
    '<h1 class="page-title">Cahier technique</h1>'+
    '<p class="page-sub">'+esc(DATA.atelierSub)+'</p></div></header>'+
    
    '<section class="section tint-sky"><div class="container">'+
    '<div class="section-head reveal"><div><p class="label">Cahier technique</p>'+
    '<h2 class="h2">Les étapes d’une aquarelle</h2></div></div>'+
    '<p class="lead reveal">L’aquarelle est très exigeante et ne s’improvise pas. La technique est un prérequis indispensable pour libérer le geste et s’exprimer.</p>'+
    '<h3 class="h3 reveal">Avant de commencer</h3>'+
    '<div class="rel-grid">'+
    '<div class="tech-card reveal"><h4>Composition / dessin&nbsp;:</h4><ul class="tech-list">'+
    '<li>Point de focal fixé avant de peindre</li>'+
    '<li>2 narrations, 2 niveaux de lecture&nbsp;: 1 paysage et 2 les personnages</li>'+
    '<li>Dynamique de la composition</li><li>Choisir un format</li>'+
    '<li>Déplacer le cadre sur le sujet</li>'+
    '<li>Respecter le dessin (proportions, horizontales, verticales et point de fuite)</li></ul></div>'+
    '<div class="tech-card reveal"><h4>Couleurs&nbsp;:</h4><ul class="tech-list">'+
    '<li>Contraste couleurs chaudes et froides</li><li>Harmonie colorée</li>'+
    '<li>Le choix des couleurs doit traduire l’émotion éprouvée face au sujet</li>'+
    '<li>Préparer les couleurs avant de peindre (faire de la place sur sa palette)</li>'+
    '<li>Pigments (granuleux, lisses, crémeux..)</li></ul></div>'+
    '<div class="tech-card reveal"><h4>Valeurs&nbsp;:</h4><ul class="tech-list">'+
    '<li>Contraste des valeur équilibré</li><li>Réserver blancs</li>'+
    '<li>Zones laissées claires</li><li>Drawing gum</li></ul></div>'+
    '</div>'+
    '<h3 class="h3 reveal" style="margin-top:2.4rem">Durant l’exécution</h3>'+
    '<div class="rel-grid">'+
    '<div class="tech-card reveal"><h4>Lavis&nbsp;:</h4><ul class="tech-list">'+
    '<li>Liaison des premiers lavis</li><li>Pureté des lavis durant l’exécution</li>'+
    '<li>Laisser les imperfections, jouer avec, les utiliser a bon escient</li>'+
    '<li>Éclaircir les lavis pour la profondeur (plus légers et plus bleus pour les lointains)</li></ul></div>'+
    '<div class="tech-card reveal"><h4>Différentes techniques de pinceaux.</h4>'+
    '<p style="font-size:.93rem;color:var(--muted);margin:0 0 .8rem">Varier les techniques et les effets dynamise la composition et contribue à la qualité visuelle&nbsp;:</p>'+
    '<ul class="chip-list">'+
    '<li class="chip">Gros Pinceau lavis petit gris</li><li class="chip">Pinceau synthétique détail</li>'+
    '<li class="chip">Humide sur humide</li><li class="chip">Humide sur sec</li>'+
    '<li class="chip">Moucheté</li><li class="chip">Pinceau sec</li>'+
    '<li class="chip">Rouler le pinceaux</li><li class="chip">Pinceau écrasé en touches verticales</li>'+
    '<li class="chip">Filé Pinceau fin</li><li class="chip">Pinceau éventail</li>'+
    '<li class="chip">Retraits</li><li class="chip">Incliner la toile pour déplacer les pigments</li>'+
    '<li class="chip">Coulures</li><li class="chip">Auréoles</li><li class="chip">Vaporisateur</li>'+
    '</ul></div>'+
    '<div class="tech-card reveal"><h4>Ajuster&nbsp;:</h4><ul class="tech-list">'+
    '<li>Vérifier la carte des formes de près et de loin (ajuster la peinture)</li>'+
    '<li>Placer les détails à la fin en fonction du chemin visuel</li>'+
    '<li>Glacis pour rehausser le contraste chaud / froid</li></ul></div>'+
    '</div></div></section>'+

    '<section class="section"><div class="container narrow reveal">'+
    '<p class="label">Cahier technique</p>'+
    '<h2 class="h2">Des aquarelles montées sur châssis</h2>'+
    '<p>Traditionnellement, les aquarelles sont protégées par un sous verre et un cadre.</p>'+
    '<p>Certaines aquarelles au sein de cette exposition ont été réalisées différemment&nbsp;: le papier est tendu sur un châssis et la peinture est protégée avec un vernis mat. Ce mode de réalisation supprime les reflets du verre et préserve ainsi la clarté des couleurs.</p>'+
    '<h3 class="h3">Montage du papier&nbsp;:</h3>'+
    '<p>Après plusieurs minutes dans l’eau, le papier est agrafé sur le châssis. En séchant, il se rétracte. Tendu comme un tambour, il ne gondolera pas durant l’exécution de l’aquarelle.</p>'+
    '<p>Le papier sur châssis est aussi un choix de l’artiste&nbsp;: un papier coton frangé monté sur du bois confère à l’aquarelle une qualité esthétique d\'"objet artisanal".</p>'+
    '</div></section>'+

    '<section class="section tint-sand"><div class="container">'+
    '<div class="section-head reveal"><div><p class="label">Des aquarelles "locales"&nbsp;!</p>'+
    '<h2 class="h2">Fabrication des cadres</h2></div></div>'+
    '<p class="lead reveal">Les châssis en bois sont confectionnés dans la Manche par le peintre avec du bois issus de forêts (européennes) durables.</p>'+
    '<div class="fact-card reveal" style="max-width:44em"><ul class="tech-list">'+
    '<li>La peinture utilisée est fabriquée en France.</li>'+
    '<li>Le papier 100&nbsp;% coton est fabriqué en Italie</li>'+
    '<li>Le fixatif pour aquarelle est fabriqué en Allemagne et le vernis final est fabriqué en Italie.</li></ul></div>'+
    '<div class="step-grid">'+
    '<div class="step-card reveal"><p class="step-num">01</p><p>À l’aide de baguettes «&nbsp;quart de rond&nbsp;», d’une boîte à onglets, d’une scie et de colle à bois, je réalise un cadre bois.</p></div>'+
    '<div class="step-card reveal"><p class="step-num">02</p><p>La feuille de papier en coton découpée à la dimension, est trempée dans l’eau pendant 4 minutes.</p></div>'+
    '<div class="step-card reveal"><p class="step-num">03</p><p>Excédent d’eau de la feuille enlevé en l’accrochant 10 minutes sur un fil à linge.</p></div>'+
    '<div class="step-card reveal"><p class="step-num">04</p><p>Feuille positionnée, tendue puis agrafée sur le cadre.</p></div>'+
    '<div class="step-card reveal"><p class="step-num">05</p><p>Après séchage 1 heure. Le papier sec est tendu sur le châssis. L’aquarelle réalisée, un premier spray pour fixer les pigments suivi d’un vernis mat protègent l’aquarelle de l’humidité.</p></div>'+
    '<div class="step-card reveal"><p class="step-num">06</p><p>Le cadre peint et verni pour être encadré.</p></div>'+
    '</div>'+
    '<p class="tech-note reveal">Attention cette protection préserve l’œuvre de quelques gouttes d’eau voire de postillons&nbsp;! Le papier restera vulnérable aux coups et au détrempage.</p>'+
    '<blockquote class="big-quote reveal" style="margin-top:2.6rem">L’aquarelle est un fabuleux moyen d’évasion. Alors, à vos outils&nbsp;! À vos pinceaux&nbsp;!</blockquote>'+
    '</div></section>'+

    '<section class="section"><div class="container">'+
    '<div class="section-head reveal"><div><h2 class="h2">L\u2019atelier</h2></div></div>'+
    
'<p class="atelier-note reveal">Cliquez pour agrandir.</p>'+
    '<div class="atelier-grid'+(DATA.photos.length===1?" atelier-one":"")+'" id="atelier-grid" data-cap="L\u2019atelier">'+g+'</div>'+
    '</div></section>'+
    '<section class="section wash-band"><div class="container narrow center reveal">'+
    '<h2 class="h2">Exposition et vente</h2>'+
    '<p class="lead">Aquarelles sur commandes.</p>'+
    '<p class="invitation-cta"><a class="btn" href="#/galerie">Découvrir les aquarelles</a></p>'+
    '</div></section>';
}
function initCarousels(){
  var car=document.getElementById("wk-carousel");
  if(car){var track=car.querySelector(".wk-track"),imgs=track?[].slice.call(track.children):[];
    var prev=car.querySelector(".wk-prev"),next=car.querySelector(".wk-next"),
    dots=car.querySelector(".wk-dots"),i=0;
    function show(k){i=(k+imgs.length)%imgs.length;
      track.style.transform="translateX(-"+i*100+"%)";
      if(dots)[].forEach.call(dots.children,function(d,n){d.className=n===i?"on":"";});}
    if(imgs.length>1){
      if(dots)imgs.forEach(function(im,k){var d=document.createElement("button");
        d.type="button";d.className="wk-dot"+(k?"":" on");
        d.setAttribute("aria-label","Voir l\u2019image "+(k+1));
        var s=(im.querySelector&&im.querySelector("img"))||((im.tagName==="IMG")?im:null);
        if(s)d.style.backgroundImage="url('"+(s.currentSrc||s.src)+"')";
        d.onclick=function(){show(k);};dots.appendChild(d);});
      if(prev)prev.onclick=function(){show(i-1);};
      if(next)next.onclick=function(){show(i+1);};
      var x0=null;
      car.addEventListener("touchstart",function(e){x0=e.touches[0].clientX;},{passive:true});
      car.addEventListener("touchend",function(e){if(x0===null)return;
        var dx=e.changedTouches[0].clientX-x0;
        if(Math.abs(dx)>40)show(dx<0?i+1:i-1);x0=null;});}
    car.addEventListener("keydown",function(e){if(!lb.hidden)return;
      if(e.key==="ArrowLeft"){show(i-1);e.preventDefault();}
      else if(e.key==="ArrowRight"){show(i+1);e.preventDefault();}});
    var old=document.querySelector(".wk-lightbox");
    if(old&&old.parentNode)old.parentNode.removeChild(old);
    var lb=document.createElement("div");lb.className="wk-lightbox";lb.hidden=true;
    lb.setAttribute("role","dialog");lb.setAttribute("aria-modal","true");
    lb.setAttribute("aria-label","Image agrandie");
    lb.innerHTML='<figure><img alt=""></figure>'+
      '<button type="button" class="hl-lb-btn hl-lb-prev" aria-label="Image précédente">\u2039</button>'+
      '<button type="button" class="hl-lb-btn hl-lb-next" aria-label="Image suivante">\u203A</button>'+
      '<button type="button" class="hl-lb-close" aria-label="Fermer">\u2715</button>';
    document.body.appendChild(lb);
    if(imgs.length<2)lb.classList.add("hl-lb-single");
    window.__wkLb=lb;
    var zimg=lb.querySelector("img"),zprev=lb.querySelector(".hl-lb-prev"),
        znext=lb.querySelector(".hl-lb-next"),zclose=lb.querySelector(".hl-lb-close");
    function zshow(k){show(k);var im=imgs[i];
      if(im){var s=(im.querySelector&&im.querySelector("img"))||((im.tagName==="IMG")?im:null);
        if(s){zimg.src=s.currentSrc||s.src;zimg.alt=s.alt;}}
      lb.hidden=false;document.documentElement.style.overflow="hidden";zclose.focus();}
    function zhide(){lb.hidden=true;document.documentElement.style.overflow="";}
    var zb=car.querySelector(".wk-zoom");
    if(zb)zb.onclick=function(){zshow(i);};
    if(track)track.onclick=function(){zshow(i);};
    zprev.onclick=function(){zshow(i-1);};
    znext.onclick=function(){zshow(i+1);};
    zclose.onclick=zhide;
    lb.onclick=function(e){if(e.target===lb)zhide();};
    if(!window.__wkLbKeys){window.__wkLbKeys=true;
      document.addEventListener("keydown",function(e){var L=window.__wkLb;if(!L||L.hidden)return;
        if(e.key==="Escape"){L.querySelector(".hl-lb-close").click();}
        else if(e.key==="ArrowLeft"){L.querySelector(".hl-lb-prev").click();}
        else if(e.key==="ArrowRight"){L.querySelector(".hl-lb-next").click();}});}}
  var hc=document.getElementById("hc-carousel");
  if(hc){var hci=[].slice.call(hc.querySelectorAll(".hc-img")),
    hp=hc.querySelector(".wk-prev"),hn=hc.querySelector(".wk-next"),
    hd=hc.querySelector(".wk-dots"),hi=0,ht=null,hhover=false;
  function hshow(k){hi=(k+hci.length)%hci.length;
    hci.forEach(function(im,n){im.className="hc-img"+(n===hi?" on":"");});
    if(hd)[].forEach.call(hd.children,function(d,n){d.className="wk-dot"+(n===hi?" on":"");});}
  if(hd)hci.forEach(function(im,k){var d=document.createElement("button");d.type="button";
    d.className="wk-dot"+(k?"":" on");d.setAttribute("aria-label","Voir l\u2019image "+(k+1));
    if(im.tagName==="IMG")d.style.backgroundImage="url('"+(im.currentSrc||im.src)+"')";
    d.onclick=function(){hshow(k);hrestart();};hd.appendChild(d);});
  if(hp)hp.onclick=function(){hshow(hi-1);hrestart();};
  if(hn)hn.onclick=function(){hshow(hi+1);hrestart();};
  var hx0=null;
  hc.addEventListener("touchstart",function(e){hx0=e.touches[0].clientX;},{passive:true});
  hc.addEventListener("touchend",function(e){if(hx0===null)return;
    var dx=e.changedTouches[0].clientX-hx0;
    if(Math.abs(dx)>40)hshow(dx<0?hi+1:hi-1);hx0=null;hrestart();});
  function htick(){if(!hhover)hshow(hi+1);}
  function hrestart(){if(ht)clearInterval(ht);ht=setInterval(htick,5500);}
  hc.addEventListener("mouseenter",function(){hhover=true;});
  hc.addEventListener("mouseleave",function(){hhover=false;});
  hc.addEventListener("focusin",function(){hhover=true;});
  hc.addEventListener("focusout",function(){hhover=false;});
  hrestart();}
  var row=document.getElementById("flip-row");
  if(row){var bp=document.getElementById("flip-prev"),bn=document.getElementById("flip-next");
    function step(){return Math.max(240,row.clientWidth*.8);}
    if(bp)bp.onclick=function(){row.scrollBy({left:-step(),behavior:"smooth"});};
    if(bn)bn.onclick=function(){row.scrollBy({left:step(),behavior:"smooth"});};}}
function initAtelier(){
  document.documentElement.style.overflow="";
  var old=document.querySelector(".hl-lightbox");
  if(old&&old.parentNode)old.parentNode.removeChild(old);
  var grid=document.getElementById("atelier-grid");if(!grid)return;
  var btns=[].slice.call(grid.querySelectorAll(".atelier-btn"));if(!btns.length)return;
  var idx=0;
  var lb=document.createElement("div");lb.className="hl-lightbox";lb.hidden=true;
  lb.setAttribute("role","dialog");lb.setAttribute("aria-modal","true");lb.setAttribute("aria-label","Photo agrandie");
  lb.innerHTML='<figure><img alt=""><figcaption></figcaption></figure>'+
    '<button type="button" class="hl-lb-btn hl-lb-prev" aria-label="Photo précédente">‹</button>'+
    '<button type="button" class="hl-lb-btn hl-lb-next" aria-label="Photo suivante">›</button>'+
    '<button type="button" class="hl-lb-close" aria-label="Fermer">✕</button>';
  document.body.appendChild(lb);window.__hlLb=lb;
  if(btns.length===1)lb.classList.add("hl-lb-single");
  var img=lb.querySelector("img"),cap=lb.querySelector("figcaption");
  var prev=lb.querySelector(".hl-lb-prev"),next=lb.querySelector(".hl-lb-next");
  var closer=lb.querySelector(".hl-lb-close");
  function show(i){idx=(i+btns.length)%btns.length;var b=btns[idx],t=b.querySelector("img");
    img.src=b.getAttribute("data-full")||t.src;img.alt=t.alt;
    cap.textContent=(grid.getAttribute("data-cap")||"Atelier")+" — "+(idx+1)+" / "+btns.length;
    lb.hidden=false;document.documentElement.style.overflow="hidden";closer.focus();}
  function close(){lb.hidden=true;document.documentElement.style.overflow="";
    if(btns[idx])btns[idx].focus();}
  btns.forEach(function(b,i){b.addEventListener("click",function(){show(i);});});
  prev.addEventListener("click",function(){show(idx-1);});
  next.addEventListener("click",function(){show(idx+1);});
  closer.addEventListener("click",close);
  lb.addEventListener("click",function(e){if(e.target===lb)close();});
  if(!window.__hlLbKeys){window.__hlLbKeys=true;
    document.addEventListener("keydown",function(e){var L=window.__hlLb;if(!L||L.hidden)return;
      if(e.key==="Escape"){L.querySelector(".hl-lb-close").click();}
      else if(e.key==="ArrowLeft"){L.querySelector(".hl-lb-prev").click();}
      else if(e.key==="ArrowRight"){L.querySelector(".hl-lb-next").click();}});}
}
function render(){
  var r=parseHash(),html,route=r.route,root=route.split("/")[0];
  if(route.indexOf("oeuvre/")===0)html=pageWork(route.slice(7));
  else if(route.indexOf("evenement/")===0)html=pageNewsItem(route.slice(10));
  else if(route.indexOf("actualite/")===0)html=pageNewsItem(route.slice(10));
  else if(route==="artiste")html=pageArtist();
  else if(route==="atelier")html=pageAtelier();
  else if(route==="galerie"||route==="aquarelles")html=pageGallery();
  else if(route==="evenements"||route==="actualites")html=pageNews();
  else if(route==="contact")html=pageContact(r.q);
  else if(route==="confidentialite")html=pageLegal();
  else if(route==="admin")html=ADMIN?pageAdmin():pageAdminGate();
  else {route="accueil";html=pageHome();}
  main.innerHTML='<div class="fade-in">'+html+"</div>";
  document.querySelectorAll(".site-nav a").forEach(function(a){
    a.classList.toggle("on",a.getAttribute("data-r")===root||
      (root.indexOf("oeuvre")===0&&a.getAttribute("data-r")==="aquarelles")||
      (root.indexOf("actualite")===0&&a.getAttribute("data-r")==="actualites"));});
  var PG={accueil:"home",artiste:"artist",aquarelles:"gallery",galerie:"gallery",oeuvre:"work",
    actualites:"news_list",evenements:"news_list",actualite:"news_item",evenement:"news_item",
    contact:"contact",atelier:"atelier"};
  document.body.className="pg-"+(PG[root]||root);
  document.title=route==="accueil"?
    "Hilaire Legentil — Artiste auteur · Aquarelles — mer & paysage":
    route==="artiste"?"La démarche de l’artiste — Hilaire Legentil":
    document.querySelector("h1")?document.querySelector("h1").textContent+
    " — Hilaire Legentil":"Hilaire Legentil";
  window.scrollTo(0,0);
  initReveal();initGallery();initContact();initMap();initAdmin();makeEditable();initAtelier();initCarousels();initNotify();
  var rs=document.getElementById("ck-reset");
  if(rs)rs.onclick=function(){try{localStorage.removeItem("hl_consent");}catch(e){}
    location.hash="#/accueil";location.reload();};
  closeNav();
}
window.addEventListener("hashchange",render);

/* ----------------------------------------------- interactions ---------- */
function initReveal(){
  var els=document.querySelectorAll(".reveal");
  if("IntersectionObserver" in window){
    var io=new IntersectionObserver(function(entries){
      entries.forEach(function(en){if(en.isIntersecting){
        en.target.classList.add("vis");io.unobserve(en.target);}});},
      {threshold:.12,rootMargin:"0px 0px -4% 0px"});
    els.forEach(function(el){io.observe(el);});
  } else els.forEach(function(el){el.classList.add("vis");});
}
function initGallery(){
  var root=document.getElementById("hl-filters"),grid=document.getElementById("grid");
  if(!root||!grid)return;
  var items=[].slice.call(grid.querySelectorAll(".work"));
  items.forEach(function(it,i){it.setAttribute("data-idx",""+i);});
  var countEl=document.getElementById("gcount"),chipsEl=document.getElementById("hl-chips"),
      resetBtn=document.getElementById("hl-reset");
  var ATTR={sujet:"data-sujet",ambiance:"data-amb",technique:"data-tech",annee:"data-year"};
  var LABELS={sujet:"Sujet",ambiance:"Ambiance",technique:"Technique",annee:"Année"};
  var GROUPS=["sujet","ambiance","technique","annee"];
  var state={sujet:"",ambiance:"",technique:"",annee:"",sort:"gallery"};
  var dds=[];
  function closeAll(){dds.forEach(function(dd){dd.classList.remove("is-open");
    var b=dd.querySelector(".hl-dd-btn");if(b)b.setAttribute("aria-expanded","false");});}
  [].forEach.call(root.querySelectorAll(".hl-dd"),function(dd){
    var btn=dd.querySelector(".hl-dd-btn"),menu=dd.querySelector(".hl-dd-menu");
    if(!btn||!menu)return;dds.push(dd);
    btn.addEventListener("click",function(){var open=dd.classList.contains("is-open");closeAll();
      if(!open){dd.classList.add("is-open");btn.setAttribute("aria-expanded","true");}});
    menu.addEventListener("click",function(e){var opt=e.target.closest(".hl-dd-opt");if(!opt)return;
      select(dd.getAttribute("data-g"),opt.getAttribute("data-v"));closeAll();btn.focus();});
    menu.addEventListener("keydown",function(e){var opts=[].slice.call(menu.querySelectorAll(".hl-dd-opt"));
      if(e.key==="Escape"){e.preventDefault();closeAll();btn.focus();}
      else if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();
        var i=opts.indexOf(document.activeElement);
        var n=e.key==="ArrowDown"?(i<0?0:Math.min(i+1,opts.length-1)):(i<0?opts.length-1:Math.max(i-1,0));
        if(opts[n])opts[n].focus();}
      else if(e.key==="Home"){e.preventDefault();if(opts[0])opts[0].focus();}
      else if(e.key==="End"){e.preventDefault();if(opts.length)opts[opts.length-1].focus();}});
    dd.addEventListener("focusout",function(e){if(!dd.contains(e.relatedTarget)){
      dd.classList.remove("is-open");btn.setAttribute("aria-expanded","false");}});
  });
  window.__hlCloseAll=closeAll;window.__hlFilters=root;
  if(!initGallery._doc){initGallery._doc=true;
    document.addEventListener("click",function(e){
      if(!window.__hlFilters||!document.body.contains(window.__hlFilters))return;
      if(!window.__hlFilters.contains(e.target)&&window.__hlCloseAll)window.__hlCloseAll();});
    document.addEventListener("keydown",function(e){
      if(e.key==="Escape"&&window.__hlCloseAll)window.__hlCloseAll();});}
  function select(g,v){if(g==="sort")state.sort=v||"gallery";else state[g]=v||"";
    syncDD(g);apply();}
  function syncDD(g){var dd=root.querySelector('.hl-dd[data-g="'+g+'"]');if(!dd)return;
    var val=g==="sort"?state.sort:(state[g]||"");var chosen=null;
    [].forEach.call(dd.querySelectorAll(".hl-dd-opt"),function(o){var sel=o.getAttribute("data-v")===val;
      o.classList.toggle("is-sel",sel);o.setAttribute("aria-selected",sel?"true":"false");if(sel)chosen=o;});
    var lab=dd.querySelector(".hl-dd-val");if(lab&&chosen)lab.textContent=chosen.getAttribute("data-l")||chosen.textContent;
    dd.classList.toggle("is-set",g!=="sort"&&!!state[g]);}
  function yearOf(it){return parseInt(it.getAttribute("data-year"),10)||0;}
  function apply(){var visible=items.filter(function(it){
      for(var i=0;i<GROUPS.length;i++){var g=GROUPS[i];
        if(state[g]&&(it.getAttribute(ATTR[g])||"").trim()!==state[g])return false;}
      return true;});
    visible.sort(function(a,b){var ia=+a.getAttribute("data-idx"),ib=+b.getAttribute("data-idx");
      if(state.sort==="recent")return (yearOf(b)-yearOf(a))||(ib-ia);
      if(state.sort==="old")return (yearOf(a)-yearOf(b))||(ia-ib);
      return ia-ib;});
    items.forEach(function(it){it.classList.remove("hl-in");
      it.style.display=visible.indexOf(it)<0?"none":"";});
    void grid.offsetWidth;
    visible.forEach(function(it){grid.appendChild(it);it.classList.add("hl-in");});
    var n=visible.length;
    if(countEl){countEl.textContent=n===0?"Aucune aquarelle ne correspond à cette combinaison de filtres.":n+(n>1?" œuvres":" œuvre");
      countEl.classList.toggle("is-empty",n===0);}
    if(chipsEl)chipsEl.innerHTML=GROUPS.filter(function(g){return state[g];}).map(function(g){
      return '<button type="button" class="hl-fchip" data-g="'+g+'" aria-label="Retirer le filtre '+escA(LABELS[g]+" : "+state[g])+'">'+
        esc(LABELS[g])+'&nbsp;: '+esc(state[g])+'<span class="hl-fx" aria-hidden="true">×</span></button>';}).join("");
    var active=GROUPS.some(function(g){return state[g];});
    if(resetBtn)resetBtn.hidden=!active;
    root.classList.toggle("is-filtered",active);}
  if(chipsEl)chipsEl.addEventListener("click",function(e){var chip=e.target.closest(".hl-fchip");
    if(!chip)return;select(chip.getAttribute("data-g"),"");});
  if(resetBtn)resetBtn.addEventListener("click",function(){
    GROUPS.forEach(function(g){state[g]="";syncDD(g);});apply();resetBtn.focus();});
  apply();
}
function initNotify(){
  var slugs=DATA.works.map(function(w){return w.s;});
  if(!slugs.length)return;
  function lsG(k){try{return localStorage.getItem(k);}catch(e){return null;}}
  function lsS(k,v){try{localStorage.setItem(k,v);}catch(e){}}
  function ssG(k){try{return sessionStorage.getItem(k);}catch(e){return null;}}
  function ssS(k,v){try{sessionStorage.setItem(k,v);}catch(e){}}
  function seenArr(){try{var v=JSON.parse(lsG("hlSeen")||"null");
    return Object.prototype.toString.call(v)==="[object Array]"?v:null;}catch(e){return null;}}
  var grid=document.getElementById("grid");
  var seen=seenArr();
  var fresh=seen?slugs.filter(function(s){return seen.indexOf(s)<0;}):[];
  if(grid){
    [].forEach.call(grid.querySelectorAll(".work"),function(card){
      var m=(/#\/oeuvre\/([^/?#]+)/.exec(card.getAttribute("href")||"")||[])[1];
      if(m&&fresh.indexOf(decodeURIComponent(m))>=0){
        var b=document.createElement("span");b.className="hl-new-badge";
        b.textContent="Nouvelle aquarelle";card.insertBefore(b,card.firstChild);}});
    lsS("hlSeen",JSON.stringify(slugs));
    var toast=document.querySelector(".hl-toast");
    if(toast&&toast.parentNode)toast.parentNode.removeChild(toast);
    return;}
  if(initNotify._done)return;initNotify._done=true;
  if(!seen){lsS("hlSeen",JSON.stringify(slugs));return;}
  if(!fresh.length||ssG("hlToastDone")==="1")return;
  ssS("hlToastDone","1");
  var t=document.createElement("div");t.className="hl-toast";t.setAttribute("role","status");
  t.innerHTML='<p class="hl-toast-label">Galerie</p>'+
    '<p class="hl-toast-title">'+(fresh.length===1?"1 nouvelle aquarelle en ligne"
      :fresh.length+" nouvelles aquarelles en ligne")+'</p>'+
    '<p class="hl-toast-sub">Depuis votre dernière visite.</p>'+
    '<a class="hl-toast-cta" href="#/galerie">Découvrir</a>'+
    '<button type="button" class="hl-toast-x" aria-label="Fermer la notification">×</button>';
  document.body.appendChild(t);
  requestAnimationFrame(function(){t.classList.add("is-in");});
  function closeT(){t.classList.remove("is-in");
    setTimeout(function(){if(t.parentNode)t.parentNode.removeChild(t);},500);}
  t.querySelector(".hl-toast-x").onclick=closeT;
  t.querySelector(".hl-toast-cta").onclick=closeT;
  var ck=document.getElementById("cookie-bar");
  if(ck&&!ck.hidden)t.style.bottom=(ck.offsetHeight+26)+"px";
}
function initContact(){
  var form=document.getElementById("contact-form");if(!form)return;
  form.addEventListener("submit",function(e){
    e.preventDefault();
    var name=document.getElementById("f-name").value.trim(),
        mail=document.getElementById("f-email").value.trim(),
        tel=document.getElementById("f-phone").value.trim(),
        cat=document.getElementById("f-cat").value,
        subj=document.getElementById("f-subject").value.trim(),
        msg=document.getElementById("f-message").value.trim();
    if(!name||!mail||!subj||!msg){alert("Merci de renseigner au minimum : votre nom, votre e-mail, l’objet et votre message.");return;}
    var body="Bonjour Hilaire,\n\n"+msg+"\n\n— "+name+(tel?"\nTéléphone : "+tel:"")+"\n(Répondre à : "+mail+")";
    var href="mailto:"+DATA.email+"?subject="+encodeURIComponent("["+cat+"] "+subj)+"&body="+encodeURIComponent(body);
    document.getElementById("form-ok").hidden=false;
    window.location.href=href;
  });
}
var mapReady=false;
function hlGet(){try{var v=localStorage.getItem("hl_consent");
  if(v==="oui")return{done:true,map:true,ga:true,off:true};
  if(v==="non")return{done:true,map:false,ga:false,off:true};
  var j=JSON.parse(v);if(j&&j.done)return{done:true,map:!!j.map,ga:!!j.ga,off:!!j.off};}catch(e){}
  return{done:false,map:false,ga:false,off:false};}
function hlSet(o){try{o.done=true;o.ts=Date.now();localStorage.setItem("hl_consent",JSON.stringify(o));}catch(e){}}
function hlApplyConsent(){var c=hlGet();var bar=document.getElementById("cookie-bar");var gaOn=!!DATA.ga;
  if(bar)bar.hidden=!(!c.done||(gaOn&&!c.off));
  var m=document.getElementById("ck-map"),g=document.getElementById("ck-ga");
  if(c.done){if(m)m.checked=c.map;if(g)g.checked=c.ga;
    if(c.map)initMap();if(c.ga&&gaOn)hlGaInit();}}
function initMap(){
  var el=document.getElementById("map");
  if(!el||el.dataset.mapInit||typeof L==="undefined")return;
  var C=hlGet();
  if(!(C.done&&C.map)){
    var gate=document.getElementById("map-consent");
    if(gate){gate.hidden=false;
      var b=document.getElementById("map-load");
      if(b)b.onclick=function(){var c=hlGet();
        hlSet({map:true,ga:c.done&&c.ga,off:c.off});gate.hidden=true;initMap();hlApplyConsent();};}
    return;}
  el.dataset.mapInit="1";
  el.hidden=false;
  var c=[49.4894,-1.5048];
  var map=L.map(el,{scrollWheelZoom:false}).setView(c,8);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:18,
    attribution:"&copy; OpenStreetMap"}).addTo(map);
  L.circle(c,{radius:75000,color:"#38a888",weight:1.6,opacity:.9,
    fillColor:"#38a888",fillOpacity:.10}).addTo(map);
  L.circle(c,{radius:2000,color:"#0a7d85",weight:1.2,fillColor:"#0a7d85",fillOpacity:.55}).addTo(map);
  var icon=L.divIcon({className:"",html:'<div style="width:14px;height:14px;border-radius:50%;'+
    'background:#0a7d85;border:3px solid #faf8f3;box-shadow:0 0 0 2px #38a888"></div>',
    iconSize:[14,14],iconAnchor:[7,7]});
  L.marker(c,{icon:icon,title:"Yvetot-Bocage — Normandie"}).addTo(map)
   .bindPopup("<strong>Yvetot-Bocage</strong><br>Manche — Normandie<br><em>Zone d’environ 75 km autour</em>");
  map.on("click",function(){map.scrollWheelZoom.enable();});
  map.on("mouseout",function(){map.scrollWheelZoom.disable();});
}
/* ----------------- confidentialité & mentions (monofichier) ------------------ */
function pageLegal(){
  return '<header class="page-head"><div class="container reveal"><p class="label">Informations</p>'+
  '<h1 class="page-title">Confidentialité &amp; mentions légales</h1></div></header>'+
  '<section class="section"><div class="container article legal-body reveal" style="text-align:left">'+
  '<h2>Éditeur</h2><p><strong>Hilaire Legentil</strong> — artiste auteur · SIREN 927&nbsp;753&nbsp;780 · Yvetot-Bocage, 50700 Valognes (Manche, Normandie) · '+
  '<a class="lnk" href="mailto:'+DATA.email+'">'+DATA.email+'</a></p>'+
  '<h2>Directeur de la publication</h2><p>Hilaire Legentil.</p>'+
  '<h2>Hébergement</h2><p>Ce fichier se consulte localement, sans serveur. La version en ligne peut être hébergée par GitHub Pages (GitHub, Inc., San Francisco, États-Unis) ou par l’hébergeur choisi par l’éditeur.</p>'+
  '<h2>Vente et commandes</h2><p>Ce site ne réalise aucune vente et n’encaisse aucun paiement en ligne. Les commandes se concluent directement avec l’artiste (contact, téléphone, courriel).</p>'+
  '<h2>Propriété intellectuelle</h2><p>Aquarelles, photographies, affiches et textes sont la propriété exclusive d’Hilaire Legentil. Toute reproduction sans autorisation écrite est interdite.</p>'+
  '<h2>Cookies</h2><p>Ce fichier ne dépose <strong>aucun cookie</strong> et n’utilise aucun traceur. Le bandeau du premier passage offre trois choix : tout accepter, tout refuser ou personnaliser (carte, mesure d’audience). Vos choix, horodatés (preuve du consentement), sont conservés six mois uniquement dans votre navigateur, jamais transmis ; le refus ne prive d’aucune fonctionnalité hormis la carte. Si une mesure d’audience est activée, elle ne se charge qu’après votre accord et l’adresse IP est anonymisée.</p>'+
  '<h3>Notifications des nouvelles aquarelles</h3><p>Si vous les activez, elles reposent sur un identifiant technique anonyme conservé par votre navigateur — aucune donnée personnelle. Vous pouvez les couper à tout moment depuis les réglages du navigateur.</p>'+
  '<h3>Carte interactive</h3><p>Les tuiles OpenStreetMap ne sont sollicitées qu’après votre accord explicite ; sans accord, rien n’est chargé depuis ce service tiers.</p>'+
  '<p><button class="btn btn-outline" id="ck-reset" type="button">Effacer mon choix (revoir le bandeau)</button></p>'+
  '<h2>Données personnelles</h2><p>Le formulaire prépare un e-mail dans votre propre logiciel de messagerie : aucune donnée n’est collectée par ce fichier. Sur la version en ligne, le message est adressé au seul artiste pour répondre à votre demande, puis supprimé au plus tard 12 mois après réception. Vous disposez de droits d’accès, de rectification et d’effacement.</p>'+
  '<h2>Vos droits</h2><p>Conformément au RGPD, vous disposez de droits d’accès, rectification, effacement et opposition : écrivez à <a class="lnk" href="mailto:'+DATA.email+'">'+DATA.email+'</a>. Réclamation possible auprès de la <a class="lnk" href="https://www.cnil.fr" rel="noopener" target="_blank">CNIL</a>.</p>'+
  '</div></section>';}

/* ----------------------- administration (monofichier) ------------------ */
function admStatus(msg,err){var el=document.getElementById("adm-status");
  if(el){el.textContent=msg||"";el.classList.toggle("err",!!err);}}
var admTimer=null;
function persistLocal(quiet){
  try{localStorage.setItem("hl_data",JSON.stringify({savedAt:Date.now(),data:DATA}));
    if(!quiet)admStatus("Enregistré dans ce navigateur. Pensez à « Exporter » pour diffuser la version à jour.");
    return true;}
  catch(e){if(!quiet)admStatus("Stockage local indisponible ou plein : les modifications n’ont pas pu être gardées dans ce navigateur.",true);
    return false;}}
function updatedHtml(){
  var json=JSON.stringify(DATA).replace(/<\//g,"<\\/");
  return PRISTINE.replace(/\/\*HLDATA\*\/[\s\S]*?\/\*HLDATA-END\*\//,"/*HLDATA*/"+json+"/*HLDATA-END*/");}
function processImage(file,maxSide,cb){
  var fr=new FileReader();
  fr.onload=function(){var img=new Image();
    img.onload=function(){
      var w=img.width,h=img.height,r=Math.min(1,maxSide/Math.max(w,h));
      var c=document.createElement("canvas");
      c.width=Math.max(1,Math.round(w*r));c.height=Math.max(1,Math.round(h*r));
      var ctx=c.getContext("2d");
      ctx.drawImage(img,0,0,c.width,c.height);
      var txt="Hilaire Legentil",fs=Math.max(18,Math.round(c.width*0.040)),
      pad=Math.max(8,Math.round(c.width*0.020));
      ctx.font="italic "+fs+"px Georgia,serif";ctx.textAlign="right";ctx.textBaseline="alphabetic";
      ctx.fillStyle="rgba(10,25,30,.47)";ctx.fillText(txt,c.width-pad+2,c.height-pad+2);
      ctx.fillStyle="rgba(255,255,255,.69)";ctx.fillText(txt,c.width-pad,c.height-pad);
      var uri;
      try{uri=c.toDataURL("image/webp",.82);
        if(uri.indexOf("image/webp")<0)uri=c.toDataURL("image/jpeg",.85);}
      catch(e){uri=c.toDataURL("image/jpeg",.85);}
      cb(uri,c.width,c.height);};
    img.onerror=function(){admStatus("Cette image n’a pas pu être lue.",true);};
    img.src=fr.result;};
  fr.readAsDataURL(file);}

function pageAdminGate(){
  return '<header class="page-head"><div class="container reveal"><p class="label">Administration</p>'+
  '<h1 class="page-title">Espace administrateur</h1></div></header>'+
  '<section class="section"><div class="container narrow center reveal">'+
  '<div class="contact-card" style="max-width:430px;margin:0 auto;text-align:left">'+
  '<p class="small muted" style="margin-bottom:1.2rem">Réservé à Hilaire : gestion des œuvres et des actualités du site.</p>'+
  '<div class="field"><label for="adm-pin">Code d’accès</label>'+
  '<input type="password" id="adm-pin" autocomplete="off"></div>'+
  '<button class="btn btn-full" id="adm-go" type="button">Déverrouiller</button>'+
  '<p class="form-note">Code défini dans Réglages (par défaut : aquarelles_2026).</p>'+
  '</div></div></section>';}

function admThumb(src){return src?'<img class="adm-thumb" src="'+src+'" alt="">':
  '<span class="adm-thumb adm-noimg">—</span>';}
function admWorkRow(w,i){
  return '<div class="adm-row" data-i="'+i+'">'+admThumb(w.i)+
  '<div class="adm-fields">'+
  '<input data-f="t" value="'+escA(w.t)+'" placeholder="Titre de l’aquarelle" aria-label="Titre">'+
  '<div class="adm-inline"><input data-f="c" value="'+escA(w.c)+'" placeholder="Catégorie (ex. Marines)">'+
  '<input data-f="y" value="'+escA(w.y)+'" placeholder="Année"></div>'+
  '<textarea data-f="d" rows="2" placeholder="Description (facultatif)">'+esc(w.d)+'</textarea>'+
  '<div class="adm-inline"><input data-f="sj" value="'+escA(w.sj||"")+'" placeholder="Sujet (ex. Marée basse, Barfleur)">'+
  '<input data-f="am" value="'+escA(w.am||"")+'" placeholder="Ambiance (ex. Lumière douce)"></div>'+
  '<div class="adm-wimgs">'+((w.im&&w.im.length)?w.im.map(function(u,k){
    return '<span class="adm-wimg"><img src="'+u+'" alt=""><button type="button" data-a="imdel" data-k="'+k+'" aria-label="Retirer l\u2019image">✕</button></span>';}).join(""):"")+
  ((w.im||[]).length<5?'<label class="adm-wadd">＋ image<input type="file" accept="image/*" hidden data-a="addimg"></label>':"")+
  '</div>'+
  '</div><div class="adm-actions">'+
  '<button type="button" data-a="up" title="Monter dans la galerie">↑</button>'+
  '<button type="button" data-a="down" title="Descendre">↓</button>'+
  '<label>Image<input type="file" accept="image/*" hidden data-a="img"></label>'+
  '<button type="button" data-a="del" class="danger">Supprimer</button>'+
  '</div></div>';}
function admNewsRow(n,i){
  return '<div class="adm-row" data-i="'+i+'">'+admThumb(n.cov)+
  '<div class="adm-fields">'+
  '<input data-f="t" value="'+escA(n.t)+'" placeholder="Titre de l’actualité" aria-label="Titre">'+
  '<div class="adm-inline"><input data-f="rd" value="'+escA(n.rd||"")+'" placeholder="Date (2025-07-21)">'+
  '<input data-f="tm" value="'+escA(n.tm||"")+'" placeholder="Heure (14 h 30 – 18 h)">'+
  '<input data-f="pl" value="'+escA(n.pl||"")+'" placeholder="Lieu (salle, ville)"></div>'+
  '<div class="adm-inline"><input data-f="l" value="'+escA(n.l||"")+'" placeholder="Lien (https://…)"></div>'+
  '<textarea data-f="body" rows="3" placeholder="Texte — laissez une ligne vide entre les paragraphes">'+esc((n.p||[]).join("\n\n"))+'</textarea>'+
  '</div><div class="adm-actions">'+
  '<label>Affiche<input type="file" accept="image/*" hidden data-a="img"></label>'+
  '<button type="button" data-a="del" class="danger">Supprimer</button>'+
  '</div></div>';}
function admAddWork(){
  return '<div class="adm-add"><h3 class="h3">Ajouter une œuvre</h3>'+
  '<form id="adm-add-work">'+
  '<div class="adm-grid2"><div><label>Titre</label><input data-f="t" placeholder="Ex. : Marée basse à Barfleur"></div>'+
  '<div><label>Catégorie &amp; année</label><div class="adm-inline">'+
  '<input data-f="c" placeholder="Catégorie"><input data-f="y" placeholder="Année"></div></div></div>'+
  '<div style="margin-top:.8rem"><label>Description</label><textarea data-f="d" rows="2" placeholder="Facultatif"></textarea></div>'+
  '<div style="margin-top:.8rem"><label>Photographie de l’aquarelle</label>'+
  '<input data-f="file" type="file" accept="image/*" required></div>'+
  '<button class="btn" type="submit" style="margin-top:1.1rem">Ajouter à la galerie</button>'+
  '</form></div>';}
function admAddNews(){
  return '<div class="adm-add"><h3 class="h3">Ajouter un événement</h3>'+
  '<form id="adm-add-news">'+
  '<div class="adm-grid2"><div><label>Titre</label><input data-f="t" placeholder="Ex. : Exposition à Barfleur"></div>'+
  '<div><label>Date</label><input data-f="rd" placeholder="2026-07-12 (ou 2026-07, 2026)"></div></div>'+
  '<div class="adm-grid2" style="margin-top:.8rem"><div><label>Heure (facultatif)</label><input data-f="tm" placeholder="14 h 30 – 18 h"></div>'+
  '<div><label>Lieu (facultatif)</label><input data-f="pl" placeholder="Salle polyvalente, Barfleur"></div></div>'+
  '<div style="margin-top:.8rem"><label>Lien externe</label><input data-f="l" placeholder="https://… (facultatif)"></div>'+
  '<div style="margin-top:.8rem"><label>Texte</label><textarea data-f="body" rows="3" placeholder="Lieu, dates, horaires…"></textarea></div>'+
  '<div style="margin-top:.8rem"><label>Affiche</label><input data-f="file" type="file" accept="image/*"></div>'+
  '<button class="btn" type="submit" style="margin-top:1.1rem">Publier l’événement</button>'+
  '</form></div>';}
function admSettings(){
  function f(l,k){return '<div><label>'+l+'</label><input data-s="'+k+'" value="'+escA(DATA[k]||"")+'"></div>';}
  function t(l,k){return '<div style="margin-top:.8rem"><label>'+l+'</label>'+
    '<textarea data-s="'+k+'" rows="3">'+esc(DATA[k]||"")+'</textarea></div>';}
  return '<div class="adm-add"><h3 class="h3">Réglages</h3>'+
  '<div class="adm-grid2">'+f("Code d’accès administrateur","pin")+f("Téléphone affiché","phone")+
  f("E-mail affiché","email")+
  f("Instagram (sans @)","instagram")+
  f("Facebook (adresse complète, facultatif)","fb")+'</div>'+
  '<div class="adm-grid2" style="margin-top:.8rem">'+
  f("ID Google Analytics (G-…, vide = désactivé)","ga")+'</div>'+
  t("Bandeau — petite ligne","heroB")+t("Bandeau — nom","heroT")+t("Bandeau — ligne sous le nom","heroS")+
  t("Phrase d’accroche de l’accueil","homeIntro")+
  t("Présentation de l’artiste","artistIntro")+
  '<p class="form-note" style="margin-top:.6rem">Chaque modification est enregistrée automatiquement dans ce navigateur.</p>'+
  '</div>';}
function pageAdmin(){
  return '<header class="page-head"><div class="container reveal"><p class="label">Administration</p>'+
  '<h1 class="page-title">Gérer le site</h1>'+
  '<p class="page-sub">Titres modifiables directement sur les pages — œuvres, sur le vif, actualités et atelier gérés ici.</p></div></header>'+
  '<section class="section"><div class="container">'+
  admGitHub()+
  '<p class="adm-status" id="adm-status" role="status"></p>'+
  '<div class="adm-bar">'+
  '<button class="btn" id="adm-reset" type="button">Réinitialiser</button>'+
  '<button class="btn" id="adm-logout" type="button">Verrouiller</button></div>'+
  '<h2 class="h3">Les œuvres <span class="muted small">('+DATA.works.length+')</span></h2>'+
  '<div id="adm-works">'+DATA.works.map(admWorkRow).join("")+'</div>'+admAddWork()+
  '<h2 class="h3">Sur le vif <span class="muted small">('+DATA.atelier.length+')</span></h2>'+
  '<p class="muted small">Les aquarelles peintes devant le sujet, affichées dans la galerie (rubrique Sur le vif).</p>'+
  '<div id="adm-atelier">'+DATA.atelier.map(admVifRow).join("")+'</div>'+
  admAddVif()+
  '<h2 class="h3">Les actualités <span class="muted small">('+DATA.news.length+')</span></h2>'+
  '<div id="adm-news">'+DATA.news.map(admNewsRow).join("")+'</div>'+admAddNews()+
  '<h2 class="h3">L\u2019atelier <span class="muted small">('+DATA.photos.length+')</span></h2>'+
  '<p class="muted small">Les photos affichées sur la page L\u2019atelier — ajoutez-en autant que vous voulez, remplacez-les ou réordonnez-les.</p>'+
  '<div id="adm-photos">'+DATA.photos.map(admPhotoRow).join("")+'</div>'+
  admAddAtelier()+
  admSettings()+
  '</div></section>';}
function bindList(id,arr){
  var box=document.getElementById(id);if(!box)return;
  box.addEventListener("input",function(e){
    var f=e.target.getAttribute("data-f");if(!f||e.target.type==="file")return;
    var row=e.target.closest(".adm-row");if(!row)return;
    var it=arr[+row.getAttribute("data-i")];if(!it)return;
    var v=e.target.value;
    if(f==="body")it.p=v.split(/\n\s*\n/).map(function(x){return x.trim();}).filter(Boolean);
    else if(f==="rd"){it.rd=v;it.dt=jsDateFr(v);}
    else it[f]=v;
    clearTimeout(admTimer);admTimer=setTimeout(function(){persistLocal(true);},500);});
  box.addEventListener("change",function(e){
    if(e.target.getAttribute("data-a")!=="img")return;
    var file=e.target.files[0];if(!file)return;
    var row=e.target.closest(".adm-row");if(!row)return;
    var i=+row.getAttribute("data-i");
    processImage(file,1400,function(uri){
      if(arr[i]){if(arr===DATA.works){arr[i].i=uri;}else{arr[i].cov=uri;}persistLocal();render();}});});
  box.addEventListener("click",function(e){
    var b=e.target.closest("[data-a]");
    if(!b||b.tagName==="LABEL"||b.tagName==="INPUT")return;
    var a=b.getAttribute("data-a"),row=b.closest(".adm-row");if(!row)return;
    var i=+row.getAttribute("data-i");
    if(a==="del"){if(!confirm("Supprimer « "+arr[i].t+" » ?"))return;
      arr.splice(i,1);persistLocal();render();}
    if(a==="up"&&i>0){var x=arr[i];arr[i]=arr[i-1];arr[i-1]=x;persistLocal();render();}
    if(a==="down"&&i<arr.length-1){var y=arr[i];arr[i]=arr[i+1];arr[i+1]=y;persistLocal();render();}});}

function admVifRow(p,i){
  return '<div class="adm-row" data-i="'+i+'">'+admThumb(p.i)+
  '<div class="adm-fields"><p style="margin:0">Aquarelle « sur le vif » — n°'+(i+1)+'</p>'+
  '<p class="muted small" style="margin:.2rem 0 0">Affichée dans la galerie, section Sur le vif</p></div>'+
  '<div class="adm-actions">'+
  '<button type="button" data-a="up" title="Monter">↑</button>'+
  '<button type="button" data-a="down" title="Descendre">↓</button>'+
  '<button type="button" data-a="del" class="danger">Supprimer</button>'+
  '</div></div>';}
function admPhotoRow(p,i){
  return '<div class="adm-row" data-i="'+i+'">'+admThumb(p.i)+
  '<div class="adm-fields"><p style="margin:0">Photo de l\u2019atelier — n°'+(i+1)+'</p>'+
  '<p class="muted small" style="margin:.2rem 0 0">Affichée sur la page L\u2019atelier</p></div>'+
  '<div class="adm-actions">'+
  '<button type="button" data-a="up" title="Monter">↑</button>'+
  '<button type="button" data-a="down" title="Descendre">↓</button>'+
  '<label>Remplacer<input type="file" accept="image/*" hidden data-a="img"></label>'+
  '<button type="button" data-a="del" class="danger">Supprimer</button>'+
  '</div></div>';}
function admAddAtelier(){
  return '<div class="adm-add"><h3 class="h3">Ajouter une photo à l\u2019atelier</h3>'+
  '<form id="adm-add-atelier">'+
  '<div><label>Image</label><input type="file" accept="image/*" required></div>'+
  '<button class="btn" type="submit" style="margin-top:1.1rem">Ajouter la photo</button>'+
  '</form></div>';}
function admAddVif(){
  return '<div class="adm-add"><h3 class="h3">Ajouter une aquarelle sur le vif</h3>'+
  '<form id="adm-add-vif">'+
  '<div><label>Image de l’aquarelle</label><input type="file" accept="image/*" required></div>'+
  '<button class="btn" type="submit" style="margin-top:1.1rem">Ajouter à la galerie</button>'+
  '</form></div>';}
function bindAtelier(){
  var box=document.getElementById("adm-atelier"),ph=document.getElementById("adm-photos");
  if(box)box.addEventListener("click",function(e){
    var b=e.target.closest("button[data-a]");if(!b)return;
    var row=b.closest(".adm-row");if(!row)return;
    var i=+row.getAttribute("data-i"),p=DATA.atelier[i],a=b.getAttribute("data-a");
    if(!p)return;
    if(a==="del"){DATA.atelier.splice(i,1);persistLocal();render();admStatus("Aquarelle sur le vif supprimée.");return;}
    if(a==="up"&&i>0){DATA.atelier[i]=DATA.atelier[i-1];DATA.atelier[i-1]=p;persistLocal();render();return;}
    if(a==="down"&&i<DATA.atelier.length-1){DATA.atelier[i]=DATA.atelier[i+1];DATA.atelier[i+1]=p;persistLocal();render();}});
  if(ph){
    ph.addEventListener("click",function(e){
      var b=e.target.closest("button[data-a]");if(!b)return;
      var row=b.closest(".adm-row");if(!row)return;
      var i=+row.getAttribute("data-i"),a=b.getAttribute("data-a");
      if(!DATA.photos[i])return;
      if(a==="del"){DATA.photos.splice(i,1);persistLocal();render();admStatus("Photo supprimée.");return;}
      if(a==="up"&&i>0){DATA.photos[i]=DATA.photos[i-1];DATA.photos[i-1]=DATA.photos[i===0?0:i];}
      if(a==="up"&&i>0){var t=DATA.photos[i];DATA.photos[i]=DATA.photos[i-1];DATA.photos[i-1]=t;persistLocal();render();return;}
      if(a==="down"&&i<DATA.photos.length-1){var u=DATA.photos[i];DATA.photos[i]=DATA.photos[i+1];DATA.photos[i+1]=u;persistLocal();render();return;}});
    ph.addEventListener("change",function(e){
      if(e.target.getAttribute("data-a")!=="img")return;
      var row=e.target.closest(".adm-row");if(!row)return;
      var i=+row.getAttribute("data-i"),f=e.target.files[0];
      if(!f||!DATA.photos[i])return;
      processImage(f,1400,function(uri,w,h){
        DATA.photos[i]={i:uri,w:w,h:h};persistLocal();render();
        admStatus("Photo remplacée.");});});}
  var af=document.getElementById("adm-add-atelier");
  if(af)af.addEventListener("submit",function(e){e.preventDefault();
    var f=af.querySelector('input[type=file]').files[0];
    if(!f){admStatus("Choisissez d\u2019abord une image.",true);return;}
    processImage(f,1400,function(uri,w,h){
      DATA.photos.push({i:uri,w:w,h:h});persistLocal();render();
      admStatus("Photo ajoutée à la page L\u2019atelier.");});});}
function ghCfgLoad(){try{return JSON.parse(localStorage.getItem("hl_gh")||"{}")||{};}catch(e){return {};}}
function ghCfgSave(c){try{localStorage.setItem("hl_gh",JSON.stringify(c));}catch(e){}}
function admGitHub(){
  var c=ghCfgLoad();
  return '<div class="gh-gate" id="adm-gh">'+
  '<h2 class="gh-title">Mettre le site <em>en ligne</em></h2>'+
  '<p class="muted small">Collez votre clé GitHub une seule fois : les photos ajoutées partent directement en ligne, le site se met à jour en 1 à 2 minutes.</p>'+
  '<p class="gh-state small" id="gh-user">'+
  (c.token?'✓ Clé enregistrée'+(c.repo?' · Dépôt : '+esc(c.repo)+' (branche '+esc(c.branch||"main")+')':''):'Clé : — absente')+'</p>'+
  '<label>Jeton d\u2019accès GitHub (la clé)</label>'+
  '<div class="gh-row"><input id="gh-token" type="password" placeholder="github_pat_… ou ghp_…" value="'+escA(c.token||"")+'">'+
  '<button class="btn" id="gh-verify" type="button">🔑 Vérifier et enregistrer</button>'+
  '<button class="btn" id="gh-forget" type="button">Effacer</button></div>'+
  '<div class="gh-row" style="margin-top:.8rem">'+
  '<input id="gh-repo" placeholder="compte/dépôt" value="'+escA(c.repo||"")+'">'+
  '<input id="gh-branch" value="'+escA(c.branch||"main")+'" aria-label="Branche" style="flex:0 1 120px">'+
  '<button class="btn" id="gh-list" type="button">Mes dépôts</button></div>'+
  '<select id="gh-sel" hidden style="margin-top:.5rem;width:100%"></select>'+
  '<div style="margin-top:1.1rem"><button class="btn" id="gh-publish" type="button">Publier le site maintenant</button></div>'+
  '<details class="gh-help"><summary>📖 Comment obtenir un jeton ? (5 minutes, pas à pas)</summary>'+
  '<ol><li>Sur github.com, cliquez votre avatar → <strong>Settings</strong> → Developer settings → Personal access tokens → <strong>Fine-grained tokens</strong> → Generate new token.</li>'+
  '<li><strong>Nom</strong> : « Site Hilaire » · <strong>Expiration</strong> : 1 an.</li>'+
  '<li><strong>Repository access</strong> : Only select repositories → sélectionnez le dépôt du site.</li>'+
  '<li><strong>Permissions</strong> → Repository permissions → <strong>Contents : Read and write</strong>.</li>'+
  '<li>Cliquez <strong>Generate token</strong>, copiez la clé et collez-la ci-dessus.</li></ol>'+
  '<p class="muted small">💡 Avec un jeton « classic », cochez la case <strong>repo</strong> entière. Si GitHub répond « Resource not accessible by personal access token », le jeton n\u2019a pas le droit d\u2019écriture : vérifiez l\u2019étape 4 et que le bon dépôt est sélectionné.</p></details>'+
  '</div>';}
function b64u(s){return btoa(unescape(encodeURIComponent(s)));}
function ghApi(path,opts){opts=opts||{};var c=ghCfgLoad();
  var h={"Authorization":"Bearer "+c.token,"Accept":"application/vnd.github+json",
    "X-GitHub-Api-Version":"2022-11-28"};
  if(opts.headers)for(var k in opts.headers)h[k]=opts.headers[k];
  opts.headers=h;return fetch("https://api.github.com"+path,opts);}
function ghListRepos(){
  var st=document.getElementById("gh-user");
  st.textContent="Chargement de vos dépôts…";
  return ghApi("/user/repos?per_page=100&sort=pushed").then(function(r){return r.json();})
  .then(function(rl){
    var sel=document.getElementById("gh-sel");sel.innerHTML="";
    var c=ghCfgLoad(),n=0;
    rl.forEach(function(r){if(r.permissions&&r.permissions.push){
      var o=document.createElement("option");o.value=r.full_name;
      o.setAttribute("data-b",r.default_branch||"main");
      o.textContent=r.full_name;if(c.repo===r.full_name)o.selected=true;
      sel.appendChild(o);n++;}});
    if(n){sel.hidden=false;
      sel.onchange=function(){var o=sel.options[sel.selectedIndex];
        document.getElementById("gh-repo").value=o.value;
        document.getElementById("gh-branch").value=o.getAttribute("data-b");};
      st.textContent=n+" dépôt(s) accessible(s) — choisissez le vôtre :";}
    else st.textContent="Aucun dépôt accessible avec cette clé (vérifiez le droit « repo »).";})
  .catch(function(e){st.textContent="Réseau indisponible : "+e;});}
function bindGitHub(){
  if(!document.getElementById("adm-gh"))return;
  function save(){ghCfgSave({repo:(document.getElementById("gh-repo").value||"").trim(),
    branch:(document.getElementById("gh-branch").value||"main").trim(),
    token:(document.getElementById("gh-token").value||"").trim()});}
  var st=document.getElementById("gh-user");
  var v=document.getElementById("gh-verify");
  if(v)v.onclick=function(){save();var c=ghCfgLoad();
    if(!c.token){st.textContent="Collez d'abord la clé.";return;}
    st.textContent="Vérification de la clé…";
    ghApi("/user").then(function(r){return r.json().then(function(j){return {s:r.status,j:j};});})
    .then(function(x){if(x.s===200){st.textContent="✓ Clé validée — connecté en tant que "+(x.j.login||"?")+".";
        if(c.repo)document.getElementById("gh-repo").value=c.repo;ghListRepos();}
      else st.textContent="GitHub a refusé ("+x.s+") : "+(x.j.message||"")+".";})
    .catch(function(e){st.textContent="Réseau indisponible : "+e;});};
  var f=document.getElementById("gh-forget");
  if(f)f.onclick=function(){var c=ghCfgLoad();c.token="";ghCfgSave(c);
    document.getElementById("gh-token").value="";
    var sel=document.getElementById("gh-sel");sel.hidden=true;sel.innerHTML="";
    st.textContent="Clé effacée de ce navigateur.";};
  var l=document.getElementById("gh-list");
  if(l)l.onclick=function(){save();
    if(!ghCfgLoad().token){st.textContent="Collez d'abord la clé.";return;}ghListRepos();};
  var p=document.getElementById("gh-publish");
  if(p)p.onclick=function(){save();var c=ghCfgLoad();
    if(!c.repo||!c.token){st.textContent="Renseignez la clé (1) et le dépôt (2) d'abord.";return;}
    admStatus("Publication en cours — ne fermez pas la page…");
    ghApi("/repos/"+c.repo+"/contents/index.html?ref="+encodeURIComponent(c.branch))
    .then(function(r){return r.json().then(function(j){return {s:r.status,j:j};});})
    .then(function(x){var sha=x.s===200?x.j.sha:null;
      var payload={message:"Site mis à jour depuis l'administration",branch:c.branch,
        content:b64u(updatedHtml())};if(sha)payload.sha=sha;
      return ghApi("/repos/"+c.repo+"/contents/index.html",{method:"PUT",
        headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)})
      .then(function(r){return r.json().then(function(j){return {s:r.status,j:j};});});})
    .then(function(x){if(x.s===200||x.s===201)
        admStatus("Publié ✔ GitHub Pages se met à jour dans une à deux minutes.");
      else admStatus("Publication refusée ("+x.s+") : "+(x.j.message||"")+".",true);})
    .catch(function(e){admStatus("Réseau indisponible : "+e,true);});};}
function initAdmin(){
  var go=document.getElementById("adm-go");
  if(go){
    var unlock=function(){
      var v=document.getElementById("adm-pin").value;
      if(v===(DATA.pin||"aquarelles_2026")){
        try{sessionStorage.setItem("hl_admin","1");}catch(e){}
        ADMIN=true;render();}
      else{alert("Code incorrect.");document.getElementById("adm-pin").value="";}};
    go.addEventListener("click",unlock);
    document.getElementById("adm-pin").addEventListener("keydown",function(e){if(e.key==="Enter")unlock();});
    setTimeout(function(){document.getElementById("adm-pin").focus();},50);
    return;}
  if(!document.getElementById("adm-works"))return;
  bindList("adm-works",DATA.works);
  var wbox=document.getElementById("adm-works");
  if(wbox){
    wbox.addEventListener("change",function(e){
      if(e.target.getAttribute("data-a")!=="addimg")return;
      var row=e.target.closest(".adm-row");if(!row)return;
      var it=DATA.works[+row.getAttribute("data-i")];if(!it)return;
      var f=e.target.files[0];if(!f)return;
      if(!it.im)it.im=[];
      if(it.im.length>=5){admStatus("Cinq images maximum par œuvre (hors principale).",true);return;}
      processImage(f,1400,function(uri){it.im.push(uri);persistLocal();render();
        admStatus("Image ajoutée à l’œuvre.");});});
    wbox.addEventListener("click",function(e){
      var b=e.target.closest('button[data-a="imdel"]');if(!b)return;
      var row=b.closest(".adm-row");if(!row)return;
      var it=DATA.works[+row.getAttribute("data-i")];if(!it||!it.im)return;
      it.im.splice(+b.getAttribute("data-k"),1);persistLocal();render();});}
  bindList("adm-news",DATA.news);
  bindAtelier();
  bindGitHub();
  var aw=document.getElementById("adm-add-work");
  aw.addEventListener("submit",function(e){e.preventDefault();
    var file=aw.querySelector('input[type=file]').files[0];
    var t=aw.querySelector('[data-f=t]').value.trim()||"Sans titre";
    if(!file){admStatus("Choisissez d’abord la photographie de l’aquarelle.",true);return;}
    processImage(file,1400,function(uri,w,h){
      var base=slugJs(t),s=base,k=1;while(workBySlug(s))s=base+"-"+(++k);
      DATA.works.push({t:t,s:s,c:aw.querySelector('[data-f=c]').value.trim(),
        y:aw.querySelector('[data-f=y]').value.trim(),
        d:aw.querySelector('[data-f=d]').value.trim(),i:uri,w:w,h:h});
      persistLocal();render();
      admStatus("Œuvre ajoutée à la galerie.");});});
  var an=document.getElementById("adm-add-news");
  an.addEventListener("submit",function(e){e.preventDefault();
    var t=an.querySelector('[data-f=t]').value.trim();
    if(!t){admStatus("Donnez un titre à l’actualité.",true);return;}
    var rd=an.querySelector('[data-f=rd]').value.trim(),
        tm=an.querySelector('[data-f=tm]').value.trim(),
        pl=an.querySelector('[data-f=pl]').value.trim(),
        body=an.querySelector('[data-f=body]').value,
        link=an.querySelector('[data-f=l]').value.trim(),
        file=an.querySelector('input[type=file]').files[0];
    var done=function(uri){
      var base=slugJs(t),s=base,k=1;while(newsBySlug(s))s=base+"-"+(++k);
      DATA.news.unshift({t:t,s:s,dt:jsDateFr(rd),rd:rd,tm:tm,pl:pl,
        p:body.split(/\n\s*\n/).map(function(x){return x.trim();}).filter(Boolean),
        cov:uri||"",img:[],l:link});
      persistLocal();render();
      admStatus("Actualité publiée.");};
    if(file)processImage(file,1400,done);else done("");});
  document.querySelectorAll("[data-s]").forEach(function(inp){
    inp.addEventListener("input",function(){
      DATA[inp.getAttribute("data-s")]=inp.value;persistLocal(true);});});
  document.getElementById("adm-logout").addEventListener("click",function(){
    try{sessionStorage.removeItem("hl_admin");}catch(e){}
    ADMIN=false;location.hash="#/accueil";render();});
  document.getElementById("adm-reset").addEventListener("click",function(){
    if(confirm("Revenir aux données d’origine du fichier ? Les modifications locales seront perdues.")){
      try{localStorage.removeItem("hl_data");}catch(e){}
      location.reload();}});}

/* ------- édition directe des titres quand l'espace est déverrouillé ------- */
function makeEditable(){
  if(!ADMIN)return;
  if(!window.__edGuard){window.__edGuard=1;
    document.addEventListener("click",function(e){
      if(e.target.isContentEditable)e.preventDefault();},true);
    document.addEventListener("keydown",function(e){
      if(e.target.isContentEditable&&e.key==="Enter"){e.preventDefault();e.target.blur();}});}
  function editable(el,apply){if(!el)return;
    el.setAttribute("contenteditable","true");el.classList.add("edit");el.spellcheck=false;
    el.addEventListener("blur",function(){
      var v=el.textContent.replace(/\s+/g," ").trim();
      if(v){apply(v);persistLocal(true);}});}
  document.querySelectorAll(".work").forEach(function(card){
    var slug=(card.getAttribute("href")||"").replace("#/oeuvre/","");
    editable(card.querySelector(".work-title"),function(v){var w=workBySlug(slug);if(w)w.t=v;});});
  var mw=location.hash.match(/^#\/oeuvre\/(.+)$/);
  if(mw)editable(document.querySelector(".page-title"),function(v){var w=workBySlug(mw[1]);if(w)w.t=v;});
  document.querySelectorAll(".news-row").forEach(function(row){
    var slug=(row.getAttribute("href")||"").replace("#/evenement/","");
    editable(row.querySelector(".news-title"),function(v){var n=newsBySlug(slug);if(n)n.t=v;});});
  var mn=location.hash.match(/^#\/actualite\/(.+)$/);
  if(mn)editable(document.querySelector(".page-title"),function(v){var n=newsBySlug(mn[1]);if(n)n.t=v;});
  var mo=location.hash.match(/^#\/oeuvre\/(.+)$/);
  if(mo){var wdesc=document.querySelector(".work-aside .article-body");
    if(wdesc){wdesc.setAttribute("contenteditable","true");wdesc.classList.add("edit");
      wdesc.addEventListener("blur",function(){
        var w=workBySlug(mo[1]);if(!w)return;
        var v=wdesc.textContent.replace(/\s+/g," ").trim();
        w.d=v;persistLocal(true);});}}}

/* menu mobile + en-tête */
var toggle=document.getElementById("nav-toggle"),nav=document.getElementById("site-nav");
function closeNav(){nav.classList.remove("open");document.body.classList.remove("nav-open");
  toggle.setAttribute("aria-expanded","false");}
toggle.addEventListener("click",function(){
  var open=nav.classList.toggle("open");
  document.body.classList.toggle("nav-open",open);
  toggle.setAttribute("aria-expanded",open?"true":"false");});
nav.addEventListener("click",function(e){if(e.target.closest("a"))closeNav();});
var header=document.getElementById("site-header");
window.addEventListener("scroll",function(){
  header.classList.toggle("scrolled",window.scrollY>40);},{passive:true});
/* navigation clavier entre œuvres */
document.addEventListener("keydown",function(e){
  if(/input|textarea|select/i.test(e.target.tagName))return;
  var m=location.hash.match(/^#\/oeuvre\/(.+)$/);if(!m)return;
  var idx=-1;DATA.works.forEach(function(w,i){if(w.s===m[1])idx=i;});if(idx<0)return;
  if(e.key==="ArrowRight")location.hash="#/oeuvre/"+DATA.works[(idx+1)%DATA.works.length].s;
  if(e.key==="ArrowLeft")location.hash="#/oeuvre/"+DATA.works[(idx-1+DATA.works.length)%DATA.works.length].s;});
/* pied de page */
document.getElementById("footer-contact").innerHTML=
  '<li><a href="tel:'+DATA.phone.replace(/\s/g,"")+'">'+esc(DATA.phone)+'</a></li>'+
  '<li><a href="mailto:'+DATA.email+'">'+esc(DATA.email)+'</a></li>'+
  '<li><a href="https://www.instagram.com/'+DATA.instagram+'/" rel="me noopener" target="_blank">Instagram — '+esc(DATA.instagram)+'</a></li>'+
  (DATA.fb?'<li><a href="'+escA(DATA.fb)+'" rel="me noopener" target="_blank">Facebook</a></li>':"");
document.getElementById("year").textContent=new Date().getFullYear();
(function(){
  var bar=document.getElementById("cookie-bar");
  if(!bar)return;
  if(DATA.ga){var t=document.getElementById("ck-ga-txt");
    if(t)t.textContent=" La mesure d’audience anonymisée, si elle est activée, exige le même accord.";
    var row=document.getElementById("ck-ga-row");if(row)row.hidden=false;}
  hlApplyConsent();
  document.getElementById("ck-accept").onclick=function(){hlSet({map:true,ga:!!DATA.ga,off:!!DATA.ga});hlApplyConsent();};
  document.getElementById("ck-refuse").onclick=function(){hlSet({map:false,ga:false,off:!!DATA.ga});hlApplyConsent();};
  var cu=document.getElementById("ck-custom"),opts=document.getElementById("cookie-opts");
  if(cu)cu.onclick=function(){var open=!!(opts&&opts.hidden);if(opts)opts.hidden=!open;
    cu.setAttribute("aria-expanded",open?"true":"false");};
  var sv=document.getElementById("ck-save");
  if(sv)sv.onclick=function(){var m=document.getElementById("ck-map"),g=document.getElementById("ck-ga");
    hlSet({map:m?m.checked:true,ga:(!!DATA.ga&&g)?g.checked:false,off:!!DATA.ga});hlApplyConsent();};
})();
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
