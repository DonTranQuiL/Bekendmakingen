"""Config flow for Bekendmakingen integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN, CONF_MUNICIPALITY, CONF_INSTANCE_NAME, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, CONF_FILTERS

_LOGGER = logging.getLogger(__name__)

MIN_SCAN_INTERVAL_SECONDS = 300

FILTER_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            {"value": "alles", "label": "ALLES (Geen filter)"},
            {"value": "aanvragen", "label": "Aanvragen"},
            {"value": "verleend", "label": "Vergunning verleend"},
            {"value": "meldingen", "label": "Meldingen"},
            {"value": "geweigerd", "label": "Geweigerd"},
            {"value": "overig", "label": "Overige nieuws"},
        ],
        multiple=True,
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)

async def validate_municipality(hass: HomeAssistant, municipality: str) -> bool:
    return bool(municipality.strip())

def validate_scan_interval(scan_interval: int) -> bool:
    return scan_interval >= MIN_SCAN_INTERVAL_SECONDS

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            municipality = user_input.get(CONF_MUNICIPALITY)
            instance_name = user_input.get(CONF_INSTANCE_NAME)
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            filters = user_input.get(CONF_FILTERS, ["alles"])

            if not municipality: 
                errors[CONF_MUNICIPALITY] = "required"
            if not instance_name: 
                errors[CONF_INSTANCE_NAME] = "required"
            if not validate_scan_interval(scan_interval): 
                errors[CONF_SCAN_INTERVAL] = "invalid_scan_interval"

            if not errors:
                for entry in self._async_current_entries():
                    if entry.data.get(CONF_MUNICIPALITY) == municipality and entry.data.get(CONF_INSTANCE_NAME) == instance_name:
                        return self.async_abort(reason="already_configured")

                if await validate_municipality(self.hass, municipality):
                    return self.async_create_entry(
                        title=f"Bekendmakingen ({instance_name})",
                        data={
                            CONF_MUNICIPALITY: municipality,
                            CONF_INSTANCE_NAME: instance_name,
                        },
                        options={
                            CONF_SCAN_INTERVAL: scan_interval,
                            CONF_FILTERS: filters,
                        },
                    )
                else:
                    errors["base"] = "invalid_municipality"

        data_schema = vol.Schema({
            vol.Required(CONF_MUNICIPALITY): str,
            vol.Required(CONF_INSTANCE_NAME): str,
            vol.Optional(CONF_FILTERS, default=["alles"]): FILTER_SELECTOR,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        # FIX: We now pass it empty to avoid the read-only property crash
        return OptionsFlowHandler()

class OptionsFlowHandler(config_entries.OptionsFlow):
    # FIX: __init__ completely removed so Home Assistant can inject it safely

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            scan_interval = user_input.get(CONF_SCAN_INTERVAL)
            if not validate_scan_interval(scan_interval):
                return self.async_show_form(
                    step_id="init",
                    data_schema=vol.Schema({
                        vol.Optional(CONF_FILTERS, default=self.config_entry.options.get(CONF_FILTERS, ["alles"])): FILTER_SELECTOR,
                        vol.Optional(CONF_SCAN_INTERVAL, default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): int
                    }),
                    errors={CONF_SCAN_INTERVAL: "invalid_scan_interval"},
                )
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Optional(CONF_FILTERS, default=self.config_entry.options.get(CONF_FILTERS, ["alles"])): FILTER_SELECTOR,
            vol.Optional(CONF_SCAN_INTERVAL, default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): int,
        })
        return self.async_show_form(step_id="init", data_schema=options_schema)
