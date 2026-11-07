"""Bosch eBike API client."""

from __future__ import annotations

import hashlib
import base64
import secrets
import logging
import time
import urllib.parse
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    AUTH_URL,
    TOKEN_URL,
    BIKES_ENDPOINT,
    ACTIVITIES_ENDPOINT,
    BIKE_PASS_ENDPOINT,
    SERVICE_RECORDS_ENDPOINT,
    SERVICE_RECORDS_V2_ENDPOINT,
    SYSTEM_SMART,
    SYSTEM_BES2,
    BES2_KC_IDP_HINT,
    BES2_BIKES_ENDPOINT,
    BES2_ACTIVITIES_ENDPOINT,
    BES2_STATISTICS_ENDPOINT,
    CAPACITY_TESTERS_PATH_CANDIDATES,
    BATTERIES_PATH_CANDIDATES,
    DRIVE_UNITS_PATH_CANDIDATES,
)

from .oauth_error import rejection_reason
from .token_info import token_scope

_LOGGER = logging.getLogger(__name__)


class BoschEBikeAPI:
    """Async client for the Bosch eBike Data Act API."""

    # Single shared timeout for every Bosch cloud request. Without it a hung
    # connection would block the coordinator poll indefinitely.
    _TIMEOUT = aiohttp.ClientTimeout(total=30)

    # Once the Digital Service Book had to be read from v1, v2 is only tried
    # again this often (see get_service_records).
    _SERVICE_BOOK_V2_RECHECK_INTERVAL_S = 24 * 60 * 60

    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: str,
        access_token: str | None = None,
        refresh_token: str | None = None,
        system: str = SYSTEM_SMART,
    ) -> None:
        self._session = session
        self._client_id = client_id
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._system = system
        self._code_verifier: str | None = None
        # See CAPACITY_TESTERS_PATH_CANDIDATES in const.py for why this
        # exists: {discovery_key: winning_path_template}. In-memory only —
        # rebuilt (and re-probed) on every HA/integration restart, which is
        # cheap and also gives a wrong first guess a chance to self-correct
        # if a later release reorders the candidate list.
        self._discovered_paths: dict[str, str] = {}
        self._unresolved_since: dict[str, float] = {}
        # Which Digital Service Book API version answered last ("v2" or "v1",
        # None before the first request) and when v2 last failed, so that a v1
        # verdict does not cost a failing v2 request on every poll. In memory
        # only, like the discovery cache above.
        self._service_book_version: str | None = None
        self._service_book_v2_failed_at: float = 0.0

    # -- PKCE helpers --

    def generate_pkce(self) -> tuple[str, str]:
        """Generate PKCE code_verifier and code_challenge. Returns (verifier, challenge)."""
        verifier = secrets.token_urlsafe(32)
        self._code_verifier = verifier
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return verifier, challenge

    def get_authorize_url(self, redirect_uri: str) -> str:
        """Build the OAuth2 authorization URL with PKCE."""
        _, challenge = self.generate_pkce()
        params = (
            f"?client_id={self._client_id}"
            f"&response_type=code"
            f"&redirect_uri={redirect_uri}"
            f"&code_challenge={challenge}"
            f"&code_challenge_method=S256"
            f"&scope=openid"
        )
        if self._system == SYSTEM_BES2:
            params += f"&kc_idp_hint={BES2_KC_IDP_HINT}"
        return f"{AUTH_URL}{params}"

    # -- Token management --

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange authorization code for tokens (with PKCE)."""
        data = {
            "grant_type": "authorization_code",
            "client_id": self._client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": self._code_verifier,
        }
        async with self._session.post(TOKEN_URL, data=data, timeout=self._TIMEOUT) as resp:
            resp.raise_for_status()
            tokens = await resp.json()
        self._access_token = tokens["access_token"]
        self._refresh_token = tokens.get("refresh_token")
        return tokens

    async def exchange_code_no_pkce(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange authorization code for tokens (without PKCE)."""
        data = {
            "grant_type": "authorization_code",
            "client_id": self._client_id,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        async with self._session.post(TOKEN_URL, data=data, timeout=self._TIMEOUT) as resp:
            resp.raise_for_status()
            tokens = await resp.json()
        self._access_token = tokens["access_token"]
        self._refresh_token = tokens.get("refresh_token")
        return tokens

    async def refresh_access_token(self) -> dict[str, Any]:
        """Refresh the access token using the refresh token."""
        if not self._refresh_token:
            raise AuthError("No refresh token available")
        data = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "refresh_token": self._refresh_token,
        }
        async with self._session.post(TOKEN_URL, data=data, timeout=self._TIMEOUT) as resp:
            if resp.status >= 400:
                # A refused login is not a failed request: the stored refresh
                # token, or the Client-ID itself, is no longer valid and only a
                # new sign-in helps. As an AuthError this starts the
                # re-authentication; as the ClientResponseError that
                # raise_for_status() makes of it, the setup retried forever
                # without ever asking (issue #98). Read the reply before
                # raising; failing to read it must not hide the status.
                try:
                    body = (await resp.text())[:500]
                except Exception:  # noqa: BLE001
                    body = ""
                reason = rejection_reason(resp.status, body)
                if reason is not None:
                    raise AuthError(f"Bosch rejected the refresh token ({reason})")
            resp.raise_for_status()
            tokens = await resp.json()
        self._access_token = tokens["access_token"]
        if "refresh_token" in tokens:
            self._refresh_token = tokens["refresh_token"]
        return tokens

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    @property
    def service_book_version(self) -> str | None:
        """Digital Service Book API version that answered last, for the diagnostics."""
        return self._service_book_version

    @property
    def access_token_scope(self) -> str | None:
        """Scope claim of the current access token, for log lines only."""
        return token_scope(self._access_token)

    def set_tokens(self, access_token: str, refresh_token: str | None) -> None:
        """Set tokens from stored config entry."""
        self._access_token = access_token
        self._refresh_token = refresh_token

    # -- API calls --

    async def _get(self, path: str, retry_on_401: bool = True) -> Any:
        """GET request with Bearer auth and auto-refresh on 401."""
        if not self._access_token:
            raise AuthError("Not authenticated")
        headers = {"Authorization": f"Bearer {self._access_token}"}
        url = f"{API_BASE_URL}{path}"
        async with self._session.get(url, headers=headers, timeout=self._TIMEOUT) as resp:
            if resp.status == 401 and retry_on_401:
                _LOGGER.debug("401 received, refreshing token")
                await self.refresh_access_token()
                return await self._get(path, retry_on_401=False)
            if resp.status >= 400:
                # raise_for_status() keeps only the status line, but Bosch's
                # own reply is what tells an outage from a revoked consent or
                # a moved endpoint (issue #95 was a bare "404 Not Found" on
                # the activity list). Keep a short piece of it on the
                # exception so the coordinator can put it in the log. Read it
                # here, before raising; a failure to read must never replace
                # the status error itself.
                try:
                    body = (await resp.text())[:300]
                except Exception:  # noqa: BLE001
                    body = ""
                try:
                    resp.raise_for_status()
                except aiohttp.ClientResponseError as err:
                    err.body = body
                    raise
            return await resp.json()

    _PATH_UNRESOLVED = "__unresolved__"
    # A 404 on every candidate is ambiguous: it could mean "wrong path
    # prefix" (needs a restart to ever recover, since the guess itself is
    # what's wrong) or "correct path, but no dealer has connected a
    # diagnostic tool to THIS battery/drive-unit yet" (the documented common
    # case for this data, which resolves itself once a dealer visit
    # happens - no restart should be required for that). Since the two
    # cannot be told apart from a 404 alone, "unresolved" is re-checked
    # periodically instead of being cached forever, so real data that shows
    # up later is still picked up without the user needing to restart HA.
    _UNRESOLVED_RECHECK_INTERVAL_S = 24 * 60 * 60

    async def _get_with_path_discovery(
        self, discovery_key: str, candidates: list[str], query: str
    ) -> Any | None:
        """GET one of several candidate paths, caching whichever one works.

        See CAPACITY_TESTERS_PATH_CANDIDATES in const.py for the reasoning.
        Tries the previously-discovered path first (if any), then falls back
        through the remaining candidates in order. A 404 moves on to the
        next candidate; any other error (network failure, 401 already
        retried by _get, 5xx, ...) propagates so the caller's normal
        per-poll error handling applies instead of being mistaken for "wrong
        path". Returns None once every candidate has 404'd, without raising —
        this endpoint family is optional (dealer-visit-gated) data, so a
        confirmed absence is not an error condition. Re-probes from scratch
        after _UNRESOLVED_RECHECK_INTERVAL_S instead of giving up forever
        (see that constant's docstring for why).
        """
        cached = self._discovered_paths.get(discovery_key)
        if cached == self._PATH_UNRESOLVED:
            since = self._unresolved_since.get(discovery_key, 0.0)
            if time.monotonic() - since < self._UNRESOLVED_RECHECK_INTERVAL_S:
                return None
            cached = None  # cooldown elapsed - fall through and re-probe
        ordered = (
            [cached] + [c for c in candidates if c != cached] if cached else candidates
        )
        for template in ordered:
            path = f"{template}?{query}" if query else template
            try:
                data = await self._get(path)
            except aiohttp.ClientResponseError as err:
                if err.status == 404:
                    continue
                raise
            self._discovered_paths[discovery_key] = template
            self._unresolved_since.pop(discovery_key, None)
            return data
        self._discovered_paths[discovery_key] = self._PATH_UNRESOLVED
        self._unresolved_since[discovery_key] = time.monotonic()
        _LOGGER.debug(
            "Bosch eBike: none of the %d candidate paths for '%s' resolved "
            "(all 404); this Diagnosis Field Data endpoint may be genuinely "
            "unavailable for this account or its real path is unconfirmed. "
            "Will retry after %d hours.",
            len(candidates), discovery_key,
            self._UNRESOLVED_RECHECK_INTERVAL_S // 3600,
        )
        return None

    @staticmethod
    def _part_serial_query(part_number: str | None, serial_number: str | None) -> str | None:
        """Query string identifying a component by part+serial, or None if either is missing.

        Diagnosis Field Data API endpoints identify the battery/drive-unit by
        part number + serial number, not bikeId (unlike every other
        per-bike endpoint in this client).
        """
        if not part_number or not serial_number:
            return None
        return (
            f"partNumber={urllib.parse.quote(str(part_number), safe='')}"
            f"&serialNumber={urllib.parse.quote(str(serial_number), safe='')}"
        )

    async def get_capacity_tester(
        self, system: str, part_number: str | None, serial_number: str | None
    ) -> dict[str, Any] | None:
        """Latest Bosch Capacity Tester measurement(s) for one battery.

        Documented for both Smart System and eBike System 2 (Generation 3
        and 2 respectively). None if part/serial are missing or no candidate
        path resolves.
        """
        query = self._part_serial_query(part_number, serial_number)
        if query is None:
            return None
        candidates = CAPACITY_TESTERS_PATH_CANDIDATES.get(system)
        if not candidates:
            return None
        return await self._get_with_path_discovery(
            f"capacity_testers_{system}", candidates, query
        )

    async def get_battery_field_data(
        self, part_number: str | None, serial_number: str | None
    ) -> dict[str, Any] | None:
        """Dealer DiagnosticTool 3 battery field data. eBike System 2 only."""
        query = self._part_serial_query(part_number, serial_number)
        if query is None:
            return None
        return await self._get_with_path_discovery(
            "batteries", BATTERIES_PATH_CANDIDATES, query
        )

    async def get_drive_unit_field_data(
        self, part_number: str | None, serial_number: str | None
    ) -> dict[str, Any] | None:
        """Dealer DiagnosticTool 3 drive-unit field data. eBike System 2 only."""
        query = self._part_serial_query(part_number, serial_number)
        if query is None:
            return None
        return await self._get_with_path_discovery(
            "drive_units", DRIVE_UNITS_PATH_CANDIDATES, query
        )

    async def get_bikes(self) -> list[dict[str, Any]]:
        """Fetch all bike profiles."""
        data = await self._get(BIKES_ENDPOINT)
        return data.get("bikes", [])

    async def get_latest_activity(self) -> dict[str, Any] | None:
        """Fetch the most recent activity summary."""
        data = await self._get(f"{ACTIVITIES_ENDPOINT}?limit=1&sort=-startTime")
        summaries = data.get("activitySummaries", [])
        return summaries[0] if summaries else None

    async def get_recent_activities(self, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch the most recent *limit* activity summaries in one request.

        Used for polling instead of get_latest_activity()'s bare limit=1
        fetch: Bosch's own sort=-startTime ordering has been observed to
        keep reporting a stale activity as "latest" for some accounts
        (issue #57), which a single-item fetch has no way to detect or
        correct. Callers cross-check the returned items by their own
        startTime rather than trusting item 0, the same defensive approach
        already used for the BES2 endpoint's unreliable ordering.
        """
        data = await self._get(
            f"{ACTIVITIES_ENDPOINT}?limit={limit}&sort=-startTime"
        )
        return data.get("activitySummaries", [])

    async def get_all_activities(self, page_size: int = 50) -> list[dict[str, Any]]:
        """Fetch all activity summaries with pagination."""
        all_activities: list[dict[str, Any]] = []
        offset = 0

        while True:
            data = await self._get(
                f"{ACTIVITIES_ENDPOINT}?limit={page_size}&offset={offset}&sort=-startTime"
            )
            summaries = data.get("activitySummaries", [])
            if not summaries:
                break

            all_activities.extend(summaries)

            total = data.get("pagination", {}).get("total", 0)
            offset += page_size
            _LOGGER.debug(
                "Bosch eBike: Fetched %d/%d activities", len(all_activities), total
            )

            if offset >= total:
                break

        _LOGGER.info("Bosch eBike: Imported %d activities total", len(all_activities))
        return all_activities

    async def get_activity_detail(self, activity_id: str) -> dict[str, Any]:
        """Fetch full activity detail including GPS track points."""
        data = await self._get(f"{ACTIVITIES_ENDPOINT}/{activity_id}/details")
        return data

    async def get_bike_pass(self, bike_id: str) -> dict[str, Any]:
        """Bike Pass (frame number + theft report logs) for one bike."""
        return await self._get(f"{BIKE_PASS_ENDPOINT}?bikeId={bike_id}")

    async def get_service_records(self, bike_id: str) -> dict[str, Any]:
        """Digital Service Book records (battery measurements, customer reports) for one bike.

        Bosch published v2 of this API (spec 2.0.3). It is a superset of v1,
        nothing was removed or renamed, and v1 still answered when v2 came
        out; nothing says for how long. So v2 is tried first, and v1 is the
        fallback whenever v2 does not deliver: any HTTP error, an unreadable
        body, and also an answer without a single record. The last one
        matters because the spec says an empty list is what v2 returns when
        it has no data for a bike, which is also what a v2 that was not filled
        for this account yet would say, while v1 may still hold the records.
        A v2 that is not live, wants something v1 does not, or is empty must
        never cost the data v1 still delivers. If v1 has nothing either, its
        (empty) answer is the answer.

        The version that worked is remembered. Once v1 had to be used, v2 is
        only tried again every _SERVICE_BOOK_V2_RECHECK_INTERVAL_S, so there
        is no extra request per poll, and a v2 that starts delivering later
        is still picked up.

        An auth error is not a version problem and propagates; so does a
        network failure, which would hit v1 just the same.
        """
        query = f"?bikeId={bike_id}"
        now = time.monotonic()
        if (
            self._service_book_version != "v1"
            or now - self._service_book_v2_failed_at
            >= self._SERVICE_BOOK_V2_RECHECK_INTERVAL_S
        ):
            try:
                data = await self._get(f"{SERVICE_RECORDS_V2_ENDPOINT}{query}")
            except AuthError:
                raise
            except (aiohttp.ClientResponseError, ValueError) as err:
                reason = f"{type(err).__name__}: {err}"
            else:
                if isinstance(data, dict) and data.get("serviceRecords"):
                    if self._service_book_version != "v2":
                        _LOGGER.info("Bosch eBike: the Digital Service Book is read from API v2")
                    self._service_book_version = "v2"
                    return data
                reason = "no records"
            if self._service_book_version != "v1":
                _LOGGER.info(
                    "Bosch eBike: Digital Service Book API v2 did not deliver (%s); "
                    "using v1 and trying v2 again in %d hours",
                    reason, self._SERVICE_BOOK_V2_RECHECK_INTERVAL_S // 3600,
                )
            self._service_book_version = "v1"
            self._service_book_v2_failed_at = now
        return await self._get(f"{SERVICE_RECORDS_ENDPOINT}{query}")

    # -- eBike System 2 (BES2) API calls --

    async def get_bikes_bes2(
        self, serial: str | None = None, part: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetch BES2 bike profiles, optionally filtered by drive-unit serial/part."""
        path = BES2_BIKES_ENDPOINT
        params = []
        if serial:
            params.append(f"serialNumber={urllib.parse.quote(serial, safe='')}")
        if part:
            params.append(f"partNumber={urllib.parse.quote(part, safe='')}")
        if params:
            path = f"{path}?{'&'.join(params)}"
        data = await self._get(path)
        return data.get("bikes", []) if isinstance(data, dict) else []

    async def get_activities_bes2(
        self, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Fetch BES2 activities with pagination."""
        data = await self._get(f"{BES2_ACTIVITIES_ENDPOINT}?limit={limit}&offset={offset}")
        return data.get("activities", []) if isinstance(data, dict) else []

    async def get_activity_detail_bes2(self, activity_id) -> dict[str, Any]:
        """Fetch full BES2 activity detail."""
        return await self._get(f"{BES2_ACTIVITIES_ENDPOINT}/{activity_id}")

    async def get_statistics_bes2(self) -> dict[str, Any]:
        """Fetch BES2 lifetime/aggregate statistics (totals, monthly)."""
        data = await self._get(BES2_STATISTICS_ENDPOINT)
        return data if isinstance(data, dict) else {}

    async def get_all_activity_details(
        self, activity_ids: list[str], progress_callback: Any = None
    ) -> list[dict[str, Any]]:
        """Fetch full details for all activities (including GPS)."""
        details: list[dict[str, Any]] = []
        total = len(activity_ids)
        for idx, aid in enumerate(activity_ids):
            try:
                detail = await self.get_activity_detail(aid)
                details.append(detail)
                _LOGGER.debug("Bosch eBike: Fetched detail %d/%d: %s", idx + 1, total, aid)
                if progress_callback:
                    progress_callback(idx + 1, total)
            except Exception as err:
                _LOGGER.warning("Bosch eBike: Failed to fetch activity %s: %s", aid, err)
        _LOGGER.info("Bosch eBike: Fetched %d/%d activity details", len(details), total)
        return details


class AuthError(Exception):
    """Authentication error."""
