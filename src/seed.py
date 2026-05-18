"""Load seed data into the SQLite database.

Usage:
    python -m src.seed
"""
from __future__ import annotations

import json
from pathlib import Path

from src.database import (
    get_conn,
    init_db,
    insert_conflict,
    insert_source,
    upsert_place,
)
from src.reconcile import reconcile_sources

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_json(name: str):
    with open(DATA_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_places() -> int:
    """Load seed_places.json into the places + place_sources tables."""
    places = load_json("seed_places.json")
    with get_conn() as conn:
        for p in places:
            record = {
                "id": p["id"],
                "canonical_name": p["name"],
                "lat": p["lat"],
                "lng": p["lng"],
                "address": p.get("address"),
                "category": p.get("category"),
                "confidence": "HIGH",
                "last_verified": p["last_verified"],
            }
            upsert_place(conn, record)
            insert_source(
                conn,
                place_id=p["id"],
                source_name=p["source"],
                source_data={k: v for k, v in p.items() if k != "id"},
            )
    return len(places)


def seed_conflicts() -> int:
    """Load conflicting_sources.json: insert each source record + reconcile."""
    conflicting = load_json("conflicting_sources.json")
    with get_conn() as conn:
        for entry in conflicting:
            place_id = entry["place_id"]
            sources = entry["sources"]
            # Replace any pre-existing records for these sources so the
            # conflicting_sources.json richer dataset (with phone/hours) wins.
            conn.execute(
                "DELETE FROM place_sources WHERE place_id = ? AND source_name IN ({})".format(
                    ",".join("?" * len(sources))
                ),
                [place_id, *sources.keys()],
            )
            for source_name, source_data in sources.items():
                insert_source(conn, place_id, source_name, source_data)

            # Reconcile + persist conflicts
            result = reconcile_sources(sources)
            for c in result["conflicts"]:
                insert_conflict(conn, place_id, c)
            # Update confidence on the place record based on reconciliation
            conn.execute(
                "UPDATE places SET confidence = ? WHERE id = ?",
                (result["confidence"], place_id),
            )
    return len(conflicting)


def main() -> None:
    init_db()
    n_places = seed_places()
    n_conflicting = seed_conflicts()
    print(f"Seeded {n_places} places.")
    print(f"Processed {n_conflicting} multi-source entries with conflict detection.")


if __name__ == "__main__":
    main()
