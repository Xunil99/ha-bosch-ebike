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
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_BATTERY_CAPACITY_WH,
    SERVICE_WARN_DAYS,
    SERVICE_WARN_KM,
    EVENT_SERVICE_DUE_SOON,
    EVENT_SERVICE_OVERDUE,
    EVENT_MAINTENANCE_DUE_SOON,
    EVENT_MAINTENANCE_OVERDUE,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY_SUFFIX = "consumption_state"


class BoschEBikeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch Bosch eBike data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, api: BoschEBikeAPI) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self._initial_import_done = False
        self._all_activities: list[dict[str, Any]] = []
        self._latest_activity_details: list[dict[str, Any]] | None = None
        self._latest_activity_id: str | None = None
        # Battery consumption tracking (Wh delta between polls)
        self._prev_delivered_wh: float | None = None
        self._prev_activity_ids: set[str] = set()
        self._battery_capacity_wh: float = DEFAULT_BATTERY_CAPACITY_WH
        self._activity_consumption: dict[str, dict[str, Any]] = {}
        # Per-activity bike attribution (activity_id -> bike_id) for multi-bike accounts
        self._activity_bike: dict[str, str] = {}
        # Per-activity track cache (activity_id -> [{lat,lon,...}]) for heatmap card
        self._all_tracks_cache: dict[str, list[dict[str, Any]]] = {}
        # Maintenance state per bike
        # bike_id -> {"items": [{id,name,interval_km,interval_days,last_done_at,last_done_odometer,warned}], "service_warned": {...}}
        self._maintenance: dict[str, dict[str, Any]] = {}
        # Persistent storage for consumption state (survives HA restarts)
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_{STORAGE_KEY_SUFFIX}"
        )
        self._state_loaded = False

    async def async_load_persisted_state(self) -> None:
        """Restore battery consumption state from disk (once at startup)."""
        if self._state_loaded:
            return
        data = await self._store.async_load()
        if isinstance(data, dict):
            prev_wh = data.get("prev_delivered_wh")
            if isinstance(prev_wh, (int, float)):
                self._prev_delivered_wh = float(prev_wh)
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
            maintenance = data.get("maintenance")
            if isinstance(maintenance, dict):
                self._maintenance = {
                    bid: bike_data for bid, bike_data in maintenance.items()
                    if isinstance(bid, str) and isinstance(bike_data, dict)
                }
            capacity = data.get("battery_capacity_wh")
            if isinstance(capacity, (int, float)) and capacity > 0:
                self._battery_capacity_wh = float(capacity)
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
                "prev_delivered_wh": self._prev_delivered_wh,
                "prev_activity_ids": sorted(self._prev_activity_ids),
                "activity_consumption": self._activity_consumption,
                "activity_bike": self._activity_bike,
                "maintenance": self._maintenance,
                "battery_capacity_wh": self._battery_capacity_wh,
            }
        )

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

    def set_battery_capacity(self, capacity_wh: float) -> None:
        """Set the battery capacity (configurable by user)."""
        self._battery_capacity_wh = capacity_wh
        self.hass.async_create_task(self._async_save_state())

    def _track_battery_consumption(self, bikes: list[dict[str, Any]]) -> bool:
        """Track deliveredWhOverLifetime changes and allocate to activities.

        Returns True if persistent state changed and should be saved.
        """
        current_wh: float | None = None
        for bike in bikes:
            for battery in bike.get("batteries", []) or []:
                wh = battery.get("deliveredWhOverLifetime")
                if wh is not None:
                    current_wh = wh
                    break
            if current_wh is not None:
                break

        if current_wh is None:
            return False

        current_ids = {a.get("id") for a in self._all_activities if a.get("id")}
        state_changed = False

        if self._prev_delivered_wh is not None:
            delta_wh = current_wh - self._prev_delivered_wh
            if delta_wh > 0:
                new_ids = current_ids - self._prev_activity_ids
                new_activities = [
                    a for a in self._all_activities if a.get("id") in new_ids
                ]

                if new_activities:
                    total_distance = sum(
                        a.get("distance", 0) or 0 for a in new_activities
                    )

                    for activity in new_activities:
                        aid = activity.get("id")
                        if not aid:
                            continue
                        dist = activity.get("distance", 0) or 0
                        if total_distance > 0 and len(new_activities) > 1:
                            share = delta_wh * (dist / total_distance)
                            is_exact = False
                        else:
                            share = delta_wh
                            is_exact = len(new_activities) == 1

                        self._activity_consumption[aid] = {
                            "consumed_wh": round(share, 1),
                            "capacity_wh": self._battery_capacity_wh,
                            "is_exact": is_exact,
                            "percentage": round(
                                (share / self._battery_capacity_wh) * 100, 1
                            ) if self._battery_capacity_wh > 0 else 0,
                        }
                        state_changed = True
                        _LOGGER.info(
                            "Battery consumption for activity %s: %.1f Wh (%.1f%%)",
                            aid, share,
                            (share / self._battery_capacity_wh) * 100
                            if self._battery_capacity_wh > 0 else 0,
                        )

        # Basislinie aktualisieren
        if self._prev_delivered_wh != current_wh:
            self._prev_delivered_wh = current_wh
            state_changed = True
        if self._prev_activity_ids != current_ids:
            self._prev_activity_ids = current_ids
            state_changed = True

        return state_changed

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch bikes and activities from Bosch API."""
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
                        # Same activity, update in place
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

        # Persist updated tokens back to config entry
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
            if activity_id and activity_id != self._latest_activity_id:
                try:
                    details = await self.api.get_activity_detail(activity_id)
                    self._latest_activity_details = details
                    self._latest_activity_id = activity_id
                except Exception:
                    pass  # GPS details are optional, don't fail the whole update

        # Restore persisted consumption state on first run
        await self.async_load_persisted_state()

        # Battery consumption tracking via Wh delta
        state_changed = self._track_battery_consumption(bikes)

        # Bike attribution via odometer-matching (only meaningful for multi-bike accounts;
        # for single-bike accounts every activity is attributed to that bike)
        new_attribution = self.attribute_activities_to_bikes(bikes, self._all_activities)
        if new_attribution != self._activity_bike:
            self._activity_bike = new_attribution
            state_changed = True

        # Service & maintenance reminders
        if self._check_service_and_maintenance(bikes):
            state_changed = True

        if state_changed:
            await self._async_save_state()

        return {
            "bikes": bikes,
            "latest_activity": latest_activity,
            "all_activities": self._all_activities,
            "latest_activity_details": self._latest_activity_details,
            "activity_consumption": self._activity_consumption,
            "activity_bike": self._activity_bike,
            "maintenance": self._maintenance,
            "battery_capacity_wh": self._battery_capacity_wh,
        }

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

            # Built-in Bosch service info
            service = bike.get("serviceDue") or {}
            service_warned = bs["service_warned"]

            service_date = service.get("date")
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

            service_odo = service.get("odometer")
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

    def remove_maintenance_item(self, bike_id: str, item_id: str) -> bool:
        bs = self._bike_state(bike_id)
        before = len(bs["items"])
        bs["items"] = [i for i in bs["items"] if i["id"] != item_id]
        if len(bs["items"]) != before:
            self.hass.async_create_task(self._async_save_state())
            return True
        return False
