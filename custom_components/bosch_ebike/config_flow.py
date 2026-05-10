"""Config flow for Bosch eBike integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_LIVE_ODOMETER_ENTITY,
    CONF_LIVE_SOC_ENTITY,
    REDIRECT_URI,
    AUTH_URL,
)
from .api import BoschEBikeAPI

_LOGGER = logging.getLogger(__name__)


class BoschEBikeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bosch eBike."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler (live BLE sensor wiring).

        Since HA 2024.11 the framework auto-populates ``self.config_entry`` on
        the OptionsFlow instance, so we MUST NOT pass it in. Doing so raises
        TypeError because the parent OptionsFlow no longer accepts an
        argument in its default __init__.
        """
        return BoschEBikeOptionsFlowHandler()

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
        """Step 2: User opens login URL in browser, then pastes the auth code or full callback URL."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw = user_input.get("auth_code", "").strip()
            code = self._extract_auth_code(raw)
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

    @staticmethod
    def _extract_auth_code(raw: str) -> str | None:
        """Accept either a bare auth code or the full callback URL.

        Detects URLs containing ``code=`` and extracts the parameter; otherwise
        returns the input as-is. Removes trailing whitespace, surrounding quotes
        and angle brackets (common when copying from terminals/emails).
        """
        if not raw:
            return None
        cleaned = raw.strip().strip("<>").strip("\"'").strip()
        if not cleaned:
            return None
        if "code=" in cleaned:
            from urllib.parse import urlparse, parse_qs
            try:
                parsed = urlparse(cleaned)
                # Accept URLs with or without scheme (e.g. "localhost:8888/callback?code=...")
                query = parsed.query or ""
                if not query and "?" in cleaned:
                    query = cleaned.split("?", 1)[1]
                params = parse_qs(query)
                code_values = params.get("code", [])
                if code_values:
                    return code_values[0].strip()
            except Exception:  # noqa: BLE001
                return None
            return None
        return cleaned


class BoschEBikeOptionsFlowHandler(OptionsFlow):
    """Options flow: optional wiring of live BLE sensors for tour enrichment.

    If both ``live_odometer_entity`` and ``live_soc_entity`` are left empty,
    the integration keeps the existing cloud-derived behavior. When set, the
    coordinator queries the HA recorder for these sensors at every tour's
    start and end and uses the deltas as ground truth for distance and
    consumption.

    Note: we deliberately do NOT override ``__init__`` here — the framework
    sets ``self.config_entry`` automatically since HA 2024.11, and from
    2025.12 onwards manually assigning it raises an AttributeError that
    surfaces as an HTTP 500 when the user opens the options dialog.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # Normalize empty strings to "not set" so users can clear values.
            cleaned: dict[str, Any] = {}
            for key in (CONF_LIVE_ODOMETER_ENTITY, CONF_LIVE_SOC_ENTITY):
                value = user_input.get(key)
                if isinstance(value, str) and value.strip():
                    cleaned[key] = value.strip()
            return self.async_create_entry(title="", data=cleaned)

        current = self.config_entry.options or {}

        sensor_selector = EntitySelector(
            EntitySelectorConfig(domain="sensor", multiple=False)
        )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_LIVE_ODOMETER_ENTITY,
                    description={
                        "suggested_value": current.get(CONF_LIVE_ODOMETER_ENTITY)
                    },
                ): sensor_selector,
                vol.Optional(
                    CONF_LIVE_SOC_ENTITY,
                    description={
                        "suggested_value": current.get(CONF_LIVE_SOC_ENTITY)
                    },
                ): sensor_selector,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
