"""Post hoc forest-population and stage-two objective diagnostics."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from canopyguard.data.fire_perimeters import file_hash
from canopyguard.evaluation.blocks import assign_blocks, systematic_folds
from canopyguard.evaluation.growth_gate import _load_inputs
from canopyguard.evaluation.growth_screen import selection_masks
from canopyguard.forecasting.growth_curve import block_mae_interval
from canopyguard.forecasting.growth_prior import training_scope
from canopyguard.forecasting.stage2_residual import fold_prior
from canopyguard.io import ensure_parent, project_root
from canopyguard.provenance import current_commit


def all_forest_mask(table, settings: dict) -> np.ndarray:
    """Keep quality and wire rules without retrospective disturbance screens."""
    excluded = table["vegetation_type"].isin(settings["excluded_map_classes"])
    forest = table["broader_group"].isin(settings["forest_groups"])
    return (
        ~table["overlap_disputed"].to_numpy()
        & table["label_change_valid"].to_numpy()
        & table["canopy_at_start"].to_numpy()
        & table["vegetation_known"].to_numpy()
        & table["hansen_valid"].to_numpy()
        & ~table["near_line"].to_numpy()
        & ~excluded.to_numpy()
        & ~table["p95_wire_excluded"].to_numpy()
        & forest.to_numpy()
    )


def _type_mean_increment(frame, start, end, train, minimum: int) -> np.ndarray:
    groups = frame["model_group"].to_numpy()
    broad = frame["broader_group"].to_numpy()
    increments = np.full(len(frame), np.nan)
    for group in np.unique(groups):
        use = groups == group
        broad_group = broad[np.flatnonzero(use)[0]]
        _, fit = training_scope(group, broad_group, train, groups, broad, minimum)
        increments[use] = float(np.mean(end[fit] - start[fit]))
    if not np.isfinite(increments).all():
        raise ValueError("Type-mean sensitivity lacks training cells")
    return increments


def _paired_score(candidate, reference, end, blocks, settings: dict) -> dict:
    if not (np.isfinite(candidate).all() and np.isfinite(reference).all()):
        raise ValueError("Post hoc predictions must be finite")
    return {
        "candidate_mae_m": float(np.mean(np.abs(candidate - end))),
        "reference_mae_m": float(np.mean(np.abs(reference - end))),
        "candidate_minus_reference": block_mae_interval(
            candidate - end,
            reference - end,
            blocks,
            draws=settings["bootstrap_draws"],
            seed=settings["seed"],
        ),
    }


def score_forest(frame, start, end, block_size: int, settings: dict) -> tuple:
    """Cross-fit the median prior on one forest population and block scale."""
    blocks = assign_blocks(frame["x"], frame["y"], block_size)
    folds = systematic_folds(blocks, settings["folds"], settings["seed"])
    median = np.full(len(frame), np.nan)
    for fold in range(settings["folds"]):
        train, test = folds != fold, folds == fold
        increment = fold_prior(frame, start, end, train, settings["min_fit_cells"])
        median[test] = start[test] + increment[test]
    return (
        {
            "cells": len(frame),
            "blocks": int(np.unique(blocks).size),
            "block_size_m": block_size,
            **_paired_score(median, start, end, blocks, settings),
        },
        (blocks, folds, median),
    )


def score_objective_mismatch(frame, start, end, settings: dict) -> dict:
    """Test two squared-error location baselines against the median prior."""
    size = settings["primary_block_m"]
    _, (blocks, folds, median) = score_forest(frame, start, end, size, settings)
    intercept = np.full(len(frame), np.nan)
    type_mean = np.full(len(frame), np.nan)
    fold_offsets = []
    for fold in range(settings["folds"]):
        train, test = folds != fold, folds == fold
        median_increment = fold_prior(
            frame, start, end, train, settings["min_fit_cells"]
        )
        offset = float(np.mean((end - start - median_increment)[train]))
        fold_offsets.append(offset)
        intercept[test] = start[test] + median_increment[test] + offset
        mean_increment = _type_mean_increment(
            frame, start, end, train, settings["min_fit_cells"]
        )
        type_mean[test] = start[test] + mean_increment[test]
    return {
        "fold_mean_residual_offsets_m": fold_offsets,
        "intercept_only": _paired_score(intercept, median, end, blocks, settings),
        "type_mean": _paired_score(type_mean, median, end, blocks, settings),
    }


def _summary_row(name: str, score: dict) -> str:
    interval = score["candidate_minus_reference"]
    return (
        f"| {name} | {score['cells']:,} | {score['blocks']} | "
        f"{score['reference_mae_m']:.3f} | {score['candidate_mae_m']:.3f} | "
        f"{interval['difference_m']:+.3f} "
        f"[{interval['ci_low_m']:+.3f}, {interval['ci_high_m']:+.3f}] |"
    )


def _report(result: dict) -> str:
    rows = [
        _summary_row(f"all forest, {size} m", result["all_forest"][str(size)])
        for size in result["block_sizes_m"]
    ]
    rows += [
        _summary_row(
            f"fire/Hansen screened forest, {size} m",
            result["forest_loss_off"][str(size)],
        )
        for size in result["block_sizes_m"]
    ]
    objective = result["objective_mismatch"]
    intercept = objective["intercept_only"]["candidate_minus_reference"]
    type_mean = objective["type_mean"]["candidate_minus_reference"]
    return "\n".join(
        [
            "# G3 post hoc forest and objective sensitivities",
            "",
            "These analyses were designed after seeing the G3 and stage-two results.",
            "They do not revise the frozen G3 or E4/E5 decisions.",
            "",
            "## Forest population",
            "",
            "All forest keeps label quality, 2013 canopy, map-class, line-distance,",
            "and wire exclusions but does not remove cells for 2013-2022 fire,",
            "Hansen loss, or LiDAR loss. The screened comparison retains the G3",
            "fire/Hansen rules but does not apply the LiDAR-loss filter.",
            "Each row refits the map-class or pooled-group median increment in",
            f"{result['folds']} spatial training folds. Intervals use "
            f"{result['bootstrap_draws']:,} whole-block bootstrap draws",
            "with fitted predictions held fixed.",
            "",
            "| Population and block | Cells | Blocks | No-change MAE | "
            "Median MAE | Median - no change [95% CI], m |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
            *rows,
            "",
            "The screened loss-off comparison excludes "
            f"{result['excluded_from_all_forest']:,} of the eligible all-forest "
            "cells based on later fire or Hansen loss.",
            "The screened improvement does not establish the same",
            "performance across all forest in this fire-dominated box.",
            "",
            "## Squared-error objective diagnostic",
            "",
            "On the screened forest at 2 km, an intercept-only residual model adds",
            "the training-fold mean residual to the median prior. A separate",
            "type-mean model replaces each training-group median increment with",
            "its mean. Neither uses terrain or another new predictor.",
            f"Intercept-only minus median MAE: {intercept['difference_m']:+.3f} "
            f"[{intercept['ci_low_m']:+.3f}, {intercept['ci_high_m']:+.3f}] m.",
            f"Type-mean minus median MAE: {type_mean['difference_m']:+.3f} "
            f"[{type_mean['ci_low_m']:+.3f}, {type_mean['ci_high_m']:+.3f}] m.",
            "The ridge and LightGBM runs used squared-error objectives but were",
            "judged by MAE. This objective mismatch can explain part of their",
            "deficit; the data do not isolate it from disturbance effects.",
            "",
            "## Provenance and limits",
            "",
            f"Run UTC: {result['generated_utc']}. Base revision: "
            f"{result['git_base_revision']}.",
            "Exact input hashes, settings and unrounded results are in the JSON.",
            "Rerun: `python scripts/run_posthoc_forest.py` in the project",
            "environment with the local DVC inputs restored.",
            "This is a post hoc analysis, and whole-block intervals omit model",
            "refit variance. It is not an independent preregistered validation.",
            "",
        ]
    )


def run_posthoc_forest(forecast: dict, outputs: dict) -> dict:
    """Write rerunnable post hoc sensitivities without changing gate outputs."""
    root = project_root()
    revision = current_commit(root)
    if revision == "unknown":
        raise RuntimeError("Git revision is required for post hoc provenance")
    settings = forecast["growth_curve"]
    table, heights = _load_inputs(forecast, settings)
    masks = {
        "all_forest": all_forest_mask(table, settings),
        "forest_loss_off": selection_masks(table, settings)["forest_loss_off"],
    }
    scores = {}
    objective = None
    for name, mask in masks.items():
        frame = table.loc[mask].reset_index(drop=True)
        start, end = heights["p95_start"][mask], heights["p95_end"][mask]
        scores[name] = {}
        for size in settings["block_sizes_m"]:
            score, _ = score_forest(frame, start, end, size, settings)
            scores[name][str(size)] = score
        if name == "forest_loss_off":
            objective = score_objective_mismatch(frame, start, end, settings)
    result = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "git_base_revision": revision,
        "analysis": "posthoc",
        "block_sizes_m": settings["block_sizes_m"],
        "folds": settings["folds"],
        "bootstrap_draws": settings["bootstrap_draws"],
        "seed": settings["seed"],
        "input_sha256": {
            "labels": file_hash(root / forecast["labels_path"]),
            "clean_cells": file_hash(root / forecast["clean_screen"]["output_path"]),
            "wire_flags": file_hash(root / forecast["clean_screen"]["wire_flags_path"]),
            "analysis_code": file_hash(Path(__file__)),
            "forecast_config": file_hash(root / "configs/forecasting.yaml"),
            "posthoc_config": file_hash(root / "configs/posthoc_forest.yaml"),
        },
        "selection_settings": {
            "forest_groups": settings["forest_groups"],
            "excluded_map_classes": settings["excluded_map_classes"],
            "p95_wire_exclusion_m": settings["p95_wire_exclusion_m"],
            "min_fit_cells": settings["min_fit_cells"],
        },
        "excluded_from_all_forest": int(
            masks["all_forest"].sum() - masks["forest_loss_off"].sum()
        ),
        **scores,
        "objective_mismatch": objective,
    }
    ensure_parent(root / outputs["metrics_path"]).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    ensure_parent(root / outputs["report_path"]).write_text(
        _report(result), encoding="utf-8"
    )
    return result
