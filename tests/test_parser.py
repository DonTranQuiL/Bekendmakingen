"""Parsing against real Officiële Bekendmakingen records (tests/fixtures)."""

from __future__ import annotations

import pytest

from custom_components.bekendmakingen import parser

from .conftest import fixture


def _item(rid: str, published="Tue, 13 Oct 2026 00:00:00 +0200") -> dict:
    return parser.build_item(
        {
            "title": f"{rid} : Utrecht",
            "link": f"https://zoek.officielebekendmakingen.nl/{rid}.html",
            "summary": "",
            "published": published,
        },
        parser.parse_metadata(fixture(f"{rid}.meta.xml")),
        parser.parse_details(fixture(f"{rid}.xml")),
    )


def test_rd_to_wgs84_reference_points() -> None:
    # Amersfoort origin and the PDOK result for Van der Vlugtsingel 7, Utrecht.
    assert parser.rd_to_wgs84(155000, 463000) == pytest.approx(
        (52.155174, 5.387206), abs=1e-5
    )
    lat, lon = parser.rd_to_wgs84(131460, 456450)
    assert lat == pytest.approx(52.09583, abs=2e-4)
    assert lon == pytest.approx(5.04375, abs=2e-4)


def test_permit_with_polygon_address_case_and_deadline() -> None:
    item = _item("gmb-2026-477883")
    assert item["id"] == "gmb-2026-477883"
    assert item["title"].startswith(
        "Verleende Omgevingsvergunning, het plaatsen van een dakkapel"
    )
    assert item["category"] == "verleend"
    assert item["rubriek"] == "omgevingsvergunning"
    assert item["address"] == "Van der Vlugtsingel 7"
    assert item["postcode"] == "3544LA"
    assert item["latitude"] == pytest.approx(52.0958, abs=5e-4)
    assert item["longitude"] == pytest.approx(5.0437, abs=5e-4)
    assert item["geo_source"] == "metadata"
    assert item["case_number"] == "GU-Z2026-0067421"
    assert item["deadline"] == "2026-11-20"
    assert item["published"] == "2026-10-13T00:00:00+02:00"
    assert item["date"] == "2026-10-13"
    assert item["summary"].startswith("Toelichting: het plaatsen van een dakkapel")
    assert "Bezwaar maken" in item["detailed_description"]
    assert "• de reden van uw bezwaar" in item["detailed_description"]
    assert item["inzage_url"].startswith("https://jeleefomgeving.nl/")


def test_traffic_decision_point_and_street() -> None:
    item = _item("gmb-2026-477160")
    assert item["category"] == "verkeer"
    assert item["address"] == "Paul Citroenstraat"  # label 'Punt 1' is ignored
    assert item["postcode"] is None
    assert item["latitude"] == pytest.approx(52.0969, abs=1e-3)
    assert item["case_number"] is None
    assert item["deadline"] is None


def test_multilinestring_center() -> None:
    item = _item("gmb-2026-478002")
    assert item["latitude"] == pytest.approx(52.0876, abs=1e-3)
    assert item["longitude"] == pytest.approx(5.0537, abs=1e-3)


def test_kerkrade_and_groningen_records() -> None:
    kerk = _item("gmb-2026-478109")
    assert (kerk["address"], kerk["postcode"]) == ("Akerstraat 10", "6466HH")
    assert kerk["case_number"] == "Z2026-00000697"
    assert kerk["category"] == "verleend"
    gron = _item("gmb-2026-476676")
    assert gron["category"] == "aanvragen"
    assert gron["case_number"] == "GRN-00038131"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Aanvraag omgevingsvergunning voor Dorpsstraat 1", "aanvragen"),
        ("Verleende omgevingsvergunning Kerkstraat 2", "verleend"),
        ("Geweigerde omgevingsvergunning", "geweigerd"),
        ("Verkeersbesluit parkeerplaats", "verkeer"),
        ("Melding Activiteitenbesluit", "meldingen"),
        ("Subsidieregeling cultuur 2026", "overig"),
    ],
)
def test_categorize(text: str, expected: str) -> None:
    assert parser.categorize(text) == expected


def test_deadline_from_text() -> None:
    text = "Het bezwaarschrift moet uiterlijk 3 december 2026 ingediend zijn."
    assert parser.parse_deadline(None, text) == "2026-12-03"
    assert parser.parse_deadline("2026-11-20", text) == "2026-11-20"
    assert parser.parse_deadline(None, "binnen zes weken") is None


def test_helpers() -> None:
    assert parser.clean_text("<p>A&amp;B <b>c</b></p>") == "A&B c"
    assert parser.record_id("https://x/gmb-2026-1.html") == "gmb-2026-1"
    assert parser.parse_pdok_point({"centroide_ll": "POINT(5.04 52.09)"}) == (
        52.09,
        5.04,
    )
    assert parser.parse_pdok_point({}) is None
    assert parser.geometry_center(None) is None
    assert parser.geometry_center("POINT(5.1 52.1)") is None  # not RD
    assert parser.haversine_km(52.0907, 5.1214, 52.0907, 5.1214) == 0
    assert parser.parse_published("garbage", "2026-10-13") == "2026-10-13"
    assert parser.parse_metadata("<broken") == {}
    assert parser.parse_details("<broken") == ""
    assert parser.parse_address("geen adres") == (None, None)
