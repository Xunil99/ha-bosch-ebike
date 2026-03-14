"""DataUpdateCoordinator for Bosch eBike."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import BoschEBikeAPI, AuthError
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


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

        return {
            "bikes": bikes,
            "latest_activity": latest_activity,
            "all_activities": self._all_activities,
        }
