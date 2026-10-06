"""Standalone tests for charge_session.py — run with: python3 tests/test_charge_session.py"""
import importlib.util
import json
import math
from pathlib import Path

_path = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "charge_session.py"
)
_spec = importlib.util.spec_from_file_location("charge_session", _path)
charge_session = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(charge_session)

Tracker = charge_session.ChargeSessionTracker
IDLE_TIMEOUT_S = charge_session.IDLE_TIMEOUT_S
MAX_RESTORE_AGE_S = charge_session.MAX_RESTORE_AGE_S
MAX_RESTORE_SESSION_S = charge_session.MAX_RESTORE_SESSION_S
CLOCK_SKEW_TOLERANCE_S = charge_session.CLOCK_SKEW_TOLERANCE_S

MIN = 60.0


def test_a_normal_overnight_charge():
    t = Tracker()
    now = 0.0
    t.seed(18, now)
    assert t.in_progress is False
    # 18% -> 100% over four hours, one sample every ten minutes.
    for soc in range(20, 101, 5):
        now += 10 * MIN
        t.feed(soc, now, capacity_wh=750)
    assert t.in_progress is True
    assert t.summary is None, "not published until the session actually ends"

    # Charger done: SoC stops rising. Nothing arrives, then the idle timer
    # fires.
    assert t.check_timeout(now + IDLE_TIMEOUT_S - 1) is False
    assert t.check_timeout(now + IDLE_TIMEOUT_S) is True
    assert t.in_progress is False

    s = t.summary
    assert s["start_soc"] == 18
    assert s["end_soc"] == 100
    assert s["soc_delta"] == 82
    assert s["energy_wh"] == 615.0  # 82% of 750 Wh
    assert s["duration_min"] == 170.0  # 17 samples x 10 min
    assert s["signal_gaps"] == 0
    # The session is dated from the plug-in, not from when the timer fired.
    assert s["started_at"] == 0.0
    assert s["ended_at"] == 170 * MIN


def test_dropout_mid_charge_does_not_split_the_session():
    # Issue #68's failure mode: the BLE bridge loses the bike for a while.
    # A dropout must not end the charge, and must not be mistaken for a
    # second one when the signal comes back.
    t = Tracker()
    t.seed(30, 0.0)
    t.feed(35, 10 * MIN, capacity_wh=500)
    for i, bad in enumerate(["unavailable", None, "unknown", float("nan"), ""]):
        t.feed(bad, (20 + i * 10) * MIN, capacity_wh=500)
    assert t.in_progress is True, "a dropout must never end a charge"
    t.feed(80, 80 * MIN, capacity_wh=500)
    t.check_timeout(80 * MIN + IDLE_TIMEOUT_S)

    s = t.summary
    assert s["start_soc"] == 30, "still measured from before the dropout"
    assert s["end_soc"] == 80
    assert s["soc_delta"] == 50
    assert s["energy_wh"] == 250.0
    assert s["signal_gaps"] == 5


def test_riding_ends_the_session_at_the_peak():
    t = Tracker()
    t.seed(40, 0.0)
    t.feed(60, 5 * MIN, capacity_wh=625)
    t.feed(90, 60 * MIN, capacity_wh=625)
    # Unplugged and ridden away.
    assert t.feed(85, 70 * MIN, capacity_wh=625) is True
    assert t.in_progress is False
    assert t.summary["end_soc"] == 90, "reported from the peak, not the drop"
    assert t.summary["duration_min"] == 60.0

    # And the sample that ended it is the baseline for what comes next,
    # not part of the finished session.
    t.feed(70, 80 * MIN, capacity_wh=625)
    assert t.in_progress is False


def test_self_discharge_after_a_full_charge():
    # A battery sitting at 100% that slips to 99% must be reported as a
    # charge to 100%, and that one percent must not start a new session.
    t = Tracker()
    t.seed(50, 0.0)
    t.feed(60, 5 * MIN, capacity_wh=750)
    t.feed(100, 60 * MIN, capacity_wh=750)
    t.feed(99, 300 * MIN, capacity_wh=750)
    assert t.in_progress is False
    assert t.summary["end_soc"] == 100
    assert t.summary["soc_delta"] == 50


def test_tiny_top_up_is_not_published():
    t = Tracker()
    t.seed(60, 0.0)
    t.feed(62, 10 * MIN, capacity_wh=750)  # 2% - below MIN_SESSION_PCT
    assert t.check_timeout(10 * MIN + IDLE_TIMEOUT_S) is False
    assert t.summary is None
    assert t.in_progress is False

    # But a real charge right afterwards still is.
    t.feed(70, 20 * MIN, capacity_wh=750)
    t.feed(95, 120 * MIN, capacity_wh=750)
    assert t.check_timeout(120 * MIN + IDLE_TIMEOUT_S) is True
    assert t.summary["soc_delta"] == 33  # 62 -> 95


def test_a_completed_summary_survives_a_failed_one():
    t = Tracker()
    t.seed(20, 0.0)
    t.feed(25, 5 * MIN, capacity_wh=750)
    t.feed(90, 60 * MIN, capacity_wh=750)
    t.check_timeout(60 * MIN + IDLE_TIMEOUT_S)
    real = dict(t.summary)
    # A later 2% blip must not overwrite last night's real charge.
    t.feed(92, 600 * MIN, capacity_wh=750)
    t.check_timeout(600 * MIN + IDLE_TIMEOUT_S)
    assert t.summary == real


def test_discharging_never_starts_a_session():
    t = Tracker()
    t.seed(100, 0.0)
    for i, soc in enumerate([90, 80, 65, 50, 30, 12]):
        t.feed(soc, (i + 1) * 20 * MIN, capacity_wh=750)
        assert t.in_progress is False
    assert t.summary is None


def test_missing_capacity_still_reports_percent():
    t = Tracker()
    t.seed(10, 0.0)
    t.feed(60, 5 * MIN, capacity_wh=None)
    t.check_timeout(5 * MIN + IDLE_TIMEOUT_S)
    assert t.summary["soc_delta"] == 50
    assert t.summary["energy_wh"] is None, "no capacity means no Wh, not a wrong Wh"

    t2 = Tracker()
    t2.seed(10, 0.0)
    t2.feed(60, 5 * MIN, capacity_wh=0)
    t2.check_timeout(5 * MIN + IDLE_TIMEOUT_S)
    assert t2.summary["energy_wh"] is None


def test_out_of_range_values_are_rejected():
    clean = charge_session.clean_soc
    assert clean(0) == 0.0
    assert clean(100) == 100.0
    assert clean("42.5") == 42.5
    for junk in (-1, 101, float("nan"), float("inf"), "n/a", None, True, False, [50]):
        assert clean(junk) is None, junk


def test_seed_alone_cannot_start_a_session():
    t = Tracker()
    t.seed(20, 0.0)
    t.seed(90, 60 * MIN)
    assert t.in_progress is False
    assert t.summary is None


def test_restore_summary():
    t = Tracker()
    restored = {"start_soc": 10, "end_soc": 90, "soc_delta": 80, "energy_wh": 600.0,
                "duration_min": 240.0, "started_at": 1.0, "ended_at": 2.0,
                "signal_gaps": 0}
    t.restore_summary(restored)
    assert t.summary == restored
    # Junk from a corrupted restored state must not replace a good summary.
    for junk in (None, "x", 5, []):
        t.restore_summary(junk)
        assert t.summary == restored


def test_iso_or_none_is_idempotent():
    iso = charge_session.iso_or_none
    assert iso(0.0) == "1970-01-01T00:00:00+00:00"
    # Re-formatting an already-formatted value must return it unchanged -
    # that is what makes restoring a summary and then publishing it again
    # safe, since a restored summary holds strings, not epochs.
    once = iso(1_785_000_000.0)
    assert iso(once) == once
    for junk in (None, "", True, False, float("nan"), float("inf"), [1], {}):
        assert iso(junk) is None, junk


def test_stale_baseline_does_not_inflate_the_duration():
    # A SoC sensor that only publishes on CHANGE goes silent while the bike
    # sits unused. If the charge were dated from that last sample, a bike
    # that stood untouched for three days and then charged for four hours
    # would be reported as a three-day charge.
    t = Tracker()
    three_days = 3 * 24 * 60 * MIN
    t.seed(40, 0.0)
    t.feed(45, three_days, capacity_wh=750)
    t.feed(95, three_days + 240 * MIN, capacity_wh=750)
    t.check_timeout(three_days + 240 * MIN + IDLE_TIMEOUT_S)

    s = t.summary
    assert s["duration_min"] == 240.0, "dated from the rise, not the stale sample"
    assert s["started_at"] == three_days
    # The start SOC is still trusted: the battery really was at 40%, however
    # long ago that was last confirmed.
    assert s["start_soc"] == 40
    assert s["soc_delta"] == 55


def test_summary_survives_a_restart_round_trip():
    # Exactly what the entity does: complete a session, publish it as
    # attributes (timestamps formatted), let HA restore those attributes,
    # feed them back, and publish again. The second publish must equal the
    # first, or the summary would visibly change across a restart.
    t = Tracker()
    t.seed(22, 0.0)
    t.feed(88, 200 * MIN, capacity_wh=625)
    t.check_timeout(200 * MIN + IDLE_TIMEOUT_S)

    def publish(tracker):
        s = dict(tracker.summary)
        s["started_at"] = charge_session.iso_or_none(s["started_at"])
        s["ended_at"] = charge_session.iso_or_none(s["ended_at"])
        return s

    first = publish(t)
    # HA hands back every attribute, including ones we must not adopt.
    restored_state_attrs = dict(first)
    restored_state_attrs.update(
        {"friendly_name": "eBike Last Charge Energy", "unit_of_measurement": "Wh",
         "in_progress": False, "soc_source": "sensor.ldi_soc", "icon": "mdi:x"}
    )
    fresh = Tracker()
    fresh.restore_summary(
        {k: v for k, v in restored_state_attrs.items()
         if k in charge_session.SUMMARY_KEYS}
    )
    assert publish(fresh) == first
    assert "friendly_name" not in fresh.summary
    assert "soc_source" not in fresh.summary
    assert fresh.summary["energy_wh"] == 412.5  # 66% of 625 Wh

    # And a restored summary is not an in-flight session.
    assert fresh.in_progress is False


def test_check_timeout_is_safe_when_idle():
    t = Tracker()
    assert t.check_timeout(0.0) is False
    assert t.check_timeout(10**9) is False
    t.seed(50, 0.0)
    assert t.check_timeout(10**9) is False


def test_total_energy_accumulates_only_published_sessions():
    t = Tracker()
    assert t.total_energy_wh == 0.0
    t.seed(20, 0.0)
    t.feed(25, 5 * MIN, capacity_wh=750)
    t.feed(60, 60 * MIN, capacity_wh=750)      # 20 -> 60 = 40% of 750 = 300 Wh
    t.check_timeout(60 * MIN + IDLE_TIMEOUT_S)
    assert t.total_energy_wh == 300.0

    # A second real charge adds on top; it never resets.
    t.feed(65, 600 * MIN, capacity_wh=750)
    t.feed(95, 700 * MIN, capacity_wh=750)     # 60 -> 95 = 35% of 750 = 262.5 Wh
    t.check_timeout(700 * MIN + IDLE_TIMEOUT_S)
    assert t.total_energy_wh == 562.5

    # A sub-threshold top-up is discarded, so it must not creep into the
    # total either - otherwise the discarded sessions would still show up
    # on the Energy Dashboard, just without ever being reported as charges.
    before = t.total_energy_wh
    t.feed(97, 1200 * MIN, capacity_wh=750)
    t.check_timeout(1200 * MIN + IDLE_TIMEOUT_S)
    assert t.total_energy_wh == before


def test_total_energy_ignores_sessions_without_capacity():
    # No capacity means no Wh figure at all. Contributing a guess here
    # would put invented energy into a dashboard people read as measured.
    t = Tracker()
    t.seed(10, 0.0)
    t.feed(60, 5 * MIN, capacity_wh=None)
    t.check_timeout(5 * MIN + IDLE_TIMEOUT_S)
    assert t.summary["soc_delta"] == 50
    assert t.summary["energy_wh"] is None
    assert t.total_energy_wh == 0.0


def test_total_energy_is_monotonic_across_restore():
    t = Tracker()
    t.restore_total_energy(1234.5)
    assert t.total_energy_wh == 1234.5
    t.seed(50, 0.0)
    t.feed(55, 5 * MIN, capacity_wh=500)
    t.feed(90, 60 * MIN, capacity_wh=500)      # 50 -> 90 = 40% of 500 = 200 Wh
    t.check_timeout(60 * MIN + IDLE_TIMEOUT_S)
    assert t.total_energy_wh == 1434.5

    # Junk or a backwards value from a corrupted restored state must not be
    # adopted: a TOTAL_INCREASING sensor reads a drop as a meter reset.
    for junk in (None, "", "abc", -1, float("nan"), float("inf"), [5]):
        t2 = Tracker()
        t2.restore_total_energy(500.0)
        t2.restore_total_energy(junk)
        assert t2.total_energy_wh == 500.0, junk


def test_restore_total_adopts_valid_values_on_a_fresh_tracker():
    # The entity restores via RestoreSensor.async_get_last_sensor_data(),
    # which hands back the NATIVE value - a float, or None. It deliberately
    # does NOT read the entity state string: a user who switches the unit to
    # kWh (the natural unit in the Energy Dashboard this sensor exists for)
    # would make that string kWh, and reading it back as Wh would divide the
    # meter by 1000 on every restart. See BoschChargedEnergySensor.
    #
    # A fresh tracker, matching the one real call site: restore_total_energy
    # runs exactly once, in async_added_to_hass, against a tracker that has
    # just been created and is still at 0.0.
    assert _fresh_restored(562.5) == 562.5
    assert _fresh_restored(0) == 0.0
    # Strings are still covered here because this function must not care
    # where its argument came from, and because HA stores restore data as
    # JSON, which can hand back surprises after a version change.
    assert _fresh_restored("562.5") == 562.5


def test_restore_total_rejects_garbage_without_lowering_an_existing_total():
    # Anything not a usable non-negative number must leave the total alone:
    # for a TOTAL_INCREASING sensor, silently dropping it reads as a meter
    # reset and takes the accumulated cost out of the Energy Dashboard. Using
    # a non-zero baseline here (rather than a fresh tracker) is what actually
    # exercises "leaves it alone" - restoring garbage onto a fresh 0.0 would
    # pass even if the guard were altogether missing.
    for junk in (None, "unknown", "unavailable", "", "None", -5, "-5",
                 float("nan"), float("inf"), [1], {}):
        assert _restored_onto_baseline(junk) == 99.0, junk


# --- carrying a running session across a restart -------------------------
#
# A charge that is running when Home Assistant stops is persisted by the
# monitor and picked up again at startup. These cover the tracker half: what
# is exported, what restore_inflight accepts, and how the state machine then
# treats the session. The failure mode to guard against is a charge that
# never happened being published, or one that did being published twice.

CAPACITY_WH = 625.0


def _mid_charge():
    """A tracker part-way through a charge: 20% -> 60%, one percent per 2 min.

    Returns the tracker and the time of its last rise (80 min after plug-in).
    """
    t = Tracker()
    t.seed(20, 0.0)
    now = 0.0
    for soc in range(21, 61):
        now += 2 * MIN
        t.feed(soc, now, capacity_wh=CAPACITY_WH)
    assert t.in_progress and t.summary is None
    return t, now


def _snapshot():
    """What the monitor would have persisted at the 60% mark."""
    t, last_rise = _mid_charge()
    snapshot = t.export_inflight()
    return json.loads(json.dumps(snapshot)), last_rise


def _restored(now_offset, snapshot=None, last_rise=None):
    """A fresh tracker with the 60% session restored *now_offset* s later."""
    if snapshot is None:
        snapshot, last_rise = _snapshot()
    t = Tracker()
    now = last_rise + now_offset
    assert t.restore_inflight(snapshot, now) is True
    return t, now, last_rise


def test_export_inflight_is_none_while_idle():
    t = Tracker()
    assert t.export_inflight() is None
    t.seed(40, 0.0)
    assert t.export_inflight() is None
    t.feed(41, 60.0)   # a single percent starts a session ...
    t.feed(40, 120.0)  # ... and falling again ends it before it is worth publishing
    assert t.in_progress is False
    assert t.export_inflight() is None


def test_export_inflight_is_plain_json_data_of_the_running_session():
    t, last_rise = _mid_charge()
    snapshot = t.export_inflight()
    assert snapshot == {
        "start_soc": 20.0, "start_ts": 0.0,
        "peak_soc": 60.0, "peak_ts": last_rise,
        "capacity_wh": CAPACITY_WH, "gaps": 0,
    }
    assert json.loads(json.dumps(snapshot)) == snapshot


def test_a_charge_survives_a_restart():
    # The headline case: charge 20% -> 100%, Home Assistant restarts at 60%
    # and is back three minutes later. Without carrying the session over,
    # only the part after the restart was booked (about half the energy).
    snapshot, last_rise = _snapshot()
    t, now, _ = _restored(3 * MIN, snapshot, last_rise)
    assert t.in_progress is True
    t.seed(62, now)                       # what async_start does at startup
    assert t.check_timeout(now) is False  # the idle window is still open

    for soc in range(63, 101):
        now += 2 * MIN
        t.feed(soc, now, capacity_wh=CAPACITY_WH)
    assert t.check_timeout(now + IDLE_TIMEOUT_S) is True

    s = t.summary
    assert s["start_soc"] == 20 and s["end_soc"] == 100 and s["soc_delta"] == 80
    assert s["energy_wh"] == 500.0        # 80% of 625 Wh, not the 39% after the restart
    assert s["started_at"] == 0.0         # dated from the plug-in, before the restart
    assert s["ended_at"] == now
    assert s["duration_min"] == round(now / 60.0, 1)
    assert t.total_energy_wh == 500.0


def test_the_soc_found_after_a_restart_only_raises_the_peak():
    # While Home Assistant was down the battery went on charging: the net
    # rise since the stored peak is booked, nothing beyond it.
    t, now, _ = _restored(3 * MIN)
    t.feed(66, now, capacity_wh=CAPACITY_WH)
    assert t.in_progress is True
    t.check_timeout(now + IDLE_TIMEOUT_S)
    assert t.summary["end_soc"] == 66
    assert t.summary["energy_wh"] == 287.5   # 20 -> 66 = 46% of 625 Wh


def test_a_restored_session_ends_from_its_stored_peak_if_the_battery_fell():
    # The bike was unplugged and ridden while Home Assistant was down. The
    # first sample shows a lower SoC, which ends the session as usual, from
    # the peak that was actually observed.
    t, now, _ = _restored(3 * MIN)
    assert t.feed(55, now, capacity_wh=CAPACITY_WH) is True
    assert t.in_progress is False
    s = t.summary
    assert s["start_soc"] == 20 and s["end_soc"] == 60
    assert s["energy_wh"] == 250.0        # 40% of 625 Wh


def test_a_restored_session_that_idled_out_while_down_ends_from_its_peak():
    # No sample may ever arrive (the bridge stays offline). Closed from the
    # stored peak, dated by it - what the idle timer would have done.
    t, now, last_rise = _restored(IDLE_TIMEOUT_S + 10 * MIN)
    assert t.check_timeout(now) is True
    assert t.in_progress is False
    s = t.summary
    assert s["end_soc"] == 60 and s["start_soc"] == 20
    assert s["ended_at"] == last_rise
    assert s["duration_min"] == 80.0
    assert t.total_energy_wh == 250.0


def test_a_restored_session_inside_the_idle_window_is_left_running():
    t, now, _ = _restored(IDLE_TIMEOUT_S - 1)
    assert t.check_timeout(now) is False
    assert t.in_progress is True
    assert t.idle_remaining_s(now) == 1.0
    assert t.check_timeout(now + 1) is True


def test_idle_remaining_s():
    t = Tracker()
    assert t.idle_remaining_s(0.0) is None
    t, last_rise = _mid_charge()
    assert t.idle_remaining_s(last_rise) == IDLE_TIMEOUT_S
    assert t.idle_remaining_s(last_rise + 600) == IDLE_TIMEOUT_S - 600
    assert t.idle_remaining_s(last_rise + IDLE_TIMEOUT_S + 99) == 0.0


def test_a_restored_session_that_is_too_small_is_not_published():
    # 20% -> 21% stored, then it idles out: below MIN_SESSION_PCT, so nothing
    # is published and nothing is left in progress.
    snapshot = {"start_soc": 20.0, "start_ts": 0.0, "peak_soc": 21.0,
                "peak_ts": 120.0, "capacity_wh": CAPACITY_WH, "gaps": 0}
    t = Tracker()
    assert t.restore_inflight(snapshot, 120.0 + IDLE_TIMEOUT_S + 1) is True
    assert t.check_timeout(120.0 + IDLE_TIMEOUT_S + 1) is False
    assert t.in_progress is False
    assert t.summary is None
    assert t.total_energy_wh == 0.0


def test_restore_inflight_rejects_what_does_not_describe_a_session():
    good, last_rise = _snapshot()
    now = last_rise + 60.0

    def broken(**changes):
        d = dict(good)
        for key, value in changes.items():
            if value is _MISSING:
                d.pop(key, None)
            else:
                d[key] = value
        return d

    # Shape: what a corrupt or hand-edited store file could hold.
    shapes = [None, "x", 5, [], good["start_soc"], True]
    for key in ("start_soc", "peak_soc", "start_ts", "peak_ts"):
        shapes.append(broken(**{key: _MISSING}))
        shapes.append(broken(**{key: None}))
    for junk in (float("nan"), float("inf"), -1, 101, True, [1], {}):
        shapes.append(broken(start_soc=junk))
        shapes.append(broken(peak_soc=junk))
    for junk in (float("nan"), float("inf"), -5.0, True, "123", [1], None):
        shapes.append(broken(start_ts=junk))
        shapes.append(broken(peak_ts=junk))
    shapes += [
        broken(start_soc=70.0, peak_soc=60.0),    # fell, so that is not a peak
        broken(start_ts=good["peak_ts"] + 1),     # started after it peaked
    ]
    cases = [(bad, now) for bad in shapes]

    # Plausibility: these hinge on the clock or on the span. They are built far
    # enough into the epoch that every timestamp stays valid, so each is
    # rejected for the reason it names and for no other - the control below
    # shows the same snapshot is fine when the clock is right.
    late, late_now = _long_session(80 * MIN)
    assert Tracker().restore_inflight(late, late_now) is True
    cases += [
        (dict(late, peak_ts=late_now + CLOCK_SKEW_TOLERANCE_S + 1), late_now),   # from the future
        (dict(late, peak_ts=late_now - MAX_RESTORE_AGE_S - 1,
              start_ts=late_now - MAX_RESTORE_AGE_S - 1 - 80 * MIN), late_now),  # too old to book
        _long_session(MAX_RESTORE_SESSION_S + 1),                                # absurdly long
    ]

    for bad, at in cases:
        t = Tracker()
        assert t.restore_inflight(bad, at) is False, bad
        assert t.in_progress is False, bad
        assert t.export_inflight() is None, bad


_MISSING = object()


def _long_session(span_s):
    """A snapshot whose session lasted *span_s*, ending a minute before "now".

    Placed ten days into the epoch so the start stays a valid (non-negative)
    timestamp however long the span is. Returns (snapshot, now).
    """
    peak_ts = 10 * 86400.0
    snapshot = {"start_soc": 20.0, "start_ts": peak_ts - span_s,
                "peak_soc": 60.0, "peak_ts": peak_ts,
                "capacity_wh": CAPACITY_WH, "gaps": 0}
    return snapshot, peak_ts + 60.0


def test_restore_inflight_accepts_the_boundaries():
    good, last_rise = _snapshot()
    # Exactly as old as allowed.
    t = Tracker()
    assert t.restore_inflight(good, last_rise + MAX_RESTORE_AGE_S) is True
    # Exactly as far in the future as tolerated (a clock that is a little behind).
    t = Tracker()
    assert t.restore_inflight(good, last_rise - CLOCK_SKEW_TOLERANCE_S) is True
    # Exactly the longest session.
    long_one, long_now = _long_session(MAX_RESTORE_SESSION_S)
    t = Tracker()
    assert t.restore_inflight(long_one, long_now) is True


def test_restore_inflight_never_replaces_a_running_session():
    t, last_rise = _mid_charge()
    before = t.export_inflight()
    other = {"start_soc": 5.0, "start_ts": 1.0, "peak_soc": 90.0,
             "peak_ts": last_rise, "capacity_wh": 400.0, "gaps": 7}
    assert t.restore_inflight(other, last_rise) is False
    assert t.export_inflight() == before


def test_restore_inflight_survives_bad_capacity_and_gap_values():
    good, last_rise = _snapshot()
    now = last_rise + 60.0
    for junk in (None, "x", -5, 0, float("nan"), float("inf"), True, [1]):
        t = Tracker()
        assert t.restore_inflight(dict(good, capacity_wh=junk), now) is True, junk
        assert t.export_inflight()["capacity_wh"] is None, junk
        # Without a capacity the session still completes; it just has no energy.
        t.check_timeout(now + IDLE_TIMEOUT_S)
        assert t.summary["energy_wh"] is None and t.total_energy_wh == 0.0
    for junk in (None, "2", -1, 1.5, True, [1]):
        t = Tracker()
        assert t.restore_inflight(dict(good, gaps=junk), now) is True, junk
        assert t.export_inflight()["gaps"] == 0, junk


def test_the_capacity_and_gaps_of_the_original_session_travel_with_it():
    good, last_rise = _snapshot()
    snapshot = dict(good, capacity_wh=500.0, gaps=2)
    t = Tracker()
    now = last_rise + 3 * MIN
    assert t.restore_inflight(snapshot, now) is True
    t.feed("unavailable", now + 10)           # one more dropout after the restart
    # The capacity a session started with is the one it is booked with, even
    # if a different one is passed for later samples.
    t.feed(70, now + 20, capacity_wh=999.0)
    t.check_timeout(now + 20 + IDLE_TIMEOUT_S)
    s = t.summary
    assert s["signal_gaps"] == 3
    assert s["energy_wh"] == 250.0            # 20 -> 70 = 50% of 500 Wh


def test_a_session_closed_from_the_restored_state_is_not_lost_to_a_late_total_restore():
    # The sensor restores its total in async_added_to_hass, after the monitor
    # has already restored and possibly closed the session at startup. That
    # session must be added to the restored total, not swallowed by it.
    t, now, _ = _restored(IDLE_TIMEOUT_S + 10 * MIN)
    assert t.check_timeout(now) is True
    assert t.total_energy_wh == 250.0
    t.restore_total_energy(1000.0)
    assert t.total_energy_wh == 1250.0

    # And the other order gives the same answer.
    t2, now2, _ = _restored(IDLE_TIMEOUT_S + 10 * MIN)
    t2.restore_total_energy(1000.0)
    assert t2.check_timeout(now2) is True
    assert t2.total_energy_wh == 1250.0


def test_restore_total_energy_is_idempotent():
    t = Tracker()
    t.restore_total_energy(300.0)
    t.restore_total_energy(300.0)
    assert t.total_energy_wh == 300.0
    t.restore_total_energy(200.0)   # never lowers it
    assert t.total_energy_wh == 300.0


def test_a_second_restore_never_counts_a_session_twice():
    # The sensor entity can be re-added within one run. What it then reads back
    # was stored while the tracker was already counting, so it contains the
    # sessions published since; adding the tracker's own total on top again
    # would count them twice, and on a TOTAL_INCREASING meter that sticks.
    t, now, _ = _restored(IDLE_TIMEOUT_S + 10 * MIN)
    t.restore_total_energy(1000.0)
    assert t.check_timeout(now) is True
    assert t.total_energy_wh == 1250.0              # 1000 + the 250 Wh session
    t.restore_total_energy(1250.0)                  # what the entity wrote back
    assert t.total_energy_wh == 1250.0
    t.restore_total_energy(1100.0)                  # older reading: never lowers
    assert t.total_energy_wh == 1250.0
    t.restore_total_energy(1300.0)                  # a reading that is ahead: adopted
    assert t.total_energy_wh == 1300.0


def test_an_unusable_first_restore_does_not_use_up_the_first_call():
    t = Tracker()
    for junk in (None, "unknown", -1, float("nan")):
        t.restore_total_energy(junk)
    t.restore_total_energy(500.0)
    assert t.total_energy_wh == 500.0
    # Still additive afterwards: this was the first usable call.
    t, now, _ = _restored(IDLE_TIMEOUT_S + 10 * MIN)
    t.restore_total_energy("unavailable")
    assert t.check_timeout(now) is True
    t.restore_total_energy(1000.0)
    assert t.total_energy_wh == 1250.0


def test_restore_summary_does_not_replace_a_session_completed_in_this_run():
    old = {"start_soc": 10, "end_soc": 90, "soc_delta": 80, "energy_wh": 600.0,
           "duration_min": 240.0, "started_at": 1.0, "ended_at": 2.0,
           "signal_gaps": 0}
    t, now, last_rise = _restored(IDLE_TIMEOUT_S + 10 * MIN)
    assert t.check_timeout(now) is True
    newer = t.summary
    t.restore_summary(old)
    assert t.summary is newer
    assert t.summary["ended_at"] == last_rise


def test_a_closed_session_exports_nothing_so_it_cannot_be_booked_twice():
    t, now, _ = _restored(IDLE_TIMEOUT_S + 10 * MIN)
    assert t.export_inflight() is not None
    t.check_timeout(now)
    assert t.export_inflight() is None
    # Restoring the snapshot taken before the close would resurrect it; that
    # is why the monitor clears the stored copy as soon as a session ends.
    assert not math.isnan(t.total_energy_wh)


def _fresh_restored(raw):
    t = Tracker()
    t.restore_total_energy(raw)
    return t.total_energy_wh


def _restored_onto_baseline(raw):
    t = Tracker()
    t.restore_total_energy(99.0)
    t.restore_total_energy(raw)
    return t.total_energy_wh


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
