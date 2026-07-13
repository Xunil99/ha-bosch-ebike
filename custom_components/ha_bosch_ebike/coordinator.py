"""DataUpdateCoordinator for Bosch eBike."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import uuid
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util

from .api import BoschEBikeAPI, AuthError
from .const import (
    DOMAIN,
    SYSTEM_SMART,
    SYSTEM_BES2,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_BATTERY_CAPACITY_WH,
    SERVICE_WARN_DAYS,
    SERVICE_WARN_KM,
    EVENT_SERVICE_DUE_SOON,
    EVENT_SERVICE_OVERDUE,
    EVENT_MAINTENANCE_DUE_SOON,
    EVENT_MAINTENANCE_OVERDUE,
    CONF_LIVE_ODOMETER_ENTITY,
    CONF_LIVE_SOC_ENTITY,
    CONF_LIVE_SENSORS,
)
from .energy_cost import compute_energy_windows
from .live_enrichment import get_state_at, parse_iso_utc, sample_is_fresh
from .range_estimate import (
    compute_range_estimate,
    track_distance_m,
    corrected_track_distance,
)
from .unassigned_activities import compute_unassigned_activities, merge_manual_overrides

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY_SUFFIX = "consumption_state"


class BoschEBikeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch Bosch eBike data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: BoschEBikeAPI,
        system: str = SYSTEM_SMART,
        bes2_serial: str | None = None,
        bes2_part: str | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self._system = system
        self._bes2_serial = bes2_serial
        self._bes2_part = bes2_part
        self._initial_import_done = False
        # Sorted newest-first; range_estimate and latest_activity rely on this.
        self._all_activities: list[dict[str, Any]] = []
        self._latest_activity_details: dict[str, Any] | None = None
        self._latest_activity_id: str | None = None
        # Per-bike latest-activity GPS details (issue #47 follow-up): reuses
        # the account-wide fetch above when a bike's own latest ride is also
        # the global latest (the common case, zero extra cost); otherwise
        # fetched separately, bounded by number of bikes.
        self._latest_activity_details_by_bike: dict[str, dict[str, Any]] = {}
        self._latest_activity_id_by_bike: dict[str, str] = {}
        # Per-bike Data Act endpoints (refreshed every poll)
        self._bike_pass: dict[str, dict[str, Any]] = {}
        self._service_records: dict[str, dict[str, Any]] = {}
        # Battery consumption tracking (Wh delta between polls), per bike:
        # each bike has its own independent lifetime energy counter, and a
        # single shared scalar previously mixed up bikes whenever more than
        # one had a new activity in the same poll.
        self._prev_delivered_wh: dict[str, float] = {}
        self._prev_activity_ids: set[str] = set()
        # Per-bike battery capacity in Wh (issue #44 follow-up): a single
        # account-wide value was wrong for multi-bike accounts whose bikes
        # have different battery sizes. See battery_capacity_wh() for the
        # per-bike / legacy-flat / default fallback chain.
        self._battery_capacity_wh: dict[str, float] = {}
        self._activity_consumption: dict[str, dict[str, Any]] = {}
        # Per-activity bike attribution (activity_id -> bike_id) for multi-bike accounts
        self._activity_bike: dict[str, str] = {}
        self._unassigned_activities: list[dict[str, Any]] = []
        self._manual_activity_bike: dict[str, str] = {}
        # Per-activity track cache (activity_id -> [{lat,lon,...}]) for heatmap card
        self._all_tracks_cache: dict[str, list[dict[str, Any]]] = {}
        # Maintenance state per bike
        # bike_id -> {"items": [{id,name,interval_km,interval_days,last_done_at,last_done_odometer,warned}], "service_warned": {...}}
        self._maintenance: dict[str, dict[str, Any]] = {}
        # User-editable service-due overrides per bike
        # bike_id -> {"date": "YYYY-MM-DD" | None, "odometer_km": float | None}
        self._service_overrides: dict[str, dict[str, Any]] = {}
        # Persistent storage for consumption state (survives HA restarts)
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_{STORAGE_KEY_SUFFIX}"
        )
        self._state_loaded = False
        # Per-activity flag: which fields have already been overridden with
        # live BLE values. activity_id -> {"odo": True, "soc": True}. Failed
        # attempts (no recorder data fresh enough) are NOT cached so they
        # retry on the next poll — useful when the recorder catches up.
        self._live_enrichment_cache: dict[str, dict[str, bool]] = {}

    @property
    def is_bes2(self) -> bool:
        """True for an eBike System 2 account.

        Used by the entity platforms to skip Smart-System-only entities
        (service book, theft/bike-pass, per-mode range, component inventory,
        consumption, range estimate) that BES2 has no data for.
        """
        return self._system == SYSTEM_BES2

    async def async_load_persisted_state(self) -> None:
        """Restore battery consumption state from disk (once at startup)."""
        if self._state_loaded:
            return
        data = await self._store.async_load()
        if isinstance(data, dict):
            prev_wh = data.get("prev_delivered_wh")
            if isinstance(prev_wh, dict):
                self._prev_delivered_wh = {
                    bid: float(v) for bid, v in prev_wh.items()
                    if isinstance(bid, str) and isinstance(v, (int, float))
                }
            elif isinstance(prev_wh, (int, float)):
                # Pre-migration store: one global scalar, not attributed to
                # any bike. Nothing to migrate - skipping it just means the
                # first poll after upgrading establishes a fresh per-bike
                # baseline instead of computing one (possibly bike-ambiguous)
                # delta immediately, which is the safe choice.
                pass
            prev_ids = data.get("prev_activity_ids")
            if isinstance(prev_ids, list):
                self._prev_activity_ids = {x for x in prev_ids if isinstance(x, str)}
            consumption = data.get("activity_consumption")
            if isinstance(consumption, dict):
                self._activity_consumption = {
                    k: v for k, v in consumption.items() if isinstance(v, dict)
                }
            attribution = data.get("activity_bike")
            if isinstance(attribution, dict):
                self._activity_bike = {
                    k: v for k, v in attribution.items()
                    if isinstance(k, str) and isinstance(v, str)
                }
            manual_attribution = data.get("manual_activity_bike")
            if isinstance(manual_attribution, dict):
                self._manual_activity_bike = {
                    k: v for k, v in manual_attribution.items()
                    if isinstance(k, str) and isinstance(v, str)
                }
            maintenance = data.get("maintenance")
            if isinstance(maintenance, dict):
                self._maintenance = {
                    bid: bike_data for bid, bike_data in maintenance.items()
                    if isinstance(bid, str) and isinstance(bike_data, dict)
                }
            overrides = data.get("service_overrides")
            if isinstance(overrides, dict):
                self._service_overrides = {
                    bid: ov for bid, ov in overrides.items()
                    if isinstance(bid, str) and isinstance(ov, dict)
                }
            capacity = data.get("battery_capacity_wh")
            if isinstance(capacity, dict):
                self._battery_capacity_wh = {
                    bid: float(v) for bid, v in capacity.items()
                    if isinstance(bid, str) and isinstance(v, (int, float)) and v > 0
                }
            elif isinstance(capacity, (int, float)) and capacity > 0:
                # Pre-migration store: one global scalar, not attributed to
                # any bike. Nothing to migrate into the per-bike dict here -
                # we don't know which bike it was for - the legacy flat
                # entry.data value is the fallback every bike reads until
                # explicitly overridden; see battery_capacity_wh().
                pass
            _LOGGER.debug(
                "Loaded persisted consumption state: prev_wh=%s, activities=%d",
                self._prev_delivered_wh,
                len(self._activity_consumption),
            )
        self._state_loaded = True

    async def _async_save_state(self) -> None:
        """Persist the battery consumption state to disk."""
        await self._store.async_save(
            {
                "prev_delivered_wh": dict(self._prev_delivered_wh),
                "prev_activity_ids": sorted(self._prev_activity_ids),
                "activity_consumption": self._activity_consumption,
                "activity_bike": self._activity_bike,
                "manual_activity_bike": self._manual_activity_bike,
                "maintenance": self._maintenance,
                "service_overrides": self._service_overrides,
                "battery_capacity_wh": dict(self._battery_capacity_wh),
            }
        )

    # -- Service-due override accessors --

    def _bike_override(self, bike_id: str) -> dict[str, Any]:
        if bike_id not in self._service_overrides:
            self._service_overrides[bike_id] = {"date": None, "odometer_km": None}
        ov = self._service_overrides[bike_id]
        ov.setdefault("date", None)
        ov.setdefault("odometer_km", None)
        return ov

    def get_service_due_date(self, bike_id: str) -> str | None:
        """Return the effective service-due date as ISO string (YYYY-MM-DD), or None."""
        return self._bike_override(bike_id)["date"]

    def get_service_due_km(self, bike_id: str) -> float | None:
        """Return the effective service-due odometer in km, or None."""
        return self._bike_override(bike_id)["odometer_km"]

    def set_service_due_date(self, bike_id: str, value: str | None) -> None:
        ov = self._bike_override(bike_id)
        if ov["date"] != value:
            ov["date"] = value
            self.hass.async_create_task(self._async_save_state())

    def set_service_due_km(self, bike_id: str, value_km: float | None) -> None:
        ov = self._bike_override(bike_id)
        if ov["odometer_km"] != value_km:
            ov["odometer_km"] = value_km
            self.hass.async_create_task(self._async_save_state())

    def _seed_service_overrides(self, bikes: list[dict[str, Any]]) -> bool:
        """Initialise per-bike overrides from the Bosch values when not yet set."""
        changed = False
        for bike in bikes:
            bike_id = bike.get("id")
            if not bike_id:
                continue
            ov = self._bike_override(bike_id)
            service = bike.get("serviceDue") or {}
            if ov["date"] is None and service.get("date"):
                # serviceDue.date is e.g. "2026-09-15" or full ISO timestamp; trim to date
                raw = str(service["date"])
                ov["date"] = raw[:10] if len(raw) >= 10 else raw
                changed = True
            if ov["odometer_km"] is None and isinstance(service.get("odometer"), (int, float)):
                ov["odometer_km"] = float(service["odometer"]) / 1000.0
                changed = True
        return changed

    @staticmethod
    def attribute_activities_to_bikes(
        bikes: list[dict[str, Any]],
        activities: list[dict[str, Any]],
        tolerance_m: float = 1500.0,
    ) -> dict[str, str]:
        """Attribute each activity to a bike via odometer matching.

        Heuristic: bikes report their current ``driveUnit.odometer`` (in meters);
        activities expose ``startOdometer`` and ``distance``. We process activities
        from newest to oldest, find the bike whose current odometer is closest to
        ``startOdometer + distance`` (within ``tolerance_m``), then "unwind" that
        bike's odometer back to ``startOdometer`` to attribute the next-older
        activity. Activities that cannot be matched within tolerance are skipped.

        Returns a dict ``{activity_id: bike_id}``. Single-bike accounts always
        attribute every activity to that one bike. Empty dict if no bikes have
        ``odometer`` data.
        """
        bike_odos: dict[str, float] = {}
        for bike in bikes:
            bid = bike.get("id")
            odo = (bike.get("driveUnit") or {}).get("odometer")
            if bid and isinstance(odo, (int, float)):
                bike_odos[bid] = float(odo)
        if not bike_odos:
            return {}

        # Single bike → trivial attribution
        if len(bike_odos) == 1:
            only_bike = next(iter(bike_odos.keys()))
            return {
                a["id"]: only_bike
                for a in activities
                if a.get("id")
            }

        sorted_acts = sorted(
            [a for a in activities if a.get("id") and a.get("startOdometer") is not None],
            key=lambda a: a.get("startTime", ""),
            reverse=True,
        )

        attribution: dict[str, str] = {}
        for act in sorted_acts:
            try:
                start_odo = float(act["startOdometer"])
                distance = float(act.get("distance", 0) or 0)
            except (TypeError, ValueError):
                continue
            end_odo = start_odo + distance

            best_bike: str | None = None
            best_diff = float("inf")
            for bid, odo in bike_odos.items():
                diff = abs(odo - end_odo)
                if diff < best_diff:
                    best_diff = diff
                    best_bike = bid

            if best_bike is None or best_diff > tolerance_m:
                continue

            attribution[act["id"]] = best_bike
            # "Unwind" bike's odometer back to before this activity
            bike_odos[best_bike] = start_odo

        return attribution

    def battery_capacity_wh(self, bike_id: str | None) -> float:
        """Effective battery capacity in Wh for *bike_id*.

        A per-bike override (set via that bike's Battery Capacity number
        entity) takes priority. A bike that was never overridden falls back
        to the legacy flat value on the config entry (pre-multi-bike,
        account wide), then to the hardcoded default. This mirrors the
        live-sensor fallback chain from issue #44 (see _live_sensor_entity).
        """
        if bike_id is not None and bike_id in self._battery_capacity_wh:
            return self._battery_capacity_wh[bike_id]
        legacy = self.config_entry.data.get("battery_capacity_wh") if self.config_entry else None
        if isinstance(legacy, (int, float)) and legacy > 0:
            return float(legacy)
        return DEFAULT_BATTERY_CAPACITY_WH

    def set_battery_capacity(self, bike_id: str, capacity_wh: float) -> None:
        """Set *bike_id*'s battery capacity and refresh its consumption entries.

        Older consumption records for THIS bike still hold the previous
        capacity_wh and the derived percentage in their dict. We rewrite both
        in place so existing rides immediately reflect the new capacity. The
        raw consumed_wh value stays as recorded. Other bikes' entries are
        untouched, since their capacity has not changed.
        """
        # Live-enrichment cache holds consumed_wh derived from the previous
        # capacity. Wipe it so the next poll recomputes from live SoC deltas.
        self.invalidate_live_enrichment_cache()

        if self._battery_capacity_wh.get(bike_id) == capacity_wh:
            return
        self._battery_capacity_wh[bike_id] = capacity_wh
        for aid, entry in self._activity_consumption.items():
            if self._activity_bike.get(aid) != bike_id:
                continue
            entry["capacity_wh"] = capacity_wh
            try:
                consumed = float(entry.get("consumed_wh", 0) or 0)
                entry["percentage"] = round((consumed / capacity_wh) * 100, 1) if capacity_wh > 0 else 0
            except (TypeError, ValueError):
                entry["percentage"] = 0
        self.hass.async_create_task(self._async_save_state())
        # Push the refreshed data to all subscribers (sensors + websocket clients)
        if self.data is not None:
            new_data = dict(self.data)
            new_data["activity_consumption"] = self._activity_consumption
            new_data["battery_capacity_wh"] = dict(self._battery_capacity_wh)
            self.async_set_updated_data(new_data)

    def _track_battery_consumption(self, bikes: list[dict[str, Any]]) -> bool:
        """Track each bike's own deliveredWhOverLifetime and allocate to activities.

        Every bike has its own independent lifetime energy counter. A single
        shared delta previously mixed up bikes: if two bikes each finished a
        ride between polls, one bike's actual Wh draw could get fractionally
        attributed to the OTHER bike's activity, and that wrong share was
        then divided by that other bike's own (correct) capacity to produce a
        confidently wrong percentage. Fixed by tracking current_wh/delta_wh
        per bike, and only ever allocating a bike's delta across that SAME
        bike's own new activities.

        Requires self._activity_bike to already reflect the CURRENT
        self._all_activities (attribution must run before this - see
        _async_update_data).

        Returns True if persistent state changed and should be saved.
        """
        current_wh_by_bike: dict[str, float] = {}
        for bike in bikes:
            bike_id = bike.get("id")
            if not bike_id:
                continue
            for battery in bike.get("batteries", []) or []:
                wh = battery.get("deliveredWhOverLifetime")
                if wh is not None:
                    current_wh_by_bike[bike_id] = wh
                    break

        if not current_wh_by_bike:
            return False

        current_ids = {a.get("id") for a in self._all_activities if a.get("id")}
        new_ids = current_ids - self._prev_activity_ids
        new_activities = [a for a in self._all_activities if a.get("id") in new_ids]

        state_changed = False
        # Ids that stayed unresolved this poll (no bike attribution yet, or
        # that bike's delta_wh was not usable) MUST NOT be folded into
        # self._prev_activity_ids below, or they would count as "already
        # seen" forever and never get a second chance - attribution and a
        # currently-non-positive delta can both genuinely resolve on a later
        # poll (cloud data catching up, mirroring issue #31's GPS-track-lag
        # handling), so leaving them out here is what actually makes the
        # "retried next poll" behaviour true instead of just a comment.
        unresolved_ids: set[str] = set()

        if new_activities:
            # Single-bike accounts get a fallback to that one bike when an
            # activity could not (yet) be attributed - same reasoning as
            # compute_range_estimate's fallback_all - since there is no
            # ambiguity about which bike it could be. Multi-bike accounts
            # leave it unattributed rather than guess which of several bikes
            # it belongs to.
            single_bike_id = bikes[0].get("id") if len(bikes) == 1 else None

            by_bike: dict[str, list[dict[str, Any]]] = {}
            for activity in new_activities:
                aid = activity.get("id")
                if not aid:
                    continue
                bike_id = self._activity_bike.get(aid) or single_bike_id
                if not bike_id:
                    unresolved_ids.add(aid)
                    continue
                by_bike.setdefault(bike_id, []).append(activity)

            for bike_id, bike_activities in by_bike.items():
                current_wh = current_wh_by_bike.get(bike_id)
                prev_wh = self._prev_delivered_wh.get(bike_id)
                delta_wh = (
                    current_wh - prev_wh
                    if current_wh is not None and prev_wh is not None
                    else None
                )
                if delta_wh is None or delta_wh <= 0:
                    unresolved_ids.update(
                        a.get("id") for a in bike_activities if a.get("id")
                    )
                    continue

                total_distance = sum(
                    a.get("distance", 0) or 0 for a in bike_activities
                )
                capacity_wh = self.battery_capacity_wh(bike_id)

                for activity in bike_activities:
                    aid = activity.get("id")
                    dist = activity.get("distance", 0) or 0
                    if total_distance > 0 and len(bike_activities) > 1:
                        share = delta_wh * (dist / total_distance)
                        is_exact = False
                    else:
                        share = delta_wh
                        is_exact = len(bike_activities) == 1

                    self._activity_consumption[aid] = {
                        "consumed_wh": round(share, 1),
                        "capacity_wh": capacity_wh,
                        "is_exact": is_exact,
                        "percentage": round(
                            (share / capacity_wh) * 100, 1
                        ) if capacity_wh > 0 else 0,
                    }
                    state_changed = True
                    _LOGGER.info(
                        "Battery consumption for activity %s (bike %s): %.1f Wh (%.1f%%)",
                        aid, bike_id, share,
                        (share / capacity_wh) * 100
                        if capacity_wh > 0 else 0,
                    )

        # Basislinien pro Bike aktualisieren
        for bike_id, current_wh in current_wh_by_bike.items():
            if self._prev_delivered_wh.get(bike_id) != current_wh:
                self._prev_delivered_wh[bike_id] = current_wh
                state_changed = True
        current_ids = current_ids - unresolved_ids
        if self._prev_activity_ids != current_ids:
            self._prev_activity_ids = current_ids
            state_changed = True

        return state_changed

    # -- Live BLE enrichment (optional) --

    def _live_sensor_entity(self, bike_id: str | None, key: str) -> str | None:
        """Configured live sensor entity_id for *bike_id*, or None.

        Per-bike config (issue #44) lives under ``options[CONF_LIVE_SENSORS]``,
        keyed by bike_id. The legacy flat ``options[key]`` value (pre-#44,
        applied to the whole account) is used ONLY as a fallback while no
        per-bike config has been saved yet — once any bike is configured via
        the per-bike options flow, an unconfigured bike gets no live sensor
        rather than silently inheriting another bike's value.
        """
        if not self.config_entry:
            return None
        options = self.config_entry.options
        per_bike = options.get(CONF_LIVE_SENSORS) or {}
        if bike_id is not None and bike_id in per_bike:
            value = per_bike[bike_id].get(key)
            return value or None
        if not per_bike:
            value = options.get(key)
            return value or None
        return None

    def live_odometer_entity(self, bike_id: str | None = None) -> str | None:
        """Configured live odometer sensor entity_id for *bike_id*, or None."""
        return self._live_sensor_entity(bike_id, CONF_LIVE_ODOMETER_ENTITY)

    def live_soc_entity(self, bike_id: str | None = None) -> str | None:
        """Configured live battery SoC sensor entity_id for *bike_id*, or None."""
        return self._live_sensor_entity(bike_id, CONF_LIVE_SOC_ENTITY)

    def invalidate_live_enrichment_cache(self) -> None:
        """Clear the per-activity enrichment cache.

        Called when the battery capacity changes (live consumption depends
        on it). Options changes reload the entry and rebuild this object.
        """
        self._live_enrichment_cache.clear()

    async def _enrich_activities_with_live_data(self) -> bool:
        """Override distance / consumption from live BLE sensors where possible.

        For each activity that has not yet been enriched, query the HA
        recorder for the sensors configured for THAT activity's bike (issue
        #44: multi-bike accounts can wire a different bridge per bike) at
        startTime and endTime. If a fresh sample exists at both points,
        derive the exact value and replace the cloud-derived one. Falls back
        transparently when no live data is available.

        Requires ``self._activity_bike`` to already reflect the CURRENT
        ``self._all_activities`` (attribution must run before this).

        Returns True if persistent state changed (consumption entries).
        """
        options = self.config_entry.options if self.config_entry else {}
        if not options.get(CONF_LIVE_SENSORS) and not options.get(
            CONF_LIVE_ODOMETER_ENTITY
        ) and not options.get(CONF_LIVE_SOC_ENTITY):
            return False

        state_changed = False
        for activity in self._all_activities:
            aid = activity.get("id")
            if not aid:
                continue
            bike_id = self._activity_bike.get(aid)
            odo_entity = self.live_odometer_entity(bike_id)
            soc_entity = self.live_soc_entity(bike_id)
            if not odo_entity and not soc_entity:
                continue
            cache = self._live_enrichment_cache.setdefault(aid, {})

            start_time = parse_iso_utc(activity.get("startTime"))
            end_time = parse_iso_utc(activity.get("endTime"))
            if start_time is None or end_time is None:
                continue
            if end_time <= start_time:
                continue

            # ---- Distance (live odometer is in km) ----
            if odo_entity and not cache.get("odo"):
                start_odo_result = await get_state_at(self.hass, odo_entity, start_time)
                end_odo_result = await get_state_at(self.hass, odo_entity, end_time)
                if start_odo_result is not None and end_odo_result is not None:
                    start_odo, start_odo_ts = start_odo_result
                    end_odo, end_odo_ts = end_odo_result
                    # issue #31/#54: re-verify freshness ourselves rather than
                    # trusting get_state_at()'s own tolerance check alone - a
                    # step-updating odometer (stationary bridge) has been
                    # observed matching an hours-old sample from before a
                    # PRIOR, unrelated ride, silently applying that ride's
                    # cumulative distance to this one.
                    if not sample_is_fresh(start_odo_ts, start_time) or not sample_is_fresh(
                        end_odo_ts, end_time
                    ):
                        _LOGGER.debug(
                            "Live distance for activity %s: rejecting stale sample "
                            "(start_odo=%.3f km @ %s for target %s, end_odo=%.3f km "
                            "@ %s for target %s) - keeping the cloud-derived distance",
                            aid,
                            start_odo, start_odo_ts.isoformat(), start_time.isoformat(),
                            end_odo, end_odo_ts.isoformat(), end_time.isoformat(),
                        )
                    elif end_odo >= start_odo:
                        live_distance_m = (end_odo - start_odo) * 1000.0
                        # Sanity guard: ignore obviously bogus values (sensor
                        # rollover, zero-length tour). 50 m .. 500 km per tour.
                        if 50.0 <= live_distance_m <= 500_000.0:
                            old = activity.get("distance")
                            activity["distance"] = round(live_distance_m, 1)
                            activity["_distance_source"] = "ble_live"
                            cache["odo"] = True
                            _LOGGER.info(
                                "Live distance for activity %s: %.0f m (was %s). "
                                "issue#31 forensic: start_odo=%.3f km @ %s (target %s), "
                                "end_odo=%.3f km @ %s (target %s)",
                                aid, live_distance_m, old,
                                start_odo, start_odo_ts.isoformat(), start_time.isoformat(),
                                end_odo, end_odo_ts.isoformat(), end_time.isoformat(),
                            )

            # ---- Consumption (live SoC in %) ----
            if soc_entity and not cache.get("soc"):
                start_soc_result = await get_state_at(self.hass, soc_entity, start_time)
                end_soc_result = await get_state_at(self.hass, soc_entity, end_time)
                capacity_wh = self.battery_capacity_wh(bike_id)
                if (
                    start_soc_result is not None
                    and end_soc_result is not None
                    and capacity_wh > 0
                ):
                    start_soc, start_soc_ts = start_soc_result
                    end_soc, end_soc_ts = end_soc_result
                    # Same defense-in-depth freshness re-check as distance above.
                    if not sample_is_fresh(start_soc_ts, start_time) or not sample_is_fresh(
                        end_soc_ts, end_time
                    ):
                        _LOGGER.debug(
                            "Live consumption for activity %s: rejecting stale SoC "
                            "sample (start=%.1f%% @ %s for target %s, end=%.1f%% @ %s "
                            "for target %s)",
                            aid,
                            start_soc, start_soc_ts.isoformat(), start_time.isoformat(),
                            end_soc, end_soc_ts.isoformat(), end_time.isoformat(),
                        )
                    else:
                        delta_pct = start_soc - end_soc
                        # Allow tiny negative drifts (regen, sensor noise).
                        if -2.0 <= delta_pct <= 100.0:
                            consumed_pct = max(0.0, delta_pct)
                            consumed_wh = (
                                consumed_pct * capacity_wh / 100.0
                            )
                            self._activity_consumption[aid] = {
                                "consumed_wh": round(consumed_wh, 1),
                                "capacity_wh": capacity_wh,
                                "is_exact": True,
                                "percentage": round(consumed_pct, 1),
                                "source": "ble_live",
                            }
                            cache["soc"] = True
                            state_changed = True
                            _LOGGER.info(
                                "Live consumption for activity %s: %.1f Wh (%.1f %%)",
                                aid, consumed_wh, consumed_pct,
                            )

        return state_changed

    async def _update_bes2(self) -> dict[str, Any]:
        """Fetch + normalize eBike System 2 data into the BES3-shaped dict."""
        from . import bes2
        try:
            raw_bikes = await self.api.get_bikes_bes2(self._bes2_serial, self._bes2_part)
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error fetching BES2 bikes: {err}") from err

        bikes = [bes2.normalize_bike(b) for b in (raw_bikes or []) if isinstance(b, dict)]

        # Token-persistence is intentionally not handled here: unlike the BES3
        # path (where it is inlined in _async_update_data), api._get
        # auto-refreshes the access token transparently. Persisting refreshed
        # tokens for the BES2 path is deferred to a later phase.

        activities: list[dict[str, Any]] = []
        try:
            raw_acts = await self.api.get_activities_bes2(limit=20, offset=0)
            activities = [bes2.normalize_activity_summary(a) for a in (raw_acts or []) if isinstance(a, dict)]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Could not fetch BES2 activities: %s", err)

        # Newest first (the BES2 endpoint order is not guaranteed). startTime is
        # an ISO-8601 string, so a plain reverse string sort is chronological.
        # Ensures latest_activity is truly the newest and the map list order
        # matches the Smart System path.
        activities.sort(key=lambda a: str(a.get("startTime") or ""), reverse=True)

        latest_activity = activities[0] if activities else None
        latest_details = None
        if latest_activity is not None:
            raw_id = latest_activity.get("id")
            if raw_id is not None:
                try:
                    detail = await self.api.get_activity_detail_bes2(raw_id)
                    latest_details = bes2.normalize_track(detail)
                    bes2.enrich_summary_from_detail(latest_activity, detail)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Could not fetch BES2 activity detail %s: %s", raw_id, err)

        # Lifetime totals (Gesamt-km / Gesamt-Höhenmeter) from /statistics.
        # totalStatistics.distance feeds the existing odometer sensor (it reads
        # driveUnit.odometer in metres); elevationGain is exposed via a new
        # per-bike "Total Elevation Gain" sensor created when stats are present.
        stats: dict[str, Any] = {}
        try:
            stats = bes2.normalize_statistics(await self.api.get_statistics_bes2())
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Could not fetch BES2 statistics: %s", err)
        if stats:
            for bike in bikes:
                if stats.get("total_distance_m") is not None:
                    bike.setdefault("driveUnit", {})["odometer"] = stats["total_distance_m"]
                bike["_bes2_statistics"] = stats

        # BES2 config entries are single-bike, so the account-wide latest
        # activity details are also this one bike's own (issue #47 follow-up
        # counterpart for the BES3 path's per-bike dict).
        latest_activity_details_by_bike: dict[str, Any] = {}
        if bikes and latest_details is not None:
            bid = bikes[0].get("id")
            if bid:
                latest_activity_details_by_bike[bid] = latest_details

        return {
            "bikes": bikes,
            "latest_activity": latest_activity,
            "all_activities": activities,
            "latest_activity_details": latest_details,
            "latest_activity_details_by_bike": latest_activity_details_by_bike,
            "activity_consumption": {},
            "activity_bike": {},
            "maintenance": self._maintenance,
            "service_overrides": self._service_overrides,
            "battery_capacity_wh": self._battery_capacity_wh,
            "range_estimate": None,
            "energy_window": {},
            "bike_pass": {},
            "service_records": {},
            "unassigned_activities": [],
        }

    async def fetch_track_detail(self, activity_id: Any) -> dict[str, Any]:
        """Return an activity detail as ``{"activityDetails": [...]}``.

        System-aware so the map/track websockets work for both generations:
        BES2 uses the eBike-System-2 endpoint and is flattened via
        ``bes2.normalize_track`` into the same point shape the Smart System
        detail already has.
        """
        if self._system == SYSTEM_BES2:
            from . import bes2
            raw = await self.api.get_activity_detail_bes2(activity_id)
            return bes2.normalize_track(raw)
        return await self.api.get_activity_detail(activity_id)

    async def _recheck_recent_activity_distances(self) -> None:
        """Issue #31: correct recent NON-latest activities from their GPS track.

        The latest-activity check only fixes _all_activities[0]. But a ride's
        full cloud GPS track can finish uploading only AFTER a newer ride has
        appeared (the morning commute, finalized only in the evening), so the
        morning ride would otherwise freeze on its partial summary forever.
        Refetch the track of the most recent still-unconfirmed activities
        (bounded by a 48 h window and a fetch cap) every poll and correct them
        upwards once their full track is available. Index 0 is handled above.
        A `gps_track`-confirmed distance is skipped (nothing would change on
        a repeat check against the same track). A `ble_live` distance is
        normally more precise than a GPS track and is skipped too - but only
        once a real track has actually been fetched and compared against it
        (`_ble_track_checked`, set only when the track was available, so a
        still-uploading track is retried on a later poll rather than locking
        the activity out). The comparison itself uses a much stricter margin
        than a raw cloud summary (see `corrected_track_distance`'s
        `min_ratio`/`min_absolute_m`), so ordinary GPS noise never overrides
        a good BLE value - only a genuinely wrong one, like an odometer
        sample that matched the wrong ride (issue #31), self-heals this way.
        """
        if getattr(self, "is_bes2", False):
            return  # BES2 uses a different track endpoint (handled elsewhere).
        if len(self._all_activities) < 2:
            return
        cutoff = dt_util.utcnow() - timedelta(hours=48)
        max_fetches = 5
        fetched = 0
        for act in self._all_activities[1:30]:
            if fetched >= max_fetches:
                break
            src = act.get("_distance_source")
            if src == "gps_track":
                continue
            if src == "ble_live" and act.get("_ble_track_checked"):
                continue
            aid = act.get("id")
            if not aid:
                continue
            end_time = parse_iso_utc(act.get("endTime")) or parse_iso_utc(
                act.get("startTime")
            )
            if end_time is None or end_time < cutoff:
                continue
            fetched += 1
            try:
                details = await self.api.get_activity_detail(aid)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "issue#31 recheck: detail fetch failed for %s: %s", aid, err
                )
                continue
            track_m = track_distance_m(details)
            summary_m = float(act.get("distance") or 0)
            _LOGGER.debug(
                "issue#31 recheck activity %s: summary=%.0f m track=%s source=%s",
                aid, summary_m,
                ("%.0f" % track_m) if track_m is not None else None,
                src or "cloud",
            )
            if src == "ble_live":
                # ble_live is normally more precise than a GPS track, so
                # require a much larger, unmistakable gap (not the 5 %/200 m
                # noise band used for a raw cloud summary) before letting the
                # track override it - ordinary GPS jitter must never win.
                corrected = corrected_track_distance(
                    summary_m, track_m, min_ratio=2.0, min_absolute_m=1000.0
                )
            else:
                corrected = corrected_track_distance(summary_m, track_m)
            if corrected is not None:
                act["distance"] = corrected
                act["_distance_source"] = "gps_track"
                _LOGGER.info(
                    "Distance for activity %s corrected from GPS track "
                    "(recheck): %.0f m (%s said %.0f m)",
                    aid, corrected, src or "summary", summary_m,
                )
            elif src == "ble_live" and track_m is not None:
                # Only mark as checked once a real track was actually
                # compared - if the track hasn't uploaded yet (track_m is
                # None), leave it eligible for retry on a later poll.
                act["_ble_track_checked"] = True

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch bikes and activities from Bosch API."""
        if self._system == SYSTEM_BES2:
            return await self._update_bes2()

        try:
            bikes = await self.api.get_bikes()

            if not self._initial_import_done:
                # First run: import ALL activities
                _LOGGER.info("Bosch eBike: Initial import — fetching all activities...")
                self._all_activities = await self.api.get_all_activities()
                self._initial_import_done = True
                _LOGGER.info(
                    "Bosch eBike: Initial import complete — %d activities loaded",
                    len(self._all_activities),
                )
            else:
                # Subsequent runs: only fetch latest activity
                latest = await self.api.get_latest_activity()
                if latest:
                    latest_id = latest.get("id")
                    if self._all_activities and self._all_activities[0].get("id") == latest_id:
                        # Same activity, update in place — but keep a derived
                        # distance (BLE odometer / GPS track): the fresh cloud
                        # copy would silently revert it and the enrichment
                        # cache prevents re-deriving (issue #31).
                        # A gps_track value is only kept while it is still >=
                        # the fresh cloud summary: tracks are fetched once and
                        # can be stale (ride still uploading) — a GROWING
                        # summary must win over a stale track-derived value.
                        old = self._all_activities[0]
                        src = old.get("_distance_source")
                        if src == "ble_live" or (
                            src == "gps_track"
                            and float(old.get("distance") or 0)
                            >= float(latest.get("distance") or 0)
                        ):
                            latest["distance"] = old.get("distance")
                            latest["_distance_source"] = src
                        self._all_activities[0] = latest
                    else:
                        # New activity, prepend
                        self._all_activities.insert(0, latest)
                        _LOGGER.info(
                            "Bosch eBike: New activity detected: %s", latest.get("title")
                        )

        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

        # Persist updated tokens back to the config entry, but only when they
        # actually changed (a token refresh happened). Writing on every poll
        # would cause needless storage writes.
        if (
            self.api.access_token != self.config_entry.data.get("access_token")
            or self.api.refresh_token != self.config_entry.data.get("refresh_token")
        ):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    "access_token": self.api.access_token,
                    "refresh_token": self.api.refresh_token,
                },
            )

        latest_activity = self._all_activities[0] if self._all_activities else None

        # Fetch GPS details for the latest activity (for start/end coordinates)
        if latest_activity:
            activity_id = latest_activity.get("id")
            # Fetch the GPS track for the latest activity. We refetch on every
            # poll while the ride stays the latest one AND its distance is not
            # yet confirmed from a derived source: the track can still be
            # uploading when we first see the activity (the ride may not be
            # finished in the Flow app yet), so a later poll may carry the full
            # track the distance sanity-check below needs (issue #31).
            distance_confirmed = latest_activity.get("_distance_source") in (
                "ble_live",
                "gps_track",
            )
            if activity_id and (
                activity_id != self._latest_activity_id or not distance_confirmed
            ):
                try:
                    details = await self.api.get_activity_detail(activity_id)
                    self._latest_activity_details = details
                    self._latest_activity_id = activity_id
                except Exception as err:  # noqa: BLE001
                    # GPS details are optional - never fail the whole update.
                    _LOGGER.debug(
                        "Could not fetch GPS details for activity %s: %s",
                        activity_id, err,
                    )

            # Sanity-check the summary distance against the GPS track
            # (issue #31): the cloud summary sometimes reports fewer metres
            # than the recorded track covers. Only ever corrects UPWARDS
            # (a partially uploaded track must never shrink the value) and
            # never touches a BLE-derived distance.
            if (
                self._latest_activity_details
                and self._latest_activity_id == activity_id
                and latest_activity.get("_distance_source") != "ble_live"
            ):
                track_m = track_distance_m(self._latest_activity_details)
                summary_m = float(latest_activity.get("distance") or 0)
                # Diagnostic (issue #31): record what we compared each poll, so a
                # future failure shows whether the cloud track was still partial.
                _LOGGER.debug(
                    "issue#31 latest activity %s: summary=%.0f m track=%s",
                    activity_id, summary_m,
                    ("%.0f" % track_m) if track_m is not None else None,
                )
                corrected = corrected_track_distance(summary_m, track_m)
                if corrected is not None:
                    latest_activity["distance"] = corrected
                    latest_activity["_distance_source"] = "gps_track"
                    _LOGGER.info(
                        "Distance for activity %s corrected from GPS track: "
                        "%.0f m (summary said %.0f m)",
                        activity_id, corrected, summary_m,
                    )

        # Issue #31: also recheck recent NON-latest activities, whose full GPS
        # track can finish uploading only after a newer ride has appeared.
        await self._recheck_recent_activity_distances()

        # Restore persisted consumption state on first run
        await self.async_load_persisted_state()

        # Bike attribution via odometer-matching (only meaningful for multi-bike accounts;
        # for single-bike accounts every activity is attributed to that bike).
        # Runs BEFORE battery consumption tracking and live-data enrichment
        # below, both of which need the current attribution to pick the right
        # bike's capacity / live sensors per activity (issue #44). Getting
        # this order wrong once already caused live enrichment to use stale
        # attribution from the prior poll; the same applies to consumption.
        new_attribution = self.attribute_activities_to_bikes(bikes, self._all_activities)
        merged_attribution = merge_manual_overrides(new_attribution, self._manual_activity_bike)
        state_changed = merged_attribution != self._activity_bike
        if state_changed:
            self._activity_bike = merged_attribution

        # Issue #47 follow-up: activities the odometer-matching above could
        # not confidently assign to any bike, minus any the user has since
        # manually assigned via the options flow.
        self._unassigned_activities = compute_unassigned_activities(
            self._all_activities, self._activity_bike, len(bikes)
        )

        # Battery consumption tracking via Wh delta
        if self._track_battery_consumption(bikes):
            state_changed = True

        # Optional: override distance / consumption with live BLE values
        # from the user-configured sensors. Replaces cloud-derived numbers
        # for any activity where a fresh recorder sample exists at both
        # tour start and end.
        if await self._enrich_activities_with_live_data():
            state_changed = True

        # Seed service-due overrides from Bosch on first sight of a bike
        if self._seed_service_overrides(bikes):
            state_changed = True

        # Service & maintenance reminders
        if self._check_service_and_maintenance(bikes):
            state_changed = True

        # Estimated range: distance-weighted Wh/km over the last ~500 km,
        # computed from data already in memory (no extra API calls).
        range_estimate: dict[str, dict[str, Any]] = {}
        single_bike = len(bikes) == 1
        for bike in bikes:
            bid = bike.get("id")
            if not bid:
                continue
            est = compute_range_estimate(
                self._all_activities,
                self._activity_bike,
                self._activity_consumption,
                bid,
                fallback_all=single_bike,
            )
            if est:
                range_estimate[bid] = est

        # Charging energy over rolling 7/30/365-day windows, per bike -
        # computed from data already in memory (no extra API calls). Feeds
        # the dashboard card's optional charging-cost summary.
        energy_window: dict[str, dict[str, float]] = {}
        for bike in bikes:
            bid = bike.get("id")
            if not bid:
                continue
            windows = compute_energy_windows(
                self._all_activities,
                self._activity_bike,
                self._activity_consumption,
                bid,
                dt_util.utcnow(),
                fallback_all=single_bike,
            )
            if windows:
                energy_window[bid] = windows

        # Per-bike GPS details for the latest ride (issue #47 follow-up):
        # each bike needs its OWN latest activity's GPS details, not the
        # account-wide latest_activity_details fetched above. Reuses that
        # fetch when a bike's own latest ride is also the account-wide
        # latest (the common case, zero extra cost); only fetches
        # separately when it differs, guarded by the same
        # distance-confirmed staleness check as the account-wide fetch.
        for bike in bikes:
            bid = bike.get("id")
            if not bid:
                continue
            bike_latest = self._bike_latest_activity(bid, fallback_all=single_bike)
            if not bike_latest:
                continue
            bike_activity_id = bike_latest.get("id")
            if not bike_activity_id:
                continue
            if bike_activity_id == self._latest_activity_id:
                self._latest_activity_details_by_bike[bid] = self._latest_activity_details
                self._latest_activity_id_by_bike[bid] = bike_activity_id
                continue
            distance_confirmed = bike_latest.get("_distance_source") in (
                "ble_live",
                "gps_track",
            )
            if (
                self._latest_activity_id_by_bike.get(bid) == bike_activity_id
                and distance_confirmed
            ):
                continue
            try:
                details = await self.api.get_activity_detail(bike_activity_id)
                self._latest_activity_details_by_bike[bid] = details
                self._latest_activity_id_by_bike[bid] = bike_activity_id
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "Could not fetch GPS details for bike %s activity %s: %s",
                    bid, bike_activity_id, err,
                )

        if state_changed:
            await self._async_save_state()

        # Per-bike Data Act endpoints (Bike Pass + Digital Service Book).
        # Fetched every poll; each call is isolated so a failure never fails
        # the whole update (mirrors the GPS-details handling above).
        # Prune stale entries so a removed bike's data does not linger forever.
        current_ids = {b.get("id") for b in bikes if b.get("id")}
        for stale in [k for k in self._bike_pass if k not in current_ids]:
            del self._bike_pass[stale]
        for stale in [k for k in self._service_records if k not in current_ids]:
            del self._service_records[stale]
        for bike in bikes:
            bike_id = bike.get("id")
            if not bike_id:
                continue
            try:
                self._bike_pass[bike_id] = await self.api.get_bike_pass(bike_id)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Could not fetch bike pass for %s: %s", bike_id, err)
            try:
                self._service_records[bike_id] = await self.api.get_service_records(bike_id)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Could not fetch service records for %s: %s", bike_id, err)

        return {
            "bikes": bikes,
            "latest_activity": latest_activity,
            "all_activities": self._all_activities,
            "latest_activity_details": self._latest_activity_details,
            "latest_activity_details_by_bike": self._latest_activity_details_by_bike,
            "activity_consumption": self._activity_consumption,
            "activity_bike": self._activity_bike,
            "maintenance": self._maintenance,
            "service_overrides": self._service_overrides,
            "battery_capacity_wh": self._battery_capacity_wh,
            "range_estimate": range_estimate,
            "energy_window": energy_window,
            "bike_pass": self._bike_pass,
            "service_records": self._service_records,
            "unassigned_activities": self._unassigned_activities,
        }

    async def async_assign_activities(self, mapping: dict[str, str]) -> None:
        """Manually assign one or more activities to a bike (issue #47 follow-up).

        Called by the options flow's activity-assignment wizard. Merged keys
        always take precedence over the odometer heuristic (see
        merge_manual_overrides) and persist across restarts.
        """
        self._manual_activity_bike.update(mapping)
        await self._async_save_state()
        await self.async_request_refresh()

    # -- Service & maintenance --

    def _bike_state(self, bike_id: str) -> dict[str, Any]:
        """Return the maintenance bag for a bike, creating it if missing."""
        if bike_id not in self._maintenance:
            self._maintenance[bike_id] = {"items": [], "service_warned": {}}
        bs = self._maintenance[bike_id]
        bs.setdefault("items", [])
        bs.setdefault("service_warned", {})
        return bs

    def _bike_current_odometer(self, bike: dict[str, Any]) -> float | None:
        """Best-known current odometer in metres (combining profile + latest activity)."""
        drive = bike.get("driveUnit") or {}
        profile_odo = drive.get("odometer")
        bike_id = bike.get("id")
        latest_end_odo = None
        for activity in self._all_activities:
            if self._activity_bike.get(activity.get("id")) != bike_id:
                continue
            start = activity.get("startOdometer")
            dist = activity.get("distance")
            if isinstance(start, (int, float)) and isinstance(dist, (int, float)):
                end = start + dist
                if latest_end_odo is None or end > latest_end_odo:
                    latest_end_odo = end
        if profile_odo is None:
            return latest_end_odo
        if latest_end_odo is None:
            return float(profile_odo)
        return max(float(profile_odo), float(latest_end_odo))

    def _bike_latest_activity(
        self, bike_id: str, fallback_all: bool = False
    ) -> dict[str, Any] | None:
        """This bike's own newest activity (self._all_activities is sorted
        newest-first, so the first match is it). Mirrors compute_range_estimate's
        fallback_all semantics: an unmapped activity counts as this bike's own
        only for single-bike accounts where attribution is empty.
        """
        for activity in self._all_activities:
            aid = activity.get("id")
            if not aid:
                continue
            mapped = self._activity_bike.get(aid)
            if mapped != bike_id and not (mapped is None and fallback_all):
                continue
            return activity
        return None

    def _check_service_and_maintenance(self, bikes: list[dict[str, Any]]) -> bool:
        """Fire events for service-due / overdue and per-bike maintenance items.

        Returns True when persistent state changed.
        """
        changed = False
        now = dt_util.utcnow()

        for bike in bikes:
            bike_id = bike.get("id")
            if not bike_id:
                continue
            bs = self._bike_state(bike_id)
            current_odo = self._bike_current_odometer(bike)

            # Effective service-due values: user override first, Bosch as fallback
            ov = self._bike_override(bike_id)
            bosch_service = bike.get("serviceDue") or {}
            service_warned = bs["service_warned"]

            service_date = ov["date"] or bosch_service.get("date")
            if service_date:
                try:
                    due = dt_util.parse_datetime(service_date) or dt_util.parse_datetime(service_date + "T00:00:00")
                except (TypeError, ValueError):
                    due = None
                if due:
                    if due.tzinfo is None:
                        due = due.replace(tzinfo=timezone.utc)
                    delta_days = (due - now).total_seconds() / 86400
                    if delta_days < 0 and not service_warned.get("date_overdue"):
                        self.hass.bus.async_fire(EVENT_SERVICE_OVERDUE, {
                            "bike_id": bike_id,
                            "kind": "date",
                            "due_date": service_date,
                            "days_overdue": int(-delta_days),
                        })
                        service_warned["date_overdue"] = True
                        changed = True
                    elif 0 <= delta_days <= SERVICE_WARN_DAYS and not service_warned.get("date_due_soon"):
                        self.hass.bus.async_fire(EVENT_SERVICE_DUE_SOON, {
                            "bike_id": bike_id,
                            "kind": "date",
                            "due_date": service_date,
                            "days_remaining": int(delta_days),
                        })
                        service_warned["date_due_soon"] = True
                        changed = True
                    elif delta_days > SERVICE_WARN_DAYS:
                        # Reset flags so next time a new service window opens, events re-fire
                        if service_warned.get("date_due_soon") or service_warned.get("date_overdue"):
                            service_warned["date_due_soon"] = False
                            service_warned["date_overdue"] = False
                            changed = True

            # Override odometer in km → metres for the comparison; Bosch fallback in metres
            ov_km = ov["odometer_km"]
            if ov_km is not None:
                service_odo = float(ov_km) * 1000.0
            else:
                service_odo = bosch_service.get("odometer")
            if isinstance(service_odo, (int, float)) and current_odo is not None:
                remaining_m = float(service_odo) - current_odo
                remaining_km = remaining_m / 1000.0
                if remaining_m < 0 and not service_warned.get("km_overdue"):
                    self.hass.bus.async_fire(EVENT_SERVICE_OVERDUE, {
                        "bike_id": bike_id,
                        "kind": "odometer",
                        "service_odometer_km": float(service_odo) / 1000,
                        "current_odometer_km": current_odo / 1000,
                        "km_overdue": -remaining_km,
                    })
                    service_warned["km_overdue"] = True
                    changed = True
                elif 0 <= remaining_km <= SERVICE_WARN_KM and not service_warned.get("km_due_soon"):
                    self.hass.bus.async_fire(EVENT_SERVICE_DUE_SOON, {
                        "bike_id": bike_id,
                        "kind": "odometer",
                        "service_odometer_km": float(service_odo) / 1000,
                        "current_odometer_km": current_odo / 1000,
                        "km_remaining": remaining_km,
                    })
                    service_warned["km_due_soon"] = True
                    changed = True
                elif remaining_km > SERVICE_WARN_KM:
                    if service_warned.get("km_due_soon") or service_warned.get("km_overdue"):
                        service_warned["km_due_soon"] = False
                        service_warned["km_overdue"] = False
                        changed = True

            # Custom maintenance items
            for item in bs["items"]:
                fire_due, fire_overdue = self._evaluate_maintenance_item(item, current_odo, now)
                if fire_overdue:
                    item["warned_overdue"] = True
                    item["warned_due_soon"] = True
                    self.hass.bus.async_fire(EVENT_MAINTENANCE_OVERDUE, {
                        "bike_id": bike_id,
                        "item_id": item["id"],
                        "name": item.get("name", ""),
                        "remaining_km": item.get("_remaining_km"),
                        "remaining_days": item.get("_remaining_days"),
                    })
                    changed = True
                elif fire_due:
                    item["warned_due_soon"] = True
                    self.hass.bus.async_fire(EVENT_MAINTENANCE_DUE_SOON, {
                        "bike_id": bike_id,
                        "item_id": item["id"],
                        "name": item.get("name", ""),
                        "remaining_km": item.get("_remaining_km"),
                        "remaining_days": item.get("_remaining_days"),
                    })
                    changed = True

        return changed

    def _evaluate_maintenance_item(
        self,
        item: dict[str, Any],
        current_odo: float | None,
        now: datetime,
    ) -> tuple[bool, bool]:
        """Compute remaining km/days; decide whether due-soon / overdue events should fire.

        Mutates ``item`` to attach ``_remaining_km`` and ``_remaining_days`` attributes.
        Returns (fire_due_soon, fire_overdue) — only True if not already warned.
        """
        interval_km = item.get("interval_km")
        interval_days = item.get("interval_days")
        last_done_odo = item.get("last_done_odometer")
        last_done_at = item.get("last_done_at")

        remaining_km: float | None = None
        if isinstance(interval_km, (int, float)) and isinstance(last_done_odo, (int, float)) and current_odo is not None:
            remaining_km = (float(last_done_odo) + float(interval_km) * 1000) - current_odo

        remaining_days: float | None = None
        if isinstance(interval_days, (int, float)) and isinstance(last_done_at, str):
            try:
                done = dt_util.parse_datetime(last_done_at)
            except (TypeError, ValueError):
                done = None
            if done:
                if done.tzinfo is None:
                    done = done.replace(tzinfo=timezone.utc)
                due_date = done + timedelta(days=float(interval_days))
                remaining_days = (due_date - now).total_seconds() / 86400

        item["_remaining_km"] = remaining_km / 1000 if remaining_km is not None else None
        item["_remaining_days"] = remaining_days

        # Decide event firing — only one path triggers per evaluation cycle
        is_overdue = (
            (remaining_km is not None and remaining_km < 0)
            or (remaining_days is not None and remaining_days < 0)
        )
        is_due_soon = (
            (remaining_km is not None and 0 <= remaining_km / 1000 <= SERVICE_WARN_KM)
            or (remaining_days is not None and 0 <= remaining_days <= SERVICE_WARN_DAYS)
        )

        # Reset flags when both metrics are out of warning range
        if not is_overdue and not is_due_soon:
            item["warned_due_soon"] = False
            item["warned_overdue"] = False

        fire_overdue = is_overdue and not item.get("warned_overdue")
        fire_due_soon = is_due_soon and not is_overdue and not item.get("warned_due_soon")
        return fire_due_soon, fire_overdue

    # -- Maintenance public API (used by service handlers) --

    def add_maintenance_item(
        self,
        bike_id: str,
        name: str,
        interval_km: float | None,
        interval_days: float | None,
        current_odometer_m: float | None = None,
    ) -> str:
        """Create a new maintenance item and return its ID."""
        bs = self._bike_state(bike_id)
        item_id = uuid.uuid4().hex[:12]
        bs["items"].append({
            "id": item_id,
            "name": name,
            "interval_km": float(interval_km) if interval_km is not None else None,
            "interval_days": float(interval_days) if interval_days is not None else None,
            "last_done_at": dt_util.utcnow().isoformat(),
            "last_done_odometer": float(current_odometer_m) if current_odometer_m is not None else None,
            "warned_due_soon": False,
            "warned_overdue": False,
        })
        self.hass.async_create_task(self._async_save_state())
        return item_id

    def complete_maintenance_item(
        self,
        bike_id: str,
        item_id: str,
        current_odometer_m: float | None = None,
    ) -> bool:
        bs = self._bike_state(bike_id)
        for item in bs["items"]:
            if item["id"] == item_id:
                item["last_done_at"] = dt_util.utcnow().isoformat()
                if current_odometer_m is not None:
                    item["last_done_odometer"] = float(current_odometer_m)
                item["warned_due_soon"] = False
                item["warned_overdue"] = False
                self.hass.async_create_task(self._async_save_state())
                return True
        return False

    def update_maintenance_item(
        self,
        bike_id: str,
        item_id: str,
        name: str | None = None,
        interval_km: float | None = None,
        interval_days: float | None = None,
        last_done_at: str | None = None,
        last_done_odometer: float | None = None,
        clear_interval_km: bool = False,
        clear_interval_days: bool = False,
    ) -> bool:
        """Update fields of an existing item. Returns True if found+updated.

        ``clear_interval_km`` / ``clear_interval_days`` flags explicitly null
        out the respective field, used by the editor when the user switches
        an item from km-trigger to date-trigger (or vice versa). Passing
        ``None`` for a field means "leave unchanged"; passing a value
        replaces it; passing the clear flag sets it to None.

        ``last_done_at`` ISO-8601 string, ``last_done_odometer`` meters - both
        optional, used by the editor when the user wants to record "I did
        this maintenance last week at km X" instead of "I just did this".
        """
        bs = self._bike_state(bike_id)
        for item in bs["items"]:
            if item["id"] != item_id:
                continue
            if name is not None:
                item["name"] = name
            if interval_km is not None:
                item["interval_km"] = float(interval_km)
            elif clear_interval_km:
                item["interval_km"] = None
            if interval_days is not None:
                item["interval_days"] = float(interval_days)
            elif clear_interval_days:
                item["interval_days"] = None
            if last_done_at is not None:
                item["last_done_at"] = last_done_at
            if last_done_odometer is not None:
                item["last_done_odometer"] = float(last_done_odometer)
                # Reset the warned-flags so an item that was overdue does
                # not stay flagged after the user records a fresh service.
                item["warned_due_soon"] = False
                item["warned_overdue"] = False
            self.hass.async_create_task(self._async_save_state())
            return True
        return False

    def remove_maintenance_item(self, bike_id: str, item_id: str) -> bool:
        bs = self._bike_state(bike_id)
        before = len(bs["items"])
        bs["items"] = [i for i in bs["items"] if i["id"] != item_id]
        if len(bs["items"]) != before:
            self.hass.async_create_task(self._async_save_state())
            return True
        return False
