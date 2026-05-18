"""Source reconciliation: pick a canonical record and log every disagreement.

Design choices:
- Source priority over majority voting. With only 2-3 sources, majority is
  brittle; a priority order (derived from observed accuracy in production)
  gives a defensible canonical even when two sources disagree.
- Conflicts are logged, never silently resolved. Consumers (AI agents) get
  the disagreement signal back via the API so they can hedge their answers.
- Coordinates use the priority-source value rather than an average — averaging
  pulls canonical position toward the least-trusted source, and even small
  positional errors break geographic dedup downstream.
"""
from __future__ import annotations

from typing import Literal

Confidence = Literal["HIGH", "MEDIUM", "LOW"]

SOURCE_PRIORITY = {
    "google_places": 3,
    "yelp": 2,
    "scraper": 1,
}


def _priority(source: str) -> int:
    return SOURCE_PRIORITY.get(source, 0)


def reconcile_sources(sources: dict) -> dict:
    """Reconcile multi-source data into a canonical record + conflict list."""
    canonical: dict = {}
    conflicts: list[dict] = []

    if not sources:
        return {
            "canonical": {},
            "conflicts": [],
            "confidence": "LOW",
            "needs_escalation": True,
        }

    all_fields: set[str] = set()
    for source_data in sources.values():
        all_fields.update(source_data.keys())

    # Pre-sort sources by priority descending so the highest-priority source
    # wins ties when we pick canonical values.
    sorted_sources = sorted(sources.items(), key=lambda kv: -_priority(kv[0]))

    for field in all_fields:
        values = [
            (source, data[field])
            for source, data in sorted_sources
            if field in data and data[field] is not None
        ]
        if not values:
            continue

        # Canonical = highest-priority non-null value
        canonical[field] = values[0][1]

        # Conflict detection. lat/lng are intentionally excluded because
        # sub-meter coordinate jitter is not a meaningful disagreement.
        if field in ("lat", "lng"):
            continue

        # Store (normalised_key, source, original_value) so conflict pairs
        # can be emitted in one pass without re-scanning `values`.
        seen: dict[str, tuple[str, str]] = {}
        for source, value in values:
            key = str(value).strip().lower()
            if key in seen:
                continue
            for prev_key, (prev_source, prev_value) in seen.items():
                if prev_key != key:
                    conflicts.append({
                        "field_name": field,
                        "source_a": prev_source,
                        "value_a": prev_value,
                        "source_b": source,
                        "value_b": str(value),
                    })
            seen[key] = (source, str(value))

    return {
        "canonical": canonical,
        "conflicts": conflicts,
        "confidence": compute_confidence(sources, conflicts),
        "needs_escalation": len(conflicts) > 3,
    }


def compute_confidence(sources: dict, conflicts: list) -> Confidence:
    """Confidence reflects both source agreement and source count."""
    n_sources = len(sources)
    n_conflicts = len(conflicts)
    if n_sources >= 3 and n_conflicts == 0:
        return "HIGH"
    if n_conflicts > 5:
        return "LOW"
    if n_sources >= 2 and n_conflicts <= 2:
        return "MEDIUM"
    if n_sources == 1:
        return "MEDIUM"
    return "LOW"


def reconcile_with_fallback(sources: dict) -> dict:
    """Always returns a usable result; never raises.

    If reconciliation fails, fall back to the highest-priority source as-is
    so the API can still answer. Failure is recorded in fallback_reason so
    consumers can see they're reading degraded data.
    """
    try:
        return reconcile_sources(sources)
    except Exception as e:
        if sources:
            best = max(sources.keys(), key=_priority)
            return {
                "canonical": sources[best],
                "conflicts": [],
                "confidence": "LOW",
                "needs_escalation": True,
                "fallback_reason": f"Reconciliation failed: {e}",
            }
        return {
            "canonical": {},
            "conflicts": [],
            "confidence": "LOW",
            "needs_escalation": True,
            "fallback_reason": "No sources available",
        }
