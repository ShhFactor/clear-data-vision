"""Staleness scoring with category-specific thresholds.

A single "stale after N days" rule misclassifies both restaurants (hours
change quarterly) and parks (mostly static). Categories are mapped to
expected refresh windows; older records score higher.

Confidence and unresolved conflicts also push the score up — a place we're
unsure about should be treated as stale even if it was verified recently.
"""
from __future__ import annotations

from datetime import datetime, timezone

STALE_THRESHOLDS_DAYS = {
    "restaurant": 30,
    "restaurant_italian": 30,
    "restaurant_indian": 30,
    "restaurant_chinese": 30,
    "cafe": 30,
    "bookstore": 90,
    "shopping": 60,
    "park": 365,
    "default": 90,
}


def _parse_iso(value) -> datetime:
    """Parse an ISO timestamp. Treat naive datetimes as UTC for consistency."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def threshold_for(category: str | None) -> int:
    if not category:
        return STALE_THRESHOLDS_DAYS["default"]
    if category in STALE_THRESHOLDS_DAYS:
        return STALE_THRESHOLDS_DAYS[category]
    # Fall back to the prefix before the underscore (restaurant_italian → restaurant)
    prefix = category.split("_")[0]
    return STALE_THRESHOLDS_DAYS.get(prefix, STALE_THRESHOLDS_DAYS["default"])


def compute_staleness_score(place: dict, now: datetime | None = None) -> dict:
    """Return {staleness_score: 0-1, reasons: [str]}."""
    reasons: list[str] = []
    score = 0.0
    now = now or datetime.now(timezone.utc)

    last_verified = place.get("last_verified")
    if last_verified:
        try:
            verified_at = _parse_iso(last_verified)
            days_old = (now - verified_at).days
            threshold = threshold_for(place.get("category"))
            if days_old > threshold:
                # Scale up to 0.6 as days_old grows past the threshold
                age_factor = min(0.6, (days_old - threshold) / threshold * 0.3 + 0.3)
                score += age_factor
                reasons.append(
                    f"last_verified {days_old} days ago (threshold: {threshold})"
                )
        except (ValueError, TypeError):
            score += 0.1
            reasons.append("invalid last_verified timestamp")

    confidence = place.get("confidence")
    if confidence == "LOW":
        score += 0.3
        reasons.append("low confidence score")
    elif confidence == "MEDIUM":
        score += 0.1
        reasons.append("medium confidence score")

    conflicts = place.get("conflicts") or []
    if conflicts:
        delta = min(0.2, len(conflicts) * 0.05)
        score += delta
        reasons.append(f"{len(conflicts)} unresolved conflicts")

    return {"staleness_score": min(score, 1.0), "reasons": reasons}


def rank_by_staleness(places: list[dict], now: datetime | None = None) -> list[dict]:
    """Return places annotated with staleness, most-stale first."""
    scored = []
    for p in places:
        s = compute_staleness_score(p, now=now)
        scored.append({"place": p, **s})
    scored.sort(key=lambda x: x["staleness_score"], reverse=True)
    return scored
