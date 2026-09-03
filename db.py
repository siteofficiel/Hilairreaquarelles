"""Hilaire Legentil — site d'artiste aquarelliste. Base de données SQLite."""
import os
import sqlite3
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "hilaire.sqlite3")

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS works (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT 'Sans titre',
    slug TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT '',
    technique TEXT DEFAULT '',
    dimensions TEXT DEFAULT '',
    year TEXT DEFAULT '',
    folder TEXT NOT NULL,
    img_w INTEGER DEFAULT 0,
    img_h INTEGER DEFAULT 0,
    position INTEGER NOT NULL DEFAULT 0,
    published INTEGER NOT NULL DEFAULT 1,
    tonality TEXT DEFAULT '',
    chroma REAL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    event_date TEXT DEFAULT '',
    body TEXT DEFAULT '',
    link TEXT DEFAULT '',
    cover TEXT DEFAULT '',
    published INTEGER NOT NULL DEFAULT 1,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS news_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id INTEGER NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    image TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT DEFAULT '',
    subject TEXT NOT NULL,
    category TEXT DEFAULT '',
    body TEXT NOT NULL,
    ip TEXT DEFAULT ''
);
"""


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def get_settings():
    conn = connect()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def set_setting(key, value):
    conn = connect()
    conn.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()
