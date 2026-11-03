"""Find a registered device by its identifier, for one config entry."""

from __future__ import annotations

from typing import Any


def device_for_identifier(
    registry: Any, identifier: tuple[str, str], config_entry_id: str
) -> Any:
    """The device registered under identifier for config_entry_id, or None.

    Home Assistant 2026.8 made device identifiers unique per config entry
    instead of across the whole registry. DeviceRegistry.async_get_device
    cannot say which of several matching devices is meant any more, is
    reported as deprecated and stops working in Home Assistant 2027.8.0
    (issue #96). Its replacement, async_get_device_by_identifier, asks for the
    config entry as well, so every caller has to pass the one it belongs to.

    Releases before 2026.8 do not have the replacement, and hacs.json still
    allows 2024.1.0, so the old call stays as the fallback there. Remove that
    branch once the minimum Home Assistant version reaches 2026.8.0.

    Every device lookup in this integration goes through here, and
    tests/test_device_lookup.py fails on a direct call anywhere else. That
    guard exists because issue #80 converted only one of three call sites.
    """
    if hasattr(registry, "async_get_device_by_identifier"):
        return registry.async_get_device_by_identifier(
            identifier=identifier, config_entry_id=config_entry_id
        )
    return registry.async_get_device(identifiers={identifier})
