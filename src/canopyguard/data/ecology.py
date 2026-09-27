from __future__ import annotations

from typing import Any


def classify_growth_habit(evt_name: str) -> str:
    """Classify Existing Vegetation Type into high-level forest growth habit."""
    name_lower = evt_name.lower()
    if "mixed" in name_lower:
        return "mixed_forest"
    if "hardwood" in name_lower or "deciduous" in name_lower or "oak" in name_lower:
        return "deciduous"
    if "pine" in name_lower or "conifer" in name_lower or "evergreen" in name_lower:
        return "coniferous"
    if "shrub" in name_lower or "chaparral" in name_lower:
        return "shrubland"
    if "grass" in name_lower or "herbaceous" in name_lower:
        return "herbaceous"
    return "other"


def parse_landfire_evt(response_json: dict[str, Any]) -> dict[str, Any]:
    """Parse the ArcGIS REST identify response into a normalized ecology record."""
    results = response_json.get("results", [])
    if not results:
        return {
            "evt_code": -1,
            "evt_name": "Unknown",
            "evt_phys": "Unknown",
            "growth_habit": "other",
        }

    first_match = results[0]
    attributes = first_match.get("attributes", {})

    evt_code_raw = attributes.get("EVT_Code", attributes.get("Value", -1))
    try:
        evt_code = int(evt_code_raw)
    except (ValueError, TypeError):
        evt_code = -1

    evt_name = str(attributes.get("EVT_Name", attributes.get("EVT_NAME", "Unknown")))
    evt_phys = str(attributes.get("EVT_PHYS", attributes.get("EVT_Phys", "Unknown")))
    growth_habit = classify_growth_habit(evt_name)

    return {
        "evt_code": evt_code,
        "evt_name": evt_name,
        "evt_phys": evt_phys,
        "growth_habit": growth_habit,
    }
