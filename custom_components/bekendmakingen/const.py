"""Constants for the Bekendmakingen integration."""

DOMAIN = "bekendmakingen"
MANUFACTURER = "Overheid.nl"
VERSION = "2.1.0b0"
DEFAULT_SCAN_INTERVAL = 3600

CONF_MUNICIPALITY = "municipality"
CONF_INSTANCE_NAME = "instance_name"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_FILTERS = "filters"
CONF_MAX_ITEMS = "max_items"

DEFAULT_MAX_ITEMS = 10
MIN_MAX_ITEMS = 10
MAX_MAX_ITEMS = 50

PLATFORMS = ["sensor"]

RSS_BASE_URL = "https://zoek.officielebekendmakingen.nl/rss?q="
RECORD_BASE_URL = "https://zoek.officielebekendmakingen.nl"
PDOK_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"

CARD_FILENAME = "bekendmakingen-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"
