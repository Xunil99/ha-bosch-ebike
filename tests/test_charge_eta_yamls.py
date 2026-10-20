"""Guard for the on-device charge-time estimate in the ESPHome YAMLs - run with:
python3 tests/test_charge_eta_yamls.py

The bridge estimates the time to 80 % and 100 % itself, from the rate at which
the SoC rises while the charger is connected. That block is copied into five
YAMLs (single bridge, C3, dual bridge, and the two examples), and a copy that
drifts from the others is easy to miss: the firmware CI only builds the factory
files and only for stable tags.

Issue #94: the reference point is the first SoC value after the charger
connects, which sits somewhere INSIDE a 1 % step. Measuring the first rate from
there counts a fraction of a step as a whole one, and because the first sample
is not smoothed, the error faded only slowly (a median of 59 % of the real time
after 5 minutes). The first step now only aligns the reference point to a step
edge, and the rate is measured from the second step on. This test pins that
shape in every copy, per bike.

The YAMLs are read as text, nothing is built: the suite is dependency-free.
"""
import re
from pathlib import Path

ESPHOME = Path(__file__).resolve().parent.parent / "esphome"

# file -> suffixes of the globals (the dual bridge keeps one set per bike)
FILES = {
    "factory.yaml": [""],
    "factory-c3.yaml": [""],
    "factory-dual.yaml": ["_1", "_2"],
    "example-bridge.yaml": [""],
    "example-bridge-mobile.yaml": [""],
}


def _text(name: str) -> str:
    return (ESPHOME / name).read_text(encoding="utf-8")


def _soc_lambda(text: str, sfx: str) -> str:
    """The on_value lambda that maintains chg_rate<sfx>."""
    head = f"if (id(chg_last_soc{sfx}) < 0) {{"
    assert text.count(head) == 1, (sfx, text.count(head))
    start = text.index(head)
    # the lambda ends where the next sensor of the platform block begins
    end = text.index("    odometer:", start)
    return text[start:end]


def test_every_yaml_with_the_estimate_is_covered_here():
    # A new copy of the block must be added to FILES, or it escapes the checks.
    found = {
        p.name for p in ESPHOME.glob("*.yaml")
        if "chg_rate" in p.read_text(encoding="utf-8")
    }
    assert found == set(FILES), sorted(found ^ set(FILES))


def test_the_synced_flag_exists_and_starts_false():
    for name, suffixes in FILES.items():
        text = _text(name)
        for sfx in suffixes:
            pattern = (
                rf"- id: chg_synced{sfx}\b[^\n]*\n"
                r"    type: bool\n"
                r"    restore_value: no\n"
                r"    initial_value: 'false'\n"
            )
            assert re.search(pattern, text), (name, sfx)


def test_a_new_reference_point_is_not_synced():
    for name, suffixes in FILES.items():
        text = _text(name)
        for sfx in suffixes:
            body = _soc_lambda(text, sfx)
            first = body[: body.index("float dsoc")]
            assert f"id(chg_synced{sfx}) = false" in first, (name, sfx)


def test_a_falling_soc_anchors_again():
    for name, suffixes in FILES.items():
        text = _text(name)
        for sfx in suffixes:
            body = _soc_lambda(text, sfx)
            drop = re.search(
                r"if \(dsoc <= -1\.0f\) \{[^}]*\}", body
            )
            assert drop, (name, sfx)
            assert f"id(chg_last_soc{sfx}) = x" in drop.group(0), (name, sfx)
            assert f"id(chg_synced{sfx}) = false" in drop.group(0), (name, sfx)


def test_the_rate_is_only_measured_from_a_synced_reference_point():
    for name, suffixes in FILES.items():
        text = _text(name)
        for sfx in suffixes:
            body = _soc_lambda(text, sfx)
            guard = body.index(f"if (id(chg_synced{sfx})) {{")
            rate = body.index(f"id(chg_rate{sfx}) = ")
            # the smoothing assignment sits inside the guard, not before it
            assert guard < rate, (name, sfx)
            # and the flag is raised after the sample, together with the new
            # reference point, so the NEXT step is measured edge to edge
            raised = body.index(f"id(chg_synced{sfx}) = true;")
            assert rate < raised, (name, sfx)
            assert body.index(f"id(chg_last_soc{sfx}) = x;", raised) > raised, (name, sfx)


def test_the_smoothing_is_unchanged():
    # Only the first sample was wrong; the 0.3 / 0.7 smoothing stays.
    for name, suffixes in FILES.items():
        text = _text(name)
        for sfx in suffixes:
            body = _soc_lambda(text, sfx)
            assert "0.3f * r + 0.7f * id(chg_rate" + sfx + ")" in body, (name, sfx)
            assert f"(id(chg_rate{sfx}) < 0) ? r" in body, (name, sfx)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
