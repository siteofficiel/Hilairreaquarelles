# -*- coding: utf-8 -*-
"""Restauration du site depuis le fichier unique (index.html).

Le fichier unique publié sur GitHub contient TOUT : textes, réglages et
images (embarquées). Ce module reconstruit la base de données et les
dossiers d'images à partir de ce fichier — utilisé :

  - automatiquement au premier lancement du site (base vide) ;
  - manuellement :  python tools/restaure.py

SÉCURITÉ : la restauration ne s'exécute que si la base est VIDE
(aucune œuvre). Elle ne peut donc jamais écraser un site existant.
"""
import base64
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "vendor"))
sys.path.insert(0, BASE)

MONO = os.path.join(BASE, "index.html")
DB_PATH = os.path.join(BASE, "data", "hilaire.sqlite3")
UPLOADS = os.path.join(BASE, "uploads")

DEFAULT_PASSWORD = "aquarelles_2026"


def _extract_data(html):
    m = re.search(r"var DATA = /\*HLDATA\*/", html)
    if not m:
        raise SystemExit("index.html ne contient pas de données (marqueur DATA introuvable).")
    return json.JSONDecoder().raw_decode(html[html.index("{", m.end()):])[0]


def _img_bytes(uri):
    return base64.b64decode(uri.split(",", 1)[1])


def _domain_from_mono(html):
    m = re.search(r'<link rel="canonical" href="(https?://[^"/]+)', html)
    return m.group(1) if m else ""


def base_est_vide():
    if not os.path.exists(DB_PATH):
        return True
    conn = sqlite3.connect(DB_PATH)
    try:
        n = conn.execute("SELECT COUNT(*) FROM works").fetchone()[0]
        return n == 0
    finally:
        conn.close()


def restore_all():
    """Reconstruit base + images depuis le fichier unique. Base vide exigé."""
    if not os.path.exists(MONO):
        raise SystemExit("index.html introuvable à la racine du site.")
    if not base_est_vide():
        raise SystemExit("Refusé : la base contient déjà des œuvres "
                         "(la restauration n'écrase jamais un site existant).")

    import db  # schéma + chemins du projet
    db.init_db()

    html = open(MONO, encoding="utf-8", errors="ignore").read()
    data = _extract_data(html)
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # dossiers d'images : repartir proprement
    for sub in ("works", "news", "atelier"):
        p = os.path.join(UPLOADS, sub)
        if os.path.isdir(p):
            shutil.rmtree(p)
        os.makedirs(p, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    existing = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ("works", "works_images", "news", "news_images", "atelier",
              "settings", "messages", "push_subs"):
        if t in existing:
            conn.execute("DELETE FROM " + t)

    # ── réglages ──
    SET = {
        "hero_baseline": data.get("heroB", ""), "hero_title": data.get("heroT", ""),
        "hero_sub": data.get("heroS", ""), "home_intro": data.get("homeIntro", ""),
        "artist_intro": data.get("artistIntro", ""), "gallery_sub": data.get("gallerySub", ""),
        "events_sub": data.get("eventsSub", ""), "contact_sub": data.get("contactSub", ""),
        "atelier_sub": data.get("atelierSub", ""), "footer_job": data.get("footerJob", ""),
        "footer_tag": data.get("footerTag", ""), "regard_art": data.get("rA", ""),
        "regard_sujet": data.get("rS", ""), "regard_univers": data.get("rU", ""),
        "regard_support": data.get("rP", ""), "regard_region": data.get("rR", ""),
        "contact_phone": data.get("phone", ""), "contact_email": data.get("email", ""),
        "instagram": data.get("instagram", ""), "facebook": data.get("fb", ""),
        "ga_id": data.get("ga", ""),
        "site_domain": _domain_from_mono(html),
    }
    for k, v in SET.items():
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (k, v or ""))

    # ── photos atelier « sur le vif » ──
    for i, p in enumerate(data.get("atelier", []), 1):
        folder = "at%02d" % i
        d = os.path.join(UPLOADS, "atelier", folder)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "medium.webp"), "wb").write(_img_bytes(p["i"]))
        conn.execute("INSERT INTO atelier(folder,img_w,img_h,position,kind) "
                     "VALUES(?,?,?,?, 'vif')", (folder, p.get("w", 0), p.get("h", 0), i))

    # ── œuvres (les « sur le vif » partagent l'image atelier : stockage unique) ──
    pos = 0
    for i, w in enumerate(data.get("works", []), 1):
        s = w.get("s") or ""
        if re.fullmatch(r"sur-le-vif-\d+", s):
            folder = "at%02d" % int(s.rsplit("-", 1)[1])
            technique = "Sur le vif"
        else:
            folder = "w%02d" % i
            d = os.path.join(UPLOADS, "works", folder)
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "medium.webp"), "wb").write(_img_bytes(w["i"]))
            technique = ""
        pos += 1
        conn.execute(
            "INSERT INTO works(title,slug,description,category,technique,dimensions,"
            "year,sujet,ambiance,folder,img_w,img_h,position,published,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
            (w.get("t", "Sans titre"), s, w.get("d", ""), w.get("c", ""), technique, "",
             w.get("y", ""), w.get("sj", ""), w.get("am", ""),
             folder, w.get("w", 0), w.get("h", 0), pos, now))

    # ── palette ──
    for i, p in enumerate(data.get("photos", []), 1):
        folder = "pal%02d" % i
        d = os.path.join(UPLOADS, "atelier", folder)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "medium.webp"), "wb").write(_img_bytes(p["i"]))
        conn.execute("INSERT INTO atelier(folder,img_w,img_h,position,kind) "
                     "VALUES(?,?,?,?, 'palette')", (folder, p.get("w", 0), p.get("h", 0), i))

    # ── actualités ──
    for i, n in enumerate(data.get("news", []), 1):
        folder = "n%02d" % i
        if n.get("cov"):
            d = os.path.join(UPLOADS, "news", folder)
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "medium.webp"), "wb").write(_img_bytes(n["cov"]))
        conn.execute(
            "INSERT INTO news(title,slug,event_date,event_time,place,body,link,cover,"
            "published,position,created_at) VALUES(?,?,?,?,?,?,?,?,1,?,?)",
            (n.get("t", ""), n.get("s", "actualite-%d" % i), n.get("rd", ""), n.get("tm", ""),
             n.get("pl", ""), "\n\n".join(n.get("p", [])), n.get("l", ""),
             folder if n.get("cov") else "", i, now))

    # ── compte administrateur (mot de passe par défaut) ──
    from werkzeug.security import generate_password_hash
    conn.execute("INSERT OR REPLACE INTO admin(username,password_hash,created_at) "
                 "VALUES(?,?,?)",
                 ("hilaire", generate_password_hash(DEFAULT_PASSWORD), now))
    conn.commit()
    conn.close()

    # le fichier « mot de passe initial » généré à l'installation ne correspond
    # plus : on le met en cohérence avec le mot de passe restauré
    pw_file = os.path.join(BASE, "data", "admin_password.txt")
    if os.path.exists(pw_file):
        open(pw_file, "w", encoding="utf-8").write(DEFAULT_PASSWORD + "\n")

    return {
        "works": len(data.get("works", [])),
        "news": len(data.get("news", [])),
        "vif": len(data.get("atelier", [])),
        "palette": len(data.get("photos", [])),
    }


if __name__ == "__main__":
    r = restore_all()
    print("Restauration terminée : %(works)d œuvres, %(news)d actualités, "
          "%(vif)d photos sur le vif, %(palette)d photo(s) de palette." % r)
    print("Connexion admin : hilaire / %s" % DEFAULT_PASSWORD)
