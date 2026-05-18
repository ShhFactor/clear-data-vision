import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "places.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS places (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    address TEXT,
    category TEXT,
    confidence TEXT CHECK(confidence IN ('HIGH', 'MEDIUM', 'LOW')) NOT NULL DEFAULT 'MEDIUM',
    last_verified TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS place_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_id TEXT,
    source_data TEXT,
    fetched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (place_id) REFERENCES places(id)
);

CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    source_a TEXT NOT NULL,
    value_a TEXT NOT NULL,
    source_b TEXT NOT NULL,
    value_b TEXT NOT NULL,
    detected_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (place_id) REFERENCES places(id)
);

CREATE INDEX IF NOT EXISTS idx_places_location ON places(lat, lng);
CREATE INDEX IF NOT EXISTS idx_places_last_verified ON places(last_verified);
CREATE INDEX IF NOT EXISTS idx_places_category ON places(category);
CREATE INDEX IF NOT EXISTS idx_sources_place ON place_sources(place_id);
CREATE INDEX IF NOT EXISTS idx_conflicts_place ON conflicts(place_id);
"""


def get_db_path() -> Path:
    env_path = os.environ.get("PLACE_DB_PATH")
    return Path(env_path) if env_path else DEFAULT_DB_PATH


@contextmanager
def get_conn(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Optional[Path] = None) -> None:
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_place(conn: sqlite3.Connection, place: dict) -> None:
    conn.execute(
        """
        INSERT INTO places (id, canonical_name, lat, lng, address, category, confidence, last_verified)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            canonical_name=excluded.canonical_name,
            lat=excluded.lat,
            lng=excluded.lng,
            address=excluded.address,
            category=excluded.category,
            confidence=excluded.confidence,
            last_verified=excluded.last_verified
        """,
        (
            place["id"],
            place.get("canonical_name") or place.get("name"),
            place["lat"],
            place["lng"],
            place.get("address"),
            place.get("category"),
            place.get("confidence", "MEDIUM"),
            place.get("last_verified", _utcnow_iso()),
        ),
    )


def insert_source(
    conn: sqlite3.Connection,
    place_id: str,
    source_name: str,
    source_data: dict,
    source_id: Optional[str] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO place_sources (place_id, source_name, source_id, source_data)
        VALUES (?, ?, ?, ?)
        """,
        (place_id, source_name, source_id, json.dumps(source_data)),
    )


def insert_conflict(conn: sqlite3.Connection, place_id: str, conflict: dict) -> None:
    conn.execute(
        """
        INSERT INTO conflicts (place_id, field_name, source_a, value_a, source_b, value_b)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            place_id,
            conflict["field_name"],
            conflict["source_a"],
            conflict["value_a"],
            conflict["source_b"],
            conflict["value_b"],
        ),
    )


def fetch_place(conn: sqlite3.Connection, place_id: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM places WHERE id = ?", (place_id,)).fetchone()
    if not row:
        return None
    place = dict(row)
    place["sources"] = fetch_sources(conn, place_id)
    place["conflicts"] = fetch_conflicts(conn, place_id)
    return place


def fetch_sources(conn: sqlite3.Connection, place_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT source_name FROM place_sources WHERE place_id = ? ORDER BY source_name",
        (place_id,),
    ).fetchall()
    return [r["source_name"] for r in rows]


def fetch_source_records(conn: sqlite3.Connection, place_id: str) -> dict:
    """Return {source_name: parsed source_data} for a place."""
    rows = conn.execute(
        "SELECT source_name, source_data FROM place_sources WHERE place_id = ?",
        (place_id,),
    ).fetchall()
    out: dict = {}
    for r in rows:
        try:
            out[r["source_name"]] = json.loads(r["source_data"]) if r["source_data"] else {}
        except json.JSONDecodeError:
            out[r["source_name"]] = {}
    return out


def fetch_conflicts(conn: sqlite3.Connection, place_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT field_name, source_a, value_a, source_b, value_b FROM conflicts WHERE place_id = ?",
        (place_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def clear_conflicts(conn: sqlite3.Connection, place_id: str) -> None:
    conn.execute("DELETE FROM conflicts WHERE place_id = ?", (place_id,))


def list_places(conn: sqlite3.Connection, limit: int = 20, offset: int = 0) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM places ORDER BY id LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return _hydrate_many(conn, [dict(r) for r in rows])


def list_places_in_bbox(
    conn: sqlite3.Connection,
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
    category: Optional[str] = None,
) -> list[dict]:
    query = "SELECT * FROM places WHERE lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?"
    params: list = [min_lat, max_lat, min_lng, max_lng]
    if category:
        query += " AND category = ?"
        params.append(category)
    rows = conn.execute(query, params).fetchall()
    return _hydrate_many(conn, [dict(r) for r in rows])


def list_all_places(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM places").fetchall()
    return _hydrate_many(conn, [dict(r) for r in rows])


def _hydrate_many(conn: sqlite3.Connection, places: list[dict]) -> list[dict]:
    """Attach sources and conflicts to a batch of places in 2 queries total
    (rather than 2 per place). Avoids the N+1 query problem on list endpoints.
    """
    if not places:
        return places

    ids = [p["id"] for p in places]
    placeholders = ",".join("?" * len(ids))

    sources_by_id: dict[str, list[str]] = {pid: [] for pid in ids}
    rows = conn.execute(
        f"SELECT DISTINCT place_id, source_name FROM place_sources "
        f"WHERE place_id IN ({placeholders}) ORDER BY place_id, source_name",
        ids,
    ).fetchall()
    for r in rows:
        sources_by_id[r["place_id"]].append(r["source_name"])

    conflicts_by_id: dict[str, list[dict]] = {pid: [] for pid in ids}
    rows = conn.execute(
        f"SELECT place_id, field_name, source_a, value_a, source_b, value_b "
        f"FROM conflicts WHERE place_id IN ({placeholders})",
        ids,
    ).fetchall()
    for r in rows:
        conflicts_by_id[r["place_id"]].append({
            "field_name": r["field_name"],
            "source_a": r["source_a"],
            "value_a": r["value_a"],
            "source_b": r["source_b"],
            "value_b": r["value_b"],
        })

    for p in places:
        p["sources"] = sources_by_id[p["id"]]
        p["conflicts"] = conflicts_by_id[p["id"]]
    return places
