"""Pure two-phase charge-rate estimation - run with:
python3 tests/test_charge_rate_estimate.py

Charging a Li-ion pack is not linear: it moves fast below roughly 80%, then
tapers off noticeably in the constant-voltage phase above it. Modelling a
single flat rate across the whole 0-100% range would systematically
underestimate the time needed to reach 100% (issue: see the design doc).
This module learns two separate rates - below 80% and above it - from a
bike's own charge history, and projects a remaining-time / ready-time
estimate for each of the two milestones users actually care about.
"""
import importlib.util
from pathlib import Path

# Load the module file directly: importing the package would pull in
# custom_components/ha_bosch_ebike/__init__.py, which needs Home Assistant.
_MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "charge_rate_estimate.py"
)
_spec = importlib.util.spec_from_file_location("charge_rate_estimate", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
MIN_SESSIONS_PER_PHASE = _mod.MIN_SESSIONS_PER_PHASE
MIN_PCT_POINTS_PER_PHASE = _mod.MIN_PCT_POINTS_PER_PHASE
PHASE_BOUNDARY_PCT = _mod.PHASE_BOUNDARY_PCT
compute_two_phase_rates = _mod.compute_two_phase_rates
estimate_time_to_target = _mod.estimate_time_to_target


def _session(start_soc, end_soc, duration_min):
    return {"start_soc": start_soc, "end_soc": end_soc, "duration_min": duration_min}


def test_pure_below_80_session_only_contributes_to_below_rate():
    sessions = [_session(20, 60, 40)]  # 40 pct-points in 40 min = 1.0 min/pct, all below 80
    rates = compute_two_phase_rates(sessions)
    assert rates["below_80_sessions"] == 1
    assert rates["above_80_sessions"] == 0
    assert rates["rate_below_80"] == 1.0
    assert rates["rate_above_80"] is None


def test_pure_above_80_session_only_contributes_to_above_rate():
    sessions = [_session(85, 100, 30)]  # 15 pct-points in 30 min = 2.0 min/pct, all above 80
    rates = compute_two_phase_rates(sessions)
    assert rates["above_80_sessions"] == 1
    assert rates["below_80_sessions"] == 0
    assert rates["rate_above_80"] == 2.0
    assert rates["rate_below_80"] is None


def test_session_spanning_80_prorates_by_percentage_points():
    # 45 -> 95 in 60 min: 35 pct-points below 80 (of 50 total) -> 42 min;
    # 15 pct-points above 80 (of 50 total) -> 18 min.
    sessions = [_session(45, 95, 60)]
    rates = compute_two_phase_rates(sessions)
    assert rates["rate_below_80"] == 42 / 35
    assert rates["rate_above_80"] == 18 / 15
    assert rates["below_80_sessions"] == 1
    assert rates["above_80_sessions"] == 1


def test_rates_aggregate_total_over_total_not_average_of_rates():
    # Two below-80 sessions with different individual rates - the aggregate
    # must be (sum minutes)/(sum pct-points), matching wh_per_km's own
    # aggregation style in range_estimate.py, NOT the mean of the two
    # per-session rates.
    sessions = [_session(0, 40, 40), _session(0, 10, 20)]  # 40 pts/40 min, 10 pts/20 min
    rates = compute_two_phase_rates(sessions)
    assert rates["rate_below_80"] == (40 + 20) / (40 + 10)


def test_session_exactly_at_boundary_start_counts_fully_above():
    sessions = [_session(80, 100, 40)]
    rates = compute_two_phase_rates(sessions)
    assert rates["below_80_sessions"] == 0
    assert rates["above_80_sessions"] == 1


def test_session_exactly_at_boundary_end_counts_fully_below():
    sessions = [_session(40, 80, 40)]
    rates = compute_two_phase_rates(sessions)
    assert rates["below_80_sessions"] == 1
    assert rates["above_80_sessions"] == 0


def test_zero_or_negative_delta_session_is_skipped():
    sessions = [_session(50, 50, 10), _session(60, 40, 10)]
    rates = compute_two_phase_rates(sessions)
    assert rates["below_80_sessions"] == 0
    assert rates["above_80_sessions"] == 0


def test_empty_history_returns_none_rates():
    rates = compute_two_phase_rates([])
    assert rates["rate_below_80"] is None
    assert rates["rate_above_80"] is None
    assert rates["below_80_sessions"] == 0
    assert rates["above_80_sessions"] == 0


def test_estimate_below_target_80_uses_below_rate_only():
    rates = {"rate_below_80": 2.0, "rate_above_80": 5.0,
             "below_80_sessions": MIN_SESSIONS_PER_PHASE, "above_80_sessions": MIN_SESSIONS_PER_PHASE,
             "below_80_pct_points": 2 * MIN_PCT_POINTS_PER_PHASE,
             "above_80_pct_points": 2 * MIN_PCT_POINTS_PER_PHASE}
    result = estimate_time_to_target(current_soc=50, target_soc=PHASE_BOUNDARY_PCT, rates=rates)
    assert result == 60.0  # (80-50) * 2.0


def test_estimate_to_100_from_below_80_combines_both_rates():
    rates = {"rate_below_80": 2.0, "rate_above_80": 5.0,
             "below_80_sessions": MIN_SESSIONS_PER_PHASE, "above_80_sessions": MIN_SESSIONS_PER_PHASE,
             "below_80_pct_points": 2 * MIN_PCT_POINTS_PER_PHASE,
             "above_80_pct_points": 2 * MIN_PCT_POINTS_PER_PHASE}
    result = estimate_time_to_target(current_soc=50, target_soc=100, rates=rates)
    assert result == (PHASE_BOUNDARY_PCT - 50) * 2.0 + (100 - PHASE_BOUNDARY_PCT) * 5.0


def test_estimate_to_100_from_above_80_uses_above_rate_only():
    rates = {"rate_below_80": 2.0, "rate_above_80": 5.0,
             "below_80_sessions": MIN_SESSIONS_PER_PHASE, "above_80_sessions": MIN_SESSIONS_PER_PHASE,
             "below_80_pct_points": 2 * MIN_PCT_POINTS_PER_PHASE,
             "above_80_pct_points": 2 * MIN_PCT_POINTS_PER_PHASE}
    result = estimate_time_to_target(current_soc=90, target_soc=100, rates=rates)
    assert result == (100 - 90) * 5.0


def test_estimate_to_80_when_already_past_80_returns_none():
    rates = {"rate_below_80": 2.0, "rate_above_80": 5.0,
             "below_80_sessions": MIN_SESSIONS_PER_PHASE, "above_80_sessions": MIN_SESSIONS_PER_PHASE,
             "below_80_pct_points": 2 * MIN_PCT_POINTS_PER_PHASE,
             "above_80_pct_points": 2 * MIN_PCT_POINTS_PER_PHASE}
    assert estimate_time_to_target(current_soc=85, target_soc=PHASE_BOUNDARY_PCT, rates=rates) is None


def test_estimate_returns_none_below_min_sessions_threshold():
    # Percentage-point coverage is comfortably above MIN_PCT_POINTS_PER_PHASE
    # for both phases here - this test is only about the session-COUNT gate,
    # not the magnitude gate (see test_estimate_returns_none_below_min_pct_points_threshold).
    rates = {"rate_below_80": 2.0, "rate_above_80": 5.0,
             "below_80_sessions": MIN_SESSIONS_PER_PHASE - 1, "above_80_sessions": MIN_SESSIONS_PER_PHASE,
             "below_80_pct_points": 2 * MIN_PCT_POINTS_PER_PHASE,
             "above_80_pct_points": 2 * MIN_PCT_POINTS_PER_PHASE}
    assert estimate_time_to_target(current_soc=50, target_soc=PHASE_BOUNDARY_PCT, rates=rates) is None
    # to 100 from below 80% needs BOTH phases' minimums met
    assert estimate_time_to_target(current_soc=50, target_soc=100, rates=rates) is None


def test_estimate_returns_none_below_min_pct_points_threshold():
    # Mirrors test_estimate_returns_none_below_min_sessions_threshold, but the
    # OTHER way round: the session COUNT gate is satisfied, while the total
    # percentage-point coverage for the below-80 phase falls short of
    # MIN_PCT_POINTS_PER_PHASE (e.g. several sessions that each barely nudge
    # across a boundary). Proves the magnitude gate is a real, independent
    # check - not just always-satisfied alongside the count gate.
    rates = {"rate_below_80": 2.0, "rate_above_80": 5.0,
             "below_80_sessions": MIN_SESSIONS_PER_PHASE, "above_80_sessions": MIN_SESSIONS_PER_PHASE,
             "below_80_pct_points": MIN_PCT_POINTS_PER_PHASE - 1,
             "above_80_pct_points": 2 * MIN_PCT_POINTS_PER_PHASE}
    assert estimate_time_to_target(current_soc=50, target_soc=PHASE_BOUNDARY_PCT, rates=rates) is None
    # to 100 from below 80% needs BOTH phases' minimums met, so the thin
    # below-80 coverage still blocks it even though above-80 is well trusted.
    assert estimate_time_to_target(current_soc=50, target_soc=100, rates=rates) is None
    # but a target fully within the well-trusted above-80 phase still works.
    assert estimate_time_to_target(current_soc=90, target_soc=100, rates=rates) == 50.0  # (100-90) * 5.0


def test_estimate_at_or_above_100_returns_zero():
    rates = {"rate_below_80": 2.0, "rate_above_80": 5.0,
             "below_80_sessions": MIN_SESSIONS_PER_PHASE, "above_80_sessions": MIN_SESSIONS_PER_PHASE,
             "below_80_pct_points": 2 * MIN_PCT_POINTS_PER_PHASE,
             "above_80_pct_points": 2 * MIN_PCT_POINTS_PER_PHASE}
    assert estimate_time_to_target(current_soc=100, target_soc=100, rates=rates) == 0.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
