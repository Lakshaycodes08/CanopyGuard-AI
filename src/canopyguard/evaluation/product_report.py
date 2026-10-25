"""Plain-English report for the preregistered E8 height comparison."""

from __future__ import annotations

METRIC_NAMES = {
    "mae_m": "Mean absolute error",
    "median_signed_error_m": "Median signed error",
    "mean_signed_error_m": "Mean signed error",
    "rmse_m": "Root mean squared error",
}


def _metric_rows(summary: dict) -> list[str]:
    rows = []
    for key, label in METRIC_NAMES.items():
        interval = summary["intervals_95"]
        bounds = (
            "too few blocks"
            if interval is None
            else (f"[{interval[key][0]:.3f}, {interval[key][1]:.3f}]")
        )
        rows.append(f"| {label} | {summary['scores'][key]:.3f} | {bounds} |")
    return rows


def _summary_table(summary: dict, block_size_m: float) -> list[str]:
    return [
        f"Cells: {summary['cells']:,}; "
        f"{block_size_m / 1000:g} km blocks: {summary['blocks']:,}.",
        "",
        "| Metric (m) | Estimate | 95% whole-block interval |",
        "| --- | ---: | ---: |",
        *_metric_rows(summary),
        "",
    ]


def render_report(result: dict) -> str:
    """Describe product agreement without calling it growth or forecast skill."""
    inputs = result["inputs"]
    benchmark = result["parameters"]["echosat_benchmark"]
    alignment_settings = result["parameters"]["echosat_alignment"]
    year = benchmark["year"]
    label_start, label_end = result["label_epochs"]
    block_size_m = benchmark["block_size_m"]
    offsets = alignment_settings["offset_sensitivity_m"]
    lines = [
        f"# E8 ECHOSAT {year} product benchmark",
        "",
        f"Configured {year} band: {result['selected_band']} of "
        f"{len(inputs['band_years'])}. Source heights were converted from stored",
        "centimetres to metres after bilinear resampling.",
        f"ECHOSAT {year} is a retrospective joint prediction informed by imagery",
        f"through {inputs['last_input_year']}. This compares modeled height with",
        f"single-date {label_end} airborne LiDAR p95 on existing "
        f"{alignment_settings['resolution_m']} m cells.",
        "It is cross-product disagreement, not a forecast,",
        "growth-rate validation, or proof of product bias.",
        "ECHOSAT is not a model feature.",
        "",
        "## Primary zero-offset comparison",
        "",
        *_summary_table(result["primary"], block_size_m),
        "The primary mask retains fire, Hansen-loss, and LiDAR-loss cells. It removes",
        "disputed overlaps, nonfinite p95 labels, PR #13 max/p95 wire exclusions,",
        "and product nodata. LiDAR p95 and modeled product height are related but",
        "different height summaries.",
        "",
        "## Exclusions",
        "",
        "| Step | Cells |",
        "| --- | ---: |",
    ]
    lines += [
        f"| {key.replace('_', ' ')} | {count:,} |"
        for key, count in result["exclusions"].items()
    ]
    lines += [
        "",
        "## Fixed position shifts",
        "",
        f"All {len(offsets) ** 2} preregistered east/north shifts "
        f"({', '.join(f'{offset:g}' for offset in offsets)} m) use the same",
        f"{result['offset_sensitivity']['common_cells']:,} valid cells. No shift was",
        "selected by agreement with LiDAR. The range is a positional sensitivity,",
        "not a confidence interval.",
        "",
        "| Metric (m) | Lowest | Highest |",
        "| --- | ---: | ---: |",
    ]
    for key, label in METRIC_NAMES.items():
        low, high = result["offset_sensitivity"]["score_ranges_m"][key]
        lines.append(f"| {label} | {low:.3f} | {high:.3f} |")
    lines += [
        "",
        "| East shift (m) | North shift (m) | Cells lost to nodata | MAE (m) |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for row in result["offsets"]:
        alignment = row["alignment"]
        lines.append(
            f"| {alignment['offset_east_m']:g} | {alignment['offset_north_m']:g} | "
            f"{row['nodata_cells_before_common_mask']:,} | "
            f"{row['scores']['mae_m']:.3f} |"
        )
    lines += ["", "## Resolution sensitivity", ""]
    for scale, row in result["resolution_sensitivity"].items():
        lines += [
            f"### {scale} m bins",
            "",
            f"Contributing paired {alignment_settings['resolution_m']} m cells: "
            f"{row['contributing_10m_cells']:,}.",
            "Occupancy distribution (cells per bin: bin count): "
            f"{row['occupancy_distribution']}.",
            "",
            *_summary_table(row, block_size_m),
        ]
    lines += ["## Reference-height strata", ""]
    strata = result["height_strata"]
    lines.append(
        f"Primary cells below the first stratum: {strata['below_first_edge']:,}."
    )
    for interval, row in strata.items():
        if interval == "below_first_edge":
            continue
        lines += ["", f"### LiDAR p95 {interval} m", ""]
        lines += (
            _summary_table(row, block_size_m)
            if row["scores"]
            else ["No paired cells.", ""]
        )
    lines += [
        "Binning on the reference can make signed errors near interval boundaries",
        "look like regression toward the mean. These strata are descriptive.",
        "",
        "## Secondary max-height reference",
        "",
        "Common p95/max/product valid cells: "
        f"{result['secondary_common_mask_cells']:,}.",
        "",
        *_summary_table(result["secondary_max_reference"], block_size_m),
        "This checks sensitivity to the LiDAR height summary, not absolute bias.",
        "",
        "## Reproducibility and scope",
        "",
        f"Git revision: `{inputs['git_revision']}`.",
        f"Source: {inputs['source_url']}",
        f"Band order: {inputs['band_order_source']}.",
        f"Intervals use {benchmark['bootstrap_draws']:,} whole "
        f"{block_size_m / 1000:g} km block draws with seed {benchmark['seed']}.",
        "",
        "The raster hash below identifies the local study-box copy. Its provenance",
        "records the original tile URL and download time.",
        "",
        "| Input | SHA-256 |",
        "| --- | --- |",
    ]
    lines += [f"| {name} | `{digest}` |" for name, digest in inputs["sha256"].items()]
    zero = next(
        row["alignment"]
        for row in result["offsets"]
        if row["alignment"]["offset_east_m"] == 0
        and row["alignment"]["offset_north_m"] == 0
    )
    lines += [
        "",
        f"Source CRS: {zero['source_crs']}; target CRS: {zero['target_crs']}.",
        f"EPSG operation: {zero['operation_epsg']} ({zero['operation']}).",
        f"Explicit PROJ pipeline: `{zero['operation_proj']}`.",
        f"PROJ: {zero['proj_version']}; GDAL: {zero['gdal_version']}.",
        f"Resampling: {zero['resampling']}; "
        f"{alignment_settings['resolution_m']} m cell grid checked: "
        f"{zero['cell_grid_checked']}.",
        f"The {zero['operation_accuracy_m']:g} m stated operation accuracy "
        "is datum uncertainty,",
        "not a measured pixel shift.",
        f"ECHOSAT {inputs['band_years'][0]}-{year} modeled change and "
        f"LiDAR {label_start}-{label_end} change span",
        "different intervals and are not compared as interchangeable growth evidence.",
        "",
    ]
    return "\n".join(lines)
