from src.geo import haversine_km, haversine_m, bounding_box


def test_haversine_same_point():
    assert haversine_km(12.9716, 77.5946, 12.9716, 77.5946) == 0.0


def test_haversine_known_distance():
    # Bangalore to Mumbai is roughly 840 km
    d = haversine_km(12.9716, 77.5946, 19.0760, 72.8777)
    assert 820 < d < 860


def test_haversine_meters():
    # 0.0001 degree of latitude is roughly 11 m
    d = haversine_m(12.9716, 77.5946, 12.9717, 77.5946)
    assert 5 < d < 20


def test_haversine_symmetric():
    a = haversine_km(12.9716, 77.5946, 19.0760, 72.8777)
    b = haversine_km(19.0760, 72.8777, 12.9716, 77.5946)
    assert abs(a - b) < 1e-9


def test_bounding_box_contains_point():
    min_lat, max_lat, min_lng, max_lng = bounding_box(12.9716, 77.5946, 1.0)
    assert min_lat < 12.9716 < max_lat
    assert min_lng < 77.5946 < max_lng
