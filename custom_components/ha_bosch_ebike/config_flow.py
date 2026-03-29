"""Config flow for Bosch eBike integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_CLIENT_ID, REDIRECT_URI, AUTH_URL
from .api import BoschEBikeAPI

_LOGGER = logging.getLogger(__name__)


class BoschEBikeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bosch eBike."""

    VERSION = 1

    def __init__(self) -> None:
        self._client_id: str | None = None
        self._api: BoschEBikeAPI | None = None
        self._authorize_url: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: User enters their Client-ID from Bosch Portal."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._client_id = user_input[CONF_CLIENT_ID].strip()
            session = async_get_clientsession(self.hass)
            self._api = BoschEBikeAPI(session, self._client_id)

            # Build authorize URL without PKCE for manual code flow
            from urllib.parse import urlencode, quote
            params = urlencode({
                "client_id": self._client_id,
                "response_type": "code",
                "redirect_uri": REDIRECT_URI,
                "scope": "openid",
            })
            self._authorize_url = f"{AUTH_URL}?{params}"
            _LOGGER.warning(
                "Bosch eBike: Open this URL in your browser to log in: %s",
                self._authorize_url,
            )
            return await self.async_step_auth_code()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_CLIENT_ID): str,
            }),
            errors=errors,
        )

    async def async_step_auth_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: User opens login URL in browser, then pastes the auth code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            code = user_input.get("auth_code", "").strip()
            if not code:
                errors["auth_code"] = "no_auth_code"
            else:
                try:
                    await self._api.exchange_code_no_pkce(code, REDIRECT_URI)
                    return self.async_create_entry(
                        title="Bosch eBike",
                        data={
                            CONF_CLIENT_ID: self._client_id,
                            "access_token": self._api.access_token,
                            "refresh_token": self._api.refresh_token,
                        },
                    )
                except Exception as err:
                    _LOGGER.exception("Token exchange failed: %s", err)
                    errors["auth_code"] = "token_error"

        return self.async_show_form(
            step_id="auth_code",
            data_schema=vol.Schema({
                vol.Required("auth_code"): str,
            }),
            description_placeholders={"authorize_url": self._authorize_url},
            errors=errors,
        )
