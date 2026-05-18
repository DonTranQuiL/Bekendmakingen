"""Tests for the Bekendmakingen sensor platform."""

from unittest.mock import MagicMock
import pytest
from homeassistant.core import HomeAssistant

from custom_components.bekendmakingen.const import (
    CONF_MUNICIPALITY,
)
from custom_components.bekendmakingen.sensor import (
    BekendmakingenSensor,
    BekendmakingenDiagnosticSensor,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock DataUpdateCoordinator filled with predictable testing data."""
    coordinator = MagicMock()

    config_entry = MagicMock()
    config_entry.entry_id = "mock_entry_id_123"
    config_entry.data = {CONF_MUNICIPALITY: "Kerkrade"}

    coordinator.config_entry = config_entry
    coordinator.last_update_success_timestamp = "2026-05-18T15:30:00+00:00"
    coordinator.error_count = 0

    # Populating mock feed data array matching sensor.py's list expectations
    coordinator.data = [
        {
            "title": "Nieuw bestemmingsplan Centrum",
            "date": "2026-05-18",
            "time": "15:30",
            "link": "https://zoek.officielebekendmakingen.nl/rss?q=Kerkrade",
            "summary": "Gemeente Kerkrade maakt een nieuw bestemmingsplan bekend.",
        },
        {
            "title": "Omgevingsvergunning Hoofdstraat 12",
            "date": "2026-05-17",
            "time": "10:00",
            "link": "https://zoek.officielebekendmakingen.nl/rss?q=Kerkrade",
            "summary": "Kapvergunning verleend voor een kastanjeboom.",
        },
    ]

    return coordinator


@pytest.mark.asyncio
async def test_bekendmakingen_sensor_state_and_attributes(
    hass: HomeAssistant,
    mock_coordinator,
):
    """Test main Bekendmakingen sensor state, attributes, and device info grouping."""
    entry = mock_coordinator.config_entry
    sensor = BekendmakingenSensor(mock_coordinator, entry)
    sensor.hass = hass
    sensor.entity_id = "sensor.bekendmakingen_kerkrade_latest_bekendmaking"

    # Asserting the core state properties
    assert sensor.native_value == "Nieuw bestemmingsplan Centrum"

    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["date"] == "2026-05-18"
    assert attrs["time"] == "15:30"
    assert attrs["link"] == "https://zoek.officielebekendmakingen.nl/rss?q=Kerkrade"
    assert (
        attrs["summary"] == "Gemeente Kerkrade maakt een nieuw bestemmingsplan bekend."
    )

    # Verify the history tracking arrays
    assert len(attrs["history"]) == 1
    assert attrs["history"][0]["title"] == "Omgevingsvergunning Hoofdstraat 12"


@pytest.mark.asyncio
async def test_bekendmakingen_sensor_empty_data(
    hass: HomeAssistant,
    mock_coordinator,
):
    """Test main sensor behavior when coordinator has no feed results."""
    mock_coordinator.data = []
    entry = mock_coordinator.config_entry
    sensor = BekendmakingenSensor(mock_coordinator, entry)
    sensor.hass = hass
    sensor.entity_id = "sensor.bekendmakingen_kerkrade_latest_bekendmaking"

    assert sensor.native_value == "Geen bekendmakingen"
    assert sensor.extra_state_attributes == {}


@pytest.mark.asyncio
async def test_bekendmakingen_diagnostic_sensors(
    hass: HomeAssistant,
    mock_coordinator,
):
    """Test state evaluation for all diagnostic sensor types."""
    entry = mock_coordinator.config_entry

    status_sensor = BekendmakingenDiagnosticSensor(
        mock_coordinator, entry, "last_update_status", "Last Update Status"
    )
    time_sensor = BekendmakingenDiagnosticSensor(
        mock_coordinator, entry, "last_update_time", "Last Update Time"
    )
    error_sensor = BekendmakingenDiagnosticSensor(
        mock_coordinator, entry, "error_count", "Consecutive Errors"
    )

    # Asserts healthy operational state parameters
    assert status_sensor.native_value == "OK"
    assert time_sensor.native_value == "2026-05-18T15:30:00+00:00"
    assert error_sensor.native_value == 0

    # Modify mock coordinator parameters to force fallback states
    mock_coordinator.last_update_success_timestamp = None
    mock_coordinator.error_count = 4

    assert status_sensor.native_value == "Error"
    assert error_sensor.native_value == 4
