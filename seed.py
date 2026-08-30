"""Import initial — Hilaire Legentil.

Crée la base, le compte administrateur, importe les photographies des
aquarelles et les actualités (expositions & presse) à partir des documents
fournis. Lancé une seule fois ; relancer ne duplique rien.
"""
import os
import secrets
import string
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "vendor"))

import db
import auth
import imaging
from utils import slugify, unique_slug

UPLOADS_SRC = "/home/user/uploads"
WORKS_DIR = os.path.join(BASE, "uploads", "works")
NEWS_DIR = os.path.join(BASE, "uploads", "news")

WORKS = [
    # (fichier, titre, catégorie, année) — titres à compléter par Hilaire
    ("20190820_134408_IMG_3332.JPG", "Sans titre", "", "2019"),
    ("20190825_200842_IMG_3792.JPG", "Sans titre", "", "2019"),
    ("20190825_201040_IMG_3793.JPG", "Sans titre", "", "2019"),
    ("20190825_201311_IMG_3794.JPG", "Sans titre", "", "2019"),
    ("20190825_201453_IMG_3795.JPG", "Sans titre", "", "2019"),
    ("20190825_201531_IMG_3796.JPG", "Sans titre", "", "2019"),
    ("20190825_201542_IMG_3797.JPG", "Sans titre", "", "2019"),
    ("20190825_201553_IMG_3798.JPG", "Sans titre", "", "2019"),
    ("20190825_201600_IMG_3799.JPG", "Sans titre", "", "2019"),
    ("20190825_201608_IMG_3800.JPG", "Sans titre", "", "2019"),
    ("20190825_201636_IMG_3801.JPG", "Sans titre", "", "2019"),
    ("20191222_114416_IMG_4390.JPG", "Sans titre", "", "2019"),
    ("20191223_225022_IMG_4383.JPG", "Sans titre", "", "2019"),
    ("20200105_170004_IMG_4461.JPG", "Sans titre", "", "2020"),
    ("20200105_170025_IMG_4462.JPG", "Sans titre", "", "2020"),
    ("20200105_170110_IMG_4463.JPG", "Sans titre", "", "2020"),
    ("20200222_194502.jpg", "Sans titre", "", "2020"),
    ("2.jpg", "Sans titre", "", "2022"),
]

NEWS = [
    {
        "title": "Galerie Art’mateur — Barfleur",
        "slug": "exposition-art-mateur-barfleur-2023",
        "event_date": "2023-05-22",
        "cover": "2023 - BARFLEUR-ARMATEURS-22-28 mai.jpg",
        "images": ["2023 - BARFLEUR-ARMATEURS-22-28 mai 2023-presse.jpg"],
        "body": (
            "Du 22 au 28 mai 2023, Hilaire Legentil a ouvert la saison de la galerie "
            "Art’mateur à Barfleur, aux côtés de Sylvie Colin (sacs et accessoires) et de "
            "Nicole Van Dorsselaere (bijoux en perles).\n\n"
            "Une nouveauté pour cet artiste alors nouveau venu chez Art’mateur, comme l’a "
            "relevé Ouest-France : « Cette passion m’est venue lors des confinements. Ces "
            "aquarelles sont réalisées sur du papier 100 % coton, matière qui apporte une "
            "tonalité douce aux couleurs. »\n\n"
            "Galerie Art’mateur, 55 rue Saint-Thomas-Becket, 50760 Barfleur — ouverte tous "
            "les jours de 10 h à 19 h, entrée gratuite."
        ),
        "link": "",
    },
    {
        "title": "Exposition à la salle polyvalente de Barfleur",
        "slug": "exposition-salle-polyvalente-barfleur-2023",
        "event_date": "2023-07-03",
        "cover": "2023 - Barfleur Salle Poly 3 au 9 juillet.jpg",
        "images": [],
        "body": (
            "Du 3 au 9 juillet 2023, les aquarelles d’Hilaire Legentil étaient présentées "
            "à la salle polyvalente de Barfleur, avec Richard Ulrich."
        ),
        "link": "",
    },
    {
        "title": "Retour à la galerie Art’mateur — Barfleur",
        "slug": "exposition-art-mateur-barfleur-2024",
        "event_date": "2024-05-20",
        "cover": "2024 - BARFLEUR-ARMATEURS-20-26 mai 2024 - 1.jpg",
        "images": ["2024 - BARFLEUR-ARMATEURS-20-26 mai 2024 - 2.jpg"],
        "body": (
            "Du 20 au 26 mai 2024, Hilaire Legentil exposait de nouveau à la galerie "
            "Art’mateur de Barfleur, dans une exposition collective autour de la "
            "sculpture (Jean-Marie Lescalier), de la peinture (Blandine Legros), de la "
            "photographie (Souleymane Traoré) et des sacs de Sylvie Colin.\n\n"
            "L’affiche reprenait ses mots : « Peindre, c’est voyager, peindre c’est "
            "méditer. J’ai choisi d’être paysagiste car la nature m’apaise et me "
            "recentre. »\n\n"
            "55 rue Saint-Thomas-Becket, 50760 Barfleur — tous les jours de 10 h à 19 h."
        ),
        "link": "",
    },
    {
        "title": "Galerie des Fuchsias — Saint-Vaast-la-Hougue",
        "slug": "galerie-des-fuchsias-saint-vaast-2024",
        "event_date": "2024-06-10",
        "cover": "2024 6 St Vaast -  10-23 juin 2024 - Fuschias.jpg",
        "images": [],
        "body": (
            "Du 10 au 23 juin 2024, la Galerie des Fuchsias à Saint-Vaast-la-Hougue a "
            "présenté « Hilaire Légentil — Aquarelliste », aux côtés de Nanou Quelvennec "
            "et Fabrice Pouteaux.\n\n"
            "Galerie des Fuchsias, 9 rue Verrue, 50550 Saint-Vaast-la-Hougue — du mardi "
            "au samedi de 11 h à 19 h, dimanche de 10 h à 18 h, lundi fermé."
        ),
        "link": "",
    },
    {
        "title": "Exposition à la salle polyvalente de Barfleur",
        "slug": "exposition-salle-polyvalente-barfleur-2024",
        "event_date": "2024-07-08",
        "cover": "2024 - BARFLEUR Salle poly 8-14 juillet.jpg",
        "images": [],
        "body": (
            "Du 8 au 14 juillet 2024, exposition à la salle polyvalente de Barfleur, "
            "ouverte chaque jour de 10 h à 18 h 30."
        ),
        "link": "",
    },
    {
        "title": "Exposition collective — salle polyvalente de Barfleur",
        "slug": "exposition-salle-polyvalente-barfleur-2025",
        "event_date": "2025-07-21",
        "cover": "2025 - Barfleur Salle Poly 21-27 juillet 2025.jpg",
        "images": [],
        "body": (
            "Du 21 au 27 juillet 2025, salle polyvalente rue des Écoles à Barfleur : "
            "aquarelles d’Hilaire Legentil, macrophotographie et peintures de Martine "
            "Gosselin-Ulrich, de 10 h 30 à 18 h 30."
        ),
        "link": "",
    },
    {
        "title": "Galerie Art’mateur — Barfleur",
        "slug": "exposition-art-mateur-barfleur-2025",
        "event_date": "2025-07-28",
        "cover": "2025 - BARFLEUR-ARMATEURS-28juillet-3aout 2025.jpg",
        "images": [],
        "body": (
            "Du 28 juillet au 3 août 2025, Hilaire Legentil exposait à la galerie "
            "Art’mateur, 55 rue Saint-Thomas-Becket à Barfleur, avec Nicole Van "
            "Dorsselaere — tous les jours de 10 h à 19 h, entrée libre et gratuite."
        ),
        "link": "",
    },
]

SETTINGS = {
    "home_intro": (
        "Des aquarelles de mer et de paysage, peintes sur papier 100 % coton — "
        "entre ciel, eau et terre, en Normandie."
    ),
    "artist_intro": (
        "Hilaire Legentil est un artiste aquarelliste installé à Yvetot-Bocage, "
        "dans la Manche, en Normandie. Sa passion pour l’aquarelle est née lors des "
        "confinements ; depuis, il peint la mer et le paysage sur papier 100 % coton, "
        "une matière qui apporte une tonalité douce aux couleurs."
    ),
    "contact_phone": "+33 7 66 50 92 05",
    "contact_email": "hilaire.legentil@free.fr",
    "instagram": "hilaire_aquarelles",
}


def seed():
    db.init_db()
    conn = db.connect()

    # ---------------------------------------------------------- réglages
    for k, v in SETTINGS.items():
        conn.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                     "ON CONFLICT(key) DO NOTHING", (k, v))
    conn.commit()

    # ------------------------------------------------------------- admin
    has_admin = conn.execute("SELECT COUNT(*) c FROM admin").fetchone()["c"]
    if not has_admin:
        alphabet = string.ascii_letters + string.digits
        password = "".join(secrets.choice(alphabet) for _ in range(14))
        auth.create_admin("hilaire", password)
        with open(os.path.join(db.DATA_DIR, "admin_password.txt"), "w") as f:
            f.write("Identifiant : hilaire\nMot de passe : " + password + "\n")
        print("→ Compte administrateur créé (identifiant « hilaire »).")
        print("  Mot de passe initial conservé dans data/admin_password.txt :")
        print(f"      {password}")
        print("  À changer dès la première connexion (Réglages).")

    # ------------------------------------------------------------ œuvres
    existing = {r["folder"] for r in conn.execute("SELECT folder FROM works")}
    count = 0
    for i, (fname, title, cat, year) in enumerate(WORKS, start=1):
        src = os.path.join(UPLOADS_SRC, fname)
        if not os.path.exists(src):
            print(f"  ! introuvable : {fname}")
            continue
        folder, w, h = imaging.import_existing_file(src, WORKS_DIR,
                                                    base_name=f"w{i:02d}")
        if folder in existing:
            continue
        slug = unique_slug(conn, "works", slugify(title, "aquarelle"))
        conn.execute(
            "INSERT INTO works(title,slug,description,category,technique,dimensions,"
            "year,folder,img_w,img_h,position,published,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (title, slug, "", cat, "", "", year, folder, w, h, i, 1, db.now_iso()))
        count += 1
        print(f"  + œuvre : {fname} ({w}×{h})")
    conn.commit()
    print(f"→ {count} œuvre(s) importée(s).")

    # -------------------------------------------------------- actualités
    existing_news = {r["slug"] for r in conn.execute("SELECT slug FROM news")}
    for n in NEWS:
        if n["slug"] in existing_news:
            continue
        cover = ""
        src_cover = os.path.join(UPLOADS_SRC, n["cover"])
        if os.path.exists(src_cover):
            base = slugify(n["slug"])[:24] + "-cov"
            cover, _, _ = imaging.import_existing_file(src_cover, NEWS_DIR,
                                                       base_name=base)
        conn.execute(
            "INSERT INTO news(title,slug,event_date,body,link,cover,published,position,"
            "created_at) VALUES(?,?,?,?,?,?,1,0,?)",
            (n["title"], n["slug"], n["event_date"], n["body"], n["link"],
             cover, db.now_iso()))
        nid = conn.execute("SELECT last_insert_rowid() i").fetchone()["i"]
        for j, img in enumerate(n.get("images", []), start=1):
            src_img = os.path.join(UPLOADS_SRC, img)
            if os.path.exists(src_img):
                folder, _, _ = imaging.import_existing_file(
                    src_img, NEWS_DIR, base_name=slugify(n["slug"])[:24] + f"-img{j}")
                conn.execute(
                    "INSERT INTO news_images(news_id,image,position) VALUES(?,?,?)",
                    (nid, folder, j))
        print(f"  + actualité : {n['title']} ({n['event_date']})")
    conn.commit()
    conn.close()
    print("→ Import terminé.")


if __name__ == "__main__":
    seed()
