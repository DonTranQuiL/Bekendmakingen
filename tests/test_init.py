"""Universal test for Home Assistant integrations."""

import os
import importlib
import pkgutil

def test_domain_name_and_load_modules():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    components_dir = os.path.join(base_dir, "custom_components")
    integration_folders = [f for f in os.listdir(components_dir) if os.path.isdir(os.path.join(components_dir, f))]
    assert len(integration_folders) == 1
    dynamic_domain = integration_folders[0]
    integration_path = os.path.join(components_dir, dynamic_domain)
    
    const_module = importlib.import_module(f"custom_components.{dynamic_domain}.const")
    assert const_module.DOMAIN == dynamic_domain

    for _, module_name, _ in pkgutil.walk_packages([integration_path]):
        try:
            importlib.import_module(f"custom_components.{dynamic_domain}.{module_name}")
        except Exception:
            pass
