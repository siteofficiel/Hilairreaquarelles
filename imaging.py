"""Validation, optimisation et dérivés des images envoyées.

Chaque image est re-encodée (métadonnées retirées) et déclinée en
plusieurs tailles, en JPEG (compatibilité maximale) et WebP (poids réduit).
L'œuvre n'est jamais retouchée : ni recadrage, ni correction de couleurs.
"""
import os
import uuid

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 60_000_000

ALLOWED_EXT = (".jpg", ".jpeg", ".png", ".webp")
MAX_UPLOAD_BYTES = 26 * 1024 * 1024  # 26 Mo

# (nom, grande largeur, qualité JPEG, qualité WebP)
DERIVATIVES = [
    ("medium", 1280, 0, 74, False),
]

MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


class ImageError(Exception):
    pass


def validate(stream, filename):
    """Vérifie l'extension et la lisibilité réelle du fichier. Retourne un PIL.Image."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise ImageError("Format non accepté. Utilisez un fichier JPG, PNG ou WebP.")
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    if size > MAX_UPLOAD_BYTES:
        raise ImageError("Le fichier est trop lourd (26 Mo maximum).")
    stream.seek(0)
    try:
        im = Image.open(stream)
        im.load()
    except Exception:
        raise ImageError("Ce fichier ne semble pas être une image valide.")
    return im


def _save_variant(im, width, jquality, wquality, outdir, base, want_jpeg=True):
    w, h = im.size
    if w > width:
        r = width / w
        resized = im.resize((width, round(h * r)), Image.LANCZOS)
    else:
        resized = im
    if want_jpeg and jquality:
        resized.save(os.path.join(outdir, f"{base}.jpg"), "JPEG", quality=jquality,
                     optimize=True, progressive=True)
    try:
        resized.save(os.path.join(outdir, f"{base}.webp"), "WEBP", quality=wquality,
                     method=6)
    except Exception:
        pass  # WebP indisponible : le JPEG reste utilisable



# ------------------------------------------------------------- filigrane
# Signature apposée sur chaque image publiée (protection contre le plagiat).
WATERMARK_TEXT = "Hilaire Legentil"
_FONT_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "static", "fonts", "CormorantGaramond-Italic.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def apply_watermark(im):
    """Appose la signature de l'artiste, discret, en bas à droite."""
    from PIL import ImageDraw, ImageFont
    w, h = im.size
    size = max(18, round(w * 0.040))
    font = None
    for p in _FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(p, size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    pad = max(6, round(w * 0.018))
    bbox = d.textbbox((0, 0), WATERMARK_TEXT, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = w - tw - pad - bbox[0]
    y = h - th - pad - bbox[1]
    d.text((x + 2, y + 2), WATERMARK_TEXT, font=font, fill=(10, 25, 30, 120))
    d.text((x, y), WATERMARK_TEXT, font=font, fill=(255, 255, 255, 175))
    from PIL import Image as _I
    return _I.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")


def store_image(stream, filename, target_root, base_name=None):
    """Sauvegarde une image dans target_root/base_name/ avec tous ses dérivés.

    Retourne (nom_de_dossier, largeur, hauteur).
    """
    im = validate(stream, filename)
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    elif im.mode == "L":
        im = im.convert("RGB")

    im = apply_watermark(im)

    base = base_name or uuid.uuid4().hex[:12]
    outdir = os.path.join(target_root, base)
    os.makedirs(outdir, exist_ok=True)

    # Dérivés d'affichage (aucune retouche d'œuvre, simple ré-encodage propre)
    for name, width, jq, wq, want_jpeg in DERIVATIVES:
        _save_variant(im, width, jq, wq, outdir, name, want_jpeg)

    w, h = im.size
    return base, w, h


def delete_image_folder(target_root, folder):
    if not folder or "/" in folder or "\\" in folder or ".." in folder:
        return
    path = os.path.join(target_root, folder)
    if os.path.isdir(path) and os.path.abspath(path).startswith(os.path.abspath(target_root)):
        for f in os.listdir(path):
            os.remove(os.path.join(path, f))
        os.rmdir(path)


def import_existing_file(src_path, target_root, base_name=None):
    """Importe un fichier déjà présent sur le serveur (seed initial)."""
    with open(src_path, "rb") as f:
        return store_image(f, os.path.basename(src_path), target_root, base_name=base_name)


# ------------------------------------------------------------- tonalité
# Vivacité colorimétrique d'une œuvre (métrique de Hasler & Süsstrunk).
# Mesurée sur l'image réelle : seuil choisi sur le creux naturel observé
# entre les aquarelles ternes (< 32) et colorées (>= 32) de la galerie.
TONALITY_THRESHOLD = 32


def chroma_of_image(path):
    from PIL import Image as _Image
    im = _Image.open(path).convert("RGB")
    im.thumbnail((220, 220))
    px = list(im.getdata())
    rg = [r - g for r, g, b in px]
    yb = [0.5 * (r + g) - b for r, g, b in px]

    def _mean(x):
        return sum(x) / len(x)

    def _std(x):
        m = _mean(x)
        return (sum((v - m) ** 2 for v in x) / len(x)) ** 0.5

    return (( _std(rg) ** 2 + _std(yb) ** 2) ** 0.5
            + 0.3 * (_mean(rg) ** 2 + _mean(yb) ** 2) ** 0.5)


def compute_tonality(variant_dir):
    """('Colorée'|'Terne', vivacité) mesurés sur les dérivés d'une œuvre."""
    for name in ("medium.webp", "medium.jpg", "xlarge.webp"):
        p = os.path.join(variant_dir, name)
        if os.path.exists(p):
            try:
                c = chroma_of_image(p)
            except Exception:
                return "", 0.0
            return ("Colorée" if c >= TONALITY_THRESHOLD else "Terne"), round(c, 1)
    return "", 0.0
