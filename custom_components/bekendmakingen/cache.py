import json
import os
import logging

_LOGGER = logging.getLogger(__name__)


class BekendmakingenCache:
    def __init__(self, hass, municipality):
        self.cache_path = hass.config.path(f".bekendmakingen_{municipality}.json")

    def save_cache(self, data):
        try:
            with open(self.cache_path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            _LOGGER.error("Error saving bekendmakingen cache: %s", e)

    def load_cache(self):
        if not os.path.exists(self.cache_path):
            return []
        try:
            with open(self.cache_path, "r") as f:
                return json.load(f)
        except Exception as e:
            _LOGGER.error("Error loading bekendmakingen cache: %s", e)
            return []

    def clear_cache(self):
        """Deletes the JSON cache file if it exists."""
        if os.path.exists(self.cache_path):
            try:
                os.remove(self.cache_path)
                _LOGGER.debug("Deleted cache file: %s", self.cache_path)
            except Exception as e:
                _LOGGER.error("Error deleting cache file: %s", e)
