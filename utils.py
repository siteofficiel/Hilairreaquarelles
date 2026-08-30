"""Utilitaires : slugs, texte, données structurées."""
import re
import unicodedata


def slugify(text, fallback="sans-titre"):
    text = str(text)
    for src, dst in (("Œ", "oe"), ("œ", "oe"), ("Æ", "ae"), ("æ", "ae"),
                     ("Ø", "o"), ("ø", "o"), ("ß", "ss")):
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or fallback


def unique_slug(conn, table, wanted, exclude_id=None):
    base, slug, i = wanted, wanted, 1
    while True:
        if exclude_id is None:
            row = conn.execute(f"SELECT 1 FROM {table} WHERE slug = ?", (slug,)).fetchone()
        else:
            row = conn.execute(f"SELECT 1 FROM {table} WHERE slug = ? AND id != ?",
                               (slug, exclude_id)).fetchone()
        if row is None:
            return slug
        i += 1
        slug = f"{base}-{i}"


def nl2paras(text):
    """Découpe un texte en paragraphes HTML sûrs (échappés par Jinja au besoin)."""
    if not text:
        return []
    out, buf = [], []
    for line in str(text).replace("\r\n", "\n").split("\n"):
        if line.strip():
            buf.append(line.strip())
        elif buf:
            out.append(" ".join(buf))
            buf = []
    if buf:
        out.append(" ".join(buf))
    return out


def parse_date(value):
    """'2024-05-20' -> ('20 mai 2024', '2024-05-20') ; tolère les dates partielles."""
    months = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
              "août", "septembre", "octobre", "novembre", "décembre"]
    v = (value or "").strip()
    m = re.match(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$", v)
    if not m:
        return v, v
    y, mo, d = m.group(1), m.group(2), m.group(3)
    parts = []
    if d:
        parts.append(f"{int(d):d}")
    if mo and 1 <= int(mo) <= 12:
        parts.append(months[int(mo) - 1])
    parts.append(y)
    return " ".join(parts), v
