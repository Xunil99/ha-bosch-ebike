"""DataUpdateCoordinator for Bosch eBike."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import BoschEBikeAPI, AuthError
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, DEFAULT_BATTERY_CAPACITY_WH

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

        if state_changed:
            await self._async_save_state()

        return {
            "bikes": bikes,
            "latest_activity": latest_activity,
            "all_activities": self._all_activities,
            "latest_activity_details": self._latest_activity_details,
            "activity_consumption": self._activity_consumption,
            "activity_bike": self._activity_bike,
            "battery_capacity_wh": self._battery_capacity_wh,
        }
