"""Run the preregistered retrospective ECHOSAT height benchmark (E8)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import rasterio

from canopyguard.config import load_config
from canopyguard.data.echosat import validate_raster
from canopyguard.evaluation.product_alignment import align_echosat_band
from canopyguard.evaluation.product_metrics import (
    height_strata,
    resolution_results,
    score_offsets,
    summarize,
)
from canopyguard.evaluation.product_population import quality_mask
from canopyguard.evaluation.product_report import render_report
from canopyguard.io import ensure_parent, project_root
from canopyguard.provenance import file_sha256, read_provenance, study_area_box


def _read_archive(path: Path) -> dict[str, np.ndarray]:
    read_provenance(path)
    with np.load(path, allow_pickle=False) as archive:
        return {name: archive[name] for name in archive.files}


def _revision(root: Path) -> str:
    result = subprocess.run(  # noqa: S603
        ["git", "-c", f"safe.directory={root}", "rev-parse", "HEAD"],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _input_record(root: Path, paths: dict[str, Path], source: dict) -> dict:
    raster_provenance = read_provenance(paths["raster"])
    if raster_provenance["source_url"] != source["tile_url"]:
        raise ValueError("ECHOSAT box copy came from a different source URL")
    return {
        "git_revision": _revision(root),
        "source_url": source["tile_url"],
        "raster_provenance": raster_provenance,
        "sha256": {name: file_sha256(path) for name, path in paths.items()},
        "band_order_source": source["band_order_source"],
        "band_years": source["band_years"],
        "last_input_year": source["last_input_year"],
        "joint_prediction_informed_through_2024": True,
        "allowed_as_forecast_feature": source["allowed_as_feature"],
    }


def _offset_products(src, band, labels, cfg, bbox, scale) -> list[dict]:
    offsets = cfg["echosat_alignment"]["offset_sensitivity_m"]
    alignment = cfg["echosat_alignment"]
    records = []
    for east in offsets:
        for north in offsets:
            values, metadata = align_echosat_band(
                src,
                band,
                labels["cell_id"],
                labels["x"],
                labels["y"],
                alignment["target_crs"],
                alignment,
                bbox,
                scale,
                float(east),
                float(north),
            )
            records.append({"product": values, "alignment": metadata})
    return records


def _input_paths(root: Path, source: dict, forecast: dict) -> dict[str, Path]:
    return {
        "raster": root / "data" / source["box_copy"],
        "labels": root / forecast["stage1_growth_model"]["labels_path"],
        "wire_flags": root
        / forecast["stage1_growth_model"]["clean_screen"]["wire_flags_path"],
        "benchmark_config": root / "configs/product_benchmark.yaml",
        "ingestion_config": root / "configs/ingestion.yaml",
        "forecasting_config": root / "configs/forecasting.yaml",
        "study_area_config": root / "configs/study_area.yaml",
    }


def _evaluate(root, cfg, source, study, forecast) -> dict:
    paths = _input_paths(root, source, forecast)
    inputs = _input_record(root, paths, source)
    labels = _read_archive(paths["labels"])
    flags = _read_archive(paths["wire_flags"])
    base, exclusions = quality_mask(labels, flags)
    settings = cfg["echosat_benchmark"]
    if source["allowed_as_feature"] or settings["year"] not in source["band_years"]:
        raise ValueError("E8 requires a benchmark-only product with a configured year")
    origin = tuple(
        np.min(labels[axis]) - cfg["echosat_alignment"]["resolution_m"] / 2
        for axis in ("x", "y")
    )
    with rasterio.open(paths["raster"]) as src:
        validate_raster(src, source)
        band = source["band_years"].index(settings["year"]) + 1
        records = _offset_products(
            src, band, labels, cfg, study_area_box(study), source["height_scale_to_m"]
        )
    zero = next(
        row
        for row in records
        if row["alignment"]["offset_east_m"] == 0
        and row["alignment"]["offset_north_m"] == 0
    )["product"]
    primary_mask = base & np.isfinite(zero)
    if not primary_mask.any():
        raise ValueError("No E8 cells pass the primary mask")
    primary = summarize(
        zero[primary_mask],
        labels["p95_end"][primary_mask],
        labels["x"][primary_mask],
        labels["y"][primary_mask],
        settings,
        origin,
    )
    exclusions["product_nodata_zero_offset"] = int((base & ~np.isfinite(zero)).sum())
    sensitivity, offsets = score_offsets(records, base, labels, settings, origin)
    secondary_mask = primary_mask & np.isfinite(labels["max_end"])
    result = {
        "question": (
            f"Retrospective ECHOSAT {settings['year']} versus single-date "
            f"{forecast['task']['primary_pair'][-1]} airborne LiDAR"
        ),
        "parameters": cfg,
        "label_epochs": forecast["task"]["primary_pair"],
        "selected_band": source["band_years"].index(settings["year"]) + 1,
        "inputs": inputs,
        "exclusions": exclusions,
        "primary": primary,
        "offset_sensitivity": sensitivity,
        "offsets": offsets,
        "resolution_sensitivity": resolution_results(
            zero, labels, primary_mask, settings, cfg["echosat_alignment"], origin
        ),
        "height_strata": height_strata(zero, labels, primary_mask, settings, origin),
        "secondary_max_reference": summarize(
            zero[secondary_mask],
            labels["max_end"][secondary_mask],
            labels["x"][secondary_mask],
            labels["y"][secondary_mask],
            settings,
            origin,
        ),
        "secondary_common_mask_cells": int(secondary_mask.sum()),
    }
    return result


def run_e8_benchmark() -> dict:
    """Write E8 results after validating all fixed inputs and source provenance."""
    root = project_root()
    cfg = load_config(root / "configs/product_benchmark.yaml")
    source = load_config(root / "configs/ingestion.yaml")["echosat"]
    forecast = load_config(root / "configs/forecasting.yaml")
    study = load_config(root / "configs/study_area.yaml")
    result = _evaluate(root, cfg, source, study, forecast)
    settings = cfg["echosat_benchmark"]
    metrics_path = ensure_parent(root / settings["metrics_path"])
    report_path = ensure_parent(root / settings["report_path"])
    metrics_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(result), encoding="utf-8")
    return result
