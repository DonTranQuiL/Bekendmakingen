import asyncio
import os
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import logging
import feedparser
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, CONF_MUNICIPALITY, CONF_FILTERS
from .cache import BekendmakingenCache

_LOGGER = logging.getLogger(__name__)

class BekendmakingenCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, config_entry):
        self.hass = hass
        self.municipality = config_entry.data[CONF_MUNICIPALITY]
        safe_municipality = self.municipality.capitalize()

        query = f'(c.product-area=="officielepublicaties")and((w.publicatienaam=="Gemeenteblad")) AND dt.creator=="{safe_municipality}"'
        safe_query = urllib.parse.quote(query)
        self.url = f"https://zoek.officielebekendmakingen.nl/rss?q={safe_query}"

        self.cache = BekendmakingenCache(hass, self.municipality)

        self.last_data = []
        self.last_update_success_timestamp = None
        self.error_count = 0

        self.selected_filters = config_entry.options.get(CONF_FILTERS, ["alles"])

        scan_interval = config_entry.options.get("scan_interval", 3600)
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=scan_interval)
        )

    def _should_keep_announcement(self, title, summary):
        if "alles" in self.selected_filters or not self.selected_filters:
            return True

        full_text = f"{title} {summary}".lower()

        if "aanvragen" in self.selected_filters and any(
            k in full_text
            for k in [
                "aanvraag omgevingsvergunning",
                "ingediende aanvraag",
                "ontvangen aanvraag",
            ]
        ):
            return True
        if "verleend" in self.selected_filters and any(
            k in full_text
            for k in [
                "verleende omgevingsvergunning",
                "toestemming omgevingsvergunning",
                "vergunning verleend",
            ]
        ):
            return True
        if "meldingen" in self.selected_filters and any(
            k in full_text for k in ["sloopmelding", "melding", "kennisgeving"]
        ):
            return True
        if "geweigerd" in self.selected_filters and any(
            k in full_text
            for k in ["geweigerde omgevingsvergunning", "afgewezen vergunning"]
        ):
            return True
        if "overig" in self.selected_filters and any(
            k in full_text for k in ["verordening", "subsidie", "besluit", "protocol"]
        ):
            return True

        return False

    def _write_debug_file_sync(self, debug_path, content):
        """Helper functie om het wegschrijven synchroon uit te voeren in een executor."""
        try:
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            _LOGGER.error("Could not write debug file: %s", e)

    async def _async_fetch_xml_details(self, session, link):
        """Asynchronously fetch the detailed XML and parse the inner contents."""
        if not link.endswith(".html"):
            return "Geen extra details beschikbaar."
            
        xml_link = link.replace(".html", ".xml")
        
        try:
            async with session.get(xml_link) as response:
                response.raise_for_status()
                xml_text = await response.text()
                
                root = ET.fromstring(xml_text)
                tekst_element = root.find(".//tekst")
                
                if tekst_element is None:
                    return "Geen detailtekst gevonden in de publicatie."
                    
                details = []
                for child in tekst_element:
                    if child.tag == "al":
                        text = "".join(child.itertext()).strip()
                        # Stop gathering information when we hit the standard boilerplate footer
                        if "Waarom publiceert de gemeente dit bericht?" in text:
                            break
                        
                        # Skip generic titles to keep the output clean
                        if text and text.lower() not in ["aanvraag omgevingsvergunning", "verleende omgevingsvergunning"]:
                            details.append(text)
                            
                    elif child.tag == "lijst":
                        for li in child.findall(".//li"):
                            li_text = "".join(li.itertext()).strip()
                            # Clean up weird spacing or newline characters from the bullet points
                            li_text = " ".join(li_text.split())
                            if li_text:
                                details.append(li_text)
                                
                return "\n".join(details).strip()
                
        except Exception as err:
            _LOGGER.error("Failed to fetch XML details for %s: %s", xml_link, err)
            return "Fout bij ophalen van details."

    async def _async_update_data(self):
        _LOGGER.debug("Fetching Bekendmakingen RSS for %s", self.municipality)
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(self.url) as response:
                response.raise_for_status()
                xml = await response.text()

                current_dir = os.path.dirname(__file__)
                debug_path = os.path.join(
                    current_dir, f"bekendmakingen_debug_{self.municipality}.txt"
                )
                debug_content = f"FETCHED URL:\n{self.url}\n\nSTATUS CODE:\n{response.status}\n\nRAW DATA RETURNED:\n{xml}"
                await self.hass.async_add_executor_job(
                    self._write_debug_file_sync, debug_path, debug_content
                )

                feed = await asyncio.to_thread(feedparser.parse, xml)

                announcements = []
                for entry in feed.entries:
                    if len(announcements) >= 10:
                        break

                    title = entry.title if hasattr(entry, "title") else ""
                    summary = entry.summary if hasattr(entry, "summary") else ""

                    if self._should_keep_announcement(title, summary):
                        raw_date = (
                            entry.published_parsed
                            if hasattr(entry, "published_parsed")
                            else None
                        )
                        formatted_date = (
                            datetime(*raw_date[:6]).strftime("%Y-%m-%d")
                            if raw_date
                            else "Onbekend"
                        )
                        formatted_time = (
                            datetime(*raw_date[:6]).strftime("%H:%M")
                            if raw_date
                            else "00:00"
                        )

                        announcements.append(
                            {
                                "title": title,
                                "link": entry.link,
                                "date": formatted_date,
                                "time": formatted_time,
                                "summary": summary,
                            }
                        )

                if announcements:
                    # Fire off concurrent requests to fetch the inner XML details for the top announcements
                    tasks = [self._async_fetch_xml_details(session, ann["link"]) for ann in announcements]
                    details_results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    for i, ann in enumerate(announcements):
                        detail = details_results[i]
                        if isinstance(detail, Exception):
                            ann["detailed_description"] = "Fout bij ophalen van details."
                        else:
                            ann["detailed_description"] = detail

                    self.last_data = announcements
                    await self.hass.async_add_executor_job(
                        self.cache.save_cache, announcements
                    )

                self.last_update_success_timestamp = dt_util.utcnow()
                self.error_count = 0
                return self.last_data
        except Exception as err:
            self.error_count += 1
            _LOGGER.error("Update failed for %s: %s", self.municipality, err)
            return self.last_data

    def clear_debug_file(self):
        """Deletes the debug text file if it exists."""
        current_dir = os.path.dirname(__file__)
        debug_path = os.path.join(
            current_dir, f"bekendmakingen_debug_{self.municipality}.txt"
        )
        if os.path.exists(debug_path):
            try:
                os.remove(debug_path)
                _LOGGER.debug("Deleted debug file: %s", debug_path)
            except Exception as e:
                _LOGGER.error("Error deleting debug file: %s", e)