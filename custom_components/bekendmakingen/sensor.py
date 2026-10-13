"""Sensors for Bekendmakingen."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANUFACTURER, VERSION
from .coordinator import BekendmakingenCoordinator
from .parser import CATEGORIES

CATEGORY_NAMES = {
    "aanvragen": "Aanvragen",
    "verleend": "Verleend",
    "geweigerd": "Geweigerd",
    "verkeer": "Verkeer",
    "meldingen": "Meldingen",
    "overig": "Overig",
}

# Large attributes: shown in the UI/card but not written to the recorder.
HEAVY_ATTRIBUTES = frozenset({"history", "items", "summary", "detailed_description"})


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: BekendmakingenCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        BekendmakingenSensor(coordinator, entry),
        BekendmakingenNewTodaySensor(coordinator, entry),
        *(BekendmakingenCategorySensor(coordinator, entry, c) for c in CATEGORIES),
        BekendmakingenDiagnosticSensor(
            coordinator, entry, "last_update_status", "Last Update Status"
        ),
        BekendmakingenDiagnosticSensor(
            coordinator,
            entry,
            "last_update_time",
            "Last Update Time",
            SensorDeviceClass.TIMESTAMP,
        ),
        BekendmakingenDiagnosticSensor(
            coordinator, entry, "error_count", "Consecutive Errors"
        ),
    ]
    async_add_entities(entities)


def _device_info(entry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Bekendmakingen ({entry.data['municipality']})",
        manufacturer=MANUFACTURER,
        model="RSS Feed",
        sw_version=VERSION,
    )


class BekendmakingenEntity(CoordinatorEntity[BekendmakingenCoordinator]):
    """Base: one device per config entry, pushes on every coordinator update."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BekendmakingenCoordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(entry)

    @property
    def available(self) -> bool:
        # Cached data stays useful when the feed is temporarily down.
        return True

    @property
    def _items(self) -> list[dict[str, Any]]:
        return self.coordinator.data or []


class BekendmakingenSensor(BekendmakingenEntity, SensorEntity):
    """Main sensor: newest title as state, all items as attributes."""

    _attr_icon = "mdi:bullhorn-variant-outline"
    _unrecorded_attributes = HEAVY_ATTRIBUTES

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = None  # main sensor takes the device name
        self._attr_unique_id = f"{entry.entry_id}_latest_bekendmaking"

    @property
    def native_value(self):
        items = self._items
        return items[0]["title"][:255] if items else "Geen bekendmakingen"

    @property
    def extra_state_attributes(self):
        items = self._items
        if not items:
            return {}
        latest = items[0]
        return {
            # v2.0 attributes (unchanged names)
            "date": latest.get("date"),
            "time": latest.get("time"),
            "link": latest.get("link"),
            "summary": latest.get("summary"),
            "detailed_description": latest.get(
                "detailed_description", "Geen extra details beschikbaar."
            ),
            "history": items[1:],
            # v2.1
            "id": latest.get("id"),
            "category": latest.get("category"),
            "published": latest.get("published"),
            "address": latest.get("address"),
            "latitude": latest.get("latitude"),
            "longitude": latest.get("longitude"),
            "municipality": self.coordinator.municipality,
            "items": items,
        }


class BekendmakingenNewTodaySensor(BekendmakingenEntity, SensorEntity):
    _attr_icon = "mdi:new-box"
    _attr_native_unit_of_measurement = "bekendmakingen"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Nieuw vandaag"
        self._attr_unique_id = f"{entry.entry_id}_new_today"

    @property
    def native_value(self) -> int:
        today = dt_util.now().date().isoformat()
        return sum(1 for i in self._items if i.get("date") == today)


class BekendmakingenCategorySensor(BekendmakingenEntity, SensorEntity):
    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "bekendmakingen"

    def __init__(self, coordinator, entry, category: str) -> None:
        super().__init__(coordinator, entry)
        self.category = category
        self._attr_name = CATEGORY_NAMES[category]
        self._attr_unique_id = f"{entry.entry_id}_count_{category}"

    @property
    def native_value(self) -> int:
        return sum(1 for i in self._items if i.get("category") == self.category)


class BekendmakingenDiagnosticSensor(BekendmakingenEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, key, name, device_class=None):
        super().__init__(coordinator, entry)
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_diag_{key}"
        self._attr_device_class = device_class

    @property
    def native_value(self):
        if self.key == "last_update_status":
            return "OK" if self.coordinator.last_update_success_timestamp else "Error"
        if self.key == "last_update_time":
            return self.coordinator.last_update_success_timestamp
        if self.key == "error_count":
            return self.coordinator.error_count
        return None
