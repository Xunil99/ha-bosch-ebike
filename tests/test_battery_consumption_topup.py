"""Standalone tests for the battery-consumption top-up window - run with:
python3 tests/test_battery_consumption_topup.py

coordinator.py imports Home Assistant, so it cannot be imported directly in
this dependency-free suite. battery_capacity_wh, _track_battery_consumption
and _activity_sort_key are extracted from its source and exec'd on their own,
mirroring test_trick_sensors.py's approach for sensor.py. dt_util is stubbed
with a controllable "now" so the top-up window's timing can be driven
deterministically across simulated polls without any real sleeping.

Forum report this covers (issue #67): a rider recharged their battery
immediately after a ride; the ride's reported consumption came out too low
against the real-world value. Root cause: _track_battery_consumption
attributes a bike's deliveredWhOverLifetime delta to a new activity exactly
once, at whichever poll first sees it - if Bosch's cloud counter is still
catching up with the ride's true energy use at that moment, the shortfall
silently disappears into the next poll's baseline instead of ever reaching
the ride. The top-up window keeps a bike's most recent activity open for a
bounded time so a later counter increase - with no newer ride in between -
still lands on it, corroborated against the bike's own odometer so a
counter increase that actually belongs to a second, not-yet-synced ride
does not get transplanted onto the wrong one, and measured against a
monotonic high-water mark so a counter dip that later recovers is never
credited twice.

Also covers issue #78: a fresh install (or a long HA downtime) can surface
a whole backlog of already-completed historical activities together in one
poll, while deliveredWhOverLifetime itself barely moved in the short
real-world gap since the previous poll - splitting that tiny delta across
the backlog by distance produced a wh_per_km around 100-1000x too low (a
reported 0.01 Wh/km -> 75000 km "range" instead of ~10-15 Wh/km -> ~50-75
km). The fix is plausibility-gated, not a blanket age filter: a poll's
whole new-activity batch is still split proportionally across everything
(old activities included) as long as the implied wh_per_km is physically
plausible (MIN_PLAUSIBLE_WH_PER_KM) - correct even across a long gap when
real riding happened throughout it. Only once the whole batch's implied
wh_per_km is implausible does it get narrowed to just the
CONSUMPTION_BACKLOG_CUTOFF-recent activities, and only if THAT narrower
split is itself plausible; otherwise the whole batch is left with no
consumption entries at all rather than a still-wrong number - already
handled gracefully everywhere consumed_wh is read. An earlier, unconditional
age-only version of this fix was caught in review before release: it wrongly
zeroed older, equally real rides and inflated recent ones whenever a long
downtime had genuine riding throughout it (see
test_downtime_with_real_riding_still_splits_across_whole_batch).
"""
import ast
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_COORD = _ROOT / "custom_components" / "ha_bosch_ebike" / "coordinator.py"
_SRC = _COORD.read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)


def _module_const(name: str) -> ast.Assign:
    node = next(
        (
            n for n in _TREE.body
            if isinstance(n, ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == name
        ),
        None,
    )
    assert node is not None, (
        f"coordinator.py no longer defines {name} at module level - update "
        "this test alongside the rename/removal"
    )
    return node


_window_node = _module_const("CONSUMPTION_TOPUP_WINDOW")
_tolerance_node = _module_const("CONSUMPTION_TOPUP_ODOMETER_TOLERANCE_M")
_max_dip_node = _module_const("MAX_PROTECTED_DELIVERED_WH_DIP")
_backlog_cutoff_node = _module_const("CONSUMPTION_BACKLOG_CUTOFF")
_min_plausible_node = _module_const("MIN_PLAUSIBLE_WH_PER_KM")

# parse_iso_utc lives in live_enrichment.py, which (like coordinator.py)
# imports Home Assistant and so cannot be imported directly here either -
# extracted the same AST way, from its own source file.
_LIVE_ENRICHMENT = _ROOT / "custom_components" / "ha_bosch_ebike" / "live_enrichment.py"
_LIVE_ENRICHMENT_TREE = ast.parse(_LIVE_ENRICHMENT.read_text(encoding="utf-8"))
_parse_iso_utc_node = next(
    n for n in _LIVE_ENRICHMENT_TREE.body
    if isinstance(n, ast.FunctionDef) and n.name == "parse_iso_utc"
)

_class_node = next(
    n for n in _TREE.body
    if isinstance(n, ast.ClassDef) and n.name == "BoschEBikeCoordinator"
)
_WANTED_METHODS = {"battery_capacity_wh", "_track_battery_consumption", "_activity_sort_key"}
_methods = [
    n for n in _class_node.body
    if isinstance(n, ast.FunctionDef) and n.name in _WANTED_METHODS
]
assert {m.name for m in _methods} == _WANTED_METHODS, (
    f"BoschEBikeCoordinator no longer defines "
    f"{_WANTED_METHODS - {m.name for m in _methods}} - update this test"
)
# _activity_sort_key is a @staticmethod - strip decorators so exec'ing it at
# module level yields a plain callable rather than a (pre-3.10-uncallable)
# staticmethod object.
for _m in _methods:
    _m.decorator_list = []


class _FakeDtUtil:
    """Stand-in for homeassistant.util.dt with a controllable 'now'."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def utcnow(self) -> datetime:
        return self.now


_fake_dt_util = _FakeDtUtil(datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc))

_ns: dict = {
    "Any": __import__("typing").Any,
    "datetime": datetime,  # parse_iso_utc's body needs this (imported at
    # live_enrichment.py's module level, outside the extracted function node)
    "timedelta": timedelta,
    "dt_util": _fake_dt_util,
    "_LOGGER": __import__("logging").getLogger("test_battery_consumption_topup"),
    "DEFAULT_BATTERY_CAPACITY_WH": 750,
}
# parse_iso_utc first (the constants/methods below don't need it, but
# _track_battery_consumption's body calls it directly by name, so it must
# already be in _ns as a global before that method execs).
exec(  # noqa: S102
    compile(ast.Module(body=[_parse_iso_utc_node], type_ignores=[]), str(_LIVE_ENRICHMENT), "exec"),
    _ns,
)
# Constants first (the method bodies read them as globals), then the
# methods, all sharing _ns as their __globals__ so later mutating
# _fake_dt_util.now is visible on every subsequent call.
exec(  # noqa: S102 - executing our own source, see the module docstring
    compile(
        ast.Module(body=[_window_node, _tolerance_node, _max_dip_node, _backlog_cutoff_node, _min_plausible_node], type_ignores=[]),
        str(_COORD), "exec",
    ),
    _ns,
)
exec(  # noqa: S102
    compile(ast.Module(body=_methods, type_ignores=[]), str(_COORD), "exec"), _ns
)
CONSUMPTION_TOPUP_WINDOW = _ns["CONSUMPTION_TOPUP_WINDOW"]
MAX_PROTECTED_DELIVERED_WH_DIP = _ns["MAX_PROTECTED_DELIVERED_WH_DIP"]
CONSUMPTION_TOPUP_ODOMETER_TOLERANCE_M = _ns["CONSUMPTION_TOPUP_ODOMETER_TOLERANCE_M"]
CONSUMPTION_BACKLOG_CUTOFF = _ns["CONSUMPTION_BACKLOG_CUTOFF"]
MIN_PLAUSIBLE_WH_PER_KM = _ns["MIN_PLAUSIBLE_WH_PER_KM"]
_parse_iso_utc = _ns["parse_iso_utc"]
_battery_capacity_wh = _ns["battery_capacity_wh"]
_track_battery_consumption = _ns["_track_battery_consumption"]
_activity_sort_key = _ns["_activity_sort_key"]


class _FakeCoordinator:
    """Just enough of BoschEBikeCoordinator's instance state to run the
    extracted methods against."""

    def __init__(self) -> None:
        self._all_activities: list = []
        self._prev_activity_ids: set = set()
        self._activity_bike: dict = {}
        self._prev_delivered_wh: dict = {}
        self._activity_consumption: dict = {}
        self._consumption_topup_activity: dict = {}
        self._consumption_topup_deadline: dict = {}
        self._consumption_topup_baseline_wh: dict = {}
        self._consumption_topup_odometer_m: dict = {}
        self._battery_capacity_wh: dict = {}
        self.config_entry = None
        self.battery_capacity_wh = types.MethodType(_battery_capacity_wh, self)
        # _activity_sort_key is a staticmethod on the real class - a plain
        # function assigned as an INSTANCE attribute is not auto-bound, so
        # self._activity_sort_key(a) calls it with exactly one argument,
        # same as the real staticmethod access does.
        self._activity_sort_key = _activity_sort_key


def _bike(bike_id: str, delivered_wh: float, odometer_m: float = 0.0) -> dict:
    return {
        "id": bike_id,
        "batteries": [{"deliveredWhOverLifetime": delivered_wh}],
        "driveUnit": {"odometer": odometer_m},
    }


def _activity(aid: str, start: str, end: str, distance: float = 5000) -> dict:
    return {"id": aid, "startTime": start, "endTime": end, "distance": distance}


def _track(coord: _FakeCoordinator, bikes: list) -> bool:
    return _track_battery_consumption(coord, bikes)


def test_single_new_ride_gets_exact_delta_and_opens_topup_window() -> None:
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}

    changed = _track(coord, [_bike("bike-1", 1200.0)])

    assert changed is True
    entry = coord._activity_consumption["a1"]
    assert entry["consumed_wh"] == 200.0
    assert entry["is_exact"] is True
    assert coord._consumption_topup_activity["bike-1"] == "a1"
    assert coord._consumption_topup_deadline["bike-1"] == t0 + CONSUMPTION_TOPUP_WINDOW
    assert coord._consumption_topup_baseline_wh["bike-1"] == 1200.0
    assert coord._consumption_topup_odometer_m["bike-1"] == 0.0
    assert coord._prev_delivered_wh["bike-1"] == 1200.0
    assert coord._prev_activity_ids == {"a1"}


def test_topup_applies_when_counter_keeps_climbing_next_poll() -> None:
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0)])
    assert coord._activity_consumption["a1"]["consumed_wh"] == 200.0

    # Poll 2, 20 minutes later: no new ride, odometer unchanged (parked), but
    # the cloud counter climbed further - the backend is still catching up
    # with the SAME ride.
    _fake_dt_util.now = t0 + timedelta(minutes=20)
    changed = _track(coord, [_bike("bike-1", 1235.0)])

    assert changed is True
    entry = coord._activity_consumption["a1"]
    assert entry["consumed_wh"] == 235.0  # 200 (poll 1) + 35 (top-up)
    assert entry["percentage"] == round(235.0 / 750 * 100, 1)
    assert coord._prev_delivered_wh["bike-1"] == 1235.0
    assert coord._consumption_topup_baseline_wh["bike-1"] == 1235.0


def test_topup_compounds_across_more_than_two_polls() -> None:
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0)])  # +200 -> 200

    _fake_dt_util.now = t0 + timedelta(minutes=20)
    _track(coord, [_bike("bike-1", 1235.0)])  # +35 -> 235

    _fake_dt_util.now = t0 + timedelta(minutes=50)
    _track(coord, [_bike("bike-1", 1250.0)])  # +15 -> 250

    _fake_dt_util.now = t0 + timedelta(hours=2)
    changed = _track(coord, [_bike("bike-1", 1260.0)])  # +10 -> 260, still < 3h

    assert changed is True
    assert coord._activity_consumption["a1"]["consumed_wh"] == 260.0
    # A regression that one-shot-closed the window after its first
    # successful top-up would have left this at 235 or stopped updating
    # the baseline - both are excluded by these two assertions together.
    assert coord._consumption_topup_activity["bike-1"] == "a1"
    assert coord._consumption_topup_baseline_wh["bike-1"] == 1260.0


def test_battery_swap_self_heals_within_one_poll() -> None:
    """Round-6 finding: the dip-protection pin (R5(i)) must NOT catch a
    genuine reset. A removable e-bike battery swap (or drive-unit
    replacement) makes deliveredWhOverLifetime restart near zero - a huge
    drop, nothing like a small backend glitch. Pinning the old high value
    against THAT would lock the bike's consumption tracking out until the
    new battery's own total organically climbs back past the old one's
    final reading (months to years); it must instead follow the drop
    immediately, exactly like the un-pinned pre-R5(i) code did."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 49_500.0}
    _track(coord, [_bike("bike-1", 50_000.0)])  # a1 = 500
    assert coord._prev_delivered_wh["bike-1"] == 50_000.0

    # Poll 2: battery swapped - fresh pack reports a near-zero lifetime
    # total. A ride that lands in this same poll can't be resolved yet
    # (delta is deeply negative against the OLD baseline) and correctly
    # stays unresolved for a retry, but the baseline itself must follow
    # the drop, not pin at 50_000.
    _fake_dt_util.now = t0 + timedelta(minutes=20)
    coord._all_activities.append(_activity("a2", "2026-08-01T09:40:00Z", "2026-08-01T09:50:00Z"))
    coord._activity_bike["a2"] = "bike-1"
    _track(coord, [_bike("bike-1", 60.0)])

    assert "a2" not in coord._activity_consumption  # correctly unresolved this poll
    assert coord._prev_delivered_wh["bike-1"] == 60.0  # followed the reset, not pinned

    # Poll 3: the NEW battery has grown normally - tracking must already
    # be back to normal, not stuck waiting to climb past 50_000 again.
    _fake_dt_util.now = t0 + timedelta(minutes=40)
    _track(coord, [_bike("bike-1", 110.0)])

    assert coord._activity_consumption["a2"]["consumed_wh"] == 50.0
    assert coord._prev_delivered_wh["bike-1"] == 110.0


def test_dip_protection_boundary_at_max_protected_wh_dip() -> None:
    for drop, should_be_pinned in (
        (MAX_PROTECTED_DELIVERED_WH_DIP, True),
        (MAX_PROTECTED_DELIVERED_WH_DIP + 0.1, False),
    ):
        coord = _FakeCoordinator()
        t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
        _fake_dt_util.now = t0

        coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
        coord._activity_bike = {"a1": "bike-1"}
        coord._prev_delivered_wh = {"bike-1": 1000.0}
        _track(coord, [_bike("bike-1", 1200.0)])
        assert coord._prev_delivered_wh["bike-1"] == 1200.0

        _fake_dt_util.now = t0 + timedelta(minutes=20)
        _track(coord, [_bike("bike-1", 1200.0 - drop)])

        expected = 1200.0 if should_be_pinned else 1200.0 - drop
        assert coord._prev_delivered_wh["bike-1"] == expected, drop


def test_dip_then_a_new_activity_does_not_inflate_its_initial_credit() -> None:
    """Round-5 finding: a newly-DISCOVERED activity's initial credit reads
    _prev_delivered_wh directly (not the top-up's own protected baseline).
    If a dip is allowed to regress that reference, a later activity
    discovered before the counter has fully recovered past its OLD high
    point gets credited for Wh it never actually consumed - exactly the
    amount of the dip's depth, on top of the top-up path's own protection."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("m", "2026-08-01T09:00:00Z", "2026-08-01T09:15:00Z")]
    coord._activity_bike = {"m": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1010.0)])  # m = 10
    assert coord._activity_consumption["m"]["consumed_wh"] == 10.0

    # Poll 2: counter dips, no new activity.
    _fake_dt_util.now = t0 + timedelta(minutes=20)
    _track(coord, [_bike("bike-1", 1005.0)])
    assert coord._prev_delivered_wh["bike-1"] == 1010.0  # must not have regressed

    # Poll 3: counter recovers to 1020 (past its OLD high of 1010) AND a
    # brand-new, unrelated activity n is discovered in the SAME poll. n's
    # initial share must be 1020 - 1010 = 10, not 1020 - 1005 = 15 (which
    # would re-include the 5 Wh the dip already "spent" once via m).
    _fake_dt_util.now = t0 + timedelta(minutes=40)
    coord._all_activities = [
        _activity("n", "2026-08-01T09:30:00Z", "2026-08-01T09:45:00Z"),
        _activity("m", "2026-08-01T09:00:00Z", "2026-08-01T09:15:00Z"),
    ]
    coord._activity_bike["n"] = "bike-1"
    _track(coord, [_bike("bike-1", 1020.0)])

    assert coord._activity_consumption["n"]["consumed_wh"] == 10.0
    assert coord._activity_consumption["m"]["consumed_wh"] == 10.0  # untouched
    # Total credited must equal the true net growth over the whole span.
    assert (
        coord._activity_consumption["m"]["consumed_wh"]
        + coord._activity_consumption["n"]["consumed_wh"]
        == 1020.0 - 1000.0
    )


def test_dip_then_recovery_does_not_double_count() -> None:
    """A counter dip must not let its later recovery be re-credited.

    Both _prev_delivered_wh and the top-up's own high-water mark
    (_consumption_topup_baseline_wh) are monotonically non-decreasing -
    neither may regress on a dip, or recovering back to the same high
    point would pay out the dip's magnitude a second time (either to the
    watched activity via the top-up path, or to a brand-new activity
    discovered after the recovery via the normal delta path).
    """
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0)])  # a1 = 200, baseline = 1200

    # Poll 2: counter dips (cloud glitch / correction). Nothing credited,
    # and neither reference may regress to 1190.
    _fake_dt_util.now = t0 + timedelta(minutes=30)
    _track(coord, [_bike("bike-1", 1190.0)])
    assert coord._activity_consumption["a1"]["consumed_wh"] == 200.0
    assert coord._prev_delivered_wh["bike-1"] == 1200.0
    assert coord._consumption_topup_baseline_wh["bike-1"] == 1200.0

    # Poll 3: counter recovers past its old high point. Only the amount
    # ABOVE the old high (1250 - 1200 = 50) may be credited, not
    # 1250 - 1190 = 60 (which would double-count the 10 Wh dip).
    _fake_dt_util.now = t0 + timedelta(hours=1)
    _track(coord, [_bike("bike-1", 1250.0)])

    entry = coord._activity_consumption["a1"]
    assert entry["consumed_wh"] == 250.0  # 200 + 50, matches the TRUE net rise (1250-1000)
    assert coord._consumption_topup_baseline_wh["bike-1"] == 1250.0


def test_topup_skipped_when_odometer_indicates_a_new_ride() -> None:
    """A large counter jump alongside real riding is likely a SEPARATE
    ride whose own activity summary just hasn't synced in yet - crediting
    it to the old watched ride would transplant one ride's energy onto
    another, worse than the pre-fix silent loss. The odometer is the
    independent signal that catches this."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0, odometer_m=10_000.0)])
    assert coord._consumption_topup_activity["bike-1"] == "a1"

    # Poll 2: counter climbs a lot AND the odometer moved 8 km - a real
    # ride almost certainly happened, so this must NOT be credited to a1.
    _fake_dt_util.now = t0 + timedelta(minutes=45)
    changed = _track(coord, [_bike("bike-1", 1450.0, odometer_m=18_000.0)])

    assert coord._activity_consumption["a1"]["consumed_wh"] == 200.0  # untouched
    assert "bike-1" not in coord._consumption_topup_activity  # window closed, not left open
    # The un-credited delta still becomes the new baseline (silently
    # absorbed, same as before this mechanism existed - not misattributed).
    assert coord._prev_delivered_wh["bike-1"] == 1450.0
    assert changed is True  # the baseline update itself still counts as a change


def test_topup_tolerates_small_odometer_noise() -> None:
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0, odometer_m=10_000.0)])

    # Odometer moved a few metres (rounding/reporting noise), well under
    # CONSUMPTION_TOPUP_ODOMETER_TOLERANCE_M - the top-up must still apply.
    _fake_dt_util.now = t0 + timedelta(minutes=20)
    _track(coord, [_bike("bike-1", 1235.0, odometer_m=10_000.0 + CONSUMPTION_TOPUP_ODOMETER_TOLERANCE_M - 1)])

    assert coord._activity_consumption["a1"]["consumed_wh"] == 235.0
    assert coord._consumption_topup_activity["bike-1"] == "a1"


def test_zero_distance_batch_splits_evenly_not_duplicated() -> None:
    """Pre-existing bug found alongside the top-up work: when 2+ brand-new
    activities for the same bike land in one poll and NONE reports a usable
    distance (e.g. tracks still uploading), total_distance is 0 - falling
    through to the single-activity share (the full delta_wh) would credit
    the WHOLE delta to EACH one, multiplying the bike's real energy growth
    by the batch size instead of splitting it."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [
        _activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:15:00Z", distance=0),
        _activity("a2", "2026-08-01T09:20:00Z", "2026-08-01T09:35:00Z", distance=0),
    ]
    coord._activity_bike = {"a1": "bike-1", "a2": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}

    _track(coord, [_bike("bike-1", 1200.0)])  # delta = 200

    assert coord._activity_consumption["a1"]["consumed_wh"] == 100.0
    assert coord._activity_consumption["a2"]["consumed_wh"] == 100.0
    assert coord._activity_consumption["a1"]["is_exact"] is False
    assert (
        coord._activity_consumption["a1"]["consumed_wh"]
        + coord._activity_consumption["a2"]["consumed_wh"]
        == 200.0
    )


def test_odometer_reference_advances_symmetrically_with_baseline() -> None:
    """Round-4 finding: when a non-superseding activity's OWN real ride
    moves the odometer (fully explaining that movement via its own,
    separately-credited delta), the still-open window's odometer reference
    must advance together with its energy baseline - otherwise a later
    poll's corroboration re-litigates already-explained distance and
    wrongly closes an otherwise still-legitimate window."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 20, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("c", "2026-08-01T14:00:00Z", "2026-08-01T15:00:00Z")]
    coord._activity_bike = {"c": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0, odometer_m=10_000.0)])  # c = 200

    # Poll 2: an older, non-superseding ride b syncs in and gets its own
    # delta; ITS real riding moves the odometer well past the tolerance on
    # its own (305 m from the window-open reference).
    _fake_dt_util.now = t0 + timedelta(minutes=20)
    coord._all_activities = [
        _activity("c", "2026-08-01T14:00:00Z", "2026-08-01T15:00:00Z"),
        _activity("b", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z"),
    ]
    coord._activity_bike["b"] = "bike-1"
    _track(coord, [_bike("bike-1", 1235.0, odometer_m=10_305.0)])
    assert coord._activity_consumption["b"]["consumed_wh"] == 35.0
    assert coord._consumption_topup_activity["bike-1"] == "c"  # not hijacked
    # The odometer reference must have advanced to 10_305 along with the
    # baseline - not stayed pinned at the poll-1 value of 10_000.
    assert coord._consumption_topup_odometer_m["bike-1"] == 10_305.0

    # Poll 3: no new ride, no further movement (odometer stays at 10_305 -
    # the SAME value it was already at when b's own delta was resolved).
    # c's continuing catch-up must still be credited, not wrongly blocked
    # by comparing against the stale poll-1 odometer reading.
    _fake_dt_util.now = t0 + timedelta(minutes=40)
    _track(coord, [_bike("bike-1", 1260.0, odometer_m=10_305.0)])

    assert coord._activity_consumption["c"]["consumed_wh"] == 225.0  # 200 + 25
    assert coord._consumption_topup_activity["bike-1"] == "c"


def test_expired_window_does_not_block_a_new_older_activity() -> None:
    """Round-4 finding: an existing window whose deadline has already
    lapsed (but not yet purged - that only happens later, in the
    reconciliation loop) must not out-rank a newly-discovered, even older
    activity - it has no legitimate claim left either."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("c", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"c": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0)])  # c opens the window
    assert coord._consumption_topup_activity["bike-1"] == "c"

    # Well past c's window (3h) - a chronologically OLDER activity b (than
    # c) is only now discovered/attributed. c's window has no legitimate
    # claim left; b must still get its own fresh window.
    _fake_dt_util.now = t0 + CONSUMPTION_TOPUP_WINDOW + timedelta(minutes=1)
    coord._all_activities = [
        _activity("c", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z"),
        _activity("b", "2026-08-01T02:00:00Z", "2026-08-01T02:30:00Z"),
    ]
    coord._activity_bike["b"] = "bike-1"
    _track(coord, [_bike("bike-1", 1215.0)])  # b = 15 (its own delta)

    assert coord._activity_consumption["b"]["consumed_wh"] == 15.0
    assert coord._consumption_topup_activity["bike-1"] == "b"
    assert coord._consumption_topup_deadline["bike-1"] == _fake_dt_util.now + CONSUMPTION_TOPUP_WINDOW


def test_older_activity_cannot_hijack_a_still_open_newer_window() -> None:
    """Round-2 finding: Bosch's backend can sync activities out of order, so
    "discovered this poll" does not mean "chronologically newest". An
    older ride attributed a poll or more after a newer one must not steal
    the newer ride's still-open top-up window - it gets its own correct
    delta the normal way, but the window must keep watching the newer ride.
    """
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 20, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    # Ride C (the true latest ride) appears first and opens the window.
    coord._all_activities = [_activity("c", "2026-08-01T14:00:00Z", "2026-08-01T15:00:00Z")]
    coord._activity_bike = {"c": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0)])  # c = 200, baseline = 1200
    assert coord._consumption_topup_activity["bike-1"] == "c"

    # Poll 2: no new ride, counter still catching up on c.
    _fake_dt_util.now = t0 + timedelta(minutes=20)
    _track(coord, [_bike("bike-1", 1235.0)])  # c = 235, baseline = 1235
    assert coord._activity_consumption["c"]["consumed_wh"] == 235.0

    # Poll 3: ride B - chronologically EARLIER than c (09:00, vs c's 14:00) -
    # only now syncs in from Bosch's backend and gets attributed. Its own
    # 15 Wh delta is correctly credited to b, but it must NOT take over the
    # top-up window from c.
    _fake_dt_util.now = t0 + timedelta(minutes=40)
    coord._all_activities = [
        _activity("c", "2026-08-01T14:00:00Z", "2026-08-01T15:00:00Z"),
        _activity("b", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z"),
    ]
    coord._activity_bike["b"] = "bike-1"
    _track(coord, [_bike("bike-1", 1250.0)])  # b = 15 (its own delta)

    assert coord._activity_consumption["b"]["consumed_wh"] == 15.0
    assert coord._consumption_topup_activity["bike-1"] == "c"  # NOT hijacked by b
    # c's own high-water mark must have advanced to 1250 even though c
    # itself wasn't touched this poll - poll 3's whole delta (1235 -> 1250)
    # was just spent on b above. Leaving it at the poll-2 value of 1235
    # would let poll 4 re-credit that same 15 Wh to c a second time.
    assert coord._consumption_topup_baseline_wh["bike-1"] == 1250.0

    # Poll 4: no new ride, counter keeps climbing - must still land on c,
    # the true latest ride, not on b.
    _fake_dt_util.now = t0 + timedelta(minutes=60)
    _track(coord, [_bike("bike-1", 1260.0)])

    assert coord._activity_consumption["c"]["consumed_wh"] == 245.0  # 235 + 10
    assert coord._activity_consumption["b"]["consumed_wh"] == 15.0  # untouched
    # Total credited must equal the counter's real net growth (1260-1000) -
    # not more, not less. A stale baseline would over-credit by exactly
    # b's own share (245+15=260 would silently become 260+15=275 instead).
    assert (
        coord._activity_consumption["c"]["consumed_wh"]
        + coord._activity_consumption["b"]["consumed_wh"]
        == 1260.0 - 1000.0
    )


def test_odometer_tolerance_is_cumulative_across_the_whole_window() -> None:
    """Round-2 finding: advancing the odometer reference on every top-up
    turned the tolerance into a fresh per-poll budget, letting several
    separate short rides each pass individually while collectively
    exceeding it. The reference must stay pinned to the window-open value."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0, odometer_m=10_000.0)])  # a1 = 200

    # Poll 2: odometer +150 m from the window-open reference - under budget.
    _fake_dt_util.now = t0 + timedelta(minutes=20)
    _track(coord, [_bike("bike-1", 1235.0, odometer_m=10_150.0)])
    assert coord._activity_consumption["a1"]["consumed_wh"] == 235.0
    # The reference must NOT have advanced to 10_150 - it stays at 10_000.
    assert coord._consumption_topup_odometer_m["bike-1"] == 10_000.0

    # Poll 3: odometer +300 m cumulative from 10_000 (exactly at tolerance) -
    # still corroborated. A buggy per-step check (comparing against 10_150,
    # the previous poll's reading) would ALSO pass here (+150 m step) -
    # this poll alone does not distinguish the two implementations.
    _fake_dt_util.now = t0 + timedelta(minutes=40)
    _track(coord, [_bike("bike-1", 1260.0, odometer_m=10_300.0)])
    assert coord._activity_consumption["a1"]["consumed_wh"] == 260.0
    assert coord._consumption_topup_odometer_m["bike-1"] == 10_000.0

    # Poll 4: odometer +450 m cumulative from 10_000 - now over budget, and
    # THIS is what proves the fix: a buggy per-step check (comparing
    # against 10_300, only +150 m) would still pass and wrongly credit
    # another 20 Wh. The cumulative check correctly blocks it instead.
    _fake_dt_util.now = t0 + timedelta(minutes=60)
    _track(coord, [_bike("bike-1", 1280.0, odometer_m=10_450.0)])
    assert coord._activity_consumption["a1"]["consumed_wh"] == 260.0  # unchanged
    assert "bike-1" not in coord._consumption_topup_activity  # window closed


def test_odometer_boundary_exact_tolerance_passes_one_over_fails() -> None:
    for extra_m, should_pass in ((0.0, True), (0.1, False)):
        coord = _FakeCoordinator()
        t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
        _fake_dt_util.now = t0

        coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
        coord._activity_bike = {"a1": "bike-1"}
        coord._prev_delivered_wh = {"bike-1": 1000.0}
        _track(coord, [_bike("bike-1", 1200.0, odometer_m=1_000.0)])

        _fake_dt_util.now = t0 + timedelta(minutes=20)
        moved = 1_000.0 + CONSUMPTION_TOPUP_ODOMETER_TOLERANCE_M + extra_m
        _track(coord, [_bike("bike-1", 1235.0, odometer_m=moved)])

        expected = 235.0 if should_pass else 200.0
        assert coord._activity_consumption["a1"]["consumed_wh"] == expected, extra_m


def test_negative_odometer_drift_does_not_block_a_topup() -> None:
    """A downward-reading odometer cannot indicate a new ride happened (real
    riding only ever moves it forward), so it is intentionally NOT treated
    as suspicious the way a forward jump is - pinned here so a future
    accidental abs() doesn't silently start blocking legitimate top-ups on
    ordinary negative sensor noise."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0, odometer_m=1_000.0)])

    _fake_dt_util.now = t0 + timedelta(minutes=20)
    _track(coord, [_bike("bike-1", 1235.0, odometer_m=990.0)])  # drifted backward

    assert coord._activity_consumption["a1"]["consumed_wh"] == 235.0


def test_topup_cannot_corroborate_without_odometer_data_and_skips() -> None:
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    # No driveUnit/odometer field at all on this account.
    _track(coord, [{"id": "bike-1", "batteries": [{"deliveredWhOverLifetime": 1200.0}]}])
    assert coord._consumption_topup_activity["bike-1"] == "a1"

    _fake_dt_util.now = t0 + timedelta(minutes=20)
    _track(coord, [{"id": "bike-1", "batteries": [{"deliveredWhOverLifetime": 1235.0}]}])

    assert coord._activity_consumption["a1"]["consumed_wh"] == 200.0  # untouched
    assert "bike-1" not in coord._consumption_topup_activity


def test_topup_expires_after_window() -> None:
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0)])

    # Well past the window: a later increase must NOT retroactively land on
    # the old ride any more - it just becomes the new baseline, same as
    # before this mechanism existed.
    _fake_dt_util.now = t0 + CONSUMPTION_TOPUP_WINDOW + timedelta(minutes=1)
    _track(coord, [_bike("bike-1", 1260.0)])

    entry = coord._activity_consumption["a1"]
    assert entry["consumed_wh"] == 200.0
    assert "bike-1" not in coord._consumption_topup_activity
    assert "bike-1" not in coord._consumption_topup_baseline_wh
    assert coord._prev_delivered_wh["bike-1"] == 1260.0


def test_topup_closes_exactly_at_the_deadline_instant() -> None:
    """The close condition is '>=', not '>' - pin the exact boundary tick
    so a regression relaxing it to '>' (window stays open one instant too
    long) cannot pass unnoticed."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0)])

    _fake_dt_util.now = t0 + CONSUMPTION_TOPUP_WINDOW  # exactly at the deadline
    _track(coord, [_bike("bike-1", 1260.0)])

    assert coord._activity_consumption["a1"]["consumed_wh"] == 200.0
    assert "bike-1" not in coord._consumption_topup_activity


def test_topup_skips_ble_live_sourced_entries() -> None:
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0)])

    # Simulate _enrich_activities_with_live_data overriding the entry right
    # after, exactly like the real poll order in _async_update_data.
    coord._activity_consumption["a1"] = {
        "consumed_wh": 180.0, "capacity_wh": 750, "is_exact": True,
        "percentage": 24.0, "source": "ble_live",
    }

    _fake_dt_util.now = t0 + timedelta(minutes=20)
    _track(coord, [_bike("bike-1", 1235.0)])

    assert coord._activity_consumption["a1"]["consumed_wh"] == 180.0


def test_new_activity_same_poll_is_not_also_topped_up() -> None:
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0)])
    assert coord._activity_consumption["a1"]["consumed_wh"] == 200.0
    old_deadline = coord._consumption_topup_deadline["bike-1"]

    # A second ride shows up in the SAME poll as a further counter jump -
    # the whole new delta belongs to it via the normal path, not split into
    # also topping up a1.
    _fake_dt_util.now = t0 + timedelta(minutes=15)
    coord._all_activities = [
        _activity("a2", "2026-08-01T09:45:00Z", "2026-08-01T10:10:00Z"),
        _activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z"),
    ]
    coord._activity_bike["a2"] = "bike-1"
    _track(coord, [_bike("bike-1", 1260.0)])

    assert coord._activity_consumption["a1"]["consumed_wh"] == 200.0
    assert coord._activity_consumption["a2"]["consumed_wh"] == 60.0
    assert coord._consumption_topup_activity["bike-1"] == "a2"
    # The window's own deadline must move with it, not keep the old (now
    # stale, expiring sooner) one - a regression updating the activity id
    # but leaving the old deadline in place would shorten a2's real
    # eligibility window without any other assertion catching it.
    assert coord._consumption_topup_deadline["bike-1"] > old_deadline
    assert coord._consumption_topup_deadline["bike-1"] == _fake_dt_util.now + CONSUMPTION_TOPUP_WINDOW


def test_topup_guarded_against_reattribution() -> None:
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0, "bike-2": 500.0}
    _track(coord, [_bike("bike-1", 1200.0), _bike("bike-2", 500.0)])
    assert coord._consumption_topup_activity["bike-1"] == "a1"

    # a1 gets reattributed to bike-2 (odometer-matching correction) before
    # the next poll - bike-1's counter must no longer touch it.
    coord._activity_bike["a1"] = "bike-2"
    _fake_dt_util.now = t0 + timedelta(minutes=10)
    _track(coord, [_bike("bike-1", 1240.0), _bike("bike-2", 500.0)])

    assert coord._activity_consumption["a1"]["consumed_wh"] == 200.0


def test_topup_missing_entry_is_a_noop() -> None:
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._all_activities = [_activity("a1", "2026-08-01T09:00:00Z", "2026-08-01T09:30:00Z")]
    coord._activity_bike = {"a1": "bike-1"}
    coord._prev_delivered_wh = {"bike-1": 1000.0}
    _track(coord, [_bike("bike-1", 1200.0)])

    del coord._activity_consumption["a1"]  # e.g. async_assign_activities popped it

    _fake_dt_util.now = t0 + timedelta(minutes=10)
    changed = _track(coord, [_bike("bike-1", 1230.0)])

    assert "a1" not in coord._activity_consumption
    assert changed is True
    assert coord._prev_delivered_wh["bike-1"] == 1230.0


def test_stale_historical_batch_gets_no_consumption_entry() -> None:
    """Issue #78: a backlog of historical activities discovered together in
    one poll must not receive a fabricated wh_per_km from a tiny
    since-last-poll delta that has nothing to do with when they actually
    happened."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0

    coord._prev_delivered_wh = {"bike-1": 50000.0}  # baseline already established
    coord._all_activities = [
        _activity("old-1", "2026-07-01T09:00:00Z", "2026-07-01T10:00:00Z", distance=20000),
        _activity("old-2", "2026-07-05T09:00:00Z", "2026-07-05T10:00:00Z", distance=15000),
        _activity("old-3", "2026-07-10T09:00:00Z", "2026-07-10T10:00:00Z", distance=25000),
    ]
    coord._activity_bike = {"old-1": "bike-1", "old-2": "bike-1", "old-3": "bike-1"}

    # Counter barely moved since the previous poll - no real riding happened
    # in that short real-world gap, exactly the issue #78 scenario.
    _track(coord, [_bike("bike-1", 50003.0)])

    assert coord._activity_consumption == {}


def test_downtime_with_real_riding_still_splits_across_whole_batch() -> None:
    """Regression guard (found in review before release, issue #78): a long
    downtime with REAL riding throughout it must still split the delta
    across the WHOLE batch by distance, old activities included - a
    plausible whole-batch wh_per_km must never trigger narrowing. Doing so
    unconditionally by age would zero out the older, equally real rides and
    inflate the computed consumption of the recent ones (caught here: 4
    real ~50 km rides sharing 2000 Wh must each get 500 Wh / 10 Wh per km,
    not have the 2 oldest zeroed and the 2 newest doubled to 20 Wh/km)."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0
    coord._prev_delivered_wh = {"bike-1": 1000.0}

    coord._all_activities = [
        _activity("day1", "2026-08-01T09:00:00Z", "2026-08-01T10:00:00Z", distance=50000),
        _activity("day2", "2026-08-02T09:00:00Z", "2026-08-02T10:00:00Z", distance=50000),
        _activity("day3", "2026-08-03T09:00:00Z", "2026-08-03T10:00:00Z", distance=50000),
        _activity("day4", "2026-08-04T09:00:00Z", "2026-08-04T10:00:00Z", distance=50000),
    ]
    coord._activity_bike = {a["id"]: "bike-1" for a in coord._all_activities}

    # delta = 2000 Wh over 200 km = 10 Wh/km - well above MIN_PLAUSIBLE_WH_PER_KM,
    # so the whole batch is used as-is, exactly like before issue #78's fix.
    _track(coord, [_bike("bike-1", 3000.0)])

    for aid in ("day1", "day2", "day3", "day4"):
        entry = coord._activity_consumption[aid]
        assert entry["consumed_wh"] == 500.0
        assert entry["is_exact"] is False


def test_fresh_activity_in_same_poll_as_implausible_stale_batch_still_gets_credited() -> None:
    """When the WHOLE batch's implied wh_per_km is implausible, narrowing to
    just the recent activity(ies) must give it its own full, undiluted
    share - the excluded stale one must not eat into its distance pool."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0
    coord._prev_delivered_wh = {"bike-1": 1000.0}

    coord._all_activities = [
        _activity("old-1", "2026-07-01T09:00:00Z", "2026-07-01T10:00:00Z", distance=200000),
        _activity("fresh-1", "2026-08-01T08:00:00Z", "2026-08-01T09:30:00Z", distance=10000),
    ]
    coord._activity_bike = {"old-1": "bike-1", "fresh-1": "bike-1"}

    # Whole batch: 15 Wh / 210 km =~ 0.07 Wh/km - implausible, triggers
    # narrowing. Fresh-only: 15 Wh / 10 km = 1.5 Wh/km - plausible.
    _track(coord, [_bike("bike-1", 1015.0)])

    assert "old-1" not in coord._activity_consumption
    assert coord._activity_consumption["fresh-1"]["consumed_wh"] == 15.0
    assert coord._activity_consumption["fresh-1"]["is_exact"] is True


def test_activity_backlog_cutoff_boundary() -> None:
    """< not <=: within the narrowing fallback, an activity exactly at the
    cutoff age is still eligible, one second older is not. The batch is
    sized so the whole-batch wh_per_km is implausible (forcing narrowing)
    but the narrowed (non-stale) subset is plausible."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0
    coord._prev_delivered_wh = {"bike-1": 1000.0}

    def _iso(dt: datetime) -> str:
        return dt.isoformat().replace("+00:00", "Z")

    just_outside = _iso(t0 - CONSUMPTION_BACKLOG_CUTOFF - timedelta(seconds=1))
    at_cutoff = _iso(t0 - CONSUMPTION_BACKLOG_CUTOFF)
    just_inside = _iso(t0 - CONSUMPTION_BACKLOG_CUTOFF + timedelta(seconds=1))

    coord._all_activities = [
        _activity("too-old", just_outside, just_outside, distance=500000),
        _activity("at-cutoff", at_cutoff, at_cutoff, distance=5000),
        _activity("just-inside", just_inside, just_inside, distance=5000),
    ]
    coord._activity_bike = {a["id"]: "bike-1" for a in coord._all_activities}

    # Whole batch: 15 Wh / 510 km =~ 0.03 Wh/km - implausible. Narrowed
    # (at-cutoff + just-inside only): 15 Wh / 10 km = 1.5 Wh/km - plausible.
    _track(coord, [_bike("bike-1", 1015.0)])

    assert "too-old" not in coord._activity_consumption
    assert "at-cutoff" in coord._activity_consumption
    assert "just-inside" in coord._activity_consumption


def test_stale_activity_missing_timestamps_fails_open() -> None:
    """Within the narrowing fallback, no endTime/startTime at all means
    nothing to judge staleness against, so it stays eligible rather than
    silently losing data for an activity shape we cannot classify (same
    fail-open direction as every other None-safe check in this file)."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0
    coord._prev_delivered_wh = {"bike-1": 1000.0}

    coord._all_activities = [
        _activity("big-old", "2026-06-01T09:00:00Z", "2026-06-01T10:00:00Z", distance=500000),
        {"id": "no-time", "distance": 5000},
    ]
    coord._activity_bike = {"big-old": "bike-1", "no-time": "bike-1"}

    # Whole batch: 15 Wh / 505 km =~ 0.03 Wh/km - implausible. Narrowed
    # (no-time only, since it fails open and big-old is genuinely stale):
    # 15 Wh / 5 km = 3.0 Wh/km - plausible.
    _track(coord, [_bike("bike-1", 1015.0)])

    assert "big-old" not in coord._activity_consumption
    assert coord._activity_consumption["no-time"]["consumed_wh"] == 15.0


def test_fresh_subset_still_implausible_gives_up_entirely() -> None:
    """If narrowing to just the recent activities STILL doesn't produce a
    plausible wh_per_km (e.g. the cloud counter itself hasn't caught up
    yet), give up on the whole poll's batch rather than attribute a still-
    wrong number to whichever activities happen to be recent."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0
    coord._prev_delivered_wh = {"bike-1": 1000.0}

    coord._all_activities = [
        _activity("old", "2026-06-01T09:00:00Z", "2026-06-01T10:00:00Z", distance=200000),
        _activity(
            "fresh-but-tiny-delta", "2026-08-01T08:00:00Z", "2026-08-01T09:30:00Z",
            distance=50000,
        ),
    ]
    coord._activity_bike = {a["id"]: "bike-1" for a in coord._all_activities}

    # delta = 2 Wh; even restricted to just the fresh 50 km ride, that is
    # 0.04 Wh/km - still implausible.
    _track(coord, [_bike("bike-1", 1002.0)])

    assert coord._activity_consumption == {}


def test_stale_batch_is_marked_seen_and_not_retried() -> None:
    """A backlog activity is settled (no data) once, not re-evaluated every
    poll forever - it goes into _prev_activity_ids like any other id whose
    delta was successfully resolved this poll, even though "resolved" here
    means "deliberately given no consumption entry"."""
    coord = _FakeCoordinator()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _fake_dt_util.now = t0
    coord._prev_delivered_wh = {"bike-1": 1000.0}

    coord._all_activities = [
        _activity("old-1", "2026-07-01T09:00:00Z", "2026-07-01T10:00:00Z", distance=20000),
    ]
    coord._activity_bike = {"old-1": "bike-1"}

    _track(coord, [_bike("bike-1", 1003.0)])
    assert "old-1" not in coord._activity_consumption
    assert "old-1" in coord._prev_activity_ids

    # A later poll with the same activity list must not reprocess it into a
    # (still wrong) consumption entry.
    _fake_dt_util.now = t0 + timedelta(hours=1)
    _track(coord, [_bike("bike-1", 1050.0)])
    assert "old-1" not in coord._activity_consumption


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
