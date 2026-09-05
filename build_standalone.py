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
        works.append({
            "t": w["title"], "s": w["slug"], "c": w["category"] or "",
            "y": w["year"] or "", "d": w["description"] or "",
            "i": uri, "w": w["img_w"], "h": w["img_h"],
            "tn": w["tonality"] or "", "cf": w["chroma"] or 0,
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
        "phone": S.get("contact_phone", ""),
        "email": S.get("contact_email", ""),
        "instagram": S.get("instagram", ""),
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
<title>Hilaire Legentil — page introuvable</title>
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:radial-gradient(60% 80% at 80% 0%,rgba(26,157,154,.14),transparent 60%),#faf8f3;
font-family:Georgia,serif;color:#263a40;text-align:center;padding:2rem}
.box{max-width:520px}
p{line-height:1.7}
a{color:#0a615e}
small{font-family:system-ui,sans-serif;color:#5a6a68}
</style>
</head>
<body>
<div class="box">
<p style="letter-spacing:.25em;text-transform:uppercase;font-size:.8rem;color:#0a615e;font-family:system-ui,sans-serif">Hilaire Legentil</p>
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
<title>Hilaire Legentil — Artiste aquarelliste · Aquarelles mer &amp; paysage</title>
<meta name="description" content="Hilaire Legentil, artiste aquarelliste à Yvetot-Bocage en Normandie. Aquarelles de mer et de paysage, peintes sur papier 100 % coton. Galerie, expositions et contact.">
<meta property="og:title" content="Hilaire Legentil — Aquarelles mer &amp; paysage">
<meta property="og:description" content="Aquarelles originales sur papier 100 % coton — mer &amp; paysage de Normandie.">
<meta property="og:locale" content="fr_FR">
<meta name="theme-color" content="#11596a">
<link rel="icon" href="__FAVICON__">
<style>__LEAFLET_CSS__</style>
<style>
__FONTS__
:root{--paper:#faf8f3;--paper2:#f3efe7;--card:#fffdf9;--ink:#0e2a32;--text:#263a40;
--muted:#5a6a68;--teal:#1a9d9a;--tealInk:#0a615e;--tealDeep:#11596a;--tealSoft:#e7f2f0;
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
.hero{position:relative;min-height:100svh;display:flex;flex-direction:column;
justify-content:flex-end;overflow:hidden;padding-top:6.5rem}
.hero-wash{position:absolute;inset:0}.hero-wash svg{width:100%;height:100%}
.hero-inner{position:relative;z-index:2;width:min(1180px,92vw);margin:0 auto 3.2rem}
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
background:radial-gradient(120% 90% at 85% -10%,rgba(26,157,154,.17),transparent 55%),
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
.wash-band{background:radial-gradient(60% 120% at 20% 50%,rgba(26,157,154,.14),transparent 60%),
radial-gradient(50% 100% at 85% 40%,rgba(17,89,106,.12),transparent 60%)}
.contact-invitation{background:radial-gradient(70% 110% at 12% 0%,rgba(201,162,94,.13),transparent 60%),radial-gradient(70% 110% at 88% 8%,rgba(26,157,154,.13),transparent 60%),linear-gradient(180deg,var(--paper),var(--tealSoft) 320%);text-align:center}
.invitation-cta{display:flex;gap:2.2rem;align-items:center;justify-content:center;flex-wrap:wrap;margin-top:2.2rem}
/* galerie */
.filter-bar{display:flex;gap:.7rem;flex-wrap:wrap}
.filter-btn{font-size:.78rem;letter-spacing:.12em;text-transform:uppercase;background:none;
border:1px solid var(--hair);color:var(--text);padding:.5rem 1.15rem;border-radius:999px;cursor:pointer}
.filter-btn.on{background:var(--tealDeep);border-color:var(--tealDeep);color:#fff}
.gallery-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:clamp(1.4rem,3vw,2.6rem)
clamp(1.2rem,2.4vw,2rem);align-items:start;grid-auto-flow:dense}
.work{display:block;color:inherit}
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
.gallery-count{margin-top:3rem;text-align:center;color:var(--muted);font-size:.82rem;
letter-spacing:.12em;text-transform:uppercase}
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
select{appearance:none;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='8'><path d='M1 1l5 5 5-5' fill='none' stroke='%231a9d9a' stroke-width='1.6'/></svg>");
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
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='34' height='8' viewBox='0 0 34 8'><path d='M1 5c4-4 8-4 12 0s8 4 12 0 6-3 8-1' fill='none' stroke='%231a9d9a' stroke-width='1.7' stroke-linecap='round'/></svg>") center/34px 8px no-repeat;
}

/* — en-têtes de page : lavis aux coins + vague sous le titre — */
.page-head{position:relative;}
.page-head::before{
  content:"";position:absolute;inset:0;pointer-events:none;
  background:
    radial-gradient(42% 62% at 7% 10%, rgba(26,157,154,.16), transparent 66%),
    radial-gradient(36% 56% at 93% 26%, rgba(17,89,106,.12), transparent 66%),
    radial-gradient(34% 52% at 68% 0%, rgba(74,148,201,.13), transparent 66%),
    radial-gradient(30% 46% at 96% 92%, rgba(201,162,94,.11), transparent 66%),
    radial-gradient(30% 46% at 18% 96%, rgba(138,154,106,.09), transparent 64%);
}
.page-head::after{
  content:"";position:absolute;left:50%;bottom:.9rem;transform:translateX(-50%);
  width:132px;height:10px;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='132' height='10' viewBox='0 0 132 10'><path d='M2 6c14-6 28-6 42 0s28 6 42 0 28-6 44-2' fill='none' stroke='%231a9d9a' stroke-width='1.7' stroke-linecap='round' opacity='.85'/><circle cx='124' cy='3.4' r='1.5' fill='%2311596a' opacity='.55'/></svg>") center/contain no-repeat;
}
.page-head .container{position:relative;}

/* — tache d'aquarelle derrière chaque œuvre (comme un fond d'atelier) — */
.work{position:relative;z-index:0;}
.work-frame{position:relative;}
.work-frame::before{
  content:"";position:absolute;inset:-16px 12px -20px -16px;z-index:-1;
  opacity:.6;transition:opacity .5s ease;
  background:
    radial-gradient(55% 60% at 30% 28%, rgba(26,157,154,.16), transparent 70%),
    radial-gradient(46% 50% at 72% 78%, rgba(17,89,106,.10), transparent 72%);
}
.work:hover .work-frame::before{opacity:1;}
.frieze a{position:relative;z-index:0;}
.frieze a::before{
  content:"";position:absolute;inset:-14px 8px -18px -12px;z-index:-1;
  background:
    radial-gradient(55% 60% at 32% 30%, rgba(26,157,154,.18), transparent 70%),
    radial-gradient(46% 50% at 70% 76%, rgba(17,89,106,.11), transparent 72%);
}
.artist-home-figure{z-index:0;}
.artist-home-figure::before{
  content:"";position:absolute;inset:-22px 14px -26px -20px;z-index:-1;
  background:
    radial-gradient(50% 58% at 30% 26%, rgba(26,157,154,.15), transparent 70%),
    radial-gradient(44% 50% at 72% 80%, rgba(17,89,106,.10), transparent 72%);
}
.work-figure{position:relative;z-index:0;}
.work-figure::before{
  content:"";position:absolute;inset:-18px 14px -22px -18px;z-index:-1;
  background:
    radial-gradient(50% 58% at 30% 26%, rgba(26,157,154,.14), transparent 70%),
    radial-gradient(44% 50% at 72% 80%, rgba(17,89,106,.10), transparent 72%);
}

/* — citation : nuage d'aquarelle organique derrière le texte — */
.quote-section .narrow{position:relative;}
.quote-section .narrow::before{
  content:"";position:absolute;inset:-34px -48px;z-index:0;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='560' height='300' viewBox='0 0 560 300'><filter id='w'><feTurbulence type='fractalNoise' baseFrequency='0.013 0.02' numOctaves='3' seed='11'/><feDisplacementMap in='SourceGraphic' scale='70'/><feGaussianBlur stdDeviation='7'/></filter><g filter='url(%23w)'><ellipse cx='280' cy='150' rx='225' ry='105' fill='%231a9d9a' opacity='0.10'/><ellipse cx='330' cy='120' rx='150' ry='78' fill='%2311596a' opacity='0.06'/><ellipse cx='215' cy='185' rx='120' ry='64' fill='%234db8ae' opacity='0.07'/></g></svg>") center/100% 100% no-repeat;
}
.quote-section .narrow > *{position:relative;z-index:1;}

/* — houle au-dessus du pied de page — */
.site-footer{position:relative;}
.site-footer::before{
  content:"";position:absolute;left:0;right:0;top:-52px;height:54px;pointer-events:none;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='620' height='54' viewBox='0 0 620 54' preserveAspectRatio='none'><path d='M0 34 C 80 16, 160 50, 240 34 S 400 16, 480 34 S 570 48, 620 30' fill='none' stroke='%231a9d9a' stroke-width='2' opacity='.55'/><path d='M0 24 C 90 8, 190 36, 290 24 S 470 8, 570 22 S 610 26, 620 20' fill='none' stroke='%234a94c9' stroke-width='1.6' opacity='.42'/><path d='M0 46 C 100 30, 200 58, 300 46 S 500 30, 620 44' fill='none' stroke='%2311596a' stroke-width='1.6' opacity='.4'/><circle cx='95' cy='24' r='2' fill='%231a9d9a' opacity='.55'/><circle cx='410' cy='16' r='2.4' fill='%23c9a25e' opacity='.6'/><circle cx='540' cy='40' r='2' fill='%238a9a6a' opacity='.55'/></svg>") repeat-x bottom;background-size:620px 54px;
}

/* — invitation contact : ligne de rivage en tête de section — */
.contact-invitation{position:relative;overflow:hidden;}
.contact-invitation::before{
  content:"";position:absolute;left:0;right:0;top:0;height:44px;opacity:.75;pointer-events:none;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='520' height='44' viewBox='0 0 520 44'><path d='M0 16 C 65 4, 130 28, 195 16 S 325 4, 390 16 S 485 26, 520 12' fill='none' stroke='%231a9d9a' stroke-width='1.8' stroke-linecap='round' opacity='.8'/><path d='M0 30 C 70 18, 140 40, 210 30 S 350 18, 420 30 S 490 38, 520 26' fill='none' stroke='%2311596a' stroke-width='1.4' stroke-linecap='round' opacity='.5'/></svg>") repeat-x top;background-size:520px 44px;
}

/* — transition douce sous le héros — */
.section-artist{position:relative;}
.section-artist::before{
  content:"";position:absolute;top:1.6rem;left:8vw;right:8vw;height:12px;opacity:.5;pointer-events:none;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='90' height='12' viewBox='0 0 90 12'><path d='M2 7c12-6 24-6 36 0s24 6 36 0 10-4 14-2' fill='none' stroke='%231a9d9a' stroke-width='1.5' stroke-linecap='round'/></svg>") repeat-x center/auto 12px;
}

/* — signature discrète dans les cartes — */
.contact-card,.fact-card{position:relative;}
.contact-card::after,.fact-card::after{
  content:"";position:absolute;bottom:.9rem;right:1rem;width:30px;height:7px;opacity:.55;pointer-events:none;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='30' height='7' viewBox='0 0 30 7'><path d='M1 4.5c4-4 7-4 11 0s7 4 11 0 4-2.5 6-1.5' fill='none' stroke='%231a9d9a' stroke-width='1.4' stroke-linecap='round'/></svg>") center/contain no-repeat;
}

/* ═══════ DUO — tantôt couleur, tantôt silence ═══════ */
.duo-section{background:linear-gradient(180deg,var(--paper),#f4f1ea)}
.duo-grid{display:grid;grid-template-columns:1fr 1fr;gap:clamp(1.6rem,3.5vw,3rem)}
.duo-panel{display:flex;flex-direction:column;gap:1.15rem;padding:clamp(1.5rem,3vw,2.3rem);
border-radius:4px;color:inherit;border:1px solid var(--hair);transition:transform .45s,box-shadow .45s}
.duo-panel:hover{transform:translateY(-5px);box-shadow:var(--sh);color:inherit}
.duo-vivid{background:linear-gradient(160deg,#eaf6f3,#dcf0ec 38%,#e0edf8 74%,#eaf6f3);border-color:#b3d8d2}
.duo-mute{background:linear-gradient(160deg,#f2f0ea,#e9e6de 60%,#e0dcd2);border-color:#d6cfc1}
.duo-figure img{width:100%;background:#fffdf9;border:1px solid rgba(14,42,50,.1);padding:.5rem;box-shadow:var(--shs)}
.duo-txt{display:flex;flex-direction:column;gap:.32rem}
.duo-tag{font-weight:600;font-size:.72rem;letter-spacing:.22em;text-transform:uppercase}
.duo-vivid .duo-tag{color:var(--tealInk)}.duo-mute .duo-tag{color:#4e5c58}
.duo-line{font-family:var(--serif);font-style:italic;font-size:1.3rem;color:var(--ink);line-height:1.35}
.duo-see{margin-top:.45rem;font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;color:var(--tealInk)}
.duo-mute .duo-see{color:#4e5c58}
.duo-panel:hover .duo-see{text-decoration:underline}
.duo-note{margin:2.6rem auto 0;max-width:640px;text-align:center;color:var(--text);font-size:1.04rem}
@media(max-width:800px){.duo-grid{grid-template-columns:1fr}}

/* ════════════════ SYMPHONIE DE COULEURS — aquarelle enrichie ════════════════ */
/* teintes réelles des aquarelles : céruléen, ocre, sauge, terre */
.tint-sand{background:linear-gradient(180deg,#f8f4ea,#f3ebd9);}
.tint-sky{background:linear-gradient(180deg,#edf4fb,#e1ecf8);}
.tint-sage{background:linear-gradient(180deg,#f0f4ec,#e7efdd);}
.tint-sand .label{color:#8a6528;}
.tint-sky .label{color:#2b6cb0;}
.tint-sage .label{color:#55663a;}

/* spectre aquarelle au-dessus du pied de page */
.spectrum{height:7px;background:linear-gradient(90deg,#1a9d9a 0%,#4a94c9 25%,#8a9a6a 50%,#c9a25e 75%,#b4714f 100%);}

/* pastilles colorées des filtres tonalité */
.filter-btn[data-filter="tn:Colorée"]::before,
.filter-btn[data-filter="tn:Terne"]::before{content:"";display:inline-block;width:9px;height:9px;
  border-radius:50%;margin-right:.55rem;vertical-align:1px;}
.filter-btn[data-filter="tn:Colorée"]::before{background:#1a9d9a;}
.filter-btn[data-filter="tn:Terne"]::before{background:#c9a25e;}

/* lavis derrière chaque œuvre selon sa tonalité */
.work[data-tn="Colorée"] .work-frame::before{background:
  radial-gradient(55% 60% at 30% 28%, rgba(26,157,154,.19), transparent 70%),
  radial-gradient(46% 50% at 72% 78%, rgba(74,148,201,.16), transparent 72%);}
.work[data-tn="Terne"] .work-frame::before{background:
  radial-gradient(55% 60% at 30% 28%, rgba(201,162,94,.21), transparent 70%),
  radial-gradient(46% 50% at 72% 78%, rgba(143,120,90,.14), transparent 72%);}

/* point de tonalité à côté du titre */
.work-title::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;
  margin-right:.5rem;vertical-align:2px;background:#1a9d9a;}
.work[data-tn="Terne"] .work-title::before{background:#c9a25e;}

/* dates qui alternent les teintes de la palette */
.timeline li:nth-child(5n+1) .tl-date{color:#0a615e;}
.timeline li:nth-child(5n+2) .tl-date{color:#2b6cb0;}
.timeline li:nth-child(5n+3) .tl-date{color:#8a6528;}
.timeline li:nth-child(5n+4) .tl-date{color:#8f4a28;}
.timeline li:nth-child(5n+5) .tl-date{color:#55663a;}
.news-rows .news-row:nth-child(5n+2) .news-date{color:#2b6cb0;}
.news-rows .news-row:nth-child(5n+3) .news-date{color:#8a6528;}
.news-rows .news-row:nth-child(5n+4) .news-date{color:#8f4a28;}
.news-rows .news-row:nth-child(5n+5) .news-date{color:#55663a;}

/* ═══════════════════ HYPER-AQUARELLE — toute la page en lavis ═══════════════════ */
/* parcours coloré du fond : le papier se teinte au fil du défilement */
body{
  background:
    radial-gradient(52% 38% at 8% 2%,  rgba(26,157,154,.075), transparent 70%),
    radial-gradient(46% 34% at 94% 14%, rgba(74,148,201,.07), transparent 70%),
    radial-gradient(50% 36% at 6% 46%,  rgba(201,162,94,.06), transparent 70%),
    radial-gradient(48% 34% at 95% 66%, rgba(138,154,106,.06), transparent 70%),
    radial-gradient(50% 36% at 10% 96%, rgba(180,113,79,.055), transparent 70%),
    var(--paper);
}
/* labels en dégradé d'encres (fallback solide conservé) */
.label{color:#0a615e;}
@supports (-webkit-background-clip: text){
  .label{background:linear-gradient(90deg,#0a615e 0%,#2b6cb0 52%,#8a6528 100%);
    -webkit-background-clip:text;background-clip:text;color:transparent;}
}
/* signature du nom : filet d'aquarelle sous la marque */
.brand-name{position:relative;}
.brand-name::after{content:"";position:absolute;left:.02em;right:.35em;bottom:-.28rem;height:5px;
  border-radius:3px;opacity:.85;
  background:linear-gradient(90deg,#1a9d9a 0%,#4a94c9 38%,#8a9a6a 66%,#c9a25e 100%);}
/* menu : soulignements arc-en-ciel, une teinte par rubrique */
.site-nav ul li:nth-child(1) a:not(.nav-close)::after{background:linear-gradient(90deg,#1a9d9a,#4a94c9);}
.site-nav ul li:nth-child(2) a:not(.nav-close)::after{background:linear-gradient(90deg,#4a94c9,#8a9a6a);}
.site-nav ul li:nth-child(3) a:not(.nav-close)::after{background:linear-gradient(90deg,#8a9a6a,#c9a25e);}
.site-nav ul li:nth-child(4) a:not(.nav-close)::after{background:linear-gradient(90deg,#c9a25e,#b4714f);}
.site-nav ul li:nth-child(5) a:not(.nav-close)::after{background:linear-gradient(90deg,#b4714f,#1a9d9a);}
/* bouton principal : aplat dégradé + halo d'aquarelle au survol */
.btn{
  background:linear-gradient(135deg,#0f7a77 0%,#11596a 55%,#2b6cb0 100%);
  color:#fff;border-color:transparent;
  box-shadow:0 10px 26px -14px rgba(17,89,106,.55);
}
.btn:hover{filter:brightness(1.12);box-shadow:0 16px 34px -14px rgba(26,157,154,.65);}
.btn-outline{background:transparent;color:var(--teal-ink);border-color:var(--teal);
  box-shadow:none;}
.btn-outline:hover{background:var(--teal);color:#fff;}
/* filets d'aquarelle : les lignes plates deviennent des fils colorés */
.page-head{border-bottom:2px solid transparent;
  border-image:linear-gradient(90deg,#1a9d9a,#4a94c9,#8a9a6a,#c9a25e,#b4714f) 1;}
.section-artist,.section-expos,.map-section{border-top:2px solid transparent;
  border-image:linear-gradient(90deg,#1a9d9a,#4a94c9,#8a9a6a,#c9a25e,#b4714f) 1;}
.spectrum{height:10px;
  box-shadow:0 6px 22px -8px rgba(26,157,154,.5);}
/* lavis propres à chaque rubrique */
.pg-artist .page-head,.pg-artiste .page-head{background:
  radial-gradient(60% 80% at 12% 0%,rgba(201,162,94,.16),transparent 60%),
  radial-gradient(55% 75% at 90% 15%,rgba(26,157,154,.12),transparent 60%),
  linear-gradient(180deg,#f7f1e4,var(--paper));}
.pg-gallery .page-head,.pg-work .page-head,.pg-aquarelles .page-head,.pg-oeuvre .page-head{background:
  radial-gradient(55% 78% at 85% -5%,rgba(74,148,201,.15),transparent 62%),
  radial-gradient(50% 72% at 8% 20%,rgba(26,157,154,.14),transparent 60%),
  radial-gradient(45% 60% at 92% 95%,rgba(201,162,94,.11),transparent 65%),
  linear-gradient(180deg,#f2f6fb,var(--paper));}
.pg-news_list .page-head,.pg-news_item .page-head,.pg-actualites .page-head,.pg-actualite .page-head{background:
  radial-gradient(58% 80% at 10% 0%,rgba(74,148,201,.14),transparent 62%),
  radial-gradient(50% 70% at 92% 30%,rgba(138,154,106,.11),transparent 62%),
  linear-gradient(180deg,#eef5fb,var(--paper));}
.pg-contact .page-head{background:
  radial-gradient(55% 78% at 88% -5%,rgba(26,157,154,.15),transparent 60%),
  radial-gradient(50% 70% at 8% 25%,rgba(138,154,106,.12),transparent 60%),
  linear-gradient(180deg,#f0f5ef,var(--paper));}
/* cadres : passe-partouts teintés qui alternent + halo coloré au survol */
.work-frame{background:#fffdf9;}
.work:nth-child(3n) .work-frame{background:#f8fcfb;}
.work:nth-child(3n+1) .work-frame{background:#fdfbf6;}
.work:nth-child(3n+2) .work-frame{background:#f9faf6;}
.work:hover .work-frame{box-shadow:0 22px 46px -18px rgba(26,157,154,.45);}
.work[data-tn="Terne"]:hover .work-frame{box-shadow:0 22px 46px -18px rgba(201,162,94,.45);}
.work-figure picture{box-shadow:0 24px 52px -20px rgba(17,89,106,.4);}
/* cartes & encadrés : liseré d'aquarelle en tête */
.contact-card,.fact-card{border-top:3px solid transparent;
  border-image:linear-gradient(90deg,#1a9d9a,#4a94c9 45%,#c9a25e) 1;}
/* pied de page : lueur d'aquarelle sur le bleu nuit */
.site-footer{background:
  radial-gradient(70% 90% at 15% 0%,rgba(26,157,154,.16),transparent 60%),
  radial-gradient(60% 80% at 85% 10%,rgba(74,148,201,.10),transparent 60%),
  #0f2e35;}

/* ═══════════════════ RESPONSIVE+ — du 320 px au grand écran ═══════════════════ */
/* cibles tactiles confortables (doigt ≈ 44 px) */
@media (hover:none){
  .btn,.filter-btn,.work-nav-link{min-height:46px;}
  .filter-btn{padding:.65rem 1.3rem;}
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
  .hero{padding-top:5.6rem;}
  .hero-inner{margin-bottom:2.2rem;}
  .page-head{padding-top:clamp(7.2rem,18vw,9rem);}
  .section-head{flex-direction:column;align-items:flex-start;gap:.9rem;}
  .news-row{align-items:flex-start;}
  .news-title{font-size:1.18rem;}
  .timeline a{flex-wrap:wrap;gap:.45rem 1rem;}
  .tl-date{flex-basis:100%;}
  .duo-line{font-size:1.16rem;}
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
  .duo-line{font-size:1.24rem;}
}
/* écrans larges : la galerie respire davantage */
@media (min-width:1500px){
  :root{--w-container:1280px;}
  .gallery-grid{gap:3rem 2.6rem;}
}
/* mode impression : papier propre, œuvres avant tout */
@media print{
  .site-header,.site-footer,.spectrum,.cookie-bar,.map-wrap,.hero-wash,
  .contact-invitation,.next-teaser,.work-nav,.filter-bar{display:none !important;}
  body{background:#fff;color:#000;font-size:12pt;}
  .work-frame,.work-figure picture{box-shadow:none;border:1px solid #999;}
  .reveal{opacity:1;transform:none;}
}

/* ═══════════════════ ATELIER — photos & visionneuse ═══════════════════ */
.pg-atelier .page-head{background:
  radial-gradient(60% 80% at 10% 0%,rgba(201,162,94,.20),transparent 60%),
  radial-gradient(55% 75% at 92% 12%,rgba(138,154,106,.18),transparent 60%),
  linear-gradient(180deg,#f6f1e3,var(--paper));}
.atelier-note{margin:0 0 1.6rem;color:var(--muted);font-size:.95rem}
.atelier-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:1.6rem}
.atelier-item{margin:0;background:var(--card);border:1px solid rgba(26,157,154,.16);
  border-radius:10px;padding:10px;box-shadow:var(--shadow-soft);
  transition:transform .35s ease,box-shadow .35s ease}
.atelier-item:nth-child(3n+2){background:#f3f4eb;border-color:rgba(138,154,106,.30)}
.atelier-item:nth-child(3n){background:#f8f1e2;border-color:rgba(201,162,94,.32)}
.atelier-item:hover{transform:translateY(-5px);
  box-shadow:0 18px 40px -18px rgba(26,157,154,.55)}
.atelier-btn{display:block;width:100%;padding:0;border:0;background:none;cursor:zoom-in;
  border-radius:6px;overflow:hidden}
.atelier-btn:focus-visible{outline:2px solid var(--teal);outline-offset:3px}
.atelier-btn img{display:block;width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:6px;
  transition:transform .5s ease}
.atelier-item:hover .atelier-btn img{transform:scale(1.04)}
.portrait-card{margin:0 0 1.4rem;background:var(--card);border:1px solid rgba(201,162,94,.35);
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
.hl-lb-btn:hover{background:rgba(26,157,154,.55)}
.hl-lb-prev{left:14px}.hl-lb-next{right:14px}
.hl-lb-close{position:absolute;top:14px;right:14px;min-width:46px;min-height:46px;
  border-radius:50%;border:1px solid rgba(255,255,255,.4);background:rgba(255,255,255,.12);
  color:#fff;font-size:1.05rem;cursor:pointer}
.hl-lb-close:hover{background:rgba(26,157,154,.55)}
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
  radial-gradient(42rem 30rem at 6% 3%,rgba(26,157,154,.17),transparent 62%),
  radial-gradient(38rem 26rem at 96% 10%,rgba(74,148,201,.16),transparent 60%),
  radial-gradient(44rem 30rem at 3% 40%,rgba(201,162,94,.13),transparent 62%),
  radial-gradient(40rem 28rem at 97% 58%,rgba(138,154,106,.14),transparent 60%),
  radial-gradient(46rem 32rem at 50% 97%,rgba(180,113,79,.13),transparent 62%);}
/* bandes alternées à peine teintées : la couleur monte à chaque section */
.main .section:nth-of-type(even):not([class*="tint-"]):not(.wash-band){background:
  linear-gradient(180deg,rgba(26,157,154,.05),rgba(74,148,201,.04) 55%,rgba(201,162,94,.05));}
.main .section:nth-of-type(odd):not([class*="tint-"]):not(.wash-band){background:
  linear-gradient(180deg,rgba(138,154,106,.035),rgba(180,113,79,.035) 60%,rgba(26,157,154,.045));}
/* titres en dégradé d'encre (encres toutes validées AA sur papier) */
@supports ((-webkit-background-clip:text) or (background-clip:text)){
  .page-title,.h2,.fact-title,.big-quote,.hero-baseline{
    background:linear-gradient(100deg,#0a615e 0%,#2b6cb0 48%,#8a6528 100%);
    -webkit-background-clip:text;background-clip:text;
    -webkit-text-fill-color:transparent;}
  .site-footer .footer-title,.footer-col .brand-name{
    background:linear-gradient(90deg,#9fd8d2,#a8cfe8 48%,#e2c289);
    -webkit-background-clip:text;background-clip:text;
    -webkit-text-fill-color:transparent;}
}
/* en-têtes de rubrique : lavis plus généreux */
.page-head{background:
  radial-gradient(60% 85% at 8% 0%,rgba(26,157,154,.18),transparent 62%),
  radial-gradient(55% 80% at 92% 8%,rgba(201,162,94,.16),transparent 60%),
  radial-gradient(45% 65% at 50% 100%,rgba(74,148,201,.10),transparent 65%),
  linear-gradient(180deg,#f6f4ec,var(--paper)) !important;}
.pg-artist .page-head,.pg-artiste .page-head{background:
  radial-gradient(60% 80% at 12% 0%,rgba(201,162,94,.28),transparent 62%),
  radial-gradient(55% 75% at 90% 15%,rgba(26,157,154,.20),transparent 60%),
  radial-gradient(40% 55% at 55% 100%,rgba(180,113,79,.12),transparent 65%),
  linear-gradient(180deg,#f8f0dc,var(--paper)) !important;}
.pg-gallery .page-head,.pg-work .page-head,.pg-aquarelles .page-head,.pg-oeuvre .page-head{background:
  radial-gradient(55% 78% at 85% -5%,rgba(74,148,201,.27),transparent 62%),
  radial-gradient(50% 72% at 8% 20%,rgba(26,157,154,.22),transparent 60%),
  radial-gradient(45% 60% at 92% 95%,rgba(201,162,94,.18),transparent 65%),
  linear-gradient(180deg,#eaf2fb,var(--paper)) !important;}
.pg-news_list .page-head,.pg-news_item .page-head,.pg-actualites .page-head,.pg-actualite .page-head{background:
  radial-gradient(58% 80% at 10% 0%,rgba(74,148,201,.24),transparent 62%),
  radial-gradient(50% 70% at 92% 30%,rgba(138,154,106,.18),transparent 62%),
  radial-gradient(42% 58% at 45% 100%,rgba(26,157,154,.14),transparent 65%),
  linear-gradient(180deg,#e9f2fa,var(--paper)) !important;}
.pg-contact .page-head{background:
  radial-gradient(55% 78% at 88% -5%,rgba(26,157,154,.26),transparent 60%),
  radial-gradient(50% 70% at 8% 25%,rgba(138,154,106,.20),transparent 60%),
  linear-gradient(180deg,#eaf3ea,var(--paper)) !important;}
.pg-atelier .page-head{background:
  radial-gradient(60% 80% at 10% 0%,rgba(201,162,94,.30),transparent 62%),
  radial-gradient(55% 75% at 92% 12%,rgba(138,154,106,.26),transparent 60%),
  radial-gradient(42% 58% at 50% 100%,rgba(180,113,79,.14),transparent 65%),
  linear-gradient(180deg,#f8f0dd,var(--paper)) !important;}
/* rubriques teintées : saturation doucement augmentée */
.tint-sand{background:linear-gradient(180deg,#f9f3e2,#f1e6cb);}
.tint-sky{background:linear-gradient(180deg,#e9f2fb,#dcebf9);}
.tint-sage{background:linear-gradient(180deg,#edf3e6,#e0ebd2);}
.wash-band{background:
  radial-gradient(60% 120% at 20% 50%,rgba(26,157,154,.20),transparent 60%),
  radial-gradient(50% 100% at 85% 40%,rgba(74,148,201,.16),transparent 62%),
  radial-gradient(45% 90% at 55% 110%,rgba(201,162,94,.12),transparent 65%);}
/* spectre plus présent, avec lueur */
.spectrum{height:14px;
  box-shadow:0 -8px 22px -8px rgba(26,157,154,.5),0 8px 22px -8px rgba(201,162,94,.45);}
/* en-tête fixe : liseré arc-en-ciel dès qu'on défile */
.site-header.is-scrolled{border-bottom:2px solid transparent;
  border-image:linear-gradient(90deg,#1a9d9a,#4a94c9,#8a9a6a,#c9a25e,#b4714f) 1;
  box-shadow:0 12px 30px -20px rgba(74,148,201,.45);}
/* menu : chaque rubrique prend sa couleur d'encre (AA) */
.site-nav ul li:nth-child(1) a:not(.nav-close):hover,
.site-nav ul li:nth-child(1) a[aria-current="page"]{color:#0a615e;}
.site-nav ul li:nth-child(2) a:not(.nav-close):hover,
.site-nav ul li:nth-child(2) a[aria-current="page"]{color:#2b6cb0;}
.site-nav ul li:nth-child(3) a:not(.nav-close):hover,
.site-nav ul li:nth-child(3) a[aria-current="page"]{color:#8a6528;}
.site-nav ul li:nth-child(4) a:not(.nav-close):hover,
.site-nav ul li:nth-child(4) a[aria-current="page"]{color:#8f4a28;}
.site-nav ul li:nth-child(5) a:not(.nav-close):hover,
.site-nav ul li:nth-child(5) a[aria-current="page"]{color:#55663a;}
.site-nav ul li:nth-child(6) a:not(.nav-close):hover,
.site-nav ul li:nth-child(6) a[aria-current="page"]{color:#0a615e;}
/* boutons : double halo coloré, éclat au survol (dégradé AA inchangé) */
.btn{box-shadow:0 12px 32px -12px rgba(26,157,154,.6),0 8px 26px -14px rgba(74,148,201,.5);
  transition:background .3s,color .3s,border-color .3s,box-shadow .3s,transform .3s,filter .3s;}
.btn:hover{filter:saturate(1.18) brightness(1.05);transform:translateY(-2px);}
/* fiche « En un regard » : liseré d'aquarelle */
.fact-card{border-top:4px solid transparent;
  border-image:linear-gradient(90deg,#1a9d9a,#4a94c9,#8a9a6a,#c9a25e,#b4714f) 1;}
/* héros : voile multicolore au-dessus du lavis SVG */
.hero::after{content:"";position:absolute;inset:0;z-index:0;pointer-events:none;background:
  radial-gradient(55% 45% at 85% 12%,rgba(74,148,201,.20),transparent 62%),
  radial-gradient(45% 40% at 8% 30%,rgba(26,157,154,.16),transparent 60%),
  radial-gradient(50% 45% at 60% 95%,rgba(201,162,94,.14),transparent 62%);}
/* pied de page : nuit bleutée traversée de lueurs */
.site-footer{background:
  radial-gradient(50rem 20rem at 12% 0%,rgba(26,157,154,.25),transparent 60%),
  radial-gradient(46rem 18rem at 88% 8%,rgba(74,148,201,.20),transparent 62%),
  radial-gradient(40rem 16rem at 50% 112%,rgba(201,162,94,.16),transparent 60%),
  linear-gradient(180deg,#123840,#0f2e35 45%,#0b2530);}
.footer-list a:hover{color:#9fd8d2;border-color:rgba(159,216,210,.5);}
/* détails */
::selection{background:rgba(26,157,154,.30);}
.lnk{border-bottom-color:rgba(43,108,176,.45);}
.lnk:hover{color:#2b6cb0;}
.link-arrow:hover{color:#8f4a28;}
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
  background:linear-gradient(180deg,#fffdf9,#faf5ea);border:1px solid rgba(201,162,94,.5);
  border-radius:6px;box-shadow:var(--shadow-soft)}
.vif-def::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;
  border-radius:6px 0 0 6px;
  background:linear-gradient(180deg,#1a9d9a,#4a94c9,#8a9a6a,#c9a25e,#b4714f)}
.vif-def-title{font-family:var(--sans);font-weight:600;font-size:.76rem;letter-spacing:.18em;
  text-transform:uppercase;color:#8a6528;margin:0 0 .55rem}
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
  color:#8a6528;white-space:nowrap}
.vif-badge::before,.vif-badge::after{content:"·";margin:0 .45em;color:#c9a25e}
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


/* ═══════════════ RYTHME & ULTRA-RESPONSIVE — espacements harmonisés ═══════════════ */
:root{--gap:clamp(1.15rem,2.6vw,1.9rem);}
html,body{overflow-x:clip;}
img,picture,svg,video{max-width:100%;}
.section{padding:clamp(3.4rem,8vw,6.4rem) 0;}
.section-head{margin-bottom:clamp(1.7rem,4vw,2.6rem);gap:1.2rem;}
.gallery-grid{gap:var(--gap);}
.atelier-grid{gap:var(--gap);}
.duo-grid{gap:var(--gap);}
.news-row{padding:clamp(1.15rem,3vw,1.65rem) .4rem;}
.timeline a{padding:clamp(1.05rem,2.6vw,1.4rem) .4rem;}
.gallery-count{margin-top:clamp(1.6rem,4vw,2.6rem);}
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
  .filter-btn{padding:.5rem .7rem;font-size:.7rem;}
}
@media (hover:none){
  .filter-btn,.footer-list a,.site-nav a:not(.nav-close),.icon-btn,.btn-tiny{min-height:46px;}
  .work:hover .work-frame,.atelier-item:hover{transform:none;}
  .atelier-item:hover .atelier-btn img{transform:none;}
}
@media (orientation:landscape) and (max-height:540px){
  .hero{min-height:auto;padding-top:5.2rem;}
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
  .filter-bar{width:min(1760px,94vw);}
}
@media (min-width:1600px){
  .gallery-section .container,.filter-bar{width:min(1920px,94vw);}
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
.duo-panel,.msg-card,.form-card{border-radius:var(--r-card);box-shadow:var(--shadow-soft);}
.atelier-btn img,.atelier-btn,.work-frame img,.news-thumb img,
.hl-lightbox img{border-radius:var(--r-img);}
.btn,.filter-btn,.icon-btn,.btn-tiny,.btn-primary,.btn-secondary{border-radius:var(--r-btn);}
/* boutons : même gabarit, même geste */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.5rem;
  min-height:48px;padding:.85rem clamp(1.2rem,2.4vw,2rem);text-align:center;}
.btn,.work-frame,.atelier-item,.filter-btn{transition:all .35s var(--t-soft);}
/* titres : même respiration */
h1,h2,h3{margin:0 0 .5em;}
/* focus unique et visible */
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,
textarea:focus-visible,[tabindex]:focus-visible{outline:2px solid var(--teal);
  outline-offset:2px;border-radius:var(--r-btn);}
/* grilles : écart unique */
.gallery-grid,.atelier-grid,.duo-grid,.news-rows{gap:var(--gap);}
/* ── hyper responsive : fluide du 320 px au 4K ── */
@media (max-width:340px){
  html{font-size:15px;}
  .container,.narrow{width:94vw;}
  .page-title{font-size:clamp(1.7rem,9vw,2.1rem);}
  .page-sub{font-size:1rem;}
  .filter-btn{padding:.5rem .65rem;letter-spacing:.08em;}
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
  .btn,.filter-btn,.icon-btn,.btn-tiny,.hl-lb-btn,.hl-lb-close,
  .nav-toggle{min-height:48px;min-width:48px;}
}


/* ═══════ PORTE DE PUBLICATION — carte d'accueil de la clé ═══════ */
.gh-gate{max-width:780px;margin:0 auto 2.2rem;background:linear-gradient(180deg,#fffdf9,#f8f3e8);
  border:1px solid rgba(201,162,94,.4);border-top:4px solid;
  border-image:linear-gradient(90deg,#1a9d9a,#4a94c9,#8a9a6a,#c9a25e,#b4714f) 1;
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
    radial-gradient(70% 40% at 15% 6%,rgba(26,157,154,.10),transparent 60%),
    radial-gradient(60% 35% at 88% 18%,rgba(74,148,201,.10),transparent 60%),
    radial-gradient(75% 45% at 50% 100%,rgba(201,162,94,.12),transparent 65%),
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

/* conformité cookies & porte carte */
.cookie-bar{position:fixed;left:50%;bottom:1.1rem;transform:translateX(-50%);z-index:160;
width:min(860px,94vw);background:var(--card);border:1px solid var(--hair);
border-top:2px solid var(--teal);border-radius:4px;box-shadow:var(--sh);padding:1rem 1.3rem}
.cookie-inner{display:flex;gap:1.4rem;align-items:center;justify-content:space-between;flex-wrap:wrap}
.cookie-txt{margin:0;font-size:.92rem;max-width:52em;color:var(--text)}
.cookie-actions{display:flex;gap:.8rem;margin:0}
.cookie-actions .btn{padding:.68rem 1.3rem;font-size:.74rem}
.map-consent{min-height:300px;display:flex;align-items:center;justify-content:center;text-align:center;
background:radial-gradient(70% 90% at 50% 110%,rgba(26,157,154,.10),transparent 70%),var(--paper)}
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
.edit[contenteditable]{outline:1px dashed rgba(26,157,154,.55);outline-offset:4px;
cursor:text;border-radius:2px}
.edit[contenteditable]:focus{outline:2px solid var(--teal);background:rgba(26,157,154,.05)}
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
        <li><a href="#/artiste" data-r="artiste">L’artiste</a></li>
        <li><a href="#/atelier" data-r="atelier">L’atelier</a></li>
        <li><a href="#/aquarelles" data-r="aquarelles">Aquarelles</a></li>
        <li><a href="#/actualites" data-r="actualites">Actualités</a></li>
        <li><a href="#/contact" data-r="contact">Contact</a></li>
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
      <p class="footer-baseline">Artiste aquarelliste<br>Aquarelles — mer &amp; paysage</p>
      <p class="footer-loc">Yvetot-Bocage · Normandie</p>
    </div>
    <div class="footer-col">
      <h2 class="footer-title">Contact</h2>
      <ul class="footer-list" id="footer-contact"></ul>
    </div>
    <div class="footer-col">
      <h2 class="footer-title">Le site</h2>
      <ul class="footer-list">
        <li><a href="#/artiste">L’artiste</a></li>
        <li><a href="#/atelier">L’atelier</a></li>
        <li><a href="#/aquarelles">Les aquarelles</a></li>
        <li><a href="#/actualites">Actualités &amp; expositions</a></li>
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
    <p class="cookie-txt">Ce fichier ne dépose aucun cookie. La carte de la page Contact
       (tuiles OpenStreetMap) ne se charge qu’avec votre accord.
       <a class="lnk" href="#/confidentialite">En savoir plus</a></p>
    <p class="cookie-actions">
      <button class="btn" id="ck-accept" type="button">Accepter</button>
      <button class="btn btn-outline" id="ck-refuse" type="button">Refuser</button>
    </p>
  </div>
</aside>
<script>__LEAFLET_JS__</script>
<script>
"use strict";
var DATA = /*HLDATA*/__DATA__/*HLDATA-END*/;
var PRISTINE="<!DOCTYPE html>\n"+document.documentElement.outerHTML;
try{var SAVED=JSON.parse(localStorage.getItem("hl_data")||"null");
    if(SAVED&&SAVED.data){DATA=SAVED.data;if(!DATA.atelier)DATA.atelier=[];if(!DATA.photos)DATA.photos=DATA.palette?[DATA.palette]:[];}}catch(e){}
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
  '" data-cat="'+esc(w.c)+'" data-tn="'+esc(w.tn||"")+'"><span class="work-frame"><img loading="lazy" alt="Aquarelle — '+
  esc(w.t)+(w.c?" — "+esc(w.c):"")+'" src="'+w.i+'"></span><span class="work-caption">'+
  '<span class="work-title">'+esc(w.t)+'</span><span class="work-meta">'+esc(meta(w))+
  '</span></span></a>';}
function newsRow(n,excerpt){return '<a class="news-row" href="#/actualite/'+n.s+'">'+
  (n.cov?'<span class="news-thumb"><img loading="lazy" alt="'+esc(n.t)+'" src="'+n.cov+'"></span>':"")+
  '<span class="news-body">'+(n.dt?'<span class="news-date">'+esc(n.dt)+'</span>':"")+
  '<span class="news-title">'+esc(n.t)+'</span>'+
  (excerpt&&n.p[0]?'<span class="news-excerpt">'+esc(n.p[0].slice(0,160))+
   (n.p[0].length>160?"…":"")+'</span>':"")+
  '</span><span class="news-arrow" aria-hidden="true">→</span></a>';}
var QUOTE='<svg class="quote-mark" viewBox="0 0 72 48" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">'+
'<path d="M8 40c10-4 16-12 16-24-7 1-12-3-12-9S17-2 23-2c8 0 13 6 13 14 0 16-10 26-24 30z" transform="translate(8 4)" fill="#1a9d9a" opacity=".45"/>'+
'<path d="M8 40c10-4 16-12 16-24-7 1-12-3-12-9S17-2 23-2c8 0 13 6 13 14 0 16-10 26-24 30z" transform="translate(34 4)" fill="#1a9d9a" opacity=".28"/></svg>';
var WASH='<div class="hero-wash" aria-hidden="true"><svg viewBox="0 0 1400 700" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg"><defs><filter id="wc" x="-20%" y="-20%" width="140%" height="140%"><feTurbulence type="fractalNoise" baseFrequency="0.012 0.02" numOctaves="3" seed="7" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="90"/><feGaussianBlur stdDeviation="7"/></filter></defs><g filter="url(#wc)"><ellipse cx="980" cy="150" rx="380" ry="190" fill="#1a9d9a" opacity="0.20"/><ellipse cx="1150" cy="330" rx="300" ry="170" fill="#11596a" opacity="0.17"/><ellipse cx="820" cy="300" rx="240" ry="130" fill="#4db8ae" opacity="0.15"/><ellipse cx="180" cy="620" rx="320" ry="160" fill="#1a9d9a" opacity="0.15"/><ellipse cx="320" cy="140" rx="260" ry="140" fill="#4a94c9" opacity="0.10"/><ellipse cx="1260" cy="560" rx="300" ry="150" fill="#c9a25e" opacity="0.10"/><ellipse cx="540" cy="580" rx="220" ry="120" fill="#8a9a6a" opacity="0.08"/></g></svg></div>';

/* ------------------------------------------------------- pages --------- */
function pageHome(){
  var duo="";
  var cands=DATA.works.filter(function(w){return w.cf;});
  if(cands.length>=2){
    var viv=cands[0],mut=cands[0];
    cands.forEach(function(w){if(w.cf>viv.cf)viv=w;if(w.cf<mut.cf)mut=w;});
    if(viv!==mut)duo='<section class="section duo-section"><div class="container">'+
    '<div class="section-head reveal"><div><p class="label">La palette</p>'+
    '<h2 class="h2">Tantôt couleur,<br>tantôt silence</h2></div></div>'+
    '<div class="duo-grid reveal">'+
    '<a class="duo-panel duo-vivid" href="#/oeuvre/'+viv.s+'">'+
    '<span class="duo-figure"><img loading="lazy" src="'+viv.i+'" alt="Aquarelle colorée — '+esc(viv.t)+'"></span>'+
    '<span class="duo-txt"><span class="duo-tag">Colorée</span>'+
    '<span class="duo-line">Des couleurs franches, qui chantent.</span>'+
    '<span class="duo-see">Voir cette aquarelle</span></span></a>'+
    '<a class="duo-panel duo-mute" href="#/oeuvre/'+mut.s+'">'+
    '<span class="duo-figure"><img loading="lazy" src="'+mut.i+'" alt="Aquarelle terne — '+esc(mut.t)+'"></span>'+
    '<span class="duo-txt"><span class="duo-tag">Terne</span>'+
    '<span class="duo-line">Des gris doux, qui murmurent.</span>'+
    '<span class="duo-see">Voir cette aquarelle</span></span></a>'+
    '</div><p class="duo-note reveal">Certaines aquarelles d’Hilaire éclatent de couleurs vives&nbsp;; d’autres se retirent presque dans le gris du papier. La même eau, le même papier 100&nbsp;% coton — deux manières de regarder le paysage.</p>'+
    '</div></section>';
  }
  var frieze=DATA.works.slice(0,3).map(function(w,i){
    return '<a class="f'+(i+1)+'" href="#/oeuvre/'+w.s+'"><img'+(i>1?' loading="lazy"':'')+
      ' src="'+w.i+'" alt="Aquarelle — '+esc(w.t)+'"></a>';}).join("");
  var sel=DATA.works.slice(0,6).map(workCard).join("");
  var news=DATA.news.slice(0,3).map(function(n){return newsRow(n,false);}).join("");
  var fig=DATA.works[0];
  return '<section class="hero">'+WASH+
  '<div class="hero-inner"><p class="hero-baseline reveal">Aquarelles — mer &amp; paysage</p>'+
  '<h1 class="hero-title reveal d1">Hilaire Legentil</h1>'+
  '<p class="hero-sub reveal d2">Artiste aquarelliste — Normandie</p>'+
  '<p class="hero-intro reveal d3">'+esc(DATA.homeIntro)+'</p>'+
  '<p class="hero-cta reveal d3"><a class="btn" href="#/aquarelles">Découvrir les œuvres</a>'+
  '<a class="link-arrow" href="#/artiste">Découvrir son parcours</a></p></div>'+
  '<div class="frieze reveal d4">'+frieze+'</div></section>'+
  '<section class="section section-artist tint-sand"><div class="container artist-home">'+
  '<div class="reveal"><p class="label">L’artiste</p>'+
  '<h2 class="h2">Peindre la lumière,<br>l’eau et le silence</h2>'+
  '<p class="lead">'+esc(DATA.artistIntro)+'</p>'+
  '<blockquote class="mini-quote">« Cette passion m’est venue lors des confinements. Ces aquarelles sont réalisées sur du papier 100&nbsp;% coton, matière qui apporte une tonalité douce aux couleurs. »<cite>— Hilaire Legentil, Ouest-France, mai 2023</cite></blockquote>'+
  '<a class="link-arrow" href="#/artiste">Découvrir son parcours</a></div>'+
  (fig?'<div class="artist-home-figure reveal"><img src="'+fig.i+'" alt="Aquarelle — '+esc(fig.t)+'">'+
   '<span class="figure-caption">'+esc(fig.t)+'</span></div>':"")+
  '</div></section>'+
  '<section class="section"><div class="container"><div class="section-head reveal">'+
  '<div><p class="label">Les aquarelles</p><h2 class="h2">Une galerie à feuilleter</h2></div>'+
  '<a class="link-arrow" href="#/aquarelles">Voir toute la galerie</a></div>'+
  '<div class="gallery-grid">'+sel+'</div></div></section>'+
  duo+
  '<section class="section quote-section"><div class="container narrow center reveal">'+QUOTE+
  '<blockquote class="big-quote">Peindre, c’est voyager&nbsp;; peindre, c’est méditer. J’ai choisi d’être paysagiste car la nature m’apaise et me recentre.<cite>Hilaire Legentil</cite></blockquote></div></section>'+
  '<section class="section tint-sky"><div class="container"><div class="section-head reveal">'+
  '<div><p class="label">Actualités</p><h2 class="h2">Expositions &amp; nouvelles</h2></div>'+
  '<a class="link-arrow" href="#/actualites">Toutes les actualités</a></div>'+
  '<div class="news-rows">'+news+'</div></div></section>'+
  '<section class="section contact-invitation"><div class="container narrow reveal">'+
  '<p class="label">Prendre contact</p><h2 class="h2">Une question, une œuvre, un projet&nbsp;?</h2>'+
  '<p class="lead">Renseignement sur une aquarelle, commande d’un tableau, projet particulier ou exposition&nbsp;: écrivez à Hilaire, il vous répond personnellement.</p>'+
  '<p class="invitation-cta"><a class="btn" href="#/contact">Écrire à Hilaire</a>'+
  '<a class="link-arrow" href="#/contact?sujet=Demande%20sp%C3%A9cifique">Faire une demande spécifique</a></p></div></section>';
}

function pageArtist(){
  var tl=DATA.news.map(function(n){
    return '<li><a href="#/actualite/'+n.s+'"><span class="tl-date">'+esc(n.dt)+'</span>'+
    '<span class="tl-title">'+esc(n.t)+'</span><span class="tl-arrow" aria-hidden="true">→</span></a></li>';}).join("");
  return '<header class="page-head"><div class="container reveal"><p class="label">L’artiste</p>'+
  '<h1 class="page-title">Hilaire Legentil</h1>'+
  '<p class="page-sub">Artiste aquarelliste · Aquarelles — mer &amp; paysage</p></div></header>'+
  '<section class="section"><div class="container two-col">'+
  '<div class="reveal"><p class="lead">'+esc(DATA.artistIntro)+'</p>'+
  '<p>Sa signature tient en quelques mots imprimés sur sa carte&nbsp;: <em>«&nbsp;Aquarelles — mer &amp; paysage&nbsp;»</em>. De la pointe de Barfleur aux horizons bocagers du Cotentin, il peint ce qu’il regarde&nbsp;: la mer, les ciels, la terre — des paysages apaisés, d’une tonalité douce.</p></div>'+
  '<aside class="reveal"><figure class="portrait-card">'+
  '<img src="'+DATA.portrait+'" alt="Portrait de Hilaire Legentil" width="302" height="452" loading="lazy">'+
  '<figcaption>Hilaire Legentil</figcaption></figure>'+
  '<div class="fact-card"><h2 class="fact-title">En un regard</h2>'+
  '<dl class="fact-list"><div><dt>Art</dt><dd>Aquarelle</dd></div>'+
  '<div><dt>Sujets</dt><dd>Mer &amp; paysage</dd></div>'+
  '<div><dt>Support</dt><dd>Papier 100&nbsp;% coton</dd></div>'+
  '<div><dt>Région</dt><dd>Normandie — Yvetot-Bocage (Manche)</dd></div></dl></div></aside></div></section>'+
  '<section class="section wash-band"><div class="container narrow center reveal">'+QUOTE+
  '<blockquote class="big-quote">Peindre, c’est voyager&nbsp;; peindre, c’est méditer. J’ai choisi d’être paysagiste car la nature m’apaise et me recentre.<cite>Hilaire Legentil</cite></blockquote></div></section>'+
  '<section class="section"><div class="container two-col">'+
  '<div class="reveal"><p class="label">La démarche</p><h2 class="h2">Ce que l’eau<br>emporte, ce qu’elle laisse</h2>'+
  '<p>C’est pendant les confinements que la passion de l’aquarelle s’est imposée. Depuis, Hilaire Legentil peint sur papier 100&nbsp;% coton, une matière qu’il aime pour la <em>tonalité douce</em> qu’elle apporte aux couleurs.</p>'+
  '<p>Paysagiste, il cherche dans la nature ce qui l’apaise et le recentre&nbsp;: la mer et ses marées, les rivages de la Manche, les lumières changeantes du Cotentin.</p>'+
  '<p>Selon la lumière et l’humeur du paysage, ses aquarelles assument deux registres&nbsp;: des couleurs franches, parfois presque vives, puis soudain des gammes ternes et douces, proches du papier.</p></div>'+
  '<div class="reveal"><p class="label">La matière</p><h2 class="h2">Le papier,<br>l’eau, la couleur</h2>'+
  '<p>Chaque aquarelle est réalisée sur un papier 100&nbsp;% coton, choisi pour sa douceur et sa longévité. Le coton absorbe l’eau lentement&nbsp;: les couleurs se posent en transparences successives, les ciels gardent la trace du geste.</p>'+
  '<p>Pour toute information sur une pièce, sa disponibilité ou un projet, <a class="lnk" href="#/contact">écrivez à Hilaire</a>.</p></div></div></section>'+
  '<section class="section section-expos tint-sage"><div class="container">'+
  '<div class="section-head reveal"><div><p class="label">Expositions</p>'+
  '<h2 class="h2">Rencontrer les aquarelles</h2></div>'+
  '<a class="link-arrow" href="#/actualites">Toutes les actualités</a></div>'+
  '<ol class="timeline">'+tl+'</ol></div></section>'+
  '<section class="section contact-invitation"><div class="container narrow center reveal">'+
  '<h2 class="h2">Un projet, une demande particulière&nbsp;?</h2>'+
  '<p class="lead">Hilaire étudie toute demande&nbsp;: aquarelle sur commande, projet, exposition.</p>'+
  '<p class="invitation-cta"><a class="btn" href="#/contact">Contacter l’artiste</a></p></div></section>';
}

function pageGallery(){
  var cats=[];DATA.works.forEach(function(w){if(w.c&&cats.indexOf(w.c)<0)cats.push(w.c);});
  var vifSec=DATA.atelier.length?
    '<section class="section"><div class="container">'+
    '<div class="section-head reveal"><div><p class="label">Sur le vif</p><h2 class="h2">Peintes devant le sujet</h2></div></div>'+
    '<aside class="vif-def reveal"><p class="vif-def-title">Qu’est-ce qu’une aquarelle « sur le vif » ?</p>'+
    '<p>Peinte directement <strong>devant le sujet</strong>, en une séance, sans photographie ni retour en atelier — on dit aussi <em>« sur le motif »</em>. La lumière du moment, la marée, le vent : tout décide du rythme, et l’eau est saisie sur place, dans l’instant.</p></aside>'+
    '<p class="atelier-note reveal">Une sélection d’aquarelles réalisées par Hilaire sur le vif — cliquez pour agrandir, puis naviguez avec les flèches du clavier.</p>'+
    '<div class="atelier-grid" id="atelier-grid" data-cap="Aquarelle sur le vif">'+
    DATA.atelier.map(function(p,i){return '<figure class="atelier-item reveal"><span class="vif-badge" aria-hidden="true">sur le vif</span>'+
      '<button type="button" class="atelier-btn" aria-label="Agrandir l’aquarelle '+(i+1)+' sur '+DATA.atelier.length+'">'+
      '<img loading="lazy" decoding="async" src="'+p.i+'" alt="Aquarelle sur le vif — '+(i+1)+'"></button></figure>';}).join("")+
    '</div></div></section>':"";
  var bar='<div class="container filter-bar" role="group" aria-label="Trier les œuvres">'+
    '<button class="filter-btn on" data-f="*">Toutes</button>'+
    '<button class="filter-btn" data-f="tn:Colorée">Colorées</button>'+
    '<button class="filter-btn" data-f="tn:Terne">Ternes</button>'+
    cats.map(function(c){return '<button class="filter-btn" data-f="'+escA(c)+'">'+esc(c)+'</button>';}).join("")+
    '</div>';
  return '<header class="page-head"><div class="container reveal"><p class="label">La galerie</p>'+
  '<h1 class="page-title">Les aquarelles</h1>'+
  '<p class="page-sub">Mer &amp; paysage — aquarelles originales sur papier 100&nbsp;% coton</p></div></header>'+
  bar+
  '<section class="section gallery-section"><div class="container">'+
  '<div class="gallery-grid" id="grid">'+DATA.works.map(workCard).join("")+'</div>'+
  '<p class="gallery-count" id="gcount"></p></div></section>'+
  vifSec+
  '<section class="section contact-invitation"><div class="container narrow center reveal">'+
  '<h2 class="h2">Une aquarelle vous touche&nbsp;?</h2>'+
  '<p class="lead">Pour toute information sur une œuvre, écrivez à Hilaire&nbsp;: disponibilité, format, acquisition.</p>'+
  '<p class="invitation-cta"><a class="btn" href="#/contact">Demander des informations</a></p></div></section>';
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
  return '<header class="page-head"><div class="container reveal"><p class="label">Aquarelle</p>'+
  '<h1 class="page-title">'+esc(w.t)+'</h1><p class="page-sub">'+esc(meta(w))+'</p></div></header>'+
  '<section class="section"><div class="container work-layout">'+
  '<figure class="work-figure reveal"><img src="'+w.i+'" alt="Aquarelle « '+esc(w.t)+' » d’Hilaire Legentil">'+
  '<figcaption class="work-tech">Aquarelle originale sur papier 100&nbsp;% coton</figcaption></figure>'+
  '<aside class="reveal"><dl class="work-facts">'+facts+'</dl>'+
  (w.d?'<div class="article-body">'+w.d.split("\n").map(function(p){return '<p>'+esc(p)+'</p>';}).join("")+'</div>':"")+
  (ADMIN?'<a class="btn btn-outline btn-full" style="margin-bottom:1rem" href="#/admin">✎ Modifier titre, description…</a>':"")+
  '<a class="btn btn-full" href="#/contact?sujet='+encodeURIComponent("Demande d’information — aquarelle « "+w.t+" »")+'">Demander des informations</a>'+
  '<nav class="work-nav" aria-label="Navigation entre les œuvres">'+
  '<a class="work-nav-link" href="#/oeuvre/'+prev.s+'"><span class="wn-label">Œuvre précédente</span>'+
  '<span class="wn-title">'+esc(prev.t)+'</span></a>'+
  '<a class="work-nav-link is-next" href="#/oeuvre/'+next.s+'"><span class="wn-label">Œuvre suivante</span>'+
  '<span class="wn-title">'+esc(next.t)+'</span></a></nav>'+
  '<p class="work-counter">'+(idx+1)+' / '+DATA.works.length+' — <a class="lnk" href="#/aquarelles">retour à la galerie</a></p></aside>'+
  '</div></section>'+
  '<section class="section next-teaser"><div class="container teaser-inner">'+
  '<div class="reveal"><p class="label">À voir ensuite</p><h2 class="h3">'+esc(next.t)+'</h2>'+
  '<a class="link-arrow" href="#/oeuvre/'+next.s+'">Voir l’œuvre suivante</a></div>'+
  '<a class="teaser-figure reveal" href="#/oeuvre/'+next.s+'"><img loading="lazy" src="'+next.i+'" alt=""></a>'+
  '</div></section>';
}

function pageNews(){
  return '<header class="page-head"><div class="container reveal"><p class="label">Actualités</p>'+
  '<h1 class="page-title">Expositions &amp; nouvelles</h1>'+
  '<p class="page-sub">Où voir les aquarelles d’Hilaire Legentil</p></div></header>'+
  (ADMIN?'<section class="section" style="padding:0 0 1rem"><div class="container adm-bar">'+
  '<a class="btn" href="#/admin">+ Écrire une actualité</a></div></section>':"")+
  '<section class="section"><div class="container"><div class="news-rows">'+
  DATA.news.map(function(n){return newsRow(n,true);}).join("")+
  '</div></div></section>'+
  '<section class="section contact-invitation"><div class="container narrow center reveal">'+
  '<h2 class="h2">Vous organisez une exposition&nbsp;?</h2>'+
  '<p class="lead">Hilaire expose volontiers&nbsp;: galerie, salon, lieu d’exception — contactez-le pour en discuter.</p>'+
  '<p class="invitation-cta"><a class="btn" href="#/contact">Proposer une exposition</a></p></div></section>';
}

function pageNewsItem(slug){
  var n=null;DATA.news.forEach(function(x){if(x.s===slug)n=x;});
  if(!n)return pageNews();
  var others=DATA.news.filter(function(x){return x.s!==slug;}).slice(0,3);
  return '<header class="page-head"><div class="container reveal">'+
  '<p class="label">'+(n.dt?esc(n.dt):"Actualité")+'</p><h1 class="page-title">'+esc(n.t)+'</h1></div></header>'+
  '<article class="section"><div class="container article">'+
  (n.cov?'<figure class="article-cover reveal"><img src="'+n.cov+'" alt="'+esc(n.t)+'"></figure>':"")+
  '<div class="article-body reveal">'+n.p.map(function(p){return '<p>'+esc(p)+'</p>';}).join("")+'</div>'+
  (n.img.length?'<div class="article-gallery reveal">'+n.img.map(function(u,i){
    return '<img loading="lazy" src="'+u+'" alt="'+esc(n.t)+' — image '+(i+1)+'">';}).join("")+'</div>':"")+
  (n.l?'<p><a class="link-arrow" href="'+esc(n.l)+'" rel="noopener" target="_blank">En savoir plus ↗</a></p>':"")+
  '<div class="article-footer"><a class="lnk" href="#/actualites">← Toutes les actualités</a></div>'+
  '</div></article>'+
  (others.length?'<section class="section" style="padding-top:0"><div class="container">'+
  '<p class="label reveal">À lire également</p><div class="news-rows">'+
  others.map(function(n2){return newsRow(n2,false);}).join("")+'</div></div></section>':"");
}

function pageContact(q){
  var sujet=(q&&q.sujet)||"";
  return '<header class="page-head"><div class="container reveal"><p class="label">Contact</p>'+
  '<h1 class="page-title">Écrire à Hilaire</h1><p class="page-sub">Une réponse personnelle, sans engagement</p></div></header>'+
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
  '<div class="contact-card"><h2 class="h3">En direct</h2><ul class="contact-list">'+
  '<li><span>Téléphone</span><a class="lnk" href="tel:'+DATA.phone.replace(/\s/g,"")+'">'+esc(DATA.phone)+'</a></li>'+
  '<li><span>E-mail</span><a class="lnk" href="mailto:'+DATA.email+'">'+esc(DATA.email)+'</a></li>'+
  '<li><span>Instagram</span><a class="lnk" href="https://www.instagram.com/'+DATA.instagram+'/" rel="me noopener" target="_blank">'+esc(DATA.instagram)+'</a></li>'+
  '<li><span>Atelier</span><span>Yvetot-Bocage · Manche · Normandie</span></li></ul></div>'+
  '<div class="contact-card"><h2 class="h3">Demande spécifique</h2>'+
  '<p class="small">Tableau sur demande, projet particulier, renseignement sur une œuvre, exposition ou collaboration&nbsp;: décrivez simplement votre projet, Hilaire vous répond personnellement.</p></div>'+
  '</aside></div></section>'+
  '<section class="section map-section tint-sky"><div class="container">'+
  '<div class="section-head reveal"><div><p class="label">La région</p>'+
  '<h2 class="h2">Autour d’Yvetot-Bocage</h2></div></div>'+
  '<p class="map-note reveal">Hilaire travaille dans le Cotentin, à Yvetot-Bocage (Manche). La zone entourée ci-dessous correspond à un rayon d’environ 75&nbsp;km.</p>'+
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
    '<h1 class="page-title">Dans l\u2019atelier</h1>'+
    '<p class="page-sub">Le lieu où naissent les aquarelles</p></div></header>'+
    '<section class="section"><div class="container">'+
    '<div class="section-head reveal"><div><p class="label">L\u2019atelier</p><h2 class="h2">L\u2019atelier en photos</h2></div></div>'+
    '<p class="atelier-note reveal">L\u2019atelier d\u2019Hilaire en photos — la palette et le lieu où naissent les aquarelles. Cliquez pour agrandir.</p>'+
    '<div class="atelier-grid'+(DATA.photos.length===1?" atelier-one":"")+'" id="atelier-grid" data-cap="L\u2019atelier">'+g+'</div>'+
    '</div></section>'+
    '<section class="section wash-band"><div class="container narrow center reveal">'+
    '<h2 class="h2">Envie de voir le résultat&nbsp;?</h2>'+
    '<p class="lead">Les aquarelles nées dans cet atelier — et quelques-unes peintes sur le vif.</p>'+
    '<p class="invitation-cta"><a class="btn" href="#/aquarelles">Découvrir les aquarelles</a></p>'+
    '</div></section>';
}
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
  else if(route.indexOf("actualite/")===0)html=pageNewsItem(route.slice(10));
  else if(route==="artiste")html=pageArtist();
  else if(route==="atelier")html=pageAtelier();
  else if(route==="aquarelles")html=pageGallery();
  else if(route==="actualites")html=pageNews();
  else if(route==="contact")html=pageContact(r.q);
  else if(route==="confidentialite")html=pageLegal();
  else if(route==="admin")html=ADMIN?pageAdmin():pageAdminGate();
  else {route="accueil";html=pageHome();}
  main.innerHTML='<div class="fade-in">'+html+"</div>";
  document.querySelectorAll(".site-nav a").forEach(function(a){
    a.classList.toggle("on",a.getAttribute("data-r")===root||
      (root.indexOf("oeuvre")===0&&a.getAttribute("data-r")==="aquarelles")||
      (root.indexOf("actualite")===0&&a.getAttribute("data-r")==="actualites"));});
  var PG={accueil:"home",artiste:"artist",aquarelles:"gallery",oeuvre:"work",
    actualites:"news_list",actualite:"news_item",contact:"contact",atelier:"atelier"};
  document.body.className="pg-"+(PG[root]||root);
  document.title=route==="accueil"?
    "Hilaire Legentil — Artiste aquarelliste · Aquarelles mer & paysage":
    document.querySelector("h1")?document.querySelector("h1").textContent+
    " — Hilaire Legentil":"Hilaire Legentil";
  window.scrollTo(0,0);
  initReveal();initGallery();initContact();initMap();initAdmin();makeEditable();initAtelier();
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
  var bar=document.querySelector(".filter-bar"),grid=document.getElementById("grid");
  if(!bar||!grid)return;
  var count=document.getElementById("gcount");
  function update(){count.textContent=grid.querySelectorAll(".work:not([style*='none'])").length+
    (grid.querySelectorAll(".work:not([style*='none'])").length>1?" œuvres":" œuvre");}
  bar.addEventListener("click",function(e){
    var btn=e.target.closest(".filter-btn");if(!btn)return;
    bar.querySelectorAll(".filter-btn").forEach(function(b){b.classList.toggle("on",b===btn);});
    var f=btn.getAttribute("data-f");
    grid.querySelectorAll(".work").forEach(function(it){
      var tn=(it.getAttribute("data-tn")||"").trim();
      var ok=f==="*"||(f.indexOf("tn:")===0?tn===f.slice(3):
        (it.getAttribute("data-cat")||"").trim()===f);
      it.style.display=ok?"":"none";});
    update();});
  update();
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
var mapReady=false;function hlGet(){try{return localStorage.getItem("hl_consent");}catch(e){return null;}}
function hlSet(v){try{localStorage.setItem("hl_consent",v);}catch(e){}
  var bar=document.getElementById("cookie-bar");if(bar)bar.hidden=true;}
function initMap(){
  var el=document.getElementById("map");
  if(!el||el.dataset.mapInit||typeof L==="undefined")return;
  if(hlGet()!=="oui"){
    var gate=document.getElementById("map-consent");
    if(gate){gate.hidden=false;
      var b=document.getElementById("map-load");
      if(b)b.onclick=function(){hlSet("oui");gate.hidden=true;initMap();};}
    return;}
  el.dataset.mapInit="1";
  el.hidden=false;
  var c=[49.4894,-1.5048];
  var map=L.map(el,{scrollWheelZoom:false}).setView(c,8);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:18,
    attribution:"&copy; OpenStreetMap"}).addTo(map);
  L.circle(c,{radius:75000,color:"#1a9d9a",weight:1.6,opacity:.9,
    fillColor:"#1a9d9a",fillOpacity:.10}).addTo(map);
  L.circle(c,{radius:2000,color:"#11596a",weight:1.2,fillColor:"#11596a",fillOpacity:.55}).addTo(map);
  var icon=L.divIcon({className:"",html:'<div style="width:14px;height:14px;border-radius:50%;'+
    'background:#11596a;border:3px solid #faf8f3;box-shadow:0 0 0 2px #1a9d9a"></div>',
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
  '<h2>Éditeur</h2><p><strong>Hilaire Legentil</strong> — entrepreneur individuel · SIREN 927&nbsp;753&nbsp;780 · Yvetot-Bocage, 50700 Valognes (Manche, Normandie) · '+
  '<a class="lnk" href="mailto:'+DATA.email+'">'+DATA.email+'</a></p>'+
  '<h2>Hébergement</h2><p>Ce fichier se consulte localement, sans serveur. La version en ligne peut être hébergée par GitHub Pages (GitHub, Inc., San Francisco, États-Unis) ou par l’hébergeur choisi par l’éditeur.</p>'+
  '<h2>Propriété intellectuelle</h2><p>Aquarelles, photographies, affiches et textes sont la propriété exclusive d’Hilaire Legentil. Toute reproduction sans autorisation écrite est interdite.</p>'+
  '<h2>Cookies</h2><p>Ce fichier ne dépose <strong>aucun cookie</strong> et n’utilise aucun traceur. Votre choix concernant la carte est conservé uniquement dans votre navigateur (stockage local), jamais transmis.</p>'+
  '<h3>Carte interactive</h3><p>Les tuiles OpenStreetMap ne sont sollicitées qu’après votre accord explicite ; sans accord, rien n’est chargé depuis ce service tiers.</p>'+
  '<p><button class="btn btn-outline" id="ck-reset" type="button">Effacer mon choix (revoir le bandeau)</button></p>'+
  '<h2>Données personnelles</h2><p>Le formulaire prépare un e-mail dans votre propre logiciel de messagerie : aucune donnée n’est collectée par ce fichier. Sur la version en ligne, le message est adressé au seul artiste pour répondre à votre demande, puis supprimé.</p>'+
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
  '<input data-f="l" value="'+escA(n.l||"")+'" placeholder="Lien (https://…)"></div>'+
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
  return '<div class="adm-add"><h3 class="h3">Écrire une actualité</h3>'+
  '<form id="adm-add-news">'+
  '<div class="adm-grid2"><div><label>Titre</label><input data-f="t" placeholder="Ex. : Exposition à Barfleur"></div>'+
  '<div><label>Date</label><input data-f="rd" placeholder="2026-07-12 (ou 2026-07, 2026)"></div></div>'+
  '<div style="margin-top:.8rem"><label>Lien externe</label><input data-f="l" placeholder="https://… (facultatif)"></div>'+
  '<div style="margin-top:.8rem"><label>Texte</label><textarea data-f="body" rows="3" placeholder="Lieu, dates, horaires…"></textarea></div>'+
  '<div style="margin-top:.8rem"><label>Affiche</label><input data-f="file" type="file" accept="image/*"></div>'+
  '<button class="btn" type="submit" style="margin-top:1.1rem">Publier l’actualité</button>'+
  '</form></div>';}
function admSettings(){
  function f(l,k){return '<div><label>'+l+'</label><input data-s="'+k+'" value="'+escA(DATA[k]||"")+'"></div>';}
  function t(l,k){return '<div style="margin-top:.8rem"><label>'+l+'</label>'+
    '<textarea data-s="'+k+'" rows="3">'+esc(DATA[k]||"")+'</textarea></div>';}
  return '<div class="adm-add"><h3 class="h3">Réglages</h3>'+
  '<div class="adm-grid2">'+f("Code d’accès administrateur","pin")+f("Téléphone affiché","phone")+
  f("E-mail affiché","email")+f("Instagram (sans @)","instagram")+'</div>'+
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
        body=an.querySelector('[data-f=body]').value,
        link=an.querySelector('[data-f=l]').value.trim(),
        file=an.querySelector('input[type=file]').files[0];
    var done=function(uri){
      var base=slugJs(t),s=base,k=1;while(newsBySlug(s))s=base+"-"+(++k);
      DATA.news.unshift({t:t,s:s,dt:jsDateFr(rd),rd:rd,
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
    var slug=(row.getAttribute("href")||"").replace("#/actualite/","");
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
  '<li><a href="https://www.instagram.com/'+DATA.instagram+'/" rel="me noopener" target="_blank">Instagram — '+esc(DATA.instagram)+'</a></li>';
document.getElementById("year").textContent=new Date().getFullYear();
(function(){
  var bar=document.getElementById("cookie-bar");
  if(bar&&hlGet()===null){bar.hidden=false;
    document.getElementById("ck-accept").onclick=function(){hlSet("oui");initMap();};
    document.getElementById("ck-refuse").onclick=function(){hlSet("non");};}
})();
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
