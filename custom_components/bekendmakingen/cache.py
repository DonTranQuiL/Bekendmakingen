"""Small JSON cache so the dashboard is filled instantly after a restart."""

import json
import logging
import os

_LOGGER = logging.getLogger(__name__)


class BekendmakingenCache:
    def __init__(self, hass, municipality):
        self.cache_path = hass.config.path(f".bekendmakingen_{municipality}.json")

    def save_cache(self, data):
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            _LOGGER.error("Error saving bekendmakingen cache: %s", e)

    def load_cache(self):
        if not os.path.exists(self.cache_path):
            return []
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            _LOGGER.error("Error loading bekendmakingen cache: %s", e)
            return []

    def clear_cache(self):
        """Delete the JSON cache file if it exists."""
        if os.path.exists(self.cache_path):
            try:
                os.remove(self.cache_path)
            except Exception as e:
                _LOGGER.error("Error deleting cache file: %s", e)
