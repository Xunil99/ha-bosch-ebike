"""Standalone tests for range_estimate.py — run with: python3 tests/test_range_estimate.py"""
import importlib.util
from pathlib import Path

# Load the module file directly: importing the package would pull in
# custom_components/bosch_ebike/__init__.py, which needs Home Assistant.
_MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "bosch_ebike" / "range_estimate.py"
)
_spec = importlib.util.spec_from_file_location("range_estimate", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
compute_range_estimate = _mod.compute_range_estimate


def act(aid, km, start="2026-06-01T10:00:00Z"):
    return {"id": aid, "distance": km * 1000, "startTime": start}


def test_happy_path():
    # 5 Touren à 20 km à 100 Wh -> 5 Wh/km
    activities = [act(f"a{i}", 20) for i in range(5)]
    bike_map = {f"a{i}": "bike1" for i in range(5)}
    cons = {f"a{i}": {"consumed_wh": 100.0} for i in range(5)}
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r is not None
    assert abs(r["wh_per_km"] - 5.0) < 0.001, r
    assert r["tours_used"] == 5
    assert abs(r["window_km"] - 100.0) < 0.001
    assert r["newest_tour_date"] == "2026-06-01T10:00:00Z"


def test_distance_weighted():
    # 100 km à 5 Wh/km (als 2 Touren, MIN_TOURS=3) + 10 km à 16.5 Wh/km
    # -> (500+165)/110 Wh/km, auf 2 Nachkommastellen gerundet
    activities = [act("a1", 50), act("a1b", 50), act("a2", 10)]
    bike_map = {"a1": "bike1", "a1b": "bike1", "a2": "bike1"}
    cons = {
        "a1": {"consumed_wh": 250.0},
        "a1b": {"consumed_wh": 250.0},
        "a2": {"consumed_wh": 165.0},
    }
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert abs(r["wh_per_km"] - round(665.0 / 110.0, 2)) < 0.001


def test_window_stops_at_500km():
    # 12 Touren à 50 km: nach 10 Touren sind 500 km erreicht -> Tour 11/12 ignoriert
    activities = [act(f"a{i}", 50) for i in range(12)]
    bike_map = {f"a{i}": "bike1" for i in range(12)}
    cons = {f"a{i}": {"consumed_wh": 250.0} for i in range(12)}
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 10
    assert abs(r["window_km"] - 500.0) < 0.001


def test_window_overshoot_includes_crossing_tour():
    # 9 Touren à 60 km: Tour 9 überschreitet die 500-km-Grenze (480 -> 540 km)
    # und wird laut Doku trotzdem noch mitgenommen
    activities = [act(f"a{i}", 60) for i in range(9)]
    bike_map = {f"a{i}": "bike1" for i in range(9)}
    cons = {f"a{i}": {"consumed_wh": 300.0} for i in range(9)}
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 9
    assert abs(r["window_km"] - 540.0) < 0.001


def test_min_data_thresholds():
    # nur 2 Touren -> None; 3 Touren aber < 30 km -> None
    activities = [act("a1", 20), act("a2", 20)]
    bike_map = {"a1": "bike1", "a2": "bike1"}
    cons = {"a1": {"consumed_wh": 100.0}, "a2": {"consumed_wh": 100.0}}
    assert compute_range_estimate(activities, bike_map, cons, "bike1") is None

    activities = [act(f"a{i}", 5) for i in range(3)]
    bike_map = {f"a{i}": "bike1" for i in range(3)}
    cons = {f"a{i}": {"consumed_wh": 25.0} for i in range(3)}
    assert compute_range_estimate(activities, bike_map, cons, "bike1") is None


def test_skips_invalid_tours():
    # Touren ohne Verbrauch, mit 0 Wh oder Mini-Distanz (<0.5 km) überspringen,
    # fremde Bikes ignorieren
    activities = [
        act("ok1", 20), act("nocons", 30), act("zero", 25),
        act("tiny", 0.3), act("other", 40), act("ok2", 20), act("ok3", 20),
    ]
    bike_map = {a["id"]: "bike1" for a in activities}
    bike_map["other"] = "bike2"
    cons = {
        "ok1": {"consumed_wh": 100.0}, "zero": {"consumed_wh": 0.0},
        "tiny": {"consumed_wh": 10.0}, "other": {"consumed_wh": 999.0},
        "ok2": {"consumed_wh": 100.0}, "ok3": {"consumed_wh": 100.0},
    }
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 3
    assert abs(r["wh_per_km"] - 5.0) < 0.001


def test_unmapped_activities_count_for_single_bike_fallback():
    # leere bike_map + fallback_all=True (Single-Bike-Konto, Attribution leer)
    activities = [act(f"a{i}", 20) for i in range(3)]
    cons = {f"a{i}": {"consumed_wh": 100.0} for i in range(3)}
    r = compute_range_estimate(activities, {}, cons, "bike1", fallback_all=True)
    assert r is not None and r["tours_used"] == 3


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
