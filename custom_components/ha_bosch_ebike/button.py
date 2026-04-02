"""Button platform for Bosch eBike — GPS data import."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import BoschEBikeCoordinator

_LOGGER = logging.getLogger(__name__)

# GPS export directory inside HA config
GPS_EXPORT_DIR = "bosch_ebike_gps"


def _activity_to_gpx(
    detail_response: dict[str, Any], title: str = "eBike Ride"
) -> str | None:
    """Convert a Bosch activity detail response to GPX format.

    The API returns: {"activityDetails": [{"latitude", "longitude", "altitude",
    "speed", "cadence", "riderPower", "distance"}, ...]}
    """
    points = detail_response.get("activityDetails", [])
    if not points or not isinstance(points, list):
        return None

    gpx_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="Bosch eBike HA Integration"',
        '  xmlns="http://www.topografix.com/GPX/1/1"',
        '  xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">',
        "  <trk>",
        f"    <name>{title}</name>",
        "    <trkseg>",
    ]

    valid_points = 0
    for point in points:
        lat = point.get("latitude")
        lon = point.get("longitude")
        # Filter invalid (0,0) coordinates (Null Island)
        if lat is None or lon is None:
            continue
        if lat == 0 and lon == 0:
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue

        valid_points += 1
        gpx_lines.append(f'      <trkpt lat="{lat}" lon="{lon}">')

        altitude = point.get("altitude")
        if altitude is not None:
            gpx_lines.append(f"        <ele>{altitude}</ele>")

        # Add speed, cadence, power as extensions
        speed = point.get("speed")
        cadence = point.get("cadence")
        power = point.get("riderPower")
        if any(v is not None for v in (speed, cadence, power)):
            gpx_lines.append("        <extensions>")
            gpx_lines.append("          <gpxtpx:TrackPointExtension>")
            if speed is not None:
                gpx_lines.append(f"            <gpxtpx:speed>{speed}</gpxtpx:speed>")
            if cadence is not None:
                gpx_lines.append(f"            <gpxtpx:cad>{cadence}</gpxtpx:cad>")
            if power is not None:
                gpx_lines.append(f"            <gpxtpx:power>{power}</gpxtpx:power>")
            gpx_lines.append("          </gpxtpx:TrackPointExtension>")
            gpx_lines.append("        </extensions>")

        gpx_lines.append("      </trkpt>")

    if valid_points == 0:
        return None

    gpx_lines.extend([
        "    </trkseg>",
        "  </trk>",
        "</gpx>",
    ])

    return "\n".join(gpx_lines)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bosch eBike buttons from a config entry."""
    coordinator: BoschEBikeCoordinator = hass.data[DOMAIN][entry.entry_id]

    bikes = coordinator.data.get("bikes", [])
    entities: list[ButtonEntity] = []

    for bike in bikes:
        bike_id = bike.get("id", "unknown")
        drive_name = (
            (bike.get("driveUnit") or {}).get("productName") or "eBike"
        )
        entities.append(
            BoschGPSImportButton(coordinator, bike_id, drive_name)
        )
        entities.append(
            BoschGPSImportSingleButton(coordinator, bike_id, drive_name)
        )

    async_add_entities(entities)


class BoschGPSImportButton(ButtonEntity):
    """Button to import GPS data for ALL activities."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:map-marker-path"

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        self._coordinator = coordinator
        self._bike_id = bike_id
        self._attr_unique_id = f"{bike_id}_import_all_gps"
        self._attr_name = "Import All GPS Data"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )
        self._importing = False

    async def async_press(self) -> None:
        """Handle button press — import all GPS data."""
        if self._importing:
            _LOGGER.warning("Bosch eBike: GPS import already in progress")
            return

        self._importing = True
        try:
            all_activities = self._coordinator.data.get("all_activities", [])
            if not all_activities:
                _LOGGER.warning("Bosch eBike: No activities to import GPS data from")
                return

            activity_ids = [a.get("id") for a in all_activities if a.get("id")]
            _LOGGER.info(
                "Bosch eBike: Starting GPS import for %d activities...", len(activity_ids)
            )

            # Create export directory
            export_dir = self.hass.config.path(GPS_EXPORT_DIR)
            os.makedirs(export_dir, exist_ok=True)

            imported = 0
            skipped = 0
            no_gps = 0

            for idx, activity_id in enumerate(activity_ids):
                # Check if already exported
                gpx_path = os.path.join(export_dir, f"{activity_id}.gpx")
                if os.path.exists(gpx_path):
                    skipped += 1
                    continue

                try:
                    detail = await self._coordinator.api.get_activity_detail(activity_id)

                    # Get title from the summary data
                    summary = next(
                        (a for a in all_activities if a.get("id") == activity_id), {}
                    )
                    ride_title = summary.get("title", "eBike Ride")

                    gpx_content = _activity_to_gpx(detail, title=ride_title)
                    if gpx_content:
                        await self.hass.async_add_executor_job(
                            _write_file, gpx_path, gpx_content
                        )
                        imported += 1
                    else:
                        no_gps += 1

                except Exception as err:
                    _LOGGER.warning(
                        "Bosch eBike: Failed to fetch detail for %s: %s", activity_id, err
                    )

                if (idx + 1) % 10 == 0:
                    _LOGGER.info(
                        "Bosch eBike: GPS import progress: %d/%d", idx + 1, len(activity_ids)
                    )

            _LOGGER.info(
                "Bosch eBike: GPS import complete. Imported: %d, Skipped (existing): %d, No GPS data: %d",
                imported,
                skipped,
                no_gps,
            )

            # Create a persistent notification
            self.hass.components.persistent_notification.async_create(
                f"GPS import complete!\n\n"
                f"- **Imported:** {imported} tracks\n"
                f"- **Skipped** (already exists): {skipped}\n"
                f"- **No GPS data:** {no_gps}\n\n"
                f"Files saved to: `{export_dir}`",
                title="Bosch eBike GPS Import",
                notification_id="bosch_ebike_gps_import",
            )

        finally:
            self._importing = False


class BoschGPSImportSingleButton(ButtonEntity):
    """Button to import GPS data for the LATEST activity only."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:map-marker-plus"

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        self._coordinator = coordinator
        self._bike_id = bike_id
        self._attr_unique_id = f"{bike_id}_import_latest_gps"
        self._attr_name = "Import Latest GPS Data"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    async def async_press(self) -> None:
        """Handle button press — import GPS for latest activity."""
        latest = self._coordinator.data.get("latest_activity")
        if not latest:
            _LOGGER.warning("Bosch eBike: No latest activity available")
            return

        activity_id = latest.get("id")
        if not activity_id:
            return

        export_dir = self.hass.config.path(GPS_EXPORT_DIR)
        os.makedirs(export_dir, exist_ok=True)

        try:
            detail = await self._coordinator.api.get_activity_detail(activity_id)

            _LOGGER.warning(
                "Bosch eBike: Latest activity detail keys: %s",
                list(detail.keys()) if isinstance(detail, dict) else type(detail).__name__,
            )

            ride_title = latest.get("title", "eBike Ride")

            _LOGGER.info(
                "Bosch eBike: Activity detail has %d points",
                len(detail.get("activityDetails", [])),
            )

            gpx_content = _activity_to_gpx(detail, title=ride_title)
            if gpx_content:
                gpx_path = os.path.join(export_dir, f"{activity_id}.gpx")
                await self.hass.async_add_executor_job(_write_file, gpx_path, gpx_content)
                _LOGGER.info("Bosch eBike: Exported GPX for '%s'", ride_title)

                self.hass.components.persistent_notification.async_create(
                    f"GPS track for **{ride_title}** exported to `{gpx_path}`",
                    title="Bosch eBike GPS Export",
                    notification_id="bosch_ebike_gps_single",
                )
            else:
                # Save raw JSON for inspection
                json_path = os.path.join(export_dir, f"{activity_id}_detail.json")
                await self.hass.async_add_executor_job(
                    _write_file, json_path, json.dumps(detail, indent=2, default=str)
                )
                _LOGGER.warning(
                    "Bosch eBike: No GPS track found in activity detail. "
                    "Raw data saved to %s for inspection.",
                    json_path,
                )
                self.hass.components.persistent_notification.async_create(
                    f"No GPS track found in activity detail.\n\n"
                    f"Raw JSON saved to `{json_path}` for inspection.",
                    title="Bosch eBike GPS Export",
                    notification_id="bosch_ebike_gps_single",
                )

        except Exception as err:
            _LOGGER.error("Bosch eBike: Failed to fetch activity detail: %s", err)


def _write_file(path: str, content: str) -> None:
    """Write content to file (blocking, called via executor)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
