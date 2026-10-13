"""Run the dashboard card in headless Chrome against real entity states.

Skipped when no Chrome/Chromium is installed (GitHub's Ubuntu runners have one).
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml
from homeassistant.core import HomeAssistant

from custom_components.bekendmakingen.const import CARD_FILENAME, DOMAIN

from .card_data import card_data
from .test_integration import mock_feed, setup_entry

ROOT = Path(__file__).parent.parent
CARD = ROOT / "custom_components" / DOMAIN / "frontend" / CARD_FILENAME
HARNESS = Path(__file__).parent / "card" / "harness.js"
CHROME = next(
    (
        shutil.which(n)
        for n in (
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
        )
        if shutil.which(n)
    ),
    None,
)


def test_card_calls_only_existing_services() -> None:
    services = yaml.safe_load((CARD.parent.parent / "services.yaml").read_text("utf-8"))
    calls = re.findall(
        r'callService\("bekendmakingen", "(\w+)"', CARD.read_text("utf-8")
    )
    assert calls == ["refresh"]
    assert set(calls) <= set(services)


def test_card_registered_with_version() -> None:
    from custom_components.bekendmakingen.const import VERSION

    assert f'const CARD_VERSION = "{VERSION}"' in CARD.read_text("utf-8")


def run_card(data: dict) -> dict:
    page = (
        "<!doctype html><html><head><meta charset='utf-8'></head><body>"
        f"<script type='application/json' id='states'>{json.dumps(data).replace('</', '<\\/')}</script>"
        "<pre id='out'></pre>"
        f"<script type='module'>{CARD.read_text('utf-8')}\n{HARNESS.read_text('utf-8')}</script>"
        "</body></html>"
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "card.html"
        path.write_text(page, "utf-8")
        out = subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                f"--user-data-dir={tmp}/profile",
                "--window-size=1200,900",
                "--virtual-time-budget=5000",
                "--dump-dom",
                path.as_uri(),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        ).stdout
    match = re.search(r'<pre id="out">(.*?)</pre>', out, re.DOTALL)
    assert match, out[-2000:]
    return json.loads(html.unescape(match.group(1)))


@pytest.mark.skipif(CHROME is None, reason="no Chrome/Chromium installed")
async def test_card_in_browser(hass: HomeAssistant, aioclient_mock) -> None:
    mock_feed(aioclient_mock)
    entry = await setup_entry(hass)
    data = await card_data(hass, entry)
    result = await hass.async_add_executor_job(run_card, data)
    c = result["checks"]
    assert result["errors"] == [], result["errors"]
    assert c["title"] == "Bekendmakingen Utrecht"
    assert c["status_ok"] is True
    assert c["counters"] == {
        "aanvragen": 0,
        "verleend": 2,
        "geweigerd": 0,
        "verkeer": 4,
        "meldingen": 0,
        "overig": 0,
    }
    assert c["groups"] == ["Vandaag", "Gisteren", "Deze week", "Eerder"]
    assert c["rows"] == 6
    assert c["new_rows"] == 2
    assert c["newbadge"] == "2 nieuw"
    assert c["pins"] == 6
    assert c["home"] == 1
    assert c["bad_text"] == []
    assert c["deadline_meta"] >= 1
    assert c["renders_same"] == 0
    assert c["rows_verkeer"] == 4
    assert c["verkeer_pressed"] == "true"
    assert c["rows_today"] == 2
    assert c["clear_shown"] is True
    assert c["rows_after_clear"] == 6
    assert c["rows_search"] == 1
    assert c["search_focus"] is True
    assert c["search_kept"] == "vlugtsingel"
    assert c["modal"] is True
    assert c["modal_title"].startswith("Verleende Omgevingsvergunning")
    assert c["modal_facts"][0] == "Reageren / bezwaar tot"
    assert "Kenmerk" in c["modal_facts"]
    assert "nog 5 dagen" in c["modal_deadline"]
    assert c["modal_links"][0].startswith("https://zoek.officielebekendmakingen.nl")
    assert len(c["modal_links"]) == 3
    assert c["modal_bullets"] >= 3
    assert c["modal_closed"] is True
    assert c["new_after_open"] == 1
    assert c["new_after_seen"] == 0
    assert c["badge_after_seen"] is False
    assert c["refresh_call"] == {"domain": DOMAIN, "service": "refresh", "data": {}}
    assert "boom <b>bold</b>" in c["toast"]
    assert c["toast_markup"] == 0
    assert c["xss_nodes"] == 0
    assert c["xss_link"] == 0
    assert c["xss_fired"] == 0
    assert c["legacy_rows"] == 6
    assert c["legacy_overig"] == 6
    assert c["not_found"] is True
    assert c["no_entity"] is True
    assert c["err_status"] == "3× mislukt"
    assert c["bad_config"] == "rejected"
    assert c["bad_entity"] == "rejected"
    assert c["compact"] == {"map": False, "counters": False, "size": 5}
    assert c["preset_rows"] == 1
    assert c["stub"] == {"entity": data["main"]}
    assert c["editor_fields"] == [
        "entity",
        "title",
        "show_map",
        "show_counters",
        "show_search",
        "compact",
        "categories",
        "max_items",
        "new_hours",
        "max_distance_km",
    ]
    assert c["editor_label"] == "Kaart tonen"
    assert c["editor_config"] == {"entity": data["main"], "compact": True}
    assert c["registered"] == 1
