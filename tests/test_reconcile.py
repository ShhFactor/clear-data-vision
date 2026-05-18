from src.reconcile import (
    compute_confidence,
    reconcile_sources,
    reconcile_with_fallback,
)


def test_reconcile_with_agreement():
    sources = {
        "google_places": {"name": "Pasta Vino", "hours": "10-22"},
        "yelp": {"name": "Pasta Vino", "hours": "10-22"},
    }
    result = reconcile_sources(sources)
    assert result["confidence"] == "MEDIUM"
    assert result["conflicts"] == []
    assert result["canonical"]["name"] == "Pasta Vino"


def test_reconcile_with_conflict():
    sources = {
        "google_places": {"name": "Pasta Vino", "hours": "10-22"},
        "yelp": {"name": "Pasta Vino Restaurant", "hours": "11-23"},
    }
    result = reconcile_sources(sources)
    assert len(result["conflicts"]) >= 1
    fields = {c["field_name"] for c in result["conflicts"]}
    assert "hours" in fields


def test_reconcile_picks_highest_priority():
    sources = {
        "scraper": {"name": "PASTA VINO"},
        "google_places": {"name": "Pasta Vino"},
    }
    result = reconcile_sources(sources)
    assert result["canonical"]["name"] == "Pasta Vino"


def test_reconcile_three_agreeing_sources_is_high_confidence():
    sources = {
        "google_places": {"name": "X", "hours": "10-22"},
        "yelp": {"name": "X", "hours": "10-22"},
        "scraper": {"name": "X", "hours": "10-22"},
    }
    result = reconcile_sources(sources)
    assert result["confidence"] == "HIGH"


def test_reconcile_many_conflicts_escalates():
    sources = {
        "google_places": {"a": "1", "b": "1", "c": "1", "d": "1"},
        "yelp": {"a": "2", "b": "2", "c": "2", "d": "2"},
    }
    result = reconcile_sources(sources)
    assert result["needs_escalation"] is True


def test_reconcile_empty_sources():
    result = reconcile_sources({})
    assert result["canonical"] == {}
    assert result["confidence"] == "LOW"


def test_reconcile_with_fallback_swallows_errors():
    # Passing non-dict source data should not raise
    result = reconcile_with_fallback({"google_places": None})  # type: ignore[arg-type]
    assert "canonical" in result
    assert result["confidence"] == "LOW"


def test_compute_confidence_levels():
    assert compute_confidence({"a": {}, "b": {}, "c": {}}, []) == "HIGH"
    assert compute_confidence({"a": {}, "b": {}}, [{}] * 10) == "LOW"
    assert compute_confidence({"a": {}, "b": {}}, [{}]) == "MEDIUM"
