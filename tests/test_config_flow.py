"""Config and options flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bekendmakingen.const import DOMAIN


async def test_user_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "municipality": "utrecht",
            "instance_name": "Utrecht",
            "scan_interval": 100,
        },
    )
    assert result["errors"] == {"scan_interval": "invalid_scan_interval"}
    from unittest.mock import patch

    with patch("custom_components.bekendmakingen.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "municipality": "utrecht",
                "instance_name": "Utrecht",
                "scan_interval": 3600,
                "max_items": 25,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["max_items"] == 25


async def test_options_flow(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"municipality": "utrecht", "instance_name": "Utrecht"},
        options={"scan_interval": 3600, "filters": ["alles"]},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"filters": ["alles"], "scan_interval": 10, "max_items": 20}
    )
    assert result["errors"] == {"scan_interval": "invalid_scan_interval"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"filters": ["verkeer"], "scan_interval": 1800, "max_items": 40},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["max_items"] == 40
    assert entry.options["filters"] == ["verkeer"]
