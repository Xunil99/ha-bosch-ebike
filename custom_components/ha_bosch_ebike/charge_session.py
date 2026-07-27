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
        self._total_energy_wh = 0.0

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
        return round(self._total_energy_wh, 2)

    def restore_total_energy(self, value: Any) -> None:
        """Adopt a running total read back from a restored entity state.

        Called instead of starting from zero after a restart. A negative or
        unusable value is ignored: this total feeds a TOTAL_INCREASING
        sensor, where going backwards is read as a meter reset and would
        corrupt the Energy Dashboard's history.

        Takes the larger of the restored value and whatever is already
        accumulated, rather than overwriting it. The caller subscribes to
        live SoC updates before it has necessarily restored this value (the
        subscription has to exist early so no sample is missed), so a
        session could in principle complete and add to the total before this
        runs; overwriting would silently erase it. Idempotent for the same
        reason, if this is ever called more than once.
        """
        try:
            restored = float(value)
        except (TypeError, ValueError):
            return
        if math.isfinite(restored) and restored >= 0:
            self._total_energy_wh = max(self._total_energy_wh, restored)

    def restore_summary(self, summary: dict[str, Any] | None) -> None:
        """Adopt a summary read back from a restored entity state.

        Only ever used to repopulate the last *completed* session across a
        restart. An in-flight session is not restored: reconstructing it
        would need the SoC history, and getting it wrong would publish a
        charge that never happened.
        """
        if isinstance(summary, dict):
            self._summary = summary

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
            self._total_energy_wh += energy_wh
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
