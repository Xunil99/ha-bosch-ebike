"""Charge session detection from a live battery SoC signal.

The Bosch cloud never reports charging: it only ever shows the SoC that was
current at the last sync. What it does not tell you is that the battery went
from 18% to 100% overnight, how long that took, or how much energy went into
it. Users who run the ESPHome LDI bridge do have a live SoC sensor, and that
signal is enough to reconstruct all three - which is what this module does.

Deliberately free of Home Assistant imports so the dependency-free suite
under tests/ can cover the state machine, which is the part with the
interesting failure modes. charge_monitor.ChargeSessionMonitor owns the
wiring: it feeds samples in, arms the idle timer, and publishes the summary.
It is tied to the config entry rather than to either sensor entity, so that
disabling one of them in the entity registry cannot silently stop charges
from being counted.

Design notes on the thresholds below:

* A charge is detected from a *rise*, not from any charger-state signal,
  because there isn't one. So the rise has to clear sensor jitter, and a
  session has to be big enough to be worth reporting.
* An unusable sample (unavailable, unknown, non-numeric) never ends or
  resets a session. A BLE bridge dropping out mid-charge is the normal case,
  not the exception - it is literally the failure mode reported in issue #68
  - and treating a dropout as "charging stopped" would report a 20%-charge
  every time the bike briefly went out of range.
* A session is closed from its PEAK, not from the sample that closed it. A
  battery that reaches 100% and then sits there losing a percent to
  self-discharge charged to 100%, not to 99%.
* A session that is still running when Home Assistant stops is carried over
  a restart (export_inflight / restore_inflight) rather than dropped. Only
  what was actually observed is carried over, and the state machine then
  judges the SoC found at startup by its normal rules. Whatever happened
  while Home Assistant was down can therefore only ever add the net rise
  of the SoC, never energy that was not measured: the failure mode is
  under-reporting, as it always was.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

# Minimum rise between two consecutive samples to call it "charging started".
# Bosch SoC is reported in whole percent, so anything below 1 is jitter.
MIN_RISE_PCT = 1.0
# A fall of this much below the session peak means the bike is being used
# again (or was unplugged and rolled out), so the session is over.
END_DROP_PCT = 1.0
# No further rise for this long also ends the session - the normal way a
# charge finishes is the SoC simply stopping, with no drop to detect.
IDLE_TIMEOUT_S = 1800.0
# Sessions smaller than this are not published: topping up a few percent
# while the bike sat in the hallway is not a charge worth summarizing, and
# publishing it would overwrite the real one from last night.
MIN_SESSION_PCT = 3.0
# How far back a session's start may be inferred from the previous sample.
# The charge began somewhere between the last sample and the one that showed
# the rise, and normally those are minutes apart. But a sensor that only
# reports on CHANGE goes quiet while the bike sits unused, so the previous
# sample can be days old - and dating the charge from it would report a
# battery that charged for four hours as having charged for three days.
# Beyond this bound the previous sample is treated as too stale to date the
# start from, and the rise itself is used instead. That slightly
# underreports the duration, which is the honest direction to be wrong in.
#
# Deliberately the same value as IDLE_TIMEOUT_S rather than a second tuned
# number: this module already treats that much silence as "the charge is
# over", so it cannot coherently treat a longer silence as part of one.
MAX_START_LOOKBACK_S = IDLE_TIMEOUT_S

# A stored session whose last rise is older than this is dropped on restore
# instead of being closed from its stored peak. Long enough to span an
# overnight outage, short enough that a leftover from an integration that was
# disabled for days is not booked into today's Energy Dashboard.
MAX_RESTORE_AGE_S = 12 * 3600.0
# Longest span a stored session may describe. Real charges end well inside
# this; a longer one means the stored timestamps are corrupt, and publishing
# it would also poison the charge-rate learning with a nonsense duration.
MAX_RESTORE_SESSION_S = 24 * 3600.0
# How far into the future a stored timestamp may lie before it is distrusted.
# A host without a battery-backed clock can boot with a stale time and only
# correct it a little later; a session that appears to end after "now" is
# then ignored rather than left open until the clock catches up.
CLOCK_SKEW_TOLERANCE_S = 120.0

# Keys that make up a restorable summary. Anything else on a restored
# entity state (in_progress, soc_source, and Home Assistant's own
# friendly_name/unit/icon) is recomputed rather than carried over.
SUMMARY_KEYS = frozenset(
    {
        "start_soc", "end_soc", "soc_delta", "energy_wh",
        "duration_min", "started_at", "ended_at", "signal_gaps",
    }
)

__all__ = [
    "ChargeSessionTracker",
    "SUMMARY_KEYS",
    "clean_soc",
    "iso_or_none",
    "MIN_RISE_PCT",
    "END_DROP_PCT",
    "IDLE_TIMEOUT_S",
    "MIN_SESSION_PCT",
    "MAX_START_LOOKBACK_S",
    "MAX_RESTORE_AGE_S",
    "MAX_RESTORE_SESSION_S",
    "CLOCK_SKEW_TOLERANCE_S",
]


def iso_or_none(value: Any) -> str | None:
    """Format an epoch timestamp as ISO 8601, passing strings through.

    Idempotent on purpose: a summary restored from a previous run already
    holds formatted strings, and running it through here again must not
    mangle them.
    """
    if isinstance(value, str):
        return value or None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def clean_soc(value: Any) -> float | None:
    """Return *value* as a usable SoC percentage, or None.

    None means "no information", which is what every caller has to treat
    differently from a real 0.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        soc = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(soc) or not 0.0 <= soc <= 100.0:
        return None
    return soc


def _clean_ts(value: Any) -> float | None:
    """Return *value* as a usable epoch timestamp (seconds), or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    ts = float(value)
    return ts if math.isfinite(ts) and ts >= 0.0 else None


class ChargeSessionTracker:
    """Turns a stream of (soc, timestamp) samples into charge session summaries.

    Timestamps are plain floats (seconds), so the caller decides whether
    that is a monotonic clock or wall time. The entity uses wall time,
    because the summary reports when the charge happened.
    """

    def __init__(self) -> None:
        self._last_soc: float | None = None
        self._last_ts: float | None = None
        self._start_soc: float | None = None
        self._start_ts: float | None = None
        self._peak_soc: float | None = None
        self._peak_ts: float | None = None
        self._capacity_wh: float | None = None
        self._gaps = 0
        self._summary: dict[str, Any] | None = None
        # The running total is kept as two parts so that restoring the first
        # can never erase the second, whichever happens first: what the meter
        # read before this tracker started counting (restore_total_energy),
        # and what the sessions published by this tracker added since.
        self._restored_total_wh = 0.0
        self._session_total_wh = 0.0
        self._total_restored = False

    @property
    def in_progress(self) -> bool:
        return self._start_soc is not None

    @property
    def summary(self) -> dict[str, Any] | None:
        """The last completed session, or None if none has completed yet."""
        return self._summary

    @property
    def total_energy_wh(self) -> float:
        """Wh added by every published session, monotonically increasing.

        Only sessions that were actually published count, so the sub-3%
        top-ups that _close() discards do not quietly accumulate either.
        Sessions with no known battery capacity contribute nothing rather
        than a guess, which means the total can lag reality on a bike whose
        capacity was configured late - preferable to inventing kilowatt
        hours that were never measured.
        """
        return round(self._restored_total_wh + self._session_total_wh, 2)

    def restore_total_energy(self, value: Any) -> None:
        """Adopt a running total read back from a restored entity state.

        Called instead of starting from zero after a restart. A negative or
        unusable value is ignored: this total feeds a TOTAL_INCREASING
        sensor, where going backwards is read as a meter reset and would
        corrupt the Energy Dashboard's history.

        The first call takes *value* as what the meter read BEFORE this
        tracker started counting, and whatever sessions this tracker
        publishes are added on top of it, no matter whether they complete
        before or after this is called. That is not hypothetical: a session
        restored from before a restart can be closed right at startup (see
        restore_inflight), earlier than the sensor restores its total, and
        taking the larger of the two numbers instead of adding them would
        silently drop that session.

        A later call on the same tracker (the sensor entity re-added within
        one run) is a different thing: what it reads back was written while
        this tracker was already counting, so it already contains the
        sessions published since. It is taken as an absolute reading, which
        can raise the total but never lowers it and never counts a session
        twice.
        """
        try:
            restored = float(value)
        except (TypeError, ValueError):
            return
        if not math.isfinite(restored) or restored < 0:
            return
        if not self._total_restored:
            self._restored_total_wh = restored
            self._total_restored = True
        else:
            self._restored_total_wh = max(
                self._restored_total_wh, restored - self._session_total_wh
            )

    def restore_summary(self, summary: dict[str, Any] | None) -> None:
        """Adopt a summary read back from a restored entity state.

        Only ever used to repopulate the last *completed* session across a
        restart, and only while this tracker has not completed one of its
        own: a session closed straight from the restored in-flight state
        (restore_inflight) is newer than anything stored, and must not be
        overwritten by the previous run's summary when the sensor restores.
        A session still running at shutdown is carried over separately, by
        restore_inflight.
        """
        if isinstance(summary, dict) and self._summary is None:
            self._summary = summary

    def export_inflight(self) -> dict[str, Any] | None:
        """The running session as plain JSON-safe data, or None when idle.

        What ChargeSessionMonitor persists, so that a restart does not lose
        the part of a charge that was already observed. Only what the state
        machine needs to carry on is included. The baseline (_last_soc and
        _last_ts) is not: it is re-seeded from the live sensor at startup.
        """
        if not self.in_progress:
            return None
        return {
            "start_soc": self._start_soc,
            "start_ts": self._start_ts,
            "peak_soc": self._peak_soc,
            "peak_ts": self._peak_ts,
            "capacity_wh": self._capacity_wh,
            "gaps": self._gaps,
        }

    def restore_inflight(self, data: Any, now: float) -> bool:
        """Resume a session that was running when Home Assistant stopped.

        Returns True if a session was adopted. It only ever picks a session
        back up, never invents one, and it is strict about what it accepts:
        anything that is not a clean, plausible description of a session is
        ignored, so the worst a corrupt store can do is fall back to the old
        behaviour of starting afresh at the next rise.

        The caller follows up with check_timeout(now). A session whose last
        rise is already older than IDLE_TIMEOUT_S would have been closed by
        the idle timer had Home Assistant been running, and is closed here
        from its stored peak for exactly that reason. Otherwise the session
        simply carries on: the first sample after startup is judged by
        feed()'s normal rules, so a higher SoC raises the peak, a fall of
        END_DROP_PCT closes it from the stored peak, and a silent sensor
        lets the idle timer close it.

        Nothing is extrapolated across the downtime. What was observed
        before the stop counts as observed, and the SoC found afterwards
        adds only its net rise, which can never exceed what went in.
        """
        if self.in_progress or not isinstance(data, dict):
            return False
        start_soc = clean_soc(data.get("start_soc"))
        peak_soc = clean_soc(data.get("peak_soc"))
        start_ts = _clean_ts(data.get("start_ts"))
        peak_ts = _clean_ts(data.get("peak_ts"))
        if start_soc is None or peak_soc is None or start_ts is None or peak_ts is None:
            return False
        if peak_soc < start_soc or peak_ts < start_ts:
            return False
        if peak_ts - start_ts > MAX_RESTORE_SESSION_S:
            return False
        if peak_ts > now + CLOCK_SKEW_TOLERANCE_S:
            return False
        if now - peak_ts > MAX_RESTORE_AGE_S:
            return False

        capacity = data.get("capacity_wh")
        capacity_wh: float | None = None
        if (
            not isinstance(capacity, bool)
            and isinstance(capacity, (int, float))
            and math.isfinite(capacity)
            and capacity > 0
        ):
            capacity_wh = float(capacity)
        gaps = data.get("gaps")
        if isinstance(gaps, bool) or not isinstance(gaps, int) or gaps < 0:
            gaps = 0

        self._start_soc = start_soc
        self._start_ts = start_ts
        self._peak_soc = peak_soc
        self._peak_ts = peak_ts
        self._capacity_wh = capacity_wh
        self._gaps = gaps
        return True

    def idle_remaining_s(self, now: float) -> float | None:
        """Seconds until check_timeout() would close the running session.

        None when no session is running. The monitor uses it to arm its idle
        timer for a session that was restored rather than started by a
        sample, since no sample may arrive to arm it the usual way.
        """
        if not self.in_progress or self._peak_ts is None:
            return None
        return max(0.0, IDLE_TIMEOUT_S - (now - self._peak_ts))

    def seed(self, soc: Any, now: float) -> None:
        """Set the baseline without any chance of starting a session.

        Called once at startup with the live entity's current value, so the
        first genuine rise after a restart is measured against something
        real instead of being swallowed as "no previous sample".
        """
        cleaned = clean_soc(soc)
        if cleaned is not None:
            self._last_soc = cleaned
            self._last_ts = now

    def feed(self, soc: Any, now: float, capacity_wh: float | None = None) -> bool:
        """Feed one sample. Returns True if the published summary changed."""
        cleaned = clean_soc(soc)
        if cleaned is None:
            # Unusable sample. Note it if a session is running (it goes into
            # the summary so a user can see the charge was observed through
            # a dropout) but change nothing else - see the module docstring.
            if self.in_progress:
                self._gaps += 1
            return False

        changed = False
        if self.in_progress:
            assert self._peak_soc is not None  # set together with _start_soc
            if cleaned > self._peak_soc:
                self._peak_soc = cleaned
                self._peak_ts = now
            elif self._peak_soc - cleaned >= END_DROP_PCT:
                changed = self._close()
                # This sample is the first one of whatever comes next, so it
                # must not also be compared against the session that just
                # ended.
                self._last_soc = cleaned
                self._last_ts = now
                return changed
        elif (
            self._last_soc is not None
            and cleaned - self._last_soc >= MIN_RISE_PCT
        ):
            # The rise happened between the previous sample and this one, so
            # the session started at the previous one - that is the SoC the
            # battery was actually at when it was plugged in. The start SOC
            # is trusted regardless of age (the battery really was at that
            # level), but the start TIME is only trusted within
            # MAX_START_LOOKBACK_S; see that constant for why.
            self._start_soc = self._last_soc
            self._start_ts = (
                self._last_ts
                if self._last_ts is not None
                and now - self._last_ts <= MAX_START_LOOKBACK_S
                else now
            )
            self._peak_soc = cleaned
            self._peak_ts = now
            self._capacity_wh = capacity_wh
            self._gaps = 0

        self._last_soc = cleaned
        self._last_ts = now
        return changed

    def check_timeout(self, now: float) -> bool:
        """Close a session whose SoC has not risen for IDLE_TIMEOUT_S.

        Returns True if that published a new summary. Safe to call at any
        time, including when no session is running.
        """
        if not self.in_progress or self._peak_ts is None:
            return False
        if now - self._peak_ts < IDLE_TIMEOUT_S:
            return False
        return self._close()

    def _close(self) -> bool:
        """End the running session, publishing it if it is worth reporting."""
        start_soc = self._start_soc
        start_ts = self._start_ts
        peak_soc = self._peak_soc
        peak_ts = self._peak_ts
        gaps = self._gaps
        capacity_wh = self._capacity_wh
        self._start_soc = self._start_ts = None
        self._peak_soc = self._peak_ts = None
        self._capacity_wh = None
        self._gaps = 0

        if start_soc is None or peak_soc is None or peak_ts is None or start_ts is None:
            return False
        delta = peak_soc - start_soc
        if delta < MIN_SESSION_PCT:
            return False

        duration_s = max(0.0, peak_ts - start_ts)
        energy_wh: float | None = None
        if capacity_wh and capacity_wh > 0:
            energy_wh = round(delta / 100.0 * capacity_wh, 1)
        if energy_wh:
            self._session_total_wh += energy_wh
        self._summary = {
            "start_soc": round(start_soc, 1),
            "end_soc": round(peak_soc, 1),
            "soc_delta": round(delta, 1),
            "energy_wh": energy_wh,
            "duration_min": round(duration_s / 60.0, 1),
            "started_at": start_ts,
            "ended_at": peak_ts,
            # How many times the SoC sensor was unavailable or unusable
            # during the charge. Non-zero is normal for a BLE bridge and
            # does not invalidate the numbers, but it is worth surfacing.
            "signal_gaps": gaps,
        }
        return True
