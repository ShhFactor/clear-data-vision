from fastapi.testclient import TestClient

from src.database import get_conn, init_db, insert_source, upsert_place
from src.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


def test_list_places(seed_minimal):
    r = client.get("/places")
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_get_place_by_id(seed_minimal):
    r = client.get("/places/test_001")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "test_001"
    assert body["canonical_name"] == "Test Cafe"


def test_get_nonexistent_place(seed_minimal):
    r = client.get("/places/does_not_exist")
    assert r.status_code == 404


def test_nearby_returns_close_place_only(seed_minimal):
    r = client.post("/places/nearby", json={
        "lat": 12.9716, "lng": 77.5946, "radius_km": 5,
    })
    assert r.status_code == 200
    ids = [item["place"]["id"] for item in r.json()["results"]]
    assert "test_001" in ids
    assert "test_002" not in ids


def test_nearby_validates_input():
    r = client.post("/places/nearby", json={"lat": 200, "lng": 77.5946})
    assert r.status_code == 422


def test_nearby_filters_by_category(seed_minimal):
    r = client.post("/places/nearby", json={
        "lat": 12.9716, "lng": 77.5946,
        "radius_km": 5, "category": "restaurant_italian",
    })
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_stale_route_matches_before_place_id(seed_minimal):
    """Regression: /places/stale must not be captured as place_id='stale'."""
    r = client.get("/places/stale")
    assert r.status_code == 200
    assert "stale_places" in r.json()


def test_deduplicate_endpoint():
    init_db()
    with get_conn() as conn:
        upsert_place(conn, {
            "id": "dup_a", "canonical_name": "Pasta Vino",
            "lat": 12.9716, "lng": 77.5946,
            "confidence": "HIGH", "last_verified": "2026-05-01T10:00:00+00:00",
        })
        upsert_place(conn, {
            "id": "dup_b", "canonical_name": "PASTA VINO",
            "lat": 12.9716, "lng": 77.5946,
            "confidence": "HIGH", "last_verified": "2026-05-01T10:00:00+00:00",
        })
    r = client.post("/places/deduplicate", json={
        "distance_threshold_m": 100, "name_similarity_threshold": 80,
    })
    assert r.status_code == 200
    assert r.json()["total_groups"] >= 1


def test_reconcile_endpoint():
    init_db()
    with get_conn() as conn:
        upsert_place(conn, {
            "id": "rec_001", "canonical_name": "X",
            "lat": 12.97, "lng": 77.59,
            "confidence": "MEDIUM",
            "last_verified": "2026-05-01T10:00:00+00:00",
        })
        insert_source(conn, "rec_001", "google_places",
                      {"name": "Pasta Vino", "hours": "10-22"})
        insert_source(conn, "rec_001", "yelp",
                      {"name": "Pasta Vino", "hours": "11-23"})
    r = client.post("/places/reconcile/rec_001")
    assert r.status_code == 200
    body = r.json()
    assert body["place_id"] == "rec_001"
    assert any(c["field_name"] == "hours" for c in body["conflicts"])


def test_reconcile_404(seed_minimal):
    r = client.post("/places/reconcile/missing")
    assert r.status_code == 404
