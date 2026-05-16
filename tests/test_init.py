"""Universal test for Home Assistant integrations."""

import os
import importlib


async def test_domain_name():
    """Dynamically test that the DOMAIN constant matches the folder name."""
    # 1. Find the custom_components folder
    base_dir = os.path.dirname(os.path.dirname(__file__))
    components_dir = os.path.join(base_dir, "custom_components")

    # 2. Look inside to find the name of your integration (e.g., ndw_verkeer)
    integration_folders = [
        f
        for f in os.listdir(components_dir)
        if os.path.isdir(os.path.join(components_dir, f))
    ]

    # 3. Make sure we found exactly one integration
    assert len(integration_folders) == 1, (
        "Could not find exactly one integration folder"
    )
    dynamic_domain = integration_folders[0]

    # 4. Magically import the const.py file from that specific folder
    const_module = importlib.import_module(f"custom_components.{dynamic_domain}.const")

    # 5. Verify the DOMAIN constant matches the folder name!
    assert const_module.DOMAIN == dynamic_domain
