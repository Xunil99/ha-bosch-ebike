"""Config flow for the Bosch eBike integration.

Uses Home Assistant's built-in OAuth2 helper with PKCE (public client, no
secret). The user only enters their Client-ID; login happens via the normal
"Authorize" redirect through https://my.home-assistant.io/redirect/oauth - no
manual copying of authorization codes.

Tokens are stored in the same shape the API client/coordinator already expect
(``client_id`` + ``access_token`` + ``refresh_token``), so existing entries
created with the older manual flow keep working without migration.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    LocalOAuth2ImplementationWithPkce,
)
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_LIVE_ODOMETER_ENTITY,
    CONF_LIVE_SOC_ENTITY,
    AUTH_URL,
    TOKEN_URL,
    OAUTH_SCOPE,
    FLOW_PORTAL_URL,
)

_LOGGER = logging.getLogger(__name__)


class BoschPkceImplementation(LocalOAuth2ImplementationWithPkce):
    """PKCE OAuth2 implementation that requests the openid scope."""

    @property
    def name(self) -> str:
        return "Bosch eBike"

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        # Must keep the PKCE params from the parent and add our scope.
        data = {"scope": OAUTH_SCOPE}
        data.update(super().extra_authorize_data)
        return data


class BoschEBikeConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle the OAuth2 config flow for Bosch eBike."""

    DOMAIN = DOMAIN
    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._client_id: str | None = None

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler (live BLE sensor wiring)."""
        return BoschEBikeOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: the user enters their Client-ID, then we start OAuth."""
        if user_input is not None:
            self._client_id = user_input[CONF_CLIENT_ID].strip()
            await self.async_set_unique_id(self._client_id)
            self._abort_if_unique_id_configured()
            self._register_impl(self._client_id)
            return await self.async_step_pick_implementation()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_CLIENT_ID): str}),
            description_placeholders={"portal_url": FLOW_PORTAL_URL},
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Re-authenticate an existing entry (e.g. refresh token expired)."""
        self._client_id = entry_data.get(CONF_CLIENT_ID)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-auth, then re-run the OAuth login with the stored Client-ID."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={"portal_url": FLOW_PORTAL_URL},
            )
        if self._client_id:
            self._register_impl(self._client_id)
        return await self.async_step_pick_implementation()

    def _register_impl(self, client_id: str) -> None:
        """Register a fresh PKCE implementation for the given Client-ID."""
        self.async_register_implementation(
            self.hass,
            BoschPkceImplementation(self.hass, DOMAIN, client_id, AUTH_URL, TOKEN_URL),
        )

    async def async_oauth_create_entry(
        self, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Store tokens in the legacy shape so the API client keeps working.

        HA hands us ``data["token"]`` (access_token, refresh_token, expires_at,
        ...). We flatten the bits the existing API client/coordinator read,
        which keeps backward compatibility with entries from the old flow.
        """
        token = data.get("token", {})
        entry_data = {
            CONF_CLIENT_ID: self._client_id,
            "access_token": token.get("access_token"),
            "refresh_token": token.get("refresh_token"),
        }

        # Re-auth: update the existing entry in place instead of creating a new one.
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=entry_data
            )

        return self.async_create_entry(title="Bosch eBike", data=entry_data)


class BoschEBikeOptionsFlowHandler(OptionsFlow):
    """Options flow: optional wiring of live BLE sensors for tour enrichment.

    If both ``live_odometer_entity`` and ``live_soc_entity`` are left empty,
    the integration keeps the existing cloud-derived behavior. When set, the
    coordinator queries the HA recorder for these sensors at every tour's
    start and end and uses the deltas as ground truth for distance and
    consumption.

    Note: we deliberately do NOT override ``__init__`` here - the framework
    sets ``self.config_entry`` automatically since HA 2024.11.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
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
