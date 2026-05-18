from src.dedup import find_duplicate_groups, is_duplicate_pair, normalise_name


def test_normalise_name_strips_suffixes():
    assert normalise_name("Pasta Vino Restaurant") == "pasta vino"
    assert normalise_name("Pasta Vino Restaurant Bistro") == "pasta vino"
    assert normalise_name("  CAFE COFFEE DAY  ") == "cafe coffee day"
    assert normalise_name("Phoenix Mall") == "phoenix"


def test_identical_places_are_duplicates():
    a = {"name": "Cafe Coffee Day", "lat": 12.97, "lng": 77.59}
    b = {"name": "Cafe Coffee Day", "lat": 12.97, "lng": 77.59}
    is_dup, _ = is_duplicate_pair(a, b)
    assert is_dup


def test_far_places_not_duplicates():
    a = {"name": "Pasta Vino", "lat": 12.97, "lng": 77.59}
    b = {"name": "Pasta Vino", "lat": 19.07, "lng": 72.88}
    is_dup, reason = is_duplicate_pair(a, b)
    assert not is_dup
    assert "Too far" in reason


def test_different_names_not_duplicates():
    a = {"name": "Pasta Vino", "lat": 12.97, "lng": 77.59}
    b = {"name": "Sushi Express", "lat": 12.97, "lng": 77.59}
    is_dup, reason = is_duplicate_pair(a, b)
    assert not is_dup
    assert "Names too different" in reason


def test_fuzzy_name_match():
    a = {"name": "Pasta Vino", "lat": 12.97, "lng": 77.59}
    b = {"name": "Pasta Vino Restaurant", "lat": 12.97, "lng": 77.59}
    is_dup, _ = is_duplicate_pair(a, b)
    assert is_dup


def test_find_duplicate_groups_separates_clusters():
    places = [
        {"name": "Pasta Vino", "lat": 12.9716, "lng": 77.5946},
        {"name": "PASTA VINO", "lat": 12.9716, "lng": 77.5946},
        {"name": "Sushi Express", "lat": 12.9800, "lng": 77.6000},
        {"name": "Sushi Express Bistro", "lat": 12.9800, "lng": 77.6000},
        {"name": "Unrelated Cafe", "lat": 13.0500, "lng": 77.7000},
    ]
    groups = find_duplicate_groups(places)
    assert len(groups) == 2
    sizes = sorted(len(g["places"]) for g in groups)
    assert sizes == [2, 2]


def test_high_confidence_when_three_match():
    places = [
        {"name": "Pasta Vino", "lat": 12.9716, "lng": 77.5946},
        {"name": "PASTA VINO", "lat": 12.9716, "lng": 77.5946},
        {"name": "Pasta Vino Restaurant", "lat": 12.9716, "lng": 77.5947},
    ]
    groups = find_duplicate_groups(places)
    assert len(groups) == 1
    assert groups[0]["confidence"] == "HIGH"
