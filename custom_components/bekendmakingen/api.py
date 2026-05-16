import logging
import aiohttp
import feedparser
import asyncio

_LOGGER = logging.getLogger(__name__)


class BekendmakingenApiClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_get_data(self, url: str) -> list[dict]:
        """Fetch and parse the RSS feed."""
        try:
            async with self._session.get(url) as response:
                response.raise_for_status()
                xml_data = await response.text()

                # Use a thread for feedparser since it's blocking
                feed = await asyncio.to_thread(feedparser.parse, xml_data)

                announcements = []
                for entry in feed.entries[:5]:  # Limit to latest 5
                    announcements.append(
                        {
                            "title": entry.title,
                            "link": entry.link,
                            "published": entry.published
                            if hasattr(entry, "published")
                            else None,
                            "summary": entry.summary
                            if hasattr(entry, "summary")
                            else "",
                        }
                    )
                return announcements
        except Exception as err:
            _LOGGER.error("Error fetching RSS feed: %s", err)
            return []
