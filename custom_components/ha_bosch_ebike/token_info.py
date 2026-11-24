"""Read the scope of an access token for the log, without verifying anything."""

from __future__ import annotations

import base64
import json


def _claims(token: str | None) -> dict | None:
    """The decoded middle part of a JWT, or None. Never raises."""
    try:
        payload = str(token).split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:  # noqa: BLE001
        return None
    return claims if isinstance(claims, dict) else None


def token_type(token: str | None) -> str | None:
    """Keycloak's "typ" of a refresh token: "Offline", "Refresh", "other" or None.

    Tells from the diagnostics whether Bosch granted offline_access (COBI):
    an offline token reads "Offline". Only these two names are passed on, so
    nothing else from the token can reach the diagnostics file.
    """
    claims = _claims(token)
    if claims is None or "typ" not in claims:
        return None
    return claims["typ"] if claims["typ"] in ("Offline", "Refresh") else "other"


def token_scope(token: str | None) -> str | None:
    """The "scope" claim of a JWT access token, or None if there is none.

    Only the middle part of a JWT is read. It is base64 encoded, not secret,
    and nothing here trusts it: the scope goes into the line that explains why
    Bosch refuses a request (issue #95), never into a decision. Whatever is
    wrong with the token, the answer is None rather than an error, because
    this runs while an error is already being reported.
    """
    try:
        payload = str(token).split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:  # noqa: BLE001
        return None
    scope = claims.get("scope") if isinstance(claims, dict) else None
    return scope if isinstance(scope, str) and scope else None
