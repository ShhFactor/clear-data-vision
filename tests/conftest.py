import os
import tempfile

import pytest

from src.database import get_conn, init_db, insert_source, upsert_place


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch):
    """Each test runs against a fresh empty SQLite DB."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setenv("PLACE_DB_PATH", tmp.name)
    yield tmp.name
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def seed_minimal():
    """Seed two places: a Bangalore cafe and a far-away Mumbai park.

    Used by API tests that need real DB content. The far place is included so
    distance/category filters can be exercised without ambiguity.
    """
    init_db()
    with get_conn() as conn:
        upsert_place(conn, {
            "id": "test_001",
            "canonical_name": "Test Cafe",
            "lat": 12.9716,
            "lng": 77.5946,
            "address": "MG Road",
            "category": "cafe",
            "confidence": "HIGH",
            "last_verified": "2026-05-01T10:00:00+00:00",
        })
        insert_source(conn, "test_001", "google_places",
                      {"name": "Test Cafe", "hours": "10-22"})
        upsert_place(conn, {
            "id": "test_002",
            "canonical_name": "Far Park",
            "lat": 19.0760,
            "lng": 72.8777,
            "address": "Mumbai",
            "category": "park",
            "confidence": "HIGH",
            "last_verified": "2025-08-01T10:00:00+00:00",
        })
