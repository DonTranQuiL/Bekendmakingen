"""Data coordinator for Bekendmakingen."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.parse
from datetime import timedelta
from typing import Any

import aiohttp
import feedparser
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import parser
from .cache import BekendmakingenCache
from .const import (
    CONF_FILTERS,
    CONF_MAX_ITEMS,
    CONF_MUNICIPALITY,
    CONF_SCAN_INTERVAL,
    DEFAULT_MAX_ITEMS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_MAX_ITEMS,
    MIN_MAX_ITEMS,
    PDOK_URL,
    RECORD_BASE_URL,
)

_LOGGER = logging.getLogger(__name__)

# Be gentle with the government servers: a few parallel requests at most.
_PARALLEL = 4

_LEGACY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "aanvragen": (
        "aanvraag omgevingsvergunning",
        "ingediende aanvraag",
        "ontvangen aanvraag",
    ),
    "verleend": (
        "verleende omgevingsvergunning",
        "toestemming omgevingsvergunning",
        "vergunning verleend",
    ),
    "meldingen": ("sloopmelding", "melding", "kennisgeving"),
    "geweigerd": ("geweigerde omgevingsvergunning", "afgewezen vergunning"),
    "overig": ("verordening", "subsidie", "besluit", "protocol"),
}


def municipality_name(raw: str) -> str:
    """Name as used by the feed: keep user casing, capitalize all-lowercase."""
    raw = raw.strip()
    return raw.capitalize() if raw == raw.lower() else raw


class BekendmakingenCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Fetches the Gemeenteblad feed and enriches every item."""

    def __init__(self, hass, config_entry) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self.municipality = config_entry.data[CONF_MUNICIPALITY]
        query = (
            '(c.product-area=="officielepublicaties")and'
            '((w.publicatienaam=="Gemeenteblad")) AND '
            f'dt.creator=="{municipality_name(self.municipality)}"'
        )
        self.url = f"{RECORD_BASE_URL}/rss?q={urllib.parse.quote(query)}"

        self.cache = BekendmakingenCache(hass, self.municipality)
        self.geocode_path = hass.config.path(".bekendmakingen_geocode.json")
        self.geocode_cache: dict[str, list[float] | None] = {}

        self.last_data: list[dict[str, Any]] = []
        self.last_update_success_timestamp = None
        self.error_count = 0

        options = config_entry.options
        self.selected_filters = options.get(CONF_FILTERS, ["alles"])
        self.max_items = max(
            MIN_MAX_ITEMS,
            min(MAX_MAX_ITEMS, int(options.get(CONF_MAX_ITEMS, DEFAULT_MAX_ITEMS))),
        )
        scan_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(seconds=scan_interval),
        )

    # ------------------------------------------------------------------ filters
    def _should_keep_announcement(self, title: str, summary: str) -> bool:
        """Legacy keyword filter (kept so existing filter choices behave the same)."""
        filters = self.selected_filters
        if not filters or "alles" in filters:
            return True
        full_text = f"{title} {summary}".lower()
        if parser.categorize(full_text) in filters:
            return True
        return any(
            any(k in full_text for k in _LEGACY_KEYWORDS.get(f, ())) for f in filters
        )

    # -------------------------------------------------------------- debug file
    def _debug_path(self) -> str:
        return os.path.join(
            os.path.dirname(__file__), f"bekendmakingen_debug_{self.municipality}.txt"
        )

    def _write_debug_file_sync(self, debug_path: str, content: str) -> None:
        try:
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            _LOGGER.error("Could not write debug file: %s", e)

    def clear_debug_file(self) -> None:
        """Delete the debug text file if it exists."""
        path = self._debug_path()
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                _LOGGER.error("Error deleting debug file: %s", e)

    # --------------------------------------------------------------- geocoding
    def load_geocode_cache(self) -> None:
        try:
            with open(self.geocode_path, encoding="utf-8") as f:
                self.geocode_cache = json.load(f)
        except (OSError, ValueError):
            self.geocode_cache = {}

    def _save_geocode_cache(self) -> None:
        try:
            with open(self.geocode_path, "w", encoding="utf-8") as f:
                json.dump(self.geocode_cache, f)
        except OSError as e:
            _LOGGER.debug("Could not save geocode cache: %s", e)

    def clear_geocode_cache(self) -> None:
        self.geocode_cache = {}
        if os.path.exists(self.geocode_path):
            try:
                os.remove(self.geocode_path)
            except OSError:
                pass

    async def _async_geocode(self, session, query: str) -> tuple[float, float] | None:
        """PDOK Locatieserver lookup, cached (also negative results)."""
        key = query.lower()
        if key in self.geocode_cache:
            hit = self.geocode_cache[key]
            return (hit[0], hit[1]) if hit else None
        params = {"q": query, "rows": "1", "fl": "centroide_ll,weergavenaam,type"}
        point = None
        try:
            async with session.get(
                PDOK_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                resp.raise_for_status()
                docs = (await resp.json()).get("response", {}).get("docs", [])
                if docs:
                    point = parser.parse_pdok_point(docs[0])
        except Exception as err:
            _LOGGER.debug("PDOK geocode failed for %s: %s", query, err)
            return None  # don't cache transient errors
        self.geocode_cache[key] = list(point) if point else None
        return point

    # ----------------------------------------------------------------- fetching
    async def _async_text(self, session, url: str) -> str:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            return await resp.text()

    async def _async_enrich(self, session, sem, entry: dict[str, Any]) -> dict:
        rid = parser.record_id(entry["link"])
        meta: dict[str, Any] = {}
        details = ""
        async with sem:
            try:
                meta = parser.parse_metadata(
                    await self._async_text(
                        session, f"{RECORD_BASE_URL}/{rid}/metadata.xml"
                    )
                )
            except Exception as err:
                _LOGGER.debug("No metadata for %s: %s", rid, err)
            if entry["link"].endswith(".html"):
                try:
                    details = parser.parse_details(
                        await self._async_text(
                            session, entry["link"].removesuffix(".html") + ".xml"
                        )
                    )
                except Exception as err:
                    _LOGGER.debug("No details for %s: %s", rid, err)
        item = parser.build_item(entry, meta, details)
        if item["latitude"] is None and item["address"]:
            town = municipality_name(self.municipality)
            query = " ".join(x for x in (item["address"], item["postcode"], town) if x)
            point = await self._async_geocode(session, query)
            if point:
                item["latitude"], item["longitude"] = point
                item["geo_source"] = "pdok"
        return item

    def _add_distance(self, item: dict[str, Any]) -> dict[str, Any]:
        home_lat = self.hass.config.latitude
        home_lon = self.hass.config.longitude
        if item.get("latitude") is not None and home_lat is not None:
            item["distance_km"] = parser.haversine_km(
                home_lat, home_lon, item["latitude"], item["longitude"]
            )
        return item

    async def _async_update_data(self) -> list[dict[str, Any]]:
        _LOGGER.debug("Fetching Bekendmakingen RSS for %s", self.municipality)
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                self.url, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                xml = await response.text()
                status = response.status

            if _LOGGER.isEnabledFor(logging.DEBUG):
                await self.hass.async_add_executor_job(
                    self._write_debug_file_sync,
                    self._debug_path(),
                    f"FETCHED URL:\n{self.url}\n\nSTATUS CODE:\n{status}\n\n"
                    f"RAW DATA RETURNED:\n{xml}",
                )

            feed = await self.hass.async_add_executor_job(feedparser.parse, xml)
            entries: list[dict[str, Any]] = []
            for e in feed.entries:
                if len(entries) >= self.max_items:
                    break
                title = getattr(e, "title", "")
                summary = getattr(e, "summary", "")
                if not self._should_keep_announcement(title, summary):
                    continue
                entries.append(
                    {
                        "title": title,
                        "link": getattr(e, "link", ""),
                        "summary": summary,
                        "published": getattr(e, "published", None),
                    }
                )

            # Reuse already-enriched items; only fetch details for new ones.
            known = {i.get("id"): i for i in self.last_data if i.get("schema") == 2}
            sem = asyncio.Semaphore(_PARALLEL)
            todo = [e for e in entries if parser.record_id(e["link"]) not in known]
            fresh = await asyncio.gather(
                *(self._async_enrich(session, sem, e) for e in todo),
                return_exceptions=True,
            )
            by_id = dict(known)
            for entry, item in zip(todo, fresh, strict=True):
                if isinstance(item, BaseException):
                    _LOGGER.debug("Enrich failed for %s: %s", entry["link"], item)
                    item = parser.build_item(entry, {}, "")
                by_id[item["id"]] = item

            items = [
                self._add_distance(by_id[parser.record_id(e["link"])]) for e in entries
            ]
            if todo:
                await self.hass.async_add_executor_job(self._save_geocode_cache)
            if items:
                self.last_data = items
                await self.hass.async_add_executor_job(self.cache.save_cache, items)

            self.last_update_success_timestamp = dt_util.utcnow()
            self.error_count = 0
        except Exception as err:
            self.error_count += 1
            _LOGGER.error("Update failed for %s: %s", self.municipality, err)
        return self.last_data
