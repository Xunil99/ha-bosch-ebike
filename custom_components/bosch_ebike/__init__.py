"""Bosch eBike Smart System integration for Home Assistant."""

from __future__ import annotations

import logging
import os

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BoschEBikeAPI
from .const import DOMAIN, CONF_CLIENT_ID
from .coordinator import BoschEBikeCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BUTTON, Platform.NUMBER]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Bosch eBike component."""
    # Register websocket commands once
    websocket_api.async_register_command(hass, ws_list_instances)
    websocket_api.async_register_command(hass, ws_list_activities)
    websocket_api.async_register_command(hass, ws_get_track)

    # Register static path for the Lovelace card
    card_dir = os.path.join(os.path.dirname(__file__), "www")
    card_url = "/ha_bosch_ebike/bosch-ebike-map-card.js"
    if os.path.isdir(card_dir):
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                card_url,
                os.path.join(card_dir, "bosch-ebike-map-card.js"),
                cache_headers=False,
            )
        ])

        # Auto-register as Lovelace resource so the card works without manual setup
        try:
            if "lovelace" in hass.data:
                resources: ResourceStorageCollection = hass.data["lovelace"]["resources"]
                # Check if already registered
                existing = [
                    r for r in resources.async_items()
                    if r.get("url") == card_url
                ]
                if not existing:
                    await resources.async_create_item(
                        {"res_type": "module", "url": card_url}
                    )
                    _LOGGER.info("Registered Lovelace resource: %s", card_url)
        except Exception:
            _LOGGER.debug(
                "Could not auto-register Lovelace resource. "
                "Add manually: %s (JavaScript Module)", card_url
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bosch eBike from a config entry."""
    session = async_get_clientsession(hass)
    api = BoschEBikeAPI(
        session=session,
        client_id=entry.data[CONF_CLIENT_ID],
        access_token=entry.data.get("access_token"),
        refresh_token=entry.data.get("refresh_token"),
    )

    coordinator = BoschEBikeCoordinator(hass, api)
    coordinator.config_entry = entry

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


# -- Websocket API --


def _all_coordinators(hass: HomeAssistant) -> dict[str, BoschEBikeCoordinator]:
    """Return all active coordinators keyed by config_entry_id."""
    domain_data = hass.data.get(DOMAIN, {})
    return {
        entry_id: c for entry_id, c in domain_data.items()
        if isinstance(c, BoschEBikeCoordinator)
    }


def _get_coordinator(
    hass: HomeAssistant, config_entry_id: str | None = None
) -> BoschEBikeCoordinator | None:
    """Get a specific coordinator by config_entry_id, or the first available one."""
    coords = _all_coordinators(hass)
    if config_entry_id and config_entry_id in coords:
        return coords[config_entry_id]
    return next(iter(coords.values()), None)


def _bike_label(bike: dict) -> str:
    """Build a human-readable label for a bike."""
    drive = bike.get("driveUnit") or {}
    name = drive.get("productName") or bike.get("productName") or "eBike"
    serial = drive.get("serialNumber")
    if serial:
        # Show last 4 chars of serial as disambiguator
        return f"{name} (…{serial[-4:]})"
    return name


def _account_label(coordinator: BoschEBikeCoordinator) -> str:
    """Build a human-readable label for the account/config entry."""
    entry = coordinator.config_entry
    return entry.title or entry.data.get("client_id") or entry.entry_id[:8]


@websocket_api.websocket_command(
    {vol.Required("type"): "bosch_ebike/list_instances"}
)
@websocket_api.async_response
async def ws_list_instances(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return list of all configured Bosch eBike accounts and their bikes."""
    instances = []
    for entry_id, coordinator in _all_coordinators(hass).items():
        bikes = coordinator.data.get("bikes", []) if coordinator.data else []
        bike_list = []
        for bike in bikes:
            bid = bike.get("id")
            if not bid:
                continue
            bike_list.append({"id": bid, "label": _bike_label(bike)})
        instances.append({
            "config_entry_id": entry_id,
            "label": _account_label(coordinator),
            "bikes": bike_list,
        })
    connection.send_result(msg["id"], {"instances": instances})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "bosch_ebike/list_activities",
        vol.Optional("config_entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_list_activities(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return all activity summaries across all (or one specific) accounts.

    Each activity carries `accountId` (= config_entry_id), `accountLabel` and
    `bikeId` (when attribution succeeded), so the card can filter client-side.
    """
    coords = _all_coordinators(hass)
    if not coords:
        connection.send_error(msg["id"], "not_found", "No Bosch eBike integration found")
        return

    requested_entry = msg.get("config_entry_id")
    if requested_entry:
        coords = {k: v for k, v in coords.items() if k == requested_entry}
        if not coords:
            connection.send_error(msg["id"], "not_found", "Requested account not found")
            return

    result = []
    for entry_id, coordinator in coords.items():
        all_activities = coordinator.data.get("all_activities", []) if coordinator.data else []
        activity_consumption = coordinator.data.get("activity_consumption", {}) if coordinator.data else {}
        activity_bike = coordinator.data.get("activity_bike", {}) if coordinator.data else {}
        account_label = _account_label(coordinator)
        for a in all_activities:
            aid = a.get("id")
            entry = {
                "id": aid,
                "title": a.get("title", ""),
                "startTime": a.get("startTime", ""),
                "endTime": a.get("endTime", ""),
                "distance": a.get("distance", 0),
                "durationWithoutStops": a.get("durationWithoutStops", 0),
                "speed": a.get("speed", {}),
                "elevation": a.get("elevation", {}),
                "caloriesBurned": a.get("caloriesBurned"),
                "accountId": entry_id,
                "accountLabel": account_label,
            }
            if aid and aid in activity_bike:
                entry["bikeId"] = activity_bike[aid]
            if aid and aid in activity_consumption:
                entry["consumption"] = activity_consumption[aid]
            result.append(entry)

    connection.send_result(msg["id"], {"activities": result})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "bosch_ebike/get_track",
        vol.Required("activity_id"): str,
        vol.Optional("config_entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_get_track(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return GPS track points for a specific activity."""
    requested_entry = msg.get("config_entry_id")
    coordinator = _get_coordinator(hass, requested_entry)
    if not coordinator:
        # Fall back: search every coordinator for one that knows this activity
        activity_id = msg["activity_id"]
        for c in _all_coordinators(hass).values():
            ids = {a.get("id") for a in (c.data.get("all_activities", []) if c.data else [])}
            if activity_id in ids:
                coordinator = c
                break
    if not coordinator:
        connection.send_error(msg["id"], "not_found", "No Bosch eBike integration found")
        return

    activity_id = msg["activity_id"]
    try:
        detail = await coordinator.api.get_activity_detail(activity_id)
        points = detail.get("activityDetails", [])

        # Filter and slim down the data
        track = []
        for p in points:
            lat = p.get("latitude")
            lon = p.get("longitude")
            if lat is None or lon is None:
                continue
            if lat == 0 and lon == 0:
                continue
            track.append({
                "lat": lat,
                "lon": lon,
                "ele": p.get("altitude"),
                "speed": p.get("speed"),
                "cadence": p.get("cadence"),
                "power": p.get("riderPower"),
                "distance": p.get("distance"),
            })

        connection.send_result(msg["id"], {"track": track})

    except Exception as err:
        _LOGGER.error("Failed to fetch track for %s: %s", activity_id, err)
        connection.send_error(msg["id"], "fetch_error", str(err))
