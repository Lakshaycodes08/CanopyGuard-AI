from __future__ import annotations

from canopyguard.data.ecology import classify_growth_habit, parse_landfire_evt


def test_classify_growth_habit() -> None:
    assert classify_growth_habit("Appalachian Oak-Hickory Forest") == "deciduous"
    assert classify_growth_habit("Southern Loblolly Pine Forest") == "coniferous"
    assert classify_growth_habit("Mixed Pine-Hardwood Forest") == "mixed_forest"
    assert classify_growth_habit("Coastal Shrubland") == "shrubland"
    assert classify_growth_habit("Agricultural Pasture") == "other"


def test_parse_landfire_evt() -> None:
    mock_response = {
        "results": [
            {
                "attributes": {
                    "EVT_Code": "2012",
                    "EVT_Name": "Southern Atlantic Coastal Hardwood Forest",
                    "EVT_PHYS": "Tree",
                },
            }
        ]
    }
    parsed = parse_landfire_evt(mock_response)
    assert parsed["evt_code"] == 2012
    assert "Hardwood" in parsed["evt_name"]
    assert parsed["growth_habit"] == "deciduous"


def test_parse_landfire_evt_empty() -> None:
    parsed = parse_landfire_evt({})
    assert parsed["evt_code"] == -1
    assert parsed["growth_habit"] == "other"
