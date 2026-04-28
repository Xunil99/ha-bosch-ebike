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

PLATFORMS = [Platform.SENSOR, Platform.BUTTON, Platform.NUMBER, Platform.DATE]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Bosch eBike component."""
    # Register websocket commands once
    websocket_api.async_register_command(hass, ws_list_instances)
    websocket_api.async_register_command(hass, ws_list_activities)
    websocket_api.async_register_command(hass, ws_get_track)
    websocket_api.async_register_command(hass, ws_get_all_tracks)
    websocket_api.async_register_command(hass, ws_list_maintenance)

    _register_services(hass)

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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "bosch_ebike/get_all_tracks",
        vol.Optional("config_entry_id"): str,
        vol.Optional("max_age_days"): int,
    }
)
@websocket_api.async_response
async def ws_get_all_tracks(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return GPS tracks for all (cached + on-demand fetched) activities.

    Heavy on first run (one API call per uncached activity, with concurrency
    limit). Subsequent calls return instantly from the in-memory cache.
    """
    import asyncio
    from datetime import datetime, timedelta, timezone

    requested_entry = msg.get("config_entry_id")
    max_age_days = msg.get("max_age_days")
    cutoff: datetime | None = None
    if isinstance(max_age_days, int) and max_age_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    coords = _all_coordinators(hass)
    if requested_entry:
        coords = {k: v for k, v in coords.items() if k == requested_entry}
    if not coords:
        connection.send_error(msg["id"], "not_found", "No Bosch eBike integration found")
        return

    semaphore = asyncio.Semaphore(3)
    results: list[dict] = []

    async def fetch_one(coord, activity, account_id, account_label):
        aid = activity.get("id")
        if not aid:
            return
        if cutoff is not None:
            try:
                start = activity.get("startTime")
                if start:
                    start_dt = start if isinstance(start, datetime) else datetime.fromisoformat(start.replace("Z", "+00:00"))
                    if start_dt < cutoff:
                        return
            except (TypeError, ValueError):
                return

        cache = coord._all_tracks_cache
        points = cache.get(aid)
        if points is None:
            async with semaphore:
                try:
                    detail = await coord.api.get_activity_detail(aid)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Bosch eBike: get_all_tracks: failed to load %s: %s", aid, err)
                    return
                raw = detail.get("activityDetails", [])
                points = []
                for p in raw:
                    lat = p.get("latitude")
                    lon = p.get("longitude")
                    if lat is None or lon is None or (lat == 0 and lon == 0):
                        continue
                    points.append({
                        "lat": lat,
                        "lon": lon,
                        "speed": p.get("speed"),
                    })
                cache[aid] = points

        if not points:
            return
        results.append({
            "activity_id": aid,
            "account_id": account_id,
            "account_label": account_label,
            "bike_id": coord.data.get("activity_bike", {}).get(aid) if coord.data else None,
            "title": activity.get("title", ""),
            "start_time": activity.get("startTime", ""),
            "distance": activity.get("distance", 0),
            "points": points,
        })

    tasks = []
    for entry_id, coord in coords.items():
        if not coord.data:
            continue
        label = _account_label(coord)
        for act in coord.data.get("all_activities", []):
            tasks.append(fetch_one(coord, act, entry_id, label))

    await asyncio.gather(*tasks)

    # Sort by start_time desc
    results.sort(key=lambda r: r.get("start_time") or "", reverse=True)
    connection.send_result(msg["id"], {"tracks": results})


@websocket_api.websocket_command(
    {vol.Required("type"): "bosch_ebike/list_maintenance"}
)
@websocket_api.async_response
async def ws_list_maintenance(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return all maintenance items (built-in service info + custom items) per bike."""
    out = []
    for entry_id, coord in _all_coordinators(hass).items():
        bikes = coord.data.get("bikes", []) if coord.data else []
        maintenance = coord._maintenance
        for bike in bikes:
            bike_id = bike.get("id")
            if not bike_id:
                continue
            bs = maintenance.get(bike_id, {})
            items = []
            for item in bs.get("items", []):
                items.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "interval_km": item.get("interval_km"),
                    "interval_days": item.get("interval_days"),
                    "last_done_at": item.get("last_done_at"),
                    "remaining_km": item.get("_remaining_km"),
                    "remaining_days": item.get("_remaining_days"),
                })
            out.append({
                "config_entry_id": entry_id,
                "bike_id": bike_id,
                "bike_label": _bike_label(bike),
                "items": items,
            })
    connection.send_result(msg["id"], {"bikes": out})


# -- Service handlers --

def _register_services(hass: HomeAssistant) -> None:
    """Register integration-level services for maintenance management."""

    async def add_maintenance(call):
        bike_id = call.data["bike_id"]
        name = call.data["name"]
        interval_km = call.data.get("interval_km")
        interval_days = call.data.get("interval_days")
        if interval_km is None and interval_days is None:
            raise vol.Invalid("Either interval_km or interval_days must be provided")
        # Find the coordinator that owns this bike
        coord = _coordinator_for_bike(hass, bike_id)
        if not coord:
            raise vol.Invalid(f"Bike {bike_id} not found in any configured account")
        current_odo = None
        for bike in (coord.data.get("bikes", []) if coord.data else []):
            if bike.get("id") == bike_id:
                drive = bike.get("driveUnit") or {}
                current_odo = drive.get("odometer")
                break
        coord.add_maintenance_item(bike_id, name, interval_km, interval_days, current_odo)

    async def complete_maintenance(call):
        bike_id = call.data["bike_id"]
        item_id = call.data["item_id"]
        coord = _coordinator_for_bike(hass, bike_id)
        if not coord:
            raise vol.Invalid(f"Bike {bike_id} not found in any configured account")
        current_odo = None
        for bike in (coord.data.get("bikes", []) if coord.data else []):
            if bike.get("id") == bike_id:
                drive = bike.get("driveUnit") or {}
                current_odo = drive.get("odometer")
                break
        if not coord.complete_maintenance_item(bike_id, item_id, current_odo):
            raise vol.Invalid(f"Maintenance item {item_id} not found for bike {bike_id}")

    async def remove_maintenance(call):
        bike_id = call.data["bike_id"]
        item_id = call.data["item_id"]
        coord = _coordinator_for_bike(hass, bike_id)
        if not coord:
            raise vol.Invalid(f"Bike {bike_id} not found in any configured account")
        if not coord.remove_maintenance_item(bike_id, item_id):
            raise vol.Invalid(f"Maintenance item {item_id} not found for bike {bike_id}")

    hass.services.async_register(
        DOMAIN, "add_maintenance", add_maintenance,
        schema=vol.Schema({
            vol.Required("bike_id"): str,
            vol.Required("name"): str,
            vol.Optional("interval_km"): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Optional("interval_days"): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
        })
    )
    hass.services.async_register(
        DOMAIN, "complete_maintenance", complete_maintenance,
        schema=vol.Schema({
            vol.Required("bike_id"): str,
            vol.Required("item_id"): str,
        })
    )
    hass.services.async_register(
        DOMAIN, "remove_maintenance", remove_maintenance,
        schema=vol.Schema({
            vol.Required("bike_id"): str,
            vol.Required("item_id"): str,
        })
    )


def _coordinator_for_bike(hass: HomeAssistant, bike_id: str) -> BoschEBikeCoordinator | None:
    for coord in _all_coordinators(hass).values():
        if not coord.data:
            continue
        for bike in coord.data.get("bikes", []):
            if bike.get("id") == bike_id:
                return coord
    return None
