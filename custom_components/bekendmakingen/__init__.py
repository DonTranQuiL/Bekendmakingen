"""Bekendmakingen: official municipal announcements in Home Assistant."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CARD_FILENAME, CARD_URL, DOMAIN, PLATFORMS, VERSION
from .coordinator import BekendmakingenCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _file_digest(path: Path) -> str:
    """Short hash of a file's content (cache busting)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def _coordinators(hass: HomeAssistant) -> list[BekendmakingenCoordinator]:
    return [
        c
        for c in hass.data.get(DOMAIN, {}).values()
        if isinstance(c, BekendmakingenCoordinator)
    ]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions and the dashboard card once."""

    async def handle_refresh(call: ServiceCall) -> None:
        for coord in _coordinators(hass):
            await coord.async_request_refresh()

    async def handle_clear_files(call: ServiceCall) -> None:
        for coord in _coordinators(hass):
            await hass.async_add_executor_job(coord.cache.clear_cache)
            await hass.async_add_executor_job(coord.clear_debug_file)
            await hass.async_add_executor_job(coord.clear_geocode_cache)

    hass.services.async_register(DOMAIN, "refresh", handle_refresh)
    hass.services.async_register(DOMAIN, "clear_files", handle_clear_files)

    card = Path(__file__).parent / "frontend" / CARD_FILENAME
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card), True)]
    )
    if "frontend" in hass.config.components:
        digest = await hass.async_add_executor_job(_file_digest, card)
        add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}-{digest}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bekendmakingen from a config entry."""
    coordinator = BekendmakingenCoordinator(hass, entry)
    coordinator.last_data = await hass.async_add_executor_job(
        coordinator.cache.load_cache
    )
    await hass.async_add_executor_job(coordinator.load_geocode_cache)

    if coordinator.last_data:
        # Cache present: show it instantly, refresh in the background.
        coordinator.async_set_updated_data(coordinator.last_data)
        entry.async_create_background_task(
            hass, coordinator.async_request_refresh(), "bekendmakingen_bg_refresh"
        )
    else:
        await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
