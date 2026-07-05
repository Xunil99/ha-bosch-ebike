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
    CONF_LIVE_SENSORS,
    CONF_SYSTEM,
    SYSTEM_SMART,
    SYSTEM_BES2,
    BES2_KC_IDP_HINT,
    AUTH_URL,
    TOKEN_URL,
    OAUTH_SCOPE,
    FLOW_PORTAL_URL,
    BES2_PORTAL_URL,
)
from .profile_extra import bike_label

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
        # eBike System 2 accounts authenticate via the eBike Connect identity
        # provider, selected by this Keycloak hint on the authorize URL.
        if getattr(self, "_kc_idp_hint", None):
            data["kc_idp_hint"] = self._kc_idp_hint
        return data


class BoschEBikeConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle the OAuth2 config flow for Bosch eBike."""

    DOMAIN = DOMAIN
    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._client_id: str | None = None
        self._system: str = SYSTEM_SMART

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler (live BLE sensor wiring)."""
        return BoschEBikeOptionsFlowHandler()

    @property
    def _portal_url(self) -> str:
        """Data Act portal link for the chosen system.

        Smart System users register via SingleKey ID; eBike System 2 users
        register via the eBike Connect login, which is a different URL.
        """
        return BES2_PORTAL_URL if self._system == SYSTEM_BES2 else FLOW_PORTAL_URL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: choose the eBike system (Smart System or eBike System 2)."""
        # Pass portal_url even though the menu step's own text does not use it:
        # if a stale/cached translation still carries the old {portal_url}
        # description on this step, this prevents a MISSING_VALUE crash.
        return self.async_show_menu(
            step_id="user",
            menu_options=["smart_system", "ebike_system_2"],
            description_placeholders={"portal_url": self._portal_url},
        )

    async def async_step_smart_system(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Smart System (BES3) selected."""
        self._system = SYSTEM_SMART
        return await self.async_step_credentials()

    async def async_step_ebike_system_2(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """eBike System 2 (BES2 / eBike Connect) selected."""
        self._system = SYSTEM_BES2
        return await self.async_step_credentials()

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter the Client-ID, then start the OAuth login."""
        if user_input is not None:
            self._client_id = user_input[CONF_CLIENT_ID].strip()
            await self.async_set_unique_id(self._client_id)
            self._abort_if_unique_id_configured()
            self._register_impl(self._client_id)
            return await self.async_step_pick_implementation()

        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema({vol.Required(CONF_CLIENT_ID): str}),
            description_placeholders={"portal_url": self._portal_url},
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Re-authenticate an existing entry (e.g. refresh token expired)."""
        self._client_id = entry_data.get(CONF_CLIENT_ID)
        self._system = entry_data.get(CONF_SYSTEM, SYSTEM_SMART)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-auth, then re-run the OAuth login with the stored Client-ID."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={"portal_url": self._portal_url},
            )
        if self._client_id:
            self._register_impl(self._client_id)
        return await self.async_step_pick_implementation()

    def _register_impl(self, client_id: str) -> None:
        """Register a fresh PKCE implementation for the given Client-ID.

        For eBike System 2 the implementation carries the eBike Connect
        Keycloak hint so the authorize URL routes to the right identity
        provider; Smart System leaves it unset.
        """
        impl = BoschPkceImplementation(
            self.hass, DOMAIN, client_id, AUTH_URL, TOKEN_URL
        )
        impl._kc_idp_hint = (
            BES2_KC_IDP_HINT if self._system == SYSTEM_BES2 else None
        )
        self.async_register_implementation(self.hass, impl)

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
            CONF_SYSTEM: self._system,
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

    If a bike's odometer/SoC fields are left empty, the integration keeps the
    cloud-derived behavior for that bike. When set, the coordinator queries
    the HA recorder for these sensors at every tour's start and end and uses
    the deltas as ground truth for distance and consumption.

    Multi-bike accounts (issue #44): a single ESP32 LDI bridge can only ever
    be paired to one physical bike, so the account-wide flat option from
    before this fix could not tell two bikes' bridges apart. This flow walks
    every bike on the account as its own step (step_id "bike", reused per
    bike - HA calls the matching ``async_step_<id>`` for whichever step is
    currently shown, regardless of how many times the same id is shown), and
    saves the result nested by bike_id under ``CONF_LIVE_SENSORS``. Existing
    single-bike accounts that already had the old flat option keep working
    unchanged (see ``BoschEBikeCoordinator.live_odometer_entity``/
    ``live_soc_entity`` for the fallback) until they save this flow once,
    which is when they transparently move onto the new per-bike storage.

    Note: we deliberately do NOT override ``__init__`` for ``config_entry``
    - the framework sets that automatically since HA 2024.11. We DO need an
    ``__init__`` for the wizard's own walk-through state.
    """

    def __init__(self) -> None:
        self._bikes: list[dict[str, Any]] = []
        self._bike_index: int = 0
        self._live_sensors: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _entity_schema(suggested: dict[str, Any]) -> vol.Schema:
        sensor_selector = EntitySelector(
            EntitySelectorConfig(domain="sensor", multiple=False)
        )
        return vol.Schema(
            {
                vol.Optional(
                    CONF_LIVE_ODOMETER_ENTITY,
                    description={
                        "suggested_value": suggested.get(CONF_LIVE_ODOMETER_ENTITY)
                    },
                ): sensor_selector,
                vol.Optional(
                    CONF_LIVE_SOC_ENTITY,
                    description={
                        "suggested_value": suggested.get(CONF_LIVE_SOC_ENTITY)
                    },
                ): sensor_selector,
            }
        )

    def _store_step_result(self, user_input: dict[str, Any]) -> None:
        bike_id = self._bikes[self._bike_index]["id"]
        cleaned: dict[str, Any] = {}
        for key in (CONF_LIVE_ODOMETER_ENTITY, CONF_LIVE_SOC_ENTITY):
            value = user_input.get(key)
            if isinstance(value, str) and value.strip():
                cleaned[key] = value.strip()
        if cleaned:
            self._live_sensors[bike_id] = cleaned
        else:
            self._live_sensors.pop(bike_id, None)

    async def _async_show_bike_step(self) -> ConfigFlowResult:
        if self._bike_index >= len(self._bikes):
            return self.async_create_entry(
                title="", data={CONF_LIVE_SENSORS: self._live_sensors}
            )
        bike = self._bikes[self._bike_index]
        return self.async_show_form(
            step_id="bike",
            data_schema=self._entity_schema(self._live_sensors.get(bike["id"], {})),
            description_placeholders={"bike_name": bike_label(bike)},
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Discover the account's bikes, then start the per-bike wizard."""
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        bikes = coordinator.data.get("bikes", []) if coordinator and coordinator.data else []
        self._bikes = [b for b in bikes if b.get("id")]
        self._bike_index = 0

        current = self.config_entry.options or {}
        self._live_sensors = {
            bid: dict(cfg)
            for bid, cfg in (current.get(CONF_LIVE_SENSORS) or {}).items()
        }
        # Single-bike account still on the pre-#44 flat option: seed the
        # wizard from it so the field does not appear to have been cleared.
        # Saving the form migrates it onto the per-bike storage below.
        if not self._live_sensors and len(self._bikes) == 1:
            legacy = {
                key: current.get(key)
                for key in (CONF_LIVE_ODOMETER_ENTITY, CONF_LIVE_SOC_ENTITY)
                if current.get(key)
            }
            if legacy:
                self._live_sensors[self._bikes[0]["id"]] = legacy

        return await self._async_show_bike_step()

    async def async_step_bike(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """One step per bike; step_id is reused, advancing an internal index."""
        if user_input is not None:
            self._store_step_result(user_input)
            self._bike_index += 1
        return await self._async_show_bike_step()
