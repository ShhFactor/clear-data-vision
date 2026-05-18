from datetime import datetime, timedelta, timezone

from src.staleness import compute_staleness_score, rank_by_staleness, threshold_for


NOW = datetime(2026, 5, 18, tzinfo=timezone.utc)


def test_fresh_place_has_zero_score():
    place = {
        "last_verified": (NOW - timedelta(days=1)).isoformat(),
        "category": "restaurant_italian",
        "confidence": "HIGH",
    }
    result = compute_staleness_score(place, now=NOW)
    assert result["staleness_score"] == 0.0


def test_old_restaurant_is_stale():
    place = {
        "last_verified": (NOW - timedelta(days=120)).isoformat(),
        "category": "restaurant_italian",
        "confidence": "HIGH",
    }
    result = compute_staleness_score(place, now=NOW)
    assert result["staleness_score"] > 0.3
    assert any("last_verified" in r for r in result["reasons"])


def test_old_park_is_not_stale():
    # Parks have a 365-day threshold
    place = {
        "last_verified": (NOW - timedelta(days=120)).isoformat(),
        "category": "park",
        "confidence": "HIGH",
    }
    result = compute_staleness_score(place, now=NOW)
    assert result["staleness_score"] == 0.0


def test_low_confidence_adds_to_score():
    place = {
        "last_verified": (NOW - timedelta(days=1)).isoformat(),
        "category": "park",
        "confidence": "LOW",
    }
    result = compute_staleness_score(place, now=NOW)
    assert result["staleness_score"] >= 0.3


def test_conflicts_add_to_score():
    place = {
        "last_verified": (NOW - timedelta(days=1)).isoformat(),
        "category": "park",
        "confidence": "HIGH",
        "conflicts": [{}, {}, {}],
    }
    result = compute_staleness_score(place, now=NOW)
    assert result["staleness_score"] > 0


def test_naive_timestamp_treated_as_utc():
    # No tzinfo on the string
    place = {
        "last_verified": (NOW - timedelta(days=1)).replace(tzinfo=None).isoformat(),
        "category": "cafe",
        "confidence": "HIGH",
    }
    # Should not raise — naive is treated as UTC
    result = compute_staleness_score(place, now=NOW)
    assert result["staleness_score"] == 0.0


def test_threshold_for_known_and_unknown_categories():
    assert threshold_for("restaurant_italian") == 30
    assert threshold_for("park") == 365
    assert threshold_for(None) == 90
    assert threshold_for("unknown_category") == 90


def test_rank_by_staleness_orders_descending():
    places = [
        {"id": "a", "last_verified": (NOW - timedelta(days=1)).isoformat(), "category": "cafe", "confidence": "HIGH"},
        {"id": "b", "last_verified": (NOW - timedelta(days=200)).isoformat(), "category": "cafe", "confidence": "LOW"},
        {"id": "c", "last_verified": (NOW - timedelta(days=60)).isoformat(), "category": "cafe", "confidence": "HIGH"},
    ]
    ranked = rank_by_staleness(places, now=NOW)
    ids = [r["place"]["id"] for r in ranked]
    assert ids[0] == "b"
