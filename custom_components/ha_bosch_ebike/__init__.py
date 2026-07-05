"""Bosch eBike Smart System integration for Home Assistant."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid

import aiohttp
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store

from .api import BoschEBikeAPI
from .brouter import (
    ALLOWED_PROFILES,
    MAX_POINTS,
    MIN_POINTS,
    BRouterRequestError,
    build_brouter_url,
)
from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_SYSTEM,
    DEFAULT_SYSTEM,
    CONF_BES2_SERIAL,
    CONF_BES2_PART,
)
from .coordinator import BoschEBikeCoordinator
from .profile_extra import bike_label as _bike_label

_LOGGER = logging.getLogger(__name__)

# This integration is configured exclusively via the UI (config entries),
# never via YAML — declare that so hassfest is satisfied.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.DATE,
    Platform.DEVICE_TRACKER,
]

CARD_URL = "/ha_bosch_ebike/bosch-ebike-map-card.js"


async def _async_register_card_resource(hass: HomeAssistant) -> None:
    """Register the card as a Lovelace resource - safely and idempotently.

    Runs only after Home Assistant has fully started (via async_at_started), so
    the Lovelace resource collection is already loaded from storage. As extra
    safeguards we force a load, refuse to write unless the load is confirmed,
    and only ever APPEND our own entry - we never delete anything.

    This is the careful counterpart to the data-loss bug fixed in 1.16.26:
    earlier code called async_create_item() before the collection was loaded,
    so the save persisted ONLY our entry and wiped every other Lovelace
    resource. By guaranteeing the existing entries are loaded first, the save
    always contains the full set plus ours.
    """
    try:
        lovelace_data = hass.data.get("lovelace")
        resources = getattr(lovelace_data, "resources", None)
        if resources is None and isinstance(lovelace_data, dict):
            resources = lovelace_data.get("resources")

        # Storage mode only. YAML-mode resources are read-only -> manual setup.
        if not isinstance(resources, ResourceStorageCollection):
            return

        # Force a load of all existing resources from storage, then refuse to
        # touch anything unless the load is actually confirmed. This is the
        # crucial guard: never write to an unloaded (apparently empty) collection.
        await resources.async_get_info()
        if not getattr(resources, "loaded", False):
            _LOGGER.debug(
                "Lovelace resources not loaded; skipping auto-register of %s",
                CARD_URL,
            )
            return

        if any(item.get("url") == CARD_URL for item in resources.async_items()):
            return  # already present, nothing to do

        await resources.async_create_item(
            {"res_type": "module", "url": CARD_URL}
        )
        _LOGGER.info("Registered Lovelace resource: %s", CARD_URL)
    except Exception:  # noqa: BLE001
        _LOGGER.debug(
            "Could not auto-register Lovelace resource; add it manually "
            "(JavaScript Module): %s",
            CARD_URL,
        )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Bosch eBike component."""
    # Register websocket commands once
    websocket_api.async_register_command(hass, ws_list_instances)
    websocket_api.async_register_command(hass, ws_list_activities)
    websocket_api.async_register_command(hass, ws_get_track)
    websocket_api.async_register_command(hass, ws_get_all_tracks)
    websocket_api.async_register_command(hass, ws_list_maintenance)
    websocket_api.async_register_command(hass, ws_add_maintenance)
    websocket_api.async_register_command(hass, ws_update_maintenance)
    websocket_api.async_register_command(hass, ws_complete_maintenance)
    websocket_api.async_register_command(hass, ws_remove_maintenance)
    websocket_api.async_register_command(hass, ws_get_card_settings)
    websocket_api.async_register_command(hass, ws_set_card_settings)
    websocket_api.async_register_command(hass, ws_overpass_pois)
    websocket_api.async_register_command(hass, ws_plan_route)
    websocket_api.async_register_command(hass, ws_list_routes)
    websocket_api.async_register_command(hass, ws_save_route)
    websocket_api.async_register_command(hass, ws_delete_route)

    # Singleton Store für gemeinsame Darstellungs-Settings, die sowohl
    # die 3D-Karte als auch die 2D-Karte (Chase-Cam-Overlay + Editor)
    # verwenden. Ein Speicherort, beide Cards lesen + schreiben gegen
    # diesen Store. Erspart YAML-Drift zwischen mehreren Card-Instanzen
    # und macht 'Konfig einmal ändern, überall sichtbar' möglich.
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "card_settings_store" not in domain_data:
        store = Store(hass, 1, f"{DOMAIN}_card_settings")
        loaded = await store.async_load() or {}
        domain_data["card_settings_store"] = store
        domain_data["card_settings"] = loaded if isinstance(loaded, dict) else {}

    # Singleton Store für gespeicherte Routenplaner-Routen. Gleiche
    # Mechanik wie die Card-Settings: einmal laden, in hass.data halten,
    # WS-Handler lesen/schreiben gegen diese Liste und persistieren über
    # den Store. Liegt im Backend, damit gespeicherte Routen auf allen
    # Geräten verfügbar sind (wie die Wartungsliste).
    if "saved_routes_store" not in domain_data:
        routes_store = Store(hass, 1, f"{DOMAIN}_saved_routes")
        loaded_routes = await routes_store.async_load() or []
        domain_data["saved_routes_store"] = routes_store
        domain_data["saved_routes"] = (
            loaded_routes if isinstance(loaded_routes, list) else []
        )

    _register_services(hass)

    # Register static path for the Lovelace card
    card_dir = os.path.join(os.path.dirname(__file__), "www")
    if os.path.isdir(card_dir):
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                CARD_URL,
                os.path.join(card_dir, "bosch-ebike-map-card.js"),
                cache_headers=False,
            )
        ])

        # Auto-register the card as a Lovelace resource, but ONLY after Home
        # Assistant has fully started, so the resource collection is loaded and
        # we can safely append without wiping existing entries. See the
        # _async_register_card_resource docstring for the data-loss history.
        async_at_started(hass, _async_register_card_resource)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bosch eBike from a config entry."""
    session = async_get_clientsession(hass)
    system = entry.data.get(CONF_SYSTEM, DEFAULT_SYSTEM)
    bes2_serial = entry.data.get(CONF_BES2_SERIAL)
    bes2_part = entry.data.get(CONF_BES2_PART)
    api = BoschEBikeAPI(
        session=session,
        client_id=entry.data[CONF_CLIENT_ID],
        access_token=entry.data.get("access_token"),
        refresh_token=entry.data.get("refresh_token"),
        system=system,
    )

    coordinator = BoschEBikeCoordinator(
        hass, api, system=system, bes2_serial=bes2_serial, bes2_part=bes2_part
    )
    coordinator.config_entry = entry

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # React to OptionsFlow changes (live BLE sensor wiring): reload the
    # entry so entities depending on options (e.g. the current-range
    # sensor) are created/removed immediately. The coordinator — and with
    # it the enrichment cache — is rebuilt as part of the reload.
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates by reloading the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


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
        # Current capacity acts as the source of truth — older persisted
        # consumption entries may carry a stale capacity_wh / percentage.
        current_capacity = float(
            coordinator.data.get("battery_capacity_wh", 0) or 0
        ) if coordinator.data else 0
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
                cons = dict(activity_consumption[aid])
                # Always recompute against the current capacity so a later
                # capacity change doesn't leave stale percentages on the card
                if current_capacity > 0:
                    consumed = float(cons.get("consumed_wh", 0) or 0)
                    cons["capacity_wh"] = current_capacity
                    cons["percentage"] = round(consumed / current_capacity * 100, 1)
                entry["consumption"] = cons
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
        detail = await coordinator.fetch_track_detail(activity_id)
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
        vol.Optional("date_from"): str,   # YYYY-MM-DD inclusive
        vol.Optional("date_to"): str,     # YYYY-MM-DD inclusive
    }
)
@websocket_api.async_response
async def ws_get_all_tracks(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return GPS tracks for all (cached + on-demand fetched) activities.

    Heavy on first run (one API call per uncached activity, with concurrency
    limit). Subsequent calls return instantly from the in-memory cache.

    Filtering: pass either ``max_age_days`` (relative window) OR
    ``date_from`` / ``date_to`` (absolute range, ISO YYYY-MM-DD,
    inclusive on both ends). If both are passed, the explicit date
    range wins.
    """
    import asyncio
    from datetime import datetime, timedelta, timezone

    requested_entry = msg.get("config_entry_id")
    max_age_days = msg.get("max_age_days")
    date_from_raw = msg.get("date_from")
    date_to_raw = msg.get("date_to")

    # Parse explicit date range first. A user-supplied range overrides
    # max_age_days so the UI can offer both modes without juggling
    # which one to send.
    range_from: datetime | None = None
    range_to: datetime | None = None

    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None

    range_from = _parse_date(date_from_raw)
    parsed_to = _parse_date(date_to_raw)
    if parsed_to is not None:
        # Inclusive: extend to end of the day so an activity that
        # started at 22:00 on date_to is still included.
        range_to = parsed_to + timedelta(days=1)

    cutoff: datetime | None = None
    if range_from is None and range_to is None and isinstance(max_age_days, int) and max_age_days > 0:
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
        if cutoff is not None or range_from is not None or range_to is not None:
            try:
                start = activity.get("startTime")
                if start:
                    start_dt = start if isinstance(start, datetime) else datetime.fromisoformat(start.replace("Z", "+00:00"))
                    if cutoff is not None and start_dt < cutoff:
                        return
                    if range_from is not None and start_dt < range_from:
                        return
                    if range_to is not None and start_dt >= range_to:
                        return
            except (TypeError, ValueError):
                return

        cache = coord._all_tracks_cache
        points = cache.get(aid)
        if points is None:
            async with semaphore:
                try:
                    detail = await coord.fetch_track_detail(aid)
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
            # current_odo (meters) für die On-the-Fly-Neuberechnung der
            # Rest-km / Rest-Tage. Sonst gelten _remaining_* nur so
            # lange wie sie zuletzt vom Coordinator-Refresh aktualisiert
            # wurden - nach add/complete/update sehen wir bis zum
            # nächsten Refresh veraltete Werte.
            #
            # WICHTIG: _compute_maintenance_remaining erwartet DREI
            # Argumente (item, current_odo, now). Ohne now wirft sie
            # TypeError - die ich vorher mit except: pass verschluckt
            # habe, sodass _remaining_* immer None blieb und das
            # Dashboard alle Items als "nichts fällig" filterte.
            from homeassistant.util import dt as dt_util
            now = dt_util.utcnow()
            # Smart odometer reader (same as the coordinator's periodic
            # refresh path uses): combines Bosch profile odometer with
            # the derived end-odometer from the most recent activity.
            # Falls back to whichever is available when the other is
            # None - critical for users whose Bosch API does not
            # consistently return driveUnit.odometer.
            current_odo = coord._bike_current_odometer(bike)
            items = []
            for item in bs.get("items", []):
                try:
                    # Method is _evaluate_maintenance_item. I had it
                    # wrong as _compute_maintenance_remaining in
                    # v1.16.8/v1.16.9 - the resulting AttributeError
                    # was swallowed by the broad except and the items
                    # came back with stale _remaining_* values, so
                    # the dashboard's done button looked like it
                    # never reset the counter.
                    coord._evaluate_maintenance_item(item, current_odo, now)
                except Exception as e:  # noqa: BLE001
                    _LOGGER.warning(
                        "evaluate_maintenance_item failed for %s: %s",
                        item.get("id"), e,
                    )
                items.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "interval_km": item.get("interval_km"),
                    "interval_days": item.get("interval_days"),
                    "last_done_at": item.get("last_done_at"),
                    "last_done_odometer": item.get("last_done_odometer"),
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


def _get_current_odo(coord, bike_id: str) -> float | None:
    """Helper: read current odometer (meters) from a coordinator's bike.

    Uses ``_bike_current_odometer`` (smart reader: max of Bosch profile
    odometer and the derived end-odometer of the most recent activity)
    instead of the raw ``driveUnit.odometer`` field. The raw field is
    sometimes None when the Bosch API returns the bike without a fresh
    profile reading; the activity-derived value is then the only
    accurate signal. Without this fallback, complete_maintenance on a
    km-based item would skip the ``last_done_odometer`` update and the
    counter would stay stuck at the old value.
    """
    for bike in (coord.data.get("bikes", []) if coord.data else []):
        if bike.get("id") == bike_id:
            return coord._bike_current_odometer(bike)
    return None


# Frontend-facing CRUD over WebSocket. Mirrors the integration-level
# services but returns useful payloads (created IDs, updated state) so
# the dashboard card can avoid an extra list-roundtrip after every
# mutation. Same per-bike scoping as ws_list_maintenance.
@websocket_api.websocket_command(
    {
        vol.Required("type"): "bosch_ebike/add_maintenance",
        vol.Required("bike_id"): str,
        vol.Required("name"): str,
        vol.Optional("interval_km"): vol.Any(vol.All(vol.Coerce(float), vol.Range(min=0.1)), None),
        vol.Optional("interval_days"): vol.Any(vol.All(vol.Coerce(float), vol.Range(min=0.1)), None),
    }
)
@websocket_api.async_response
async def ws_add_maintenance(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    bike_id = msg["bike_id"]
    interval_km = msg.get("interval_km")
    interval_days = msg.get("interval_days")
    if interval_km is None and interval_days is None:
        connection.send_error(msg["id"], "invalid_format", "Either interval_km or interval_days must be provided")
        return
    coord = _coordinator_for_bike(hass, bike_id)
    if not coord:
        connection.send_error(msg["id"], "not_found", f"Bike {bike_id} not found")
        return
    current_odo = _get_current_odo(coord, bike_id)
    item_id = coord.add_maintenance_item(
        bike_id, msg["name"], interval_km, interval_days, current_odo
    )
    connection.send_result(msg["id"], {"id": item_id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "bosch_ebike/update_maintenance",
        vol.Required("bike_id"): str,
        vol.Required("item_id"): str,
        # All optional fields are loosely typed and validated inside the
        # handler. Strict voluptuous schemas here have repeatedly produced
        # opaque "Unknown error" responses when the JS sent edge values
        # (empty string from a date input that was just cleared, integer
        # 0 from a number input, etc.) - so we coerce + bounds-check in
        # Python instead and return precise error messages to the UI.
        vol.Optional("name"): str,
        vol.Optional("interval_km"): vol.Any(int, float, None),
        vol.Optional("interval_days"): vol.Any(int, float, None),
        vol.Optional("last_done_at"): str,
        vol.Optional("last_done_odometer"): vol.Any(int, float, None),
    }
)
@websocket_api.async_response
async def ws_update_maintenance(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    try:
        bike_id = msg["bike_id"]
        coord = _coordinator_for_bike(hass, bike_id)
        if not coord:
            connection.send_error(msg["id"], "not_found", f"Bike {bike_id} not found")
            return

        # Coerce + validate every field here so a buggy frontend value
        # surfaces as a clear error instead of an "Unknown error" 500.
        kwargs = {}
        if "name" in msg and msg["name"] is not None:
            kwargs["name"] = str(msg["name"])

        # Interval fields: null means "clear it" (used by the type switch);
        # a positive number sets the new interval; missing means "leave it".
        clear_km = "interval_km" in msg and msg["interval_km"] is None
        clear_days = "interval_days" in msg and msg["interval_days"] is None
        if "interval_km" in msg and msg["interval_km"] is not None:
            v = float(msg["interval_km"])
            if v <= 0:
                connection.send_error(msg["id"], "invalid_format", "interval_km must be > 0")
                return
            kwargs["interval_km"] = v
        if "interval_days" in msg and msg["interval_days"] is not None:
            v = float(msg["interval_days"])
            if v <= 0:
                connection.send_error(msg["id"], "invalid_format", "interval_days must be > 0")
                return
            kwargs["interval_days"] = v

        if "last_done_at" in msg and msg["last_done_at"]:
            kwargs["last_done_at"] = str(msg["last_done_at"])
        if "last_done_odometer" in msg and msg["last_done_odometer"] is not None:
            v = float(msg["last_done_odometer"])
            if v < 0:
                connection.send_error(msg["id"], "invalid_format", "last_done_odometer must be >= 0")
                return
            kwargs["last_done_odometer"] = v

        kwargs["clear_interval_km"] = clear_km
        kwargs["clear_interval_days"] = clear_days

        ok = coord.update_maintenance_item(bike_id, msg["item_id"], **kwargs)
        if not ok:
            connection.send_error(msg["id"], "not_found", f"Item {msg['item_id']} not found for bike {bike_id}")
            return
        connection.send_result(msg["id"], {"ok": True})
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("ws_update_maintenance failed: msg=%s", msg)
        connection.send_error(msg["id"], "internal_error", f"{type(err).__name__}: {err}")


@websocket_api.websocket_command(
    {
        vol.Required("type"): "bosch_ebike/complete_maintenance",
        vol.Required("bike_id"): str,
        vol.Required("item_id"): str,
    }
)
@websocket_api.async_response
async def ws_complete_maintenance(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    bike_id = msg["bike_id"]
    item_id = msg["item_id"]
    coord = _coordinator_for_bike(hass, bike_id)
    if not coord:
        connection.send_error(msg["id"], "not_found", f"Bike {bike_id} not found")
        return
    current_odo = _get_current_odo(coord, bike_id)
    if not coord.complete_maintenance_item(bike_id, item_id, current_odo):
        connection.send_error(msg["id"], "not_found", f"Item {item_id} not found for bike {bike_id}")
        return
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "bosch_ebike/remove_maintenance",
        vol.Required("bike_id"): str,
        vol.Required("item_id"): str,
    }
)
@websocket_api.async_response
async def ws_remove_maintenance(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    bike_id = msg["bike_id"]
    coord = _coordinator_for_bike(hass, bike_id)
    if not coord:
        connection.send_error(msg["id"], "not_found", f"Bike {bike_id} not found")
        return
    if not coord.remove_maintenance_item(bike_id, msg["item_id"]):
        connection.send_error(msg["id"], "not_found", f"Item {msg['item_id']} not found for bike {bike_id}")
        return
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {vol.Required("type"): "bosch_ebike/get_card_settings"}
)
@websocket_api.async_response
async def ws_get_card_settings(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return the shared card-settings dict (display + playback options)."""
    settings = hass.data.get(DOMAIN, {}).get("card_settings", {}) or {}
    connection.send_result(msg["id"], {"settings": settings})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "bosch_ebike/set_card_settings",
        # Accept arbitrary key/value pairs. We validate the keys against an
        # allow-list below to keep the storage clean.
        vol.Required("changes"): dict,
    }
)
@websocket_api.async_response
async def ws_set_card_settings(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Merge changes into the shared card-settings store.

    Keys with a value of ``None`` are removed from the store; non-None
    values are upserted. The allow-list constrains which keys may be
    written so a misbehaving card cannot stuff arbitrary junk into the
    file. Editor UIs always send keys from this list anyway.
    """
    allowed = {
        "playback_speed", "animate_seconds",
        "default_pitch", "chase_zoom", "chase_lookahead",
        "smooth_window", "track_smooth_window",
        "terrain_exaggeration", "satellite_tile_url", "satellite_max_zoom",
        "north_up",
        # FPV/action-cam chase mode (issue #43): camera positioned real
        # metres behind + above the bike via MapLibre's
        # calculateCameraOptionsFromTo, instead of the classic pitch/zoom
        # chase camera above. "camera_mode" selects which one applies.
        "camera_mode", "fpv_height_m", "fpv_distance_m", "fpv_lookahead_m",
        # Named, user-saveable combinations of the camera fields above
        # (issue #43). "camera_presets" is a list of
        # {id, name, values: {<subset of the camera keys above>}};
        # "active_camera_preset_id" tracks which one is currently applied
        # (None once the user hand-tweaks a slider away from a saved preset).
        "camera_presets", "active_camera_preset_id",
        "show_date", "show_time", "show_sun",
        "show_speed", "show_distance", "show_elevation",
        "stats_as_chips",
        # Wartungs-Warnschwellen (Dashboard-Card): ab wann ein Item als
        # bald-fällig angezeigt wird. Defaults im Frontend: 500 km / 30 Tage.
        "maint_warn_km", "maint_warn_days",
        # 2D-Card-spezifische gemeinsame Defaults (optional, derzeit
        # nicht aktiv genutzt - Platzhalter für künftige Erweiterungen):
        "default_map_style",
    }
    domain_data = hass.data.setdefault(DOMAIN, {})
    settings = dict(domain_data.get("card_settings", {}) or {})
    changes = msg.get("changes") or {}
    for key, value in changes.items():
        if key not in allowed:
            continue
        if value is None:
            settings.pop(key, None)
        else:
            settings[key] = value
    domain_data["card_settings"] = settings
    store = domain_data.get("card_settings_store")
    if store is not None:
        await store.async_save(settings)
    connection.send_result(msg["id"], {"settings": settings})


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

    async def update_maintenance(call):
        bike_id = call.data["bike_id"]
        item_id = call.data["item_id"]
        coord = _coordinator_for_bike(hass, bike_id)
        if not coord:
            raise vol.Invalid(f"Bike {bike_id} not found in any configured account")
        # Service signature uses None to mean "leave unchanged", matching
        # the coordinator's update_maintenance_item. To clear a field via
        # a service call, omit it from the request - this is consistent
        # with HA service conventions.
        if not coord.update_maintenance_item(
            bike_id,
            item_id,
            name=call.data.get("name"),
            interval_km=call.data.get("interval_km"),
            interval_days=call.data.get("interval_days"),
        ):
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
    hass.services.async_register(
        DOMAIN, "update_maintenance", update_maintenance,
        schema=vol.Schema({
            vol.Required("bike_id"): str,
            vol.Required("item_id"): str,
            vol.Optional("name"): str,
            vol.Optional("interval_km"): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Optional("interval_days"): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
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


# -- Overpass POI proxy --
# overpass-api.de tightened its CORS policy and now rejects browser requests
# from non-whitelisted origins. We fetch POIs server-side instead, where CORS
# does not apply, and pass the result back over the websocket. Multiple
# Overpass mirrors are tried in order with a per-request timeout.

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# Whitelist of selectable POI categories. Only these keys are accepted from the
# frontend; everything else is silently dropped so arbitrary Overpass selectors
# can never be injected through the websocket API.
POI_CATEGORY_SELECTORS = {
    "charging": ['node["amenity"="charging_station"]'],
    "bicycle": ['node["shop"="bicycle"]', 'node["amenity"="bicycle_repair_station"]'],
    "water": ['node["amenity"="drinking_water"]'],
    "toilets": ['node["amenity"="toilets"]'],
    "food": [
        'node["amenity"="restaurant"]',
        'node["amenity"="cafe"]',
        'node["amenity"="biergarten"]',
        'node["amenity"="fast_food"]',
    ],
}
DEFAULT_POI_CATEGORIES = ("charging", "bicycle", "water", "toilets")


@websocket_api.websocket_command(
    {
        vol.Required("type"): "bosch_ebike/get_pois",
        vol.Required("south"): vol.Coerce(float),
        vol.Required("west"): vol.Coerce(float),
        vol.Required("north"): vol.Coerce(float),
        vol.Required("east"): vol.Coerce(float),
        vol.Optional("categories"): [str],
    }
)
@websocket_api.async_response
async def ws_overpass_pois(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Proxy Overpass POI queries through the backend (no CORS).

    Looks up POIs of the requested categories (see POI_CATEGORY_SELECTORS)
    within the supplied bounding box; without a "categories" parameter the
    classic set (charging stations, bike shops/repair stations, drinking water
    and toilets) is used. Each Overpass mirror is tried in turn; the first
    that responds with valid JSON wins. The full element list is passed back
    to the card; client-side proximity filtering keeps the radius user-tunable.
    """
    import asyncio
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    south = float(msg["south"])
    west = float(msg["west"])
    north = float(msg["north"])
    east = float(msg["east"])
    bbox = f"({south},{west},{north},{east})"

    requested = msg.get("categories") or list(DEFAULT_POI_CATEGORIES)
    categories = [key for key in requested if key in POI_CATEGORY_SELECTORS]
    if not categories:
        connection.send_error(
            msg["id"],
            "invalid_request",
            f"No valid POI categories in {requested!r}",
        )
        return

    selectors: list[str] = []
    for key in categories:
        for selector in POI_CATEGORY_SELECTORS[key]:
            if selector not in selectors:
                selectors.append(selector)

    query = (
        "[out:json][timeout:30];"
        "("
        + "".join(f"{selector}{bbox};" for selector in selectors)
        + ");"
        "out body;"
    )

    session = async_get_clientsession(hass)
    elements = None
    last_error: str | None = None

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            async with asyncio.timeout(35):
                async with session.get(
                    endpoint,
                    params={"data": query},
                    headers={"User-Agent": "ha-bosch-ebike-poi/1.0"},
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        last_error = f"{endpoint} HTTP {resp.status}: {body[:200]}"
                        _LOGGER.warning("Overpass %s", last_error)
                        continue
                    data = await resp.json(content_type=None)
                    if isinstance(data, dict) and data.get("remark"):
                        _LOGGER.warning("Overpass remark from %s: %s", endpoint, data["remark"])
                    elements = data.get("elements", []) if isinstance(data, dict) else []
                    break
        except asyncio.TimeoutError:
            last_error = f"{endpoint} timed out"
            _LOGGER.warning("Overpass %s", last_error)
        except Exception as err:  # noqa: BLE001
            last_error = f"{endpoint}: {err}"
            _LOGGER.warning("Overpass error on %s: %s", endpoint, err)

    if elements is None:
        connection.send_error(
            msg["id"],
            "overpass_failed",
            last_error or "All Overpass endpoints failed",
        )
        return

    connection.send_result(msg["id"], {"elements": elements})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "bosch_ebike/plan_route",
        vol.Required("lonlats"): [[vol.Coerce(float)]],
        vol.Required("profile"): str,
        vol.Optional("brouter_url"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def ws_plan_route(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Proxy a routing request to BRouter (CORS-safe, like the POI proxy)."""
    try:
        url = build_brouter_url(msg.get("brouter_url"), msg["lonlats"], msg["profile"])
    except BRouterRequestError as err:
        connection.send_error(msg["id"], "invalid_request", str(err))
        return

    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(30):
            resp = await session.get(url)
            body = await resp.text()
    except (TimeoutError, aiohttp.ClientError) as err:
        connection.send_error(msg["id"], "server_unreachable", f"BRouter not reachable: {err}")
        return

    # BRouter returns errors as plain text with status 200 *or* non-200 —
    # treat any non-JSON body as a routing failure and pass the text through.
    if resp.status != 200 or not body.lstrip().startswith("{"):
        connection.send_error(msg["id"], "routing_failed", body.strip()[:300] or f"HTTP {resp.status}")
        return

    try:
        geojson = json.loads(body)
    except ValueError:
        connection.send_error(msg["id"], "routing_failed", "invalid response from BRouter")
        return

    connection.send_result(msg["id"], {"geojson": geojson})


# Obergrenze für gespeicherte Planer-Routen. Schützt den Store vor
# unbegrenztem Wachstum; Updates bestehender Einträge sind immer erlaubt.
MAX_SAVED_ROUTES = 50


@websocket_api.websocket_command(
    {vol.Required("type"): "bosch_ebike/list_routes"}
)
@websocket_api.async_response
async def ws_list_routes(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return all saved route-planner routes.

    Each entry carries id, name, profile, lonlats, distance_km and the
    "updated" UTC ISO timestamp - everything the planner card needs to
    render the list and to restore a route for further editing.
    """
    routes = hass.data.get(DOMAIN, {}).get("saved_routes", []) or []
    connection.send_result(msg["id"], {"routes": routes})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "bosch_ebike/save_route",
        vol.Required("name"): str,
        vol.Required("profile"): str,
        vol.Required("lonlats"): [[vol.Coerce(float)]],
        # "id" is reserved for the websocket message id, hence "route_id".
        vol.Optional("route_id"): vol.Any(str, None),
        vol.Optional("distance_km"): vol.Any(vol.Coerce(float), None),
    }
)
@websocket_api.async_response
async def ws_save_route(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Save (upsert) a planned route under a user-chosen name.

    Upsert semantics: if "route_id" is given and exists, that entry is
    updated in place (renaming allowed). Otherwise an entry whose name
    matches case-insensitively is overwritten (keeping its id), so saving
    under an existing name never produces duplicates. Only when neither
    matches is a new entry appended - capped at MAX_SAVED_ROUTES.
    """
    from homeassistant.util import dt as dt_util

    name = (msg.get("name") or "").strip()
    if not 1 <= len(name) <= 60:
        connection.send_error(
            msg["id"], "invalid_request", "name must be 1-60 characters"
        )
        return

    profile = msg["profile"]
    if profile not in ALLOWED_PROFILES:
        connection.send_error(
            msg["id"],
            "invalid_request",
            f"profile must be one of {ALLOWED_PROFILES}, got {profile!r}",
        )
        return

    raw_points = msg.get("lonlats") or []
    if not MIN_POINTS <= len(raw_points) <= MAX_POINTS:
        connection.send_error(
            msg["id"],
            "invalid_request",
            f"waypoint count must be {MIN_POINTS}-{MAX_POINTS}, got {len(raw_points)}",
        )
        return
    lonlats: list[list[float]] = []
    for pair in raw_points:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            connection.send_error(
                msg["id"], "invalid_request", "each waypoint must be a [lon, lat] pair"
            )
            return
        lon, lat = float(pair[0]), float(pair[1])
        # NaN/Inf wuerde als nicht-standardkonformes JSON im Store landen und
        # den naechsten async_load scheitern lassen; Bereichscheck weist
        # nicht-endliche Werte automatisch ab (NaN-Vergleiche sind False).
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            connection.send_error(
                msg["id"], "invalid_request", f"waypoint out of range: {pair!r}"
            )
            return
        lonlats.append([lon, lat])

    distance_km = msg.get("distance_km")
    if distance_km is not None:
        distance_km = float(distance_km)
        if not 0.0 <= distance_km <= 100000.0:
            distance_km = None
        else:
            distance_km = round(distance_km, 1)

    domain_data = hass.data.setdefault(DOMAIN, {})
    routes = list(domain_data.get("saved_routes", []) or [])

    entry = {
        "name": name,
        "profile": profile,
        "lonlats": lonlats,
        "distance_km": distance_km,
        "updated": dt_util.utcnow().isoformat(),
    }

    route_id = msg.get("route_id")
    index = None
    if route_id:
        index = next(
            (i for i, r in enumerate(routes) if r.get("id") == route_id), None
        )
    if index is None:
        folded = name.casefold()
        index = next(
            (
                i
                for i, r in enumerate(routes)
                if (r.get("name") or "").strip().casefold() == folded
            ),
            None,
        )

    if index is not None:
        entry["id"] = routes[index].get("id") or uuid.uuid4().hex[:12]
        routes[index] = entry
    else:
        if len(routes) >= MAX_SAVED_ROUTES:
            connection.send_error(
                msg["id"],
                "limit_reached",
                f"Maximum of {MAX_SAVED_ROUTES} saved routes reached - "
                "delete an old route first",
            )
            return
        entry["id"] = uuid.uuid4().hex[:12]
        routes.append(entry)

    domain_data["saved_routes"] = routes
    store = domain_data.get("saved_routes_store")
    if store is not None:
        await store.async_save(routes)
    connection.send_result(msg["id"], {"routes": routes, "saved_id": entry["id"]})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "bosch_ebike/delete_route",
        # "id" is reserved for the websocket message id, hence "route_id".
        vol.Required("route_id"): str,
    }
)
@websocket_api.async_response
async def ws_delete_route(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Delete a saved planner route by id.

    Idempotent: an unknown id simply returns the current list, so a
    double-click in the card can never surface an error.
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    routes = list(domain_data.get("saved_routes", []) or [])
    remaining = [r for r in routes if r.get("id") != msg["route_id"]]
    if len(remaining) != len(routes):
        domain_data["saved_routes"] = remaining
        store = domain_data.get("saved_routes_store")
        if store is not None:
            await store.async_save(remaining)
    connection.send_result(msg["id"], {"routes": remaining})
