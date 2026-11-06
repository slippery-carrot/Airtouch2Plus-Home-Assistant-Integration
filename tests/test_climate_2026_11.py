"""Check the climate integration's Home Assistant 2026.11 API migration.

These static checks deliberately avoid importing Home Assistant so they can run
in a lightweight environment; runtime behaviour still needs an HA test.
"""

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIMATE = ROOT / "custom_components/airtouch2plus_enhanced/Airtouch2PlusClimateEntity.py"


def test_climate_temperature_properties_use_native_api():
    tree = ast.parse(CLIMATE.read_text(encoding="utf-8"))
    entity = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Airtouch2PlusClimateEntity"
    )
    methods = {
        node.name for node in entity.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    attributes = {
        target.id for node in entity.body if isinstance(node, ast.AnnAssign)
        for target in [node.target] if isinstance(target, ast.Name)
    }

    assert {"native_current_temperature", "native_target_temperature"} <= methods
    assert {"current_temperature", "target_temperature"} .isdisjoint(methods)
    assert "_attr_native_temperature_unit" in attributes
    assert "_attr_temperature_unit" not in attributes


def test_temperature_constants_import_from_homeassistant_const():
    tree = ast.parse(CLIMATE.read_text(encoding="utf-8"))
    imported = {
        node.module: {alias.name for alias in node.names}
        for node in tree.body if isinstance(node, ast.ImportFrom)
    }
    assert {"UnitOfTemperature", "ATTR_TEMPERATURE", "PRECISION_WHOLE"} <= imported["homeassistant.const"]
    assert "UnitOfTemperature" not in imported["homeassistant.components.climate"]


def test_marketplace_requires_ha_2026_11():
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs["homeassistant"] == "2026.11.0"
