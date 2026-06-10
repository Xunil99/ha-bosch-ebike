"""BRouter request building/validation for the route-planner card.

Pure module (no Home Assistant imports) so it is standalone-testable,
mirroring range_estimate.py. The actual HTTP call lives in __init__.py.
"""

from __future__ import annotations

from urllib.parse import urlsplit

DEFAULT_BASE_URL = "https://brouter.de"
ALLOWED_PROFILES = ("trekking", "fastbike", "mtb", "shortest")
MIN_POINTS = 2
MAX_POINTS = 30


class BRouterRequestError(ValueError):
    """Invalid route request (bad profile, URL or waypoints)."""


def build_brouter_url(
    base_url: str | None,
    lonlats: list[list[float]],
    profile: str,
) -> str:
    """Validate inputs and build the BRouter GeoJSON request URL."""
    if profile not in ALLOWED_PROFILES:
        raise BRouterRequestError(f"unsupported profile: {profile}")

    if not MIN_POINTS <= len(lonlats) <= MAX_POINTS:
        raise BRouterRequestError(
            f"waypoint count must be {MIN_POINTS}-{MAX_POINTS}, got {len(lonlats)}"
        )

    pairs: list[str] = []
    for point in lonlats:
        try:
            lon, lat = float(point[0]), float(point[1])
        except (TypeError, ValueError, IndexError) as err:
            raise BRouterRequestError(f"invalid waypoint: {point!r}") from err
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            raise BRouterRequestError(f"waypoint out of range: {point!r}")
        pairs.append(f"{lon},{lat}")

    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    scheme = urlsplit(base).scheme
    if scheme not in ("http", "https"):
        raise BRouterRequestError(f"unsupported BRouter URL scheme: {scheme!r}")

    return (
        f"{base}/brouter?lonlats={'|'.join(pairs)}"
        f"&profile={profile}&alternativeidx=0&format=geojson"
    )
