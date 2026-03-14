"""Bosch eBike API client."""

from __future__ import annotations

import hashlib
import base64
import secrets
import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL, AUTH_URL, TOKEN_URL, BIKES_ENDPOINT, ACTIVITIES_ENDPOINT

_LOGGER = logging.getLogger(__name__)


class BoschEBikeAPI:
    """Async client for the Bosch eBike Data Act API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: str,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        self._session = session
        self._client_id = client_id
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._code_verifier: str | None = None

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
        async with self._session.post(TOKEN_URL, data=data) as resp:
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
        async with self._session.post(TOKEN_URL, data=data) as resp:
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
        async with self._session.post(TOKEN_URL, data=data) as resp:
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
        async with self._session.get(url, headers=headers) as resp:
            if resp.status == 401 and retry_on_401:
                _LOGGER.debug("401 received, refreshing token")
                await self.refresh_access_token()
                return await self._get(path, retry_on_401=False)
            resp.raise_for_status()
            return await resp.json()

    async def get_bikes(self) -> list[dict[str, Any]]:
        """Fetch all bike profiles."""
        data = await self._get(BIKES_ENDPOINT)
        return data.get("bikes", [])

    async def get_latest_activity(self) -> dict[str, Any] | None:
        """Fetch the most recent activity summary."""
        data = await self._get(f"{ACTIVITIES_ENDPOINT}?limit=1&sort=-startTime")
        summaries = data.get("activitySummaries", [])
        return summaries[0] if summaries else None

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


class AuthError(Exception):
    """Authentication error."""
