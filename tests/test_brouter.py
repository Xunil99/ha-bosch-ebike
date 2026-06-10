"""Standalone tests for brouter.py — run with: python3 tests/test_brouter.py"""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parent.parent / "custom_components" / "bosch_ebike" / "brouter.py"
_spec = importlib.util.spec_from_file_location("brouter", _path)
brouter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(brouter)

build_brouter_url = brouter.build_brouter_url
BRouterRequestError = brouter.BRouterRequestError


def expect_error(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except BRouterRequestError:
        return
    raise AssertionError("expected BRouterRequestError")


def test_happy_path_default_base():
    url = build_brouter_url(None, [[12.35, 48.71], [12.45, 48.75]], "trekking")
    assert url == (
        "https://brouter.de/brouter"
        "?lonlats=12.35,48.71|12.45,48.75"
        "&profile=trekking&alternativeidx=0&format=geojson"
    ), url


def test_custom_base_and_trailing_slash():
    url = build_brouter_url("http://192.168.2.50:17777/", [[1.0, 2.0], [3.0, 4.0]], "mtb")
    assert url.startswith("http://192.168.2.50:17777/brouter?lonlats=1.0,2.0|3.0,4.0&profile=mtb"), url


def test_rejects_bad_profile():
    expect_error(build_brouter_url, None, [[1.0, 2.0], [3.0, 4.0]], "car-eco")


def test_rejects_bad_scheme():
    expect_error(build_brouter_url, "ftp://evil", [[1.0, 2.0], [3.0, 4.0]], "trekking")
    expect_error(build_brouter_url, "file:///etc", [[1.0, 2.0], [3.0, 4.0]], "trekking")


def test_rejects_too_few_or_too_many_points():
    expect_error(build_brouter_url, None, [[1.0, 2.0]], "trekking")
    expect_error(build_brouter_url, None, [[1.0, 2.0]] * 31, "trekking")


def test_rejects_out_of_range_coords():
    expect_error(build_brouter_url, None, [[181.0, 2.0], [3.0, 4.0]], "trekking")
    expect_error(build_brouter_url, None, [[1.0, 91.0], [3.0, 4.0]], "trekking")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
