"""Tell a token endpoint that refused the login from one that merely failed."""

from __future__ import annotations

import json

# RFC 6749, section 5.2: the error codes that say "this refresh token or this
# client is not valid (any more)", as opposed to a malformed request.
_REJECTED_ERRORS = ("invalid_grant", "invalid_client", "unauthorized_client")


def rejection_reason(status: int, body: str | None) -> str | None:
    """Why the token endpoint rejected a refresh token or client, None if it did not.

    Only a rejection of the login itself may send the user to the
    re-authentication, because only a new sign-in helps then (issue #98):
    401 always, 400 only with one of the OAuth error codes for an invalid
    grant or client. Another 400, a 429, a server error or an answer that
    cannot be read is a failure that the next poll may well survive, and
    asking the user to sign in again for it would be a false alarm.

    The reason is meant for the log and the re-authentication message: the
    OAuth error code, followed by Bosch's own description when it sent one.
    """
    error = description = None
    try:
        payload = json.loads(body) if body else None
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        if isinstance(payload.get("error"), str):
            error = payload["error"]
        if isinstance(payload.get("error_description"), str):
            description = payload["error_description"]
    if status != 401 and not (status == 400 and error in _REJECTED_ERRORS):
        return None
    reason = error or f"HTTP {status}"
    return f"{reason}: {description[:120]}" if description else reason
