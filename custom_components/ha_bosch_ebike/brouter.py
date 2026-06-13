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

    raw = base_url or DEFAULT_BASE_URL
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https"):
        raise BRouterRequestError(f"unsupported BRouter URL scheme: {parts.scheme!r}")
    if not parts.netloc:
        raise BRouterRequestError("BRouter URL has no host")
    # Check the raw string too: urlsplit maps a bare trailing "?" / "#" to an
    # *empty* query/fragment, which would slip past a parts-only check.
    if parts.query or parts.fragment or "?" in raw or "#" in raw:
        raise BRouterRequestError("BRouter URL must not contain query or fragment")

    # Reconstruct deterministically from parsed components so nothing can be
    # smuggled past the path (a path prefix for reverse-proxy setups is fine).
    base = f"{parts.scheme}://{parts.netloc}{parts.path.rstrip('/')}"

    return (
        f"{base}/brouter?lonlats={'|'.join(pairs)}"
        f"&profile={profile}&alternativeidx=0&format=geojson"
    )
