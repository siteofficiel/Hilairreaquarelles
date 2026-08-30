# Hilaire Legentil — Artiste aquarelliste · Aquarelles mer & paysage

Site personnel complet : galerie d'aquarelles, actualités & expositions,
contact avec carte interactive, et un espace d'administration simple réservé
à l'artiste.

## Démarrage

```bash
cd hilaire-legentil
python3 app.py          # → http://localhost:8000
```

Deux possibilités pour les dépendances (Flask, waitress, Pillow) :

- `pip install -r requirements.txt` (usage standard) ;
- ou déposer un dossier `vendor/` contenant les paquets
  (`pip install --target vendor -r requirements.txt`) : le site le charge
  automatiquement, aucune installation n'est alors nécessaire.

Variables utiles :

- `PORT` — port d'écoute (8000 par défaut).

### Premier lancement sur une machine neuve

`data/hilaire.sqlite3` est fournie avec les œuvres et actualités déjà en
place. Si elle est absente, elle est recréée vide à la première visite (la
clé secrète de session est également régénérée automatiquement si
nécessaire). L'import initial se fait avec `python3 seed.py` (néite les
photographies d'origine dans `/home/user/uploads`).

## L'espace d'administration

- Adresse : **/admin** (redirige vers /admin/login) — invisible aux visiteurs,
  exclue des robots (`Disallow: /admin`).
- Identifiant : `hilaire`
- Mot de passe initial : conservé dans **data/admin_password.txt**
  (à supprimer après lecture). **À changer dans Réglages dès la première
  connexion.**

Depuis l'administration, Hilaire peut, sans toucher au code :

- ajouter, modifier, supprimer, masquer et **réordonner** les œuvres ;
- écrire, modifier, publier / masquer / supprimer les actualités
  (image principale + images complémentaires, date, lien externe) ;
- lire et répondre aux messages du formulaire de contact ;
- modifier les textes d'accroche (accueil, page L'artiste) et ses
  coordonnées (téléphone, e-mail, Instagram) ;
- changer son mot de passe.

Les images envoyées sont automatiquement vérifiées (format, taille),
ré-encodées proprement (métadonnées retirées) et déclinées en plusieurs
tailles JPEG + WebP. **L'œuvre n'est jamais retouchée** : ni recadrage, ni
correction de couleur.

## Structure

```
hilaire-legentil/
├── app.py            # application Flask (site public + administration)
├── auth.py           # sessions, mots de passe, anti-bruteforce, CSRF
├── db.py             # base SQLite (data/hilaire.sqlite3)
├── imaging.py        # validation & optimisation des images
├── seed.py           # import initial (œuvres + expositions + réglages)
├── utils.py          # slugs, dates françaises, paragraphes
├── templates/        # pages du site + templates admin
├── static/           # CSS, JS, polices auto-hébergées, Leaflet
├── uploads/works/    # images des œuvres (dérivés par dossier)
├── uploads/news/     # images des actualités
├── data/             # base SQLite, clé secrète, mot de passe initial
└── vendor/           # dépendances Python embarquées
```

## Mise en ligne

1. Copier le dossier entier sur le serveur (Python ≥ 3.10 requis).
2. Dans `app.py`, renseigner `SITE["domain"]`
   (ex. `https://www.hilaire-legentil-aquarelles.fr`) : cela active les
   URLs canoniques, Open Graph et le sitemap absolus.
3. Compléter l'hébergeur dans `templates/legal.html` (mentions légales).
4. Servir avec waitress derrière Nginx (ou tout reverse proxy HTTPS) :

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

En HTTPS, décommenter `SESSION_COOKIE_SECURE` dans `app.py`.

**Sauvegardes** : copier régulièrement `data/` (base SQLite) et `uploads/`.

## Choix techniques

- **Identité** : palette issue de la carte de visite — vert d'eau #1a9d9a,
  bleu pétrole #11596a — sur fond papier écru ; titres en Cormorant
  Garamond, textes en Jost (polices auto-hébergées).
- **Galerie** : grille à tailles variables (grands formats, verticales,
  pans larges) pour une accroche proche d'une galerie ; page immersive par
  œuvre avec navigation précédent / suivant (aussi au clavier).
- **Carte** : Leaflet + tuiles OpenStreetMap, cercle de 75 km autour
  d'Yvetot-Bocage (49.4894, −1.5048). Aucune clé API nécessaire ; une
  migration vers Google Maps ne requerrait qu'une clé côté client.
- **SEO** : titres et meta descriptions par page, Open Graph, données
  structurées JSON-LD (Person / VisualArtwork), sitemap.xml dynamique,
  robots.txt, ALT descriptifs sur chaque œuvre.
- **Sécurité** : sessions signées, mots de passe hachés (scrypt), CSRF sur
  tous les formulaires, limitation de débit (connexion & contact),
  pot de miel + délai minimal anti-spam, validation stricte des fichiers
  envoyés, en-têtes de sécurité HTTP.
- **Performance** : images responsives en WebP/JPEG (srcset + lazy
  loading), cache annuel sur les médias, aucune dépendance CDN — le site
  fonctionne même si des services tiers tombent.

## Origine des contenus

Toutes les informations du site proviennent des documents fournis :
carte de visite (baseline, téléphone, e-mail, Instagram, SIREN), affiches
d'expositions 2023–2025 (Barfleur, Saint-Vaast-la-Hougue) et article de
presse Ouest-France (mai 2023). Les 18 aquarelles importées sont
provisoirement intitulées « Sans titre » : Hilaire peut leur donner leur
titre, leur catégorie et leur description depuis l'administration.
