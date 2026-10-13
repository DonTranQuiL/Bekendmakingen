"""Full setup against recorded feed + metadata (no live network)."""

from __future__ import annotations

import os
import re

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bekendmakingen.const import (
    CONF_FILTERS,
    CONF_INSTANCE_NAME,
    CONF_MAX_ITEMS,
    CONF_MUNICIPALITY,
    CONF_SCAN_INTERVAL,
    DOMAIN,
    PDOK_URL,
)
from custom_components.bekendmakingen.coordinator import (
    BekendmakingenCoordinator,
    municipality_name,
)

from .conftest import FIXTURES, UTRECHT_HOME, fixture

BASE = "https://zoek.officielebekendmakingen.nl"
IDS = sorted(
    {p.name.split(".")[0] for p in FIXTURES.glob("gmb-*.meta.xml")}
    & set(re.findall(r"(gmb-\d{4}-\d+)\.html", fixture("rss_utrecht.xml")))
)


def mock_feed(aioclient_mock) -> None:
    aioclient_mock.get(
        re.compile(rf"^{BASE}/rss\?q=.*"), text=fixture("rss_utrecht.xml")
    )
    for rid in IDS:
        aioclient_mock.get(
            f"{BASE}/{rid}/metadata.xml", text=fixture(f"{rid}.meta.xml")
        )
        aioclient_mock.get(f"{BASE}/{rid}.xml", text=fixture(f"{rid}.xml"))


async def setup_entry(hass: HomeAssistant, **options) -> MockConfigEntry:
    hass.config.latitude, hass.config.longitude = UTRECHT_HOME
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bekendmakingen (Utrecht)",
        data={CONF_MUNICIPALITY: "utrecht", CONF_INSTANCE_NAME: "Utrecht"},
        options={CONF_SCAN_INTERVAL: 3600, CONF_FILTERS: ["alles"], **options},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture(autouse=True)
def _cache_dir(hass: HomeAssistant, tmp_path):
    hass.config.config_dir = str(tmp_path)


async def test_setup_items_sensors_and_counts(
    hass: HomeAssistant, aioclient_mock, freezer
) -> None:
    freezer.move_to("2026-10-13 12:00:00+02:00")
    mock_feed(aioclient_mock)
    entry = await setup_entry(hass)

    main = hass.states.get("sensor.bekendmakingen_utrecht")
    assert main is not None
    items = main.attributes["items"]
    assert len(items) == 6 == len(IDS)
    # v2.0 attributes still present
    for key in ("date", "time", "link", "summary", "detailed_description", "history"):
        assert key in main.attributes
    assert len(main.attributes["history"]) == 5
    assert main.state == items[0]["title"]
    assert main.attributes["municipality"] == "utrecht"

    by_id = {i["id"]: i for i in items}
    permit = by_id["gmb-2026-477883"]
    assert permit["category"] == "verleend"
    assert permit["deadline"] == "2026-11-20"
    assert 5 < permit["distance_km"] < 7  # Leidsche Rijn vs. city centre
    assert all(i["latitude"] is not None for i in items)

    assert hass.states.get("sensor.bekendmakingen_utrecht_nieuw_vandaag").state == "6"
    assert hass.states.get("sensor.bekendmakingen_utrecht_verleend").state == "2"
    assert hass.states.get("sensor.bekendmakingen_utrecht_verkeer").state == "4"
    assert hass.states.get("sensor.bekendmakingen_utrecht_geweigerd").state == "0"
    assert (
        hass.states.get("sensor.bekendmakingen_utrecht_last_update_status").state
        == "OK"
    )
    assert (
        hass.states.get("sensor.bekendmakingen_utrecht_consecutive_errors").state == "0"
    )

    ent_reg = er.async_get(hass)
    ids = {
        e.unique_id for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    }
    assert f"{entry.entry_id}_latest_bekendmaking" in ids
    assert f"{entry.entry_id}_count_verkeer" in ids

    # Heavy attributes are not recorded.
    from custom_components.bekendmakingen.sensor import BekendmakingenSensor

    assert {
        "items",
        "history",
        "detailed_description",
    } <= BekendmakingenSensor._unrecorded_attributes

    # No debug file without debug logging; cache file written.
    comp = os.path.dirname(BekendmakingenCoordinator.__module__.replace(".", "/"))
    assert not any(
        f.startswith("bekendmakingen_debug")
        for f in os.listdir(os.path.join(os.getcwd(), comp))
    )
    assert os.path.exists(hass.config.path(".bekendmakingen_utrecht.json"))


async def test_second_refresh_reuses_items(hass: HomeAssistant, aioclient_mock) -> None:
    mock_feed(aioclient_mock)
    entry = await setup_entry(hass)
    calls = aioclient_mock.call_count
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    assert aioclient_mock.call_count == calls + 1  # only the RSS feed again


async def test_max_items_and_filters(hass: HomeAssistant, aioclient_mock) -> None:
    mock_feed(aioclient_mock)
    entry = await setup_entry(hass, **{CONF_MAX_ITEMS: 10, CONF_FILTERS: ["verleend"]})
    items = hass.states.get("sensor.bekendmakingen_utrecht").attributes["items"]
    assert {i["category"] for i in items} == {"verleend"}
    assert hass.data[DOMAIN][entry.entry_id].max_items == 10


async def test_cache_boot_and_services(hass: HomeAssistant, aioclient_mock) -> None:
    mock_feed(aioclient_mock)
    entry = await setup_entry(hass)
    assert hass.services.has_service(DOMAIN, "refresh")
    assert hass.services.has_service(DOMAIN, "clear_files")
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)

    # Reload: starts from the cache file.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        len(hass.states.get("sensor.bekendmakingen_utrecht").attributes["items"]) == 6
    )

    await hass.services.async_call(DOMAIN, "clear_files", {}, blocking=True)
    assert not os.path.exists(hass.config.path(".bekendmakingen_utrecht.json"))
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_feed_error_keeps_data(hass: HomeAssistant, aioclient_mock) -> None:
    mock_feed(aioclient_mock)
    entry = await setup_entry(hass)
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(rf"^{BASE}/rss\?q=.*"), status=500)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.error_count == 1
    assert (
        len(hass.states.get("sensor.bekendmakingen_utrecht").attributes["items"]) == 6
    )
    assert (
        hass.states.get("sensor.bekendmakingen_utrecht_consecutive_errors").state == "1"
    )


async def test_geocode_fallback_and_cache(hass: HomeAssistant, aioclient_mock) -> None:
    mock_feed(aioclient_mock)
    entry = await setup_entry(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    aioclient_mock.get(
        PDOK_URL,
        json={
            "response": {"docs": [{"centroide_ll": "POINT(5.04374527 52.09583428)"}]}
        },
    )
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    session = async_get_clientsession(hass)
    before = aioclient_mock.call_count
    point = await coordinator._async_geocode(
        session, "Van der Vlugtsingel 7 3544LA Utrecht"
    )
    assert point == (52.095834, 5.043745)
    again = await coordinator._async_geocode(
        session, "van der vlugtsingel 7 3544la utrecht"
    )
    assert again == point
    assert aioclient_mock.call_count == before + 1


def test_municipality_name() -> None:
    assert municipality_name("utrecht") == "Utrecht"
    assert municipality_name(" 's-Hertogenbosch ") == "'s-Hertogenbosch"
