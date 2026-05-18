"""Exercise every endpoint of the running server.

Usage:
    # Terminal 1 (leave running):
    ./venv/Scripts/python.exe -m uvicorn src.main:app --reload

    # Terminal 2:
    ./venv/Scripts/python.exe scripts/try_api.py
"""
from __future__ import annotations

import httpx

BASE = "http://localhost:8000"


def section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main() -> None:
    section("Health")
    r = httpx.get(f"{BASE}/health")
    print(r.json())

    section("List 5 places")
    r = httpx.get(f"{BASE}/places", params={"limit": 5})
    for p in r.json():
        print(f"  {p['id']:10}  {p['canonical_name']:35}  ({p['confidence']})")

    section("Get one place — place_001")
    r = httpx.get(f"{BASE}/places/place_001")
    p = r.json()
    print(f"  Name:       {p['canonical_name']}")
    print(f"  Confidence: {p['confidence']}")
    print(f"  Sources:    {', '.join(p['sources'])}")
    print(f"  Conflicts:  {len(p['conflicts'])}")
    for c in p["conflicts"][:3]:
        print(f"    - {c['field_name']}: {c['source_a']}={c['value_a']!r}  vs  {c['source_b']}={c['value_b']!r}")

    section("Nearby search — 1 km around MG Road")
    r = httpx.post(f"{BASE}/places/nearby", json={
        "lat": 12.9716, "lng": 77.5946, "radius_km": 1.0, "limit": 10,
    })
    for hit in r.json()["results"]:
        print(f"  {hit['distance_km']:5.2f} km  —  {hit['place']['canonical_name']} ({hit['place'].get('category')})")

    section("Nearby with category filter — Italian only, 2 km")
    r = httpx.post(f"{BASE}/places/nearby", json={
        "lat": 12.9716, "lng": 77.5946,
        "radius_km": 2.0, "category": "restaurant_italian",
    })
    for hit in r.json()["results"]:
        print(f"  {hit['distance_km']:5.2f} km  —  {hit['place']['canonical_name']}")

    section("Reconcile — UB City Mall (high-conflict)")
    r = httpx.post(f"{BASE}/places/reconcile/place_009")
    body = r.json()
    print(f"  Canonical phone: {body['canonical'].get('phone')}")
    print(f"  Confidence:      {body['confidence']}")
    print(f"  Escalate?        {body['needs_escalation']}")
    print(f"  Conflicts:       {len(body['conflicts'])}")

    section("Top 5 stalest places")
    r = httpx.get(f"{BASE}/places/stale", params={"limit": 5})
    for item in r.json()["stale_places"]:
        print(f"  {item['staleness_score']:.2f}  {item['place']['canonical_name']}")
        for reason in item["reasons"]:
            print(f"        - {reason}")

    section("Deduplicate — loose thresholds")
    r = httpx.post(f"{BASE}/places/deduplicate", json={
        "distance_threshold_m": 500, "name_similarity_threshold": 60,
    })
    body = r.json()
    print(f"  Found {body['total_groups']} duplicate groups")
    for g in body["duplicate_groups"]:
        names = [p["canonical_name"] for p in g["places"]]
        print(f"    [{g['confidence']}] {' | '.join(names)} — {g['reason']}")


if __name__ == "__main__":
    main()
