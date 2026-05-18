from math import radians, sin, cos, sqrt, atan2

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    lat1_r, lng1_r = radians(lat1), radians(lng1)
    lat2_r, lng2_r = radians(lat2), radians(lng2)
    dlat = lat2_r - lat1_r
    dlng = lng2_r - lng1_r
    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlng / 2) ** 2
    return EARTH_RADIUS_KM * 2 * atan2(sqrt(a), sqrt(1 - a))


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    return haversine_km(lat1, lng1, lat2, lng2) * 1000


def bounding_box(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """Approximate (min_lat, max_lat, min_lng, max_lng) for a radius around a point.

    Used as a cheap pre-filter before the exact haversine check. The longitude
    delta widens as you approach the poles because lines of longitude converge.
    """
    lat_delta = radius_km / 111.0
    # cos(lat) shrinks to 0 at the poles; clamp to avoid div-by-zero
    lng_delta = radius_km / max(0.0001, 111.0 * cos(radians(lat)))
    return (lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta)
