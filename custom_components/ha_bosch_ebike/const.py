"""Constants for Bosch eBike integration."""

DOMAIN = "ha_bosch_ebike"

AUTH_BASE_URL = "https://p9.authz.bosch.com/auth/realms/obc/protocol/openid-connect"
AUTH_URL = f"{AUTH_BASE_URL}/auth"
TOKEN_URL = f"{AUTH_BASE_URL}/token"
API_BASE_URL = "https://api.bosch-ebike.com"

BIKES_ENDPOINT = "/bike-profile/smart-system/v1/bikes"
ACTIVITIES_ENDPOINT = "/activity/smart-system/v1/activities"
BIKE_PASS_ENDPOINT = "/bike-pass/smart-system/v1/bike-passes"
SERVICE_RECORDS_ENDPOINT = "/service-book/smart-system/v1/service-records"

CONF_SYSTEM = "system"
SYSTEM_SMART = "smart_system"
SYSTEM_BES2 = "ebike_system_2"
DEFAULT_SYSTEM = SYSTEM_SMART

# eBike System 2 (BES2 / eBike Connect)
BES2_KC_IDP_HINT = "ebike-connect"
BES2_BIKES_ENDPOINT = "/bike-profile/ebike-system-2/v1/bikes"
BES2_ACTIVITIES_ENDPOINT = "/activity/ebike-system-2/v1/activities"
BES2_STATISTICS_ENDPOINT = "/activity/ebike-system-2/v1/statistics"

# Config keys for the BES2 drive-unit fallback identification
CONF_BES2_SERIAL = "bes2_drive_unit_serial"
CONF_BES2_PART = "bes2_drive_unit_part"

DEFAULT_SCAN_INTERVAL = 30  # minutes
DEFAULT_BATTERY_CAPACITY_WH = 750  # Default battery capacity in Wh

# Service / maintenance reminder thresholds
SERVICE_WARN_DAYS = 30
SERVICE_WARN_KM = 200

# Event names
EVENT_SERVICE_DUE_SOON = f"{DOMAIN}_service_due_soon"
EVENT_SERVICE_OVERDUE = f"{DOMAIN}_service_overdue"
EVENT_MAINTENANCE_DUE_SOON = f"{DOMAIN}_maintenance_due_soon"
EVENT_MAINTENANCE_OVERDUE = f"{DOMAIN}_maintenance_overdue"

REDIRECT_URI = "http://localhost:8888/callback"

# Bosch Data Act developer portal where the user registers an "app" to get a
# Client-ID. Smart System users log in here with their SingleKey ID.
FLOW_PORTAL_URL = "https://portal.bosch-ebike.com/data-act/app"

# Same Data Act portal, but eBike System 2 users register via the eBike Connect
# login (kc_idp_hint=ebike-connect), not SingleKey ID.
BES2_PORTAL_URL = (
    "https://portal.bosch-ebike.com/login?returnTo=%2Fdata-act%2Fapp"
    "&kc_idp_hint=ebike-connect"
)

# OAuth2 scope requested during authorization.
OAUTH_SCOPE = "openid"

CONF_CLIENT_ID = "client_id"

# Optional links to live BLE sensors (provided by the ESPHome bridge in
# `esphome/components/bosch_ebike_ldi/`). When configured, the integration
# uses recorder history of these sensors at tour start/end to compute exact
# distance and consumption — overriding the cloud-derived values.
CONF_LIVE_ODOMETER_ENTITY = "live_odometer_entity"
CONF_LIVE_SOC_ENTITY = "live_soc_entity"

# Per-bike live sensor config for multi-bike accounts (issue #44):
# options[CONF_LIVE_SENSORS] = {bike_id: {CONF_LIVE_ODOMETER_ENTITY: ..., CONF_LIVE_SOC_ENTITY: ...}}.
# The flat CONF_LIVE_ODOMETER_ENTITY/CONF_LIVE_SOC_ENTITY keys above remain as
# a legacy fallback for accounts that saved options before this key existed.
CONF_LIVE_SENSORS = "live_sensors"

# Diagnosis Field Data API (dealer Bosch DiagnosticTool 3 / Capacity Tester
# data: batteries, drive-units, capacity-testers).
#
# UNLIKE every endpoint above, the Data Act appendix PDF documents these only
# by their relative name ("/batteries", "/drive-units", "/capacity-testers"),
# never the full REST path. Compare: the PDF also calls the Digital Service
# Book endpoint just "/service-records", but the real, confirmed-working path
# is "/service-book/smart-system/v1/service-records" — a prefix segment the
# PDF never spells out anywhere. The true prefix for this family is therefore
# unconfirmed. api.py tries each candidate below once per api-client lifetime
# and caches whichever one responds successfully (see
# BoschEBikeAPI._get_with_path_discovery); if none of them work the affected
# sensors simply stay unavailable, same as the existing "dealer never
# connected a diagnostic tool" case.
CAPACITY_TESTERS_PATH_CANDIDATES = {
    SYSTEM_SMART: [
        "/diagnosis-field-data/smart-system/v1/capacity-testers",
        "/field-data/smart-system/v1/capacity-testers",
        "/smart-system/v1/capacity-testers",
    ],
    SYSTEM_BES2: [
        "/diagnosis-field-data/ebike-system-2/v1/capacity-testers",
        "/field-data/ebike-system-2/v1/capacity-testers",
        "/ebike-system-2/v1/capacity-testers",
    ],
}

# batteries / drive-units are documented as eBike System Generation 2 only —
# no Smart System variant exists in the appendix.
BATTERIES_PATH_CANDIDATES = [
    "/diagnosis-field-data/ebike-system-2/v1/batteries",
    "/field-data/ebike-system-2/v1/batteries",
    "/ebike-system-2/v1/batteries",
]
DRIVE_UNITS_PATH_CANDIDATES = [
    "/diagnosis-field-data/ebike-system-2/v1/drive-units",
    "/field-data/ebike-system-2/v1/drive-units",
    "/ebike-system-2/v1/drive-units",
]
