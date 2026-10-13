"""Pure parsing helpers for Officiële Bekendmakingen records.

Everything here is synchronous and side-effect free so it can be unit tested
against real records (see tests/fixtures).
"""

from __future__ import annotations

import html
import math
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from typing import Any

CATEGORIES = ("aanvragen", "verleend", "geweigerd", "verkeer", "meldingen", "overig")

_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "geweigerd",
        ("geweigerd", "weigering", "afgewezen", "buiten behandeling"),
    ),
    (
        "verleend",
        ("verleend", "verleende", "toestemming omgevingsvergunning"),
    ),
    (
        "aanvragen",
        ("aanvraag", "ingediende", "ontvangen aanvraag", "aangevraagd"),
    ),
    (
        "verkeer",
        ("verkeersbesluit", "verkeersmaatregel", "parkeer", "rvv", "oplaadpaal"),
    ),
    (
        "meldingen",
        ("melding", "sloopmelding"),
    ),
)

_MONTHS = {
    "januari": 1,
    "februari": 2,
    "maart": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "augustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}

_POSTCODE = re.compile(r"\b(\d{4})\s?([A-Z]{2})\b")
_ADDRESS = re.compile(
    r"([A-Z][A-Za-zÀ-ÿ'.\- ]{2,60}?\s\d{1,5}(?:\s?[a-zA-Z]{1,2}\b)?(?:-\d{1,5})?)"
    r",?\s*(\d{4}\s?[A-Z]{2})"
)
_CASE = re.compile(
    r"\b([A-Z]{1,6}-?Z?\d{4}-\d{3,10}|Z\d{4}-\d{3,10}|[A-Z]{2,5}-\d{4,10})\b"
)
_DEADLINE = re.compile(
    r"(?:uiterlijk|tot en met|t/m|voor|vóór)\s+(?:\w+dag\s+)?(\d{1,2})\s+"
    r"(januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|"
    r"november|december)\s+(\d{4})",
    re.IGNORECASE,
)
_TAGS = re.compile(r"<[^>]+>")


def clean_text(value: str | None) -> str:
    """Strip HTML tags/entities and collapse whitespace."""
    if not value:
        return ""
    return " ".join(html.unescape(_TAGS.sub(" ", value)).split())


def record_id(link: str) -> str:
    """'https://…/gmb-2026-477883.html' -> 'gmb-2026-477883'."""
    tail = link.rstrip("/").rsplit("/", 1)[-1]
    return tail.removesuffix(".html").removesuffix(".xml")


def categorize(text: str, rubriek: str = "") -> str:
    """Map a publication to one of CATEGORIES (first match wins)."""
    full = f"{text} {rubriek}".lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(k in full for k in keywords):
            return category
    return "overig"


def parse_metadata(xml_text: str) -> dict[str, Any]:
    """Parse a metadata.xml record into a flat dict (first value per name).

    DC.type appears twice (Rubriek and Informatietype); the Rubriek one is
    returned as 'rubriek'.
    """
    out: dict[str, Any] = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for el in root.iter():
        if not el.tag.endswith("metadata"):
            continue
        name = el.get("name")
        content = el.get("content")
        if not name or content is None:
            continue
        if name == "DC.type" and el.get("scheme") == "OVERHEIDop.Rubriek":
            out["rubriek"] = content
            continue
        out.setdefault(name, content)
    return out


def parse_details(xml_text: str) -> str:
    """Readable text of a publication XML: paragraphs and bullets, no footer."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ""
    tekst = root.find(".//tekst")
    if tekst is None:
        return ""
    lines: list[str] = []
    for child in tekst:
        if child.tag == "al":
            text = " ".join("".join(child.itertext()).split())
            if "Waarom publiceert de gemeente dit bericht?" in text:
                break
            if text and text.lower() not in (
                "aanvraag omgevingsvergunning",
                "verleende omgevingsvergunning",
            ):
                lines.append(text)
        elif child.tag == "lijst":
            for li in child.findall("./li"):
                parts = [
                    " ".join("".join(al.itertext()).split())
                    for al in li.findall("./al")
                ]
                text = " ".join(p for p in parts if p)
                if text:
                    lines.append(f"• {text}")
    return "\n".join(lines).strip()


def rd_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Rijksdriehoek (EPSG:28992) to WGS84 lat/lon (approximation, < 1 m)."""
    dx = (x - 155000) * 1e-5
    dy = (y - 463000) * 1e-5
    lat = (
        3235.65389 * dy
        - 32.58297 * dx**2
        - 0.2475 * dy**2
        - 0.84978 * dx**2 * dy
        - 0.0655 * dy**3
        - 0.01709 * dx**2 * dy**2
        - 0.00738 * dx
        + 0.0053 * dx**4
        - 0.00039 * dx**2 * dy**3
        + 0.00033 * dx**4 * dy
        - 0.00012 * dx * dy
    )
    lon = (
        5260.52916 * dx
        + 105.94684 * dx * dy
        + 2.45656 * dx * dy**2
        - 0.81885 * dx**3
        + 0.05594 * dx * dy**3
        - 0.05607 * dx**3 * dy
        + 0.01199 * dy
        - 0.00256 * dx**3 * dy**2
        + 0.00128 * dx * dy**4
        + 0.00022 * dy**2
        - 0.00022 * dx**2
        + 0.00026 * dx**5
    )
    return round(52.15517440 + lat / 3600, 6), round(5.38720621 + lon / 3600, 6)


def geometry_center(wkt: str | None) -> tuple[float, float] | None:
    """Centre (lat, lon) of any WKT geometry in RD coordinates.

    Uses the mean of the vertices (closing vertex of rings counted once),
    which is plenty for a map pin.
    """
    if not wkt:
        return None
    pairs = re.findall(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", wkt)
    if not pairs:
        return None
    pts = [(float(a), float(b)) for a, b in pairs]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    x = sum(p[0] for p in pts) / len(pts)
    y = sum(p[1] for p in pts) / len(pts)
    if not (0 < x < 300000 and 280000 < y < 630000):
        return None  # not RD
    return rd_to_wgs84(x, y)


def parse_address(*texts: str) -> tuple[str | None, str | None]:
    """First 'Street 12a, 1234AB' found; returns (address, postcode)."""
    for text in texts:
        if not text:
            continue
        m = _ADDRESS.search(text)
        if m:
            street = m.group(1).strip(" ,")
            street = re.sub(
                r"^(?:voor|op|aan|locatie|de locatie)\s+",
                "",
                street,
                flags=re.IGNORECASE,
            )
            return street, m.group(2).replace(" ", "")
    for text in texts:
        if text:
            m = _POSTCODE.search(text)
            if m:
                return None, m.group(1) + m.group(2)
    return None, None


def parse_street(title: str) -> str | None:
    """Street name in verkeersbesluit titles: '2026-10-11 Paul Citroenstraat, …'."""
    m = re.match(r"^\d{4}-\d{2}-\d{2}\s+([^,]{3,60}),", title or "")
    return m.group(1).strip() if m else None


def parse_case_number(*texts: str) -> str | None:
    for text in texts:
        if text:
            m = _CASE.search(text)
            if m:
                return m.group(1)
    return None


def parse_deadline(meta_value: str | None, text: str) -> str | None:
    """ISO date of the objection/response deadline, if one can be found."""
    if meta_value and re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta_value.strip()):
        return meta_value.strip()
    m = _DEADLINE.search(text or "")
    if m:
        try:
            return date(
                int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1))
            ).isoformat()
        except ValueError:
            return None
    return None


def parse_published(raw: str | None, fallback_date: str | None = None) -> str | None:
    """RSS pubDate (RFC 822) -> ISO 8601 with offset."""
    if raw:
        try:
            return parsedate_to_datetime(raw).isoformat()
        except (TypeError, ValueError):
            pass
    if fallback_date:
        try:
            return datetime.fromisoformat(fallback_date).date().isoformat()
        except ValueError:
            return None
    return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


def parse_pdok_point(doc: dict) -> tuple[float, float] | None:
    """PDOK Locatieserver 'centroide_ll': 'POINT(lon lat)' -> (lat, lon)."""
    m = re.match(r"POINT\((-?[\d.]+) (-?[\d.]+)\)", str(doc.get("centroide_ll", "")))
    if not m:
        return None
    return round(float(m.group(2)), 6), round(float(m.group(1)), 6)


def build_item(
    entry: dict[str, Any], meta: dict[str, Any], details: str
) -> dict[str, Any]:
    """Combine an RSS entry, its metadata and its text into one item dict.

    entry: {'title', 'link', 'summary', 'published'} straight from the feed.
    """
    link = entry.get("link", "")
    summary = clean_text(entry.get("summary"))
    title = (
        clean_text(meta.get("DC.title")) or summary or clean_text(entry.get("title"))
    )
    published = parse_published(entry.get("published"), meta.get("DCTERMS.available"))
    label = meta.get("OVERHEIDop.geometrieLabel") or ""
    if re.fullmatch(r"(?i)punt \d+|vlak \d+|lijn \d+", label.strip()):
        label = ""
    address, postcode = parse_address(label, title, summary)
    if not address and not postcode:
        address, postcode = parse_address(details[:600])
        if not address:
            postcode = None  # a bare postcode in the body is usually a PO box
    if not address:
        address = label or parse_street(title)
    center = geometry_center(meta.get("OVERHEIDop.geometrie"))
    abstract = clean_text(meta.get("DCTERMS.abstract"))
    try:
        dt = datetime.fromisoformat(published) if published else None
    except ValueError:
        dt = None
    return {
        "id": record_id(link),
        "title": title[:250],
        "link": link,
        "published": published,
        "date": dt.strftime("%Y-%m-%d") if dt else "Onbekend",
        "time": dt.strftime("%H:%M") if dt else "00:00",
        "category": categorize(f"{title} {summary}", meta.get("rubriek", "")),
        "rubriek": meta.get("rubriek"),
        "summary": abstract or summary,
        "detailed_description": details[:4000] or "Geen extra details beschikbaar.",
        "address": address or None,
        "postcode": postcode,
        "latitude": center[0] if center else None,
        "longitude": center[1] if center else None,
        "geo_source": "metadata" if center else None,
        "distance_km": None,
        "case_number": parse_case_number(
            meta.get("OVERHEIDop.referentienummer", ""), title, summary
        ),
        "deadline": parse_deadline(
            meta.get("OVERHEIDop.datumEindeReactietermijn"), details
        ),
        "inzage_url": meta.get("OVERHEIDop.terinzageleggingBG"),
        "schema": 2,
    }
