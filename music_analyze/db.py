import sqlite3
import time

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    artists TEXT NOT NULL DEFAULT '',
    album TEXT NOT NULL DEFAULT '',
    duration_ms INTEGER,
    publish_time INTEGER,
    fee INTEGER,
    status TEXT NOT NULL DEFAULT 'fetched',
    skip_reason TEXT,
    error TEXT,
    bpm_beat_this REAL,
    bpm_essentia REAL,
    bpm_raw REAL,
    bpm_final REAL,
    bpm_method TEXT,
    bpm_confidence REAL,
    energy REAL,
    features_json TEXT,
    source_br INTEGER,
    source_size INTEGER,
    source_kind TEXT,
    analyzed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tracks_status ON tracks(status);
"""


def connect(path=None):
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn):
    conn.executescript(SCHEMA)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(tracks)")}
    if "source_kind" not in cols:
        conn.execute("ALTER TABLE tracks ADD COLUMN source_kind TEXT")
    conn.commit()


def upsert_tracks(conn, tracks):
    sql = """
    INSERT INTO tracks (id, name, artists, album, duration_ms, publish_time, fee, status)
    VALUES (:id, :name, :artists, :album, :duration_ms, :publish_time, :fee, 'fetched')
    ON CONFLICT(id) DO UPDATE SET
        name = excluded.name,
        artists = excluded.artists,
        album = excluded.album,
        duration_ms = excluded.duration_ms,
        publish_time = excluded.publish_time,
        fee = excluded.fee
    """
    conn.executemany(sql, tracks)
    conn.commit()


def pending_tracks(conn, limit=None, retry_errors=False):
    where = "status='fetched'" + (" OR status='error'" if retry_errors else "")
    sql = f"SELECT * FROM tracks WHERE {where} ORDER BY id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return conn.execute(sql).fetchall()


def mark(conn, track_id, status, reason=None, error=None):
    conn.execute(
        "UPDATE tracks SET status=?, skip_reason=?, error=? WHERE id=?",
        (status, reason, error, track_id),
    )
    conn.commit()


def save_analysis(conn, track_id, **kw):
    kw["analyzed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    kw["id"] = track_id
    cols = ", ".join(f"{k} = :{k}" for k in kw if k != "id")
    conn.execute(
        f"UPDATE tracks SET {cols}, status='analyzed', skip_reason=NULL, error=NULL WHERE id=:id",
        kw,
    )
    conn.commit()
