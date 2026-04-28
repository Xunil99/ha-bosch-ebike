"""Constants for Bosch eBike integration."""

DOMAIN = "ha_bosch_ebike"

AUTH_BASE_URL = "https://p9.authz.bosch.com/auth/realms/obc/protocol/openid-connect"
AUTH_URL = f"{AUTH_BASE_URL}/auth"
TOKEN_URL = f"{AUTH_BASE_URL}/token"
API_BASE_URL = "https://api.bosch-ebike.com"

BIKES_ENDPOINT = "/bike-profile/smart-system/v1/bikes"
ACTIVITIES_ENDPOINT = "/activity/smart-system/v1/activities"

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

CONF_CLIENT_ID = "client_id"
