from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import EntityCategory
from .const import DOMAIN, MANUFACTURER

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        BekendmakingenSensor(coordinator, entry),
        BekendmakingenDiagnosticSensor(coordinator, entry, "last_update_status", "Last Update Status"),
        BekendmakingenDiagnosticSensor(coordinator, entry, "last_update_time", "Last Update Time", SensorDeviceClass.TIMESTAMP),
        BekendmakingenDiagnosticSensor(coordinator, entry, "error_count", "Consecutive Errors"),
    ]
    async_add_entities(entities)

class BekendmakingenSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        self.coordinator = coordinator
        self._attr_name = None # Main sensor takes the device name
        self._attr_unique_id = f"{entry.entry_id}_latest_bekendmaking"
        
        # BUNDLES THE SENSORS INTO ONE DEVICE
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Bekendmakingen ({entry.data['municipality']})",
            "manufacturer": MANUFACTURER,
            "model": "RSS Feed",
        }

    @property
    def native_value(self):
        return self.coordinator.data[0]["title"] if self.coordinator.data else "Geen bekendmakingen"

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        latest = self.coordinator.data[0]
        return {
            "date": latest["date"],
            "time": latest["time"],
            "link": latest["link"],
            "summary": latest["summary"],
            "detailed_description": latest.get("detailed_description", "Geen extra details beschikbaar."),
            "history": self.coordinator.data[1:],
        }
class BekendmakingenDiagnosticSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, key, name, device_class=None):
        self.coordinator = coordinator
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_diag_{key}"
        self._attr_device_class = device_class
        
        # MUST MATCH THE MAIN SENSOR EXACTLY TO GROUP THEM
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Bekendmakingen ({entry.data['municipality']})",
            "manufacturer": MANUFACTURER,
            "model": "RSS Feed",
        }

    @property
    def native_value(self):
        if self.key == "last_update_status":
            return "OK" if self.coordinator.last_update_success_timestamp else "Error"
        if self.key == "last_update_time":
            return self.coordinator.last_update_success_timestamp
        if self.key == "error_count":
            return self.coordinator.error_count