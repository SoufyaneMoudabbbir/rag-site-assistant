"""SQLite storage: sites, their knowledge (documents + chunks with embeddings),
conversations, leads and daily usage."""

import json
import sqlite3
from datetime import datetime, timezone

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    language      TEXT NOT NULL DEFAULT 'fr',
    color         TEXT NOT NULL DEFAULT '#b5562b',
    welcome       TEXT NOT NULL DEFAULT '',
    suggestions   TEXT NOT NULL DEFAULT '[]',
    instructions  TEXT NOT NULL DEFAULT '',
    allowed_origins TEXT NOT NULL DEFAULT '*',
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY,
    site_id     TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    source      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    chars       INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    site_id     TEXT NOT NULL,
    heading     TEXT NOT NULL,
    url         TEXT,
    text        TEXT NOT NULL,
    embedding   BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_site ON chunks(site_id);
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    site_id     TEXT NOT NULL,
    page_url    TEXT,
    started_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    sources         TEXT NOT NULL DEFAULT '[]',
    handoff         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leads (
    id              INTEGER PRIMARY KEY,
    site_id         TEXT NOT NULL,
    conversation_id TEXT,
    name            TEXT,
    email           TEXT NOT NULL,
    message         TEXT,
    page_url        TEXT,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage (
    day      TEXT PRIMARY KEY,
    messages INTEGER NOT NULL DEFAULT 0
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def site_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["suggestions"] = json.loads(d["suggestions"])
    return d


def get_site(conn: sqlite3.Connection, site_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM sites WHERE id = ?", (site_id,)).fetchone()
    return site_to_dict(row) if row else None


def count_usage(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT messages FROM usage WHERE day = ?", (today(),)).fetchone()
    return row["messages"] if row else 0


def add_usage(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO usage (day, messages) VALUES (?, 1) "
        "ON CONFLICT(day) DO UPDATE SET messages = messages + 1",
        (today(),),
    )
