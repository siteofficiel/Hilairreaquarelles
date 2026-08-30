"""Authentification administrateur + protections (anti-bruteforce, anti-spam)."""
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque

from flask import session

from werkzeug.security import check_password_hash, generate_password_hash

import db

# ---------------------------------------------------------------- sessions


def current_admin():
    """Nom d'utilisateur de l'admin connecté, sinon None."""
    return session.get("admin_user") if session.get("admin_auth") else None


def login(username, password):
    conn = db.connect()
    row = conn.execute("SELECT * FROM admin WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row and check_password_hash(row["password_hash"], password):
        session.clear()
        session["admin_auth"] = True
        session["admin_user"] = row["username"]
        session["csrf"] = secrets.token_hex(16)
        session.permanent = True
        return True
    return False


def logout():
    session.clear()


def set_password(username, new_password):
    conn = db.connect()
    conn.execute("UPDATE admin SET password_hash = ? WHERE username = ?",
                 (generate_password_hash(new_password), username))
    conn.commit()
    conn.close()


def create_admin(username, password):
    conn = db.connect()
    conn.execute("INSERT INTO admin(username, password_hash, created_at) VALUES(?,?,?)",
                 (username, generate_password_hash(password), db.now_iso()))
    conn.commit()
    conn.close()


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def csrf_ok(request):
    sent = request.form.get("csrf", "")
    known = session.get("csrf", "")
    # un jeton vide ne doit jamais être accepté (session vierge = requête forgée)
    return bool(sent) and bool(known) and hmac.compare_digest(sent, known)


# -------------------------------------------------------- limitation de débit

_BUCKETS = defaultdict(deque)


def rate_limited(key, max_events, per_seconds):
    """True si la clé `key` a dépassé max_events sur la fenêtre per_seconds."""
    now = time.time()
    q = _BUCKETS[key]
    while q and q[0] < now - per_seconds:
        q.popleft()
    if len(q) >= max_events:
        return True
    q.append(now)
    return False


def fingerprint(request):
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?")
    ua = request.headers.get("User-Agent", "")[:80]
    return hashlib.sha256(f"{ip}|{ua}".encode()).hexdigest()[:24]
