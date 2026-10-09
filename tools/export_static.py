# -*- coding: utf-8 -*-
"""Exporte le site public en fichiers statiques (publication « rapide »).

Le site en un seul fichier (index.html) contient toutes les images : simple
à sauvegarder, mais long à charger. Cet export produit au contraire un site
multi-fichiers classique — page d'accueil de quelques dizaines de kilo-octets,
images chargées une par une, uniquement celles visibles, mises en cache par
le navigateur — sans aucune perte de qualité (mêmes fichiers WebP).

Usage :
    python3 tools/export_static.py            # exporte dans dist-site/
    python3 tools/export_static.py CIBLE      # exporte ailleurs

Aucune donnée n'est modifiée : lecture seule (base + images + gabarits).
"""
import os
import shutil
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "vendor"))
sys.path.insert(0, BASE)


def export(target=None, progress=None):
    """Génère l'export statique. Retourne le dossier cible."""
    def say(msg):
        if progress is not None:
            progress["phase"] = msg
        print("* " + msg)

    dist = os.path.abspath(target or os.path.join(BASE, "dist-site"))
    if os.path.isdir(dist):
        shutil.rmtree(dist)
    os.makedirs(dist)

    os.environ["HL_STATIC_EXPORT"] = "1"
    import app as app_module  # noqa: E402
    app_module.app.config["STATIC_EXPORT"] = True
    client = app_module.app.test_client()

    conn = sqlite3.connect(os.path.join(BASE, "data", "hilaire.sqlite3"))
    conn.row_factory = sqlite3.Row
    works = [r["slug"] for r in conn.execute(
        "SELECT slug FROM works WHERE published=1 ORDER BY position, id")]
    news = [r["slug"] for r in conn.execute(
        "SELECT slug FROM news WHERE published=1 ORDER BY position, id")]
    conn.close()

    pages = ["/", "/artiste", "/atelier", "/galerie", "/evenements",
             "/contact", "/mentions-legales",
             "/confidentialite", "/sitemap.xml", "/robots.txt", "/sw.js"]
    pages += ["/galerie/" + s for s in works]
    pages += ["/evenements/" + s for s in news]

    errors = []
    for path in pages:
        say("page " + path)
        r = client.get(path)
        if r.status_code != 200:
            errors.append(f"{path} → {r.status_code}")
            continue
        if path.endswith((".xml", ".txt", ".js")):
            out = os.path.join(dist, path.lstrip("/"))
        else:
            out = os.path.join(dist, path.lstrip("/"), "index.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(r.data)

    # fichiers annexes
    shutil.copy2(os.path.join(BASE, "404.html"), os.path.join(dist, "404.html"))
    # vérification Google Search Console (googleXXXX.html à la racine)
    import glob as _glob
    for g in _glob.glob(os.path.join(BASE, "google*.html")):
        shutil.copy2(g, os.path.join(dist, os.path.basename(g)))
        say("fichier de vérification Google : " + os.path.basename(g))

    say("copie des fichiers statiques")
    shutil.copytree(os.path.join(BASE, "static"), os.path.join(dist, "static"))

    say("copie des images")
    n_img = 0
    for area in ("works", "news", "atelier"):
        src = os.path.join(BASE, "uploads", area)
        if not os.path.isdir(src):
            continue
        for folder in os.listdir(src):
            p = os.path.join(src, folder, "medium.webp")
            if os.path.isfile(p):
                out = os.path.join(dist, "uploads", area, folder, "medium.webp")
                os.makedirs(os.path.dirname(out), exist_ok=True)
                shutil.copy2(p, out)
                n_img += 1

    total = sum(len(fs) for _, _, fs in os.walk(dist))
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(dist) for f in fs)
    say(f"export terminé : {total} fichiers, {size/1e6:.1f} Mo, {n_img} images")
    if errors:
        raise RuntimeError("Pages en échec : " + "; ".join(errors))
    return dist


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    export(args[0] if args else None)
