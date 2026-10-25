"""E8 masking and uncertainty tests use tiny local arrays only."""

import numpy as np
import pandas as pd
import pytest

from canopyguard.evaluation.product_metrics import (
    _bootstrap_medians,
    aggregate_pairs,
    bootstrap_intervals,
    forest_map_stratum,
    height_strata,
    resolution_results,
    score_offsets,
    scores,
)
from canopyguard.evaluation.product_population import join_vegetation, quality_mask
from canopyguard.evaluation.product_report import render_report


def test_quality_mask_keeps_fire_and_loss_independent():
    labels = {
        "cell_id": np.array([10, 20, 30, 40]),
        "overlap_disputed": np.array([False, True, False, False]),
        "p95_end": np.array([4.0, 3.0, np.nan, 8.0]),
    }
    flags = {
        "cell_id": np.array([40, 10, 30]),
        "exclude_max_p95": np.array([True, False, False]),
    }
    mask, counts = quality_mask(labels, flags)
    assert mask.tolist() == [True, False, False, False]
    assert counts == {
        "label_cells": 4,
        "disputed_overlap": 1,
        "nonfinite_p95_after_overlap": 1,
        "wire_excluded_after_overlap_and_p95": 1,
        "before_product_nodata": 1,
    }
    with pytest.raises(ValueError, match="wire flag"):
        quality_mask(labels, {key: values[:-1] for key, values in flags.items()})


def test_2013_forest_classes_join_by_id_and_only_subset_primary_pairs():
    vegetation = pd.DataFrame(
        {
            "cell_id": [30, 10, 40, 20],
            "vegetation_type": ["shrub class", "oak class", "other", "pine class"],
            "broader_group": ["shrub", "hardwood forest", "other", "conifer forest"],
        }
    )
    joined = join_vegetation(np.array([10, 20, 30, 40]), vegetation)
    assert joined["broader_group"].tolist() == [
        "hardwood forest",
        "conifer forest",
        "shrub",
        "other",
    ]
    labels = {
        "p95_end": np.array([1.0, 2.0, 3.0, 4.0]),
        "x": np.array([5.0, 15.0, 25.0, 35.0]),
        "y": np.full(4, 5.0),
    }
    result = forest_map_stratum(
        np.array([3.0, 5.0, 100.0, 4.0]),
        labels,
        np.array([True, True, True, False]),
        joined["broader_group"],
        ["conifer forest", "hardwood forest"],
        {"block_size_m": 10, "bootstrap_draws": 40, "seed": 42},
        (0, 0),
    )
    assert result["pooled"]["cells"] == 2
    assert result["pooled"]["scores"]["mae_m"] == 2.5
    assert result["other_primary_cells"] == 1
    assert {name: row["cells"] for name, row in result["by_group"].items()} == {
        "conifer forest": 1,
        "hardwood forest": 1,
    }
    with pytest.raises(ValueError, match="cover every LiDAR cell"):
        join_vegetation(np.array([10, 20, 30, 50]), vegetation)


def test_four_scores_and_exact_block_weighted_median():
    assert scores([2.0, 4.0], [1.0, 2.0]) == {
        "mae_m": 1.5,
        "median_signed_error_m": 1.5,
        "mean_signed_error_m": 1.5,
        "rmse_m": np.sqrt(2.5),
    }
    medians = _bootstrap_medians(
        np.array([0.0, 2.0]),
        np.array([0, 1]),
        np.array([[1, 1], [2, 0], [0, 2]]),
    )
    assert medians.tolist() == [1.0, 0.0, 2.0]
    error = np.array([-3.0, 0.0, 1.0, 2.0, 9.0])
    blocks = np.array([0, 0, 1, 2, 2])
    draws = np.array([[1, 1, 1], [0, 3, 0], [2, 0, 1], [0, 0, 3]])
    expected = [np.median(np.repeat(error, draw[blocks])) for draw in draws]
    np.testing.assert_allclose(_bootstrap_medians(error, blocks, draws), expected)


def test_bootstrap_is_seeded_and_requires_two_blocks():
    paired = ([1.0, 2.0, 3.0, 4.0], [0.0, 0.0, 0.0, 0.0])
    first = bootstrap_intervals(*paired, [0, 0, 1, 1], 40, 42)
    second = bootstrap_intervals(*paired, [0, 0, 1, 1], 40, 42)
    assert first == second
    assert set(first) == set(scores(*paired))
    assert bootstrap_intervals(*paired, [0, 0, 0, 0], 40, 42) is None


def test_aggregation_uses_only_bins_with_half_of_possible_cells():
    x = np.array([5, 15, 25, 5, 15, 35, 45, 55, 35])
    y = np.array([5, 5, 5, 15, 15, 5, 5, 5, 15])
    product = np.arange(9, dtype=float)
    reference = product + 1
    p, r, centres, occupancy = aggregate_pairs(
        product,
        reference,
        x,
        y,
        30,
        {"resolution_m": 10, "aggregation_min_valid_fraction": 0.5},
        (0, 0),
    )
    assert p.tolist() == [2.0]
    assert r.tolist() == [3.0]
    assert centres.tolist() == [[15.0, 15.0]]
    assert occupancy.tolist() == [5]


def test_offsets_keep_one_common_mask_and_report_nodata_losses():
    labels = {
        "p95_end": np.zeros(3),
        "x": np.array([5.0, 15.0, 25.0]),
        "y": np.array([5.0, 5.0, 5.0]),
    }
    records = [
        {"product": np.array([1.0, 2.0, 3.0]), "alignment": {"offset_east_m": 0}},
        {"product": np.array([1.0, np.nan, 5.0]), "alignment": {"offset_east_m": 2}},
    ]
    settings = {
        "block_size_m": 10,
        "bootstrap_draws": 40,
        "seed": 42,
        "metrics": list(scores([1.0], [0.0])),
    }
    sensitivity, rows = score_offsets(
        records, np.ones(3, dtype=bool), labels, settings, (0, 0)
    )
    assert sensitivity["common_cells"] == 2
    assert sensitivity["score_ranges_m"]["mae_m"] == [2.0, 3.0]
    assert [row["nodata_cells_before_common_mask"] for row in rows] == [0, 1]


def test_fixed_resolution_and_height_strata():
    x = np.array([5, 15, 25, 5, 15, 35, 45, 55, 35], dtype=float)
    y = np.array([5, 5, 5, 15, 15, 5, 5, 5, 15], dtype=float)
    reference = np.arange(9, dtype=float)
    labels = {"p95_end": reference, "x": x, "y": y}
    settings = {
        "aggregation_scales_m": [30],
        "aggregation_min_valid_fraction": 0.5,
        "height_strata_edges_m": [0, 2, 5],
        "block_size_m": 30,
        "bootstrap_draws": 40,
        "seed": 42,
    }
    results = resolution_results(
        reference + 1,
        labels,
        np.ones(9, dtype=bool),
        settings,
        {"resolution_m": 10},
        (0, 0),
    )
    assert results["30"]["cells"] == 1
    assert results["30"]["contributing_10m_cells"] == 5
    strata = height_strata(
        reference + 1, labels, np.ones(9, dtype=bool), settings, (0, 0)
    )
    assert [strata[name]["cells"] for name in ("[0,2)", "[2,5)", "[5,inf)")] == [
        2,
        3,
        4,
    ]


def test_report_keeps_retrospective_interpretation_and_provenance():
    values = scores([1.0, 2.0], [0.0, 0.0])
    summary = {
        "cells": 2,
        "blocks": 2,
        "scores": values,
        "intervals_95": {name: [0.0, 2.0] for name in values},
    }
    alignment = {
        "offset_east_m": 0,
        "offset_north_m": 0,
        "source_crs": "EPSG:32610",
        "target_crs": "EPSG:6339",
        "operation_epsg": 9774,
        "operation": "NAD83(2011) to WGS 84",
        "operation_proj": "+proj=pipeline",
        "operation_accuracy_m": 2.0,
        "proj_version": "9.8.1",
        "gdal_version": "3.11",
        "resampling": "bilinear",
        "cell_grid_checked": True,
    }
    result = {
        "selected_band": 5,
        "inputs": {
            "band_years": list(range(2018, 2025)),
            "git_revision": "abc123",
            "source_url": "https://example.org/product.tif",
            "band_order_source": "author email",
            "last_input_year": 2024,
            "sha256": {"raster": "a" * 64},
            "vegetation_map_source_url": "https://example.org/vegetation",
        },
        "parameters": {
            "echosat_benchmark": {
                "year": 2022,
                "block_size_m": 2000,
                "bootstrap_draws": 2000,
                "seed": 42,
            },
            "echosat_alignment": {
                "resolution_m": 10,
                "offset_sensitivity_m": [-2, 0, 2],
            },
        },
        "label_epochs": ["2013", "2022"],
        "primary": summary,
        "forest_map_class": {
            "pooled": summary,
            "by_group": {"conifer forest": summary},
            "other_primary_cells": 0,
        },
        "exclusions": {"disputed_overlap": 1},
        "offset_sensitivity": {
            "common_cells": 2,
            "score_ranges_m": {name: [value, value] for name, value in values.items()},
        },
        "offsets": [
            {**summary, "alignment": alignment, "nodata_cells_before_common_mask": 0}
        ],
        "resolution_sensitivity": {
            "30": {
                **summary,
                "contributing_10m_cells": 18,
                "occupancy_distribution": {"9": 2},
            }
        },
        "height_strata": {"below_first_edge": 0, "[0,2)": summary},
        "secondary_common_mask_cells": 2,
        "secondary_max_reference": summary,
    }
    report = render_report(result)
    assert "retrospective joint prediction" in report
    assert "not a forecast" in report
    assert "9774" in report
    assert "2,000 whole 2 km block draws" in report
    assert "Pooled forest map classes" in report
