"""Give a shared bike's second account its own entities.

Bosch's "Share eBike" lets a main user invite other riders, each with their
own SingleKey ID. Rides belong to the account whose phone was connected, so
every account has its own ride history - but all of them report the same bike
ID. Every entity's unique_id is built from that bike ID, so the second config
entry's entities collided with the first entry's and Home Assistant dropped
them all.

No Home Assistant imports: entities and registry entries are duck-typed so the
logic stays testable with plain fakes (tests/test_shared_bike.py).
"""
from __future__ import annotations

import logging
from typing import Any, Iterable

_LOGGER = logging.getLogger(__name__)


def unique_ids_of_other_entries(
    registry_entries: Iterable[Any], *, entry_id: str, domain: str
) -> set[str]:
    """Return this integration's unique_ids registered to other config entries.

    The entity registry is what a colliding unique_id collides with, so it is
    the one reliable witness of who got there first. Device ownership is not:
    since Home Assistant 2026.11 a device belongs to a single config entry, so
    both accounts can own a device for the same bike.
    """
    return {
        e.unique_id
        for e in registry_entries
        if e.platform == domain and e.config_entry_id != entry_id
    }


def scope_shared_bike_entities(
    entities: list[Any],
    taken_unique_ids: set[str],
    *,
    entry_id: str,
    account_label: str,
    domain: str,
) -> list[Any]:
    """Re-scope entities of bikes whose unique_ids another config entry holds.

    Decided per bike, not per unique_id: a sensor added by an update is not
    registered by anyone yet, and both entries set up concurrently, so an
    exact match would hand its plain ID to whichever entry is faster.
    """
    for entity in entities:
        bike_ids = [
            t[1] for t in entity._attr_device_info["identifiers"] if _is_own(t, domain)
        ]
        if not any(
            uid.startswith(f"{bike_id}_")
            for bike_id in bike_ids
            for uid in taken_unique_ids
        ):
            continue
        entity._attr_unique_id = f"{entry_id}_{entity._attr_unique_id}"
        device_info = entity._attr_device_info
        device_info["identifiers"] = {
            (domain, f"{t[1]}_{entry_id}") if _is_own(t, domain) else t
            for t in device_info["identifiers"]
        }
        if device_info.get("name"):
            device_info["name"] = f"{device_info['name']} ({account_label})"
    return entities


def _is_own(identifier: tuple, domain: str) -> bool:
    """True for this domain's (domain, id) pairs.

    Identifiers are not guaranteed to be pairs, so never unpack blindly - one
    three-part identifier would otherwise break every platform's setup.
    """
    return len(identifier) == 2 and identifier[0] == domain


def scope_for_entry(hass: Any, entry: Any, entities: list[Any]) -> list[Any]:
    """Apply scope_shared_bike_entities() against the live entity registry.

    Called by every platform right before async_add_entities(). The entry
    whose entities already hold the plain unique_ids (the main user's, set up
    first) keeps them and their history; any other entry reporting the same
    bike gets entry-scoped unique_ids and its own device.
    """
    from homeassistant.helpers import entity_registry as er

    from .const import DOMAIN

    try:
        taken = unique_ids_of_other_entries(
            er.async_get(hass).entities.values(),
            entry_id=entry.entry_id,
            domain=DOMAIN,
        )
        return scope_shared_bike_entities(
            entities,
            taken,
            entry_id=entry.entry_id,
            account_label=entry.title or entry.entry_id[:8],
            domain=DOMAIN,
        )
    except Exception:  # noqa: BLE001 - never let this take down a platform
        # Worst case the second account's entities collide again, as they did
        # before this module existed; the main user's entities must load.
        _LOGGER.exception("Bosch eBike: shared-bike scoping failed, skipping it")
        return entities
