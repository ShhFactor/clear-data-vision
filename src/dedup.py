"""Deduplication: cluster near-identical places across sources.

Two-stage approach: geographic distance filter (cheap), then fuzzy name
match (expensive). Names are normalised first to strip casing and common
suffixes that don't carry identity information.
"""
from __future__ import annotations

from rapidfuzz import fuzz

from src.geo import haversine_m

NAME_SUFFIXES = [
    " restaurant", " bistro", " cafe", " coffee", " pvt ltd", " ltd",
    " bookstore", " mall", " park", " hotel", " bar",
]


def normalise_name(name: str) -> str:
    """Lowercase, strip whitespace, remove common trailing suffixes."""
    n = name.lower().strip()
    # Strip suffixes iteratively (handles "X Restaurant Bistro")
    changed = True
    while changed:
        changed = False
        for suffix in NAME_SUFFIXES:
            if n.endswith(suffix):
                n = n[: -len(suffix)].strip()
                changed = True
    return n


def is_duplicate_pair(
    place_a: dict,
    place_b: dict,
    distance_threshold_m: float = 100,
    name_similarity_threshold: int = 80,
) -> tuple[bool, str]:
    """Return (is_duplicate, reason)."""
    distance = haversine_m(
        place_a["lat"], place_a["lng"],
        place_b["lat"], place_b["lng"],
    )
    if distance > distance_threshold_m:
        return False, f"Too far: {distance:.0f}m"

    name_a = place_a.get("canonical_name") or place_a.get("name", "")
    name_b = place_b.get("canonical_name") or place_b.get("name", "")
    name_score = fuzz.token_set_ratio(normalise_name(name_a), normalise_name(name_b))
    if name_score < name_similarity_threshold:
        return False, f"Names too different: {name_score}%"

    return True, f"Geographic proximity {distance:.0f}m + name similarity {name_score}%"


def find_duplicate_groups(
    places: list[dict],
    distance_threshold_m: float = 100,
    name_similarity_threshold: int = 80,
) -> list[dict]:
    """Cluster a list of places into groups of likely duplicates.

    Greedy single-pass clustering: each place is either added to an existing
    group it matches or starts its own group. Good enough for portfolio-scale
    data; production would use a union-find structure with a spatial index.
    """
    groups: list[dict] = []
    assigned: set[int] = set()

    for i, place in enumerate(places):
        if i in assigned:
            continue
        group = [place]
        assigned.add(i)
        reasons: list[str] = []

        for j in range(i + 1, len(places)):
            if j in assigned:
                continue
            is_dup, reason = is_duplicate_pair(
                place, places[j],
                distance_threshold_m=distance_threshold_m,
                name_similarity_threshold=name_similarity_threshold,
            )
            if is_dup:
                group.append(places[j])
                assigned.add(j)
                reasons.append(reason)

        if len(group) > 1:
            groups.append({
                "places": group,
                "confidence": "HIGH" if len(group) >= 3 else "MEDIUM",
                "reason": reasons[0] if reasons else "match",
            })

    return groups
