"""Tell the user when Bosch names no bike for the account (issue #100).

With a Bosch login that works but a data sharing that is not active (yet),
Bosch answers with an empty bike list, or with a 403 on it. Nothing is wrong
with the login and Home Assistant reports no error, so the integration set up
fine and then showed no bike and no ride at all; it looked exactly like a
region block. A repair issue now says what is missing, and it goes away by
itself as soon as Bosch lists a bike.

No Home Assistant imports: the registry calls are passed in, so the decision
stays testable with plain fakes (tests/test_no_bikes.py).
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Iterable

_LOGGER = logging.getLogger(__name__)

# Key of the issue text in strings.json and translations/<language>.json.
TRANSLATION_KEY = "no_bikes"


def issue_id(entry_id: str) -> str:
    """The repair issue of one config entry (every account has its own)."""
    return f"{TRANSLATION_KEY}_{entry_id}"


def bikes_missing(bikes: Iterable[Any] | None) -> bool:
    """True when Bosch named no usable bike: no answer, no list, or no id."""
    return not any(isinstance(b, dict) and b.get("id") for b in (bikes or []))


def apply(
    bikes: Iterable[Any] | None,
    *,
    create: Callable[[], None],
    delete: Callable[[], None],
) -> None:
    """Raise the issue while no bike is named, clear it once one shows up.

    Never raises: a repair hint must not fail the coordinator update.
    """
    try:
        (create if bikes_missing(bikes) else delete)()
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Bosch eBike: could not update the 'no bikes' repair issue")
