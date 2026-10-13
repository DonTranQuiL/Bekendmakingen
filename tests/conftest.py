"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
UTRECHT_HOME = (52.0907, 5.1214)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text("utf-8")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    return


# aiohttp's DNS resolver (pycares) starts a daemon cleanup thread the first time
# a channel is destroyed. Start it before any test so HA's lingering-thread
# check does not attribute it to whichever test happens to run first.
try:  # pragma: no cover - depends on the installed aiohttp extras
    import gc

    import pycares

    pycares.Channel()
    gc.collect()
except Exception:
    pass
