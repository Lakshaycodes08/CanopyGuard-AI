import numpy as np
import pandas as pd
import pytest

from canopyguard.forecasting.region_transfer import (
    distance_to_box,
    far_from_other_regions,
    region_codes,
    stack_regions,
)


def test_distance_to_box_is_zero_inside_and_euclidean_outside():
    box = (0.0, 0.0, 10.0, 10.0)
    east = np.array([5.0, 13.0, 13.0])
    north = np.array([5.0, 5.0, 14.0])
    assert distance_to_box(east, north, box).tolist() == [0.0, 3.0, 5.0]


def test_rows_near_another_region_are_not_scored():
    table = pd.DataFrame(
        {"x": [5.0, 12.0, 50.0], "y": [5.0, 5.0, 5.0], "region": ["a", "b", "b"]}
    )
    boxes = {"a": (0.0, 0.0, 10.0, 10.0), "b": (11.0, 0.0, 60.0, 10.0)}
    keep = far_from_other_regions(table, boxes, buffer_m=5.0)
    assert keep.tolist() == [True, False, True]


def test_absent_class_columns_become_zero_not_missing():
    left = pd.DataFrame({"eco_oak": [1.0], "ndvi_mean": [0.5]})
    right = pd.DataFrame({"ndvi_mean": [0.6]})
    stacked = stack_regions({"left": left, "right": right})
    assert stacked.loc[1, "eco_oak"] == 0.0
    assert stacked["region"].tolist() == ["left", "right"]


def test_region_codes_follow_the_name_order():
    table = pd.DataFrame({"region": ["b", "a", "b"]})
    assert region_codes(table, ["a", "b"]).tolist() == [1, 0, 1]
    with pytest.raises(KeyError):
        region_codes(pd.DataFrame({"region": ["c"]}), ["a", "b"])
