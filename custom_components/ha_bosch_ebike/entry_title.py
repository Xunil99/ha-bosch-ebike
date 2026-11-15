"""The default title of a new config entry.

Every entry used to be created with the title "Bosch eBike". With two accounts
on one bike (shared_bike.py) the second account's device is named after its
entry, and the card's account picker lists the accounts by title, so two
accounts read the same. A new entry takes the first free title instead. It is
only a default: the user can rename the entry in Home Assistant, and that name
then shows up in the device name and in the picker.

No Home Assistant imports, so it is testable with plain lists
(tests/test_entry_title.py).
"""
from __future__ import annotations

from typing import Iterable


def unique_title(base: str, taken: Iterable[str | None]) -> str:
    """The first of base, "base 2", "base 3", ... that no existing entry uses.

    Counting the entries would hand out a title twice after one was deleted
    (entries "Bosch eBike" and "Bosch eBike 2", the first deleted: the next
    would be "Bosch eBike 2" again), so the numbers are searched, not counted.
    """
    used = {title for title in taken if title}
    if base not in used:
        return base
    number = 2
    while f"{base} {number}" in used:
        number += 1
    return f"{base} {number}"
