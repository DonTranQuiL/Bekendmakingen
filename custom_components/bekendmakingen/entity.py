"""Base entity for Planviewer."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, CONF_INSTANCE_NAME
from .coordinator import PlanviewerDataUpdateCoordinator


class PlanviewerBaseEntity(CoordinatorEntity[PlanviewerDataUpdateCoordinator]):
    """Base class for Planviewer entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PlanviewerDataUpdateCoordinator) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._instance_name = coordinator.config_entry.data[CONF_INSTANCE_NAME]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=f"Planviewer ({self._instance_name})",
            manufacturer=MANUFACTURER,
            model="Scraped Data",
        )
