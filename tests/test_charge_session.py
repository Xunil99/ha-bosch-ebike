"""Standalone tests for charge_session.py — run with: python3 tests/test_charge_session.py"""
import importlib.util
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
