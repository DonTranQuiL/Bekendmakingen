"""Build card test data from a real (mocked) Bekendmakingen setup."""

from __future__ import annotations

import json
from datetime import date, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import UTRECHT_HOME

MAIN = "sensor.bekendmakingen_utrecht"
DETAIL_ID = "gmb-2026-477883"
# Days ago per item position: two today, one yesterday, one this week, two older.
AGES = [0, 0, 1, 3, 10, 20]


async def card_data(hass: HomeAssistant, entry) -> dict:
    ent_reg = er.async_get(hass)
    entities, states = {}, {}
    for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        entities[entity.entity_id] = {
            "entity_id": entity.entity_id,
            "device_id": entity.device_id,
            "platform": entity.platform,
        }
        states[entity.entity_id] = json.loads(
            json.dumps(hass.states.get(entity.entity_id).as_dict(), default=str)
        )
    today = date.today()
    items = states[MAIN]["attributes"]["items"]
    # Detail item first so it is "today" and new.
    items.sort(key=lambda i: i["id"] != DETAIL_ID)
    for item, age in zip(items, AGES, strict=False):
        day = today - timedelta(days=age)
        item["published"] = f"{day.isoformat()}T00:00:00"
        item["date"] = day.isoformat()
    items[0]["deadline"] = (today + timedelta(days=5)).isoformat()
    states[MAIN]["attributes"]["history"] = items[1:]
    return {
        "states": states,
        "entities": entities,
        "home": list(UTRECHT_HOME),
        "main": MAIN,
        "detail_id": DETAIL_ID,
        "status": f"{MAIN}_last_update_status",
        "errors": f"{MAIN}_consecutive_errors",
    }
