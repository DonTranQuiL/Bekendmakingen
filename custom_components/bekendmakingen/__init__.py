import logging
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, PLATFORMS
from .coordinator import BekendmakingenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bekendmakingen from a config entry."""
    _LOGGER.debug("Start setup Bekendmakingen voor: %s", entry.entry_id)

    coordinator = BekendmakingenCoordinator(hass, entry)

    # FIX: Laad de cache in de achtergrond (voorkomt de Event Loop / Blocking error)
    coordinator.last_data = await hass.async_add_executor_job(
        coordinator.cache.load_cache
    )

    # SMART BOOT: Als er cache is, start direct op. Zo niet, doe de zware download.
    if coordinator.last_data:
        _LOGGER.debug("Cache found! Loading instantly to speed up startup.")
        coordinator.data = coordinator.last_data
        entry.async_create_background_task(
            hass, coordinator.async_request_refresh(), "bekendmakingen_bg_refresh"
        )
    else:
        _LOGGER.debug("No cache found. Starting the heavy first download...")
        await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def handle_refresh(call: ServiceCall):
        _LOGGER.debug("Handmatige Bekendmakingen refresh aangevraagd")
        for coord in hass.data[DOMAIN].values():
            await coord.async_request_refresh()

    async def handle_clear_files(call: ServiceCall):
        _LOGGER.debug("Clear Bekendmakingen files service aangevraagd")
        for coord in hass.data[DOMAIN].values():
            await hass.async_add_executor_job(coord.cache.clear_cache)
            await hass.async_add_executor_job(coord.clear_debug_file)

    hass.services.async_register(DOMAIN, "refresh", handle_refresh)
    hass.services.async_register(DOMAIN, "clear_files", handle_clear_files)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
