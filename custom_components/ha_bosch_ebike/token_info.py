"""Read the scope of an access token for the log, without verifying anything."""

from __future__ import annotations

import base64
import json


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
