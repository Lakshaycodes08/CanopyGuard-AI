"""Offline tests for the forest and wire selection preflight."""

import numpy as np
import pandas as pd
import pytest

from canopyguard.evaluation.growth_gate import _check_fit_permission
from canopyguard.evaluation.growth_screen import (
    fold_saturation_shares,
    saturation_shares,
    selection_masks,
    wire_exclusion,
)


def test_wire_flags_join_by_cell_id_and_include_ten_metre_distance():
    archive = {
        "cell_id": np.array([30, 10, 20]),
        "wire_suspect": np.array([False, True, False]),
        "dist_to_line_m": np.array([10.0, 50.0, 9.9]),
    }
    excluded = wire_exclusion(np.array([10, 20, 30]), archive, 10.0)
    assert excluded["excluded"].tolist() == [True, True, False]
    assert excluded["wire_suspect"].tolist() == [True, False, False]
    assert excluded["within_line"].tolist() == [False, True, False]
    with pytest.raises(ValueError, match="missing"):
        wire_exclusion(np.array([10, 40]), archive, 10.0)


def test_loss_off_retains_loss_cells_but_keeps_fire_hansen_and_wire():
    frame = pd.DataFrame(
        {
            "vegetation_type": ["oak", "oak", "oak", "Urban Window", "shrub"],
            "broader_group": [
                "hardwood forest",
                "hardwood forest",
                "hardwood forest",
                "other",
                "shrub",
            ],
            "overlap_disputed": [False] * 5,
            "label_change_valid": [True] * 5,
            "canopy_at_start": [True] * 5,
            "vegetation_known": [True] * 5,
            "hansen_valid": [True] * 5,
            "burned_2013_2022": [False, False, True, False, False],
            "hansen_loss": [False] * 5,
            "near_line": [False] * 5,
            "p95_wire_excluded": [False] * 5,
            "lidar_loss": [False, True, False, False, False],
        }
    )
    cfg = {
        "excluded_map_classes": ["Urban Window"],
        "forest_groups": ["hardwood forest"],
    }
    masks = selection_masks(frame, cfg)
    assert masks["forest_loss_on"].tolist() == [True, False, False, False, False]
    assert masks["forest_loss_off"].tolist() == [True, True, False, False, False]
    assert masks["all_loss_off"].tolist() == [True, True, False, False, True]


def test_saturation_is_per_class_after_selection():
    frame = pd.DataFrame({"vegetation_type": ["oak", "oak", "pine"]})
    shares = saturation_shares(
        frame, np.array([10.0, 25.0, 30.0]), {"oak": 25, "pine": 40}
    )
    assert shares["oak"]["share"] == 0.5
    assert shares["pine"]["share"] == 0.0


def test_posthoc_rule_allows_reviewed_literature_exceedance_but_requires_source():
    settings = {
        "saturation_review_fraction": 0.005,
        "source_review_confirmed": True,
        "reviewer_spot_check": {
            "reviewer": "test reviewer",
            "reviewer_type": "ai",
            "session": "test session",
            "review_window_utc": "2026-10-15T09:54:00Z/2026-10-15T10:04:00Z",
            "commit": "a" * 40,
            "scope": "A-rule code",
            "independence_limit": "reviewer proposed rule",
            "human_review": "pending",
        },
    }
    shares = {"oak": {"A_m": 25, "share": 0.006}}
    _check_fit_permission(settings, shares)
    shares["eucalyptus"] = {"A_m": None, "share": None}
    with pytest.raises(ValueError, match="eucalyptus"):
        _check_fit_permission(settings, shares)


def test_fit_permission_requires_review_provenance_and_keeps_human_status_distinct():
    review = {
        "reviewer": "Claude Opus 5",
        "reviewer_type": "ai",
        "session": "session-id",
        "review_window_utc": "2026-10-15T09:54:00Z/2026-10-15T10:04:00Z",
        "commit": "a" * 40,
        "scope": "A-rule code",
        "independence_limit": "reviewer proposed rule",
        "human_review": "pending",
    }
    settings = {"source_review_confirmed": True, "reviewer_spot_check": review}
    shares = {"oak": {"A_m": 25}}
    _check_fit_permission(settings, shares)
    with pytest.raises(ValueError, match="spot-check needs"):
        _check_fit_permission({**settings, "reviewer_spot_check": None}, shares)
    with pytest.raises(ValueError, match="cannot certify human review"):
        _check_fit_permission(
            {**settings, "reviewer_spot_check": {**review, "human_review": "complete"}},
            shares,
        )


def test_fold_exceedance_uses_each_held_out_cells_training_a():
    frame = pd.DataFrame({"vegetation_type": ["oak", "oak", "pine"]})
    shares = fold_saturation_shares(
        frame, np.array([21.0, 23.0, 18.0]), np.array([22.0, 22.0, 30.0])
    )
    assert shares["oak"]["at_or_above_A"] == 1
    assert shares["oak"]["share"] == 0.5
    assert shares["pine"]["share"] == 0.0
