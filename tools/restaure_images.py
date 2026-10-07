# -*- coding: utf-8 -*-
"""Répare les dossiers d'images manquants depuis le fichier unique (mono).

Le fichier unique index.html embarque TOUTES les images (base64). Si des
dossiers d'uploads/ ont été perdus (limite de stockage de l'espace de
travail), ce script les recrée à l'identique, sans toucher à la base.

Usage :
    python3 tools/restaure_images.py                # utilise index.html racine
    python3 tools/restaure_images.py AUTREFICHIER   # autre copie du mono

Ne modifie ni la base de données ni les dossiers déjà complets : seuls les
fichiers manquants sont écrits, les existants sont vérifiés octet/octet.
"""
import base64
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
MONO = _args[0] if _args else os.path.join(BASE, "index.html")


def main():
    import sqlite3
    html = open(MONO, encoding="utf-8", errors="ignore").read()
    m = re.search(r"var DATA = /\*HLDATA\*/", html)
    if not m:
        raise SystemExit("Fichier unique sans données (marqueur DATA introuvable).")
    data = json.JSONDecoder().raw_decode(html[html.index("{", m.end()):])[0]

    conn = sqlite3.connect(os.path.join(BASE, "data", "hilaire.sqlite3"))
    conn.row_factory = sqlite3.Row
    works = conn.execute("SELECT slug, folder FROM works ORDER BY position, id").fetchall()
    news = conn.execute("SELECT cover FROM news WHERE cover != ''").fetchall()
    atelier = conn.execute("SELECT folder FROM atelier ORDER BY position, id").fetchall()

    def uri_of(folder, area_hint=None):
        """Retourne l'image embarquée correspondant à un dossier, via le mono."""
        for j, a in enumerate(data.get("atelier", []), 1):
            if "at%02d" % j == folder or area_hint == "atelier" and folder == "at%02d" % j:
                return a["i"]
        for i, w in enumerate(data.get("works", []), 1):
            s = w.get("s") or ""
            if re.fullmatch(r"sur-le-vif-\d+", s):
                if "at%02d" % int(s.rsplit("-", 1)[1]) == folder:
                    return w["i"]
            elif "w%02d" % i == folder:
                return w["i"]
        for i, p in enumerate(data.get("photos", []), 1):
            if "pal%02d" % i == folder:
                return p["i"]
        return None

    # actualités : correspondance PAR SLUG (la base trie les news par date,
    # pas par position — l'index du mono ne correspond pas au n° du dossier)
    news_mono = {n.get("s"): n for n in data.get("news", [])}

    def uri_of_news(slug):
        n = news_mono.get(slug)
        return (n.get("cov") if n else None) or None

    ecrits, identiques, manquants = 0, 0, []
    force = "--force" in sys.argv
    jobs = [("works", w["folder"], None) for w in works]
    jobs += [("news", n["cover"], n["slug"]) for n in
             conn.execute("SELECT slug, cover FROM news WHERE cover != ''")]
    jobs += [("atelier", a["folder"], None) for a in atelier]
    for area, folder, slug in jobs:
        p = os.path.join(BASE, "uploads", area, folder, "medium.webp")
        uri = uri_of_news(slug) if area == "news" else uri_of(folder)
        if os.path.isfile(p) and not force:
            identiques += 1
            continue
        if not uri:
            manquants.append((area, folder))
            continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        b = base64.b64decode(uri.split(",", 1)[1])
        if os.path.isfile(p) and open(p, "rb").read() == b:
            identiques += 1
            continue
        open(p, "wb").write(b)
        ecrits += 1
    print(f"Images : {ecrits} restaurée(s), {identiques} déjà présentes, "
          f"{len(manquants)} sans source dans le mono.")
    if manquants:
        print("Introuvables :", manquants)
        sys.exit(1)


if __name__ == "__main__":
    main()
