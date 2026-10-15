"""Offline checks for official-map grouping and the ambiguous-cell rule."""

import numpy as np
from shapely.geometry import box

from canopyguard.data.sonoma_veg import assign_types, broad_group


def test_broad_group_uses_source_lifeform_and_dominant_named_class():
    assert broad_group(
        "Sequoia sempervirens Alliance", "Mixed Conifer-Hardwood Forest"
    ) == ("conifer forest")
    assert broad_group(
        "Quercus garryana Alliance", "Mixed Conifer-Hardwood Forest"
    ) == ("hardwood forest")
    assert broad_group("Baccharis pilularis Alliance", "Shrub") == "shrub"
    assert broad_group("California Grassland", "Herbaceous") == "grass"
    assert broad_group("Developed", "Developed") == "other"


def test_boundary_and_overlap_are_uncertain_and_small_types_pool():
    polygons = [box(0, 0, 10, 10), box(10, 0, 20, 10), box(0, 0, 10, 10)]
    table = assign_types(
        np.array([5, 15, 10, 30], dtype=float),
        np.array([5, 5, 5, 5], dtype=float),
        polygons,
        np.array(["oak", "redwood", "overlap"]),
        np.array(["hardwood forest", "conifer forest", "other"]),
        np.array([1, 2, 3]),
        chunk_size=2,
        pool_below_n=2,
    )
    assert table["vegetation_type"].tolist() == [
        "uncertain",
        "redwood",
        "uncertain",
        "uncertain",
    ]
    assert table["model_group"].tolist() == [
        "uncertain",
        "group:conifer forest",
        "uncertain",
        "uncertain",
    ]
    assert table["map_object_id"].tolist() == [-1, 2, -1, -1]
