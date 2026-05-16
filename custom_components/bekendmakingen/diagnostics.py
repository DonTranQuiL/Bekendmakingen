from __future__ import annotations
from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "municipality": entry.data["municipality"],
        "last_update_success": coordinator.last_update_success_timestamp.isoformat()
        if coordinator.last_update_success_timestamp
        else None,
        "consecutive_errors": coordinator.error_count,
        "current_data_count": len(coordinator.data) if coordinator.data else 0,
        "latest_announcement": coordinator.data[0] if coordinator.data else None,
    }
