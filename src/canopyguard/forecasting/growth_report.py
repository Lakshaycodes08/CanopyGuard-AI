"""Render the issue 8 scientific report and a growth-curve figure."""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from canopyguard.forecasting.growth_curve import chapman_richards
from canopyguard.io import ensure_parent, project_root


def interval_text(result: dict | None) -> str:
    if result is None:
        return "n/a (one block)"
    return (
        f"{result['difference_m']:+.3f} "
        f"[{result['ci_low_m']:+.3f}, {result['ci_high_m']:+.3f}]"
    )


def plot_curves(metrics: dict, path) -> None:
    preferred = (
        "Sequoia sempervirens Alliance",
        "Pseudotsuga menziesii Alliance",
        "Quercus agrifolia Alliance",
        "Quercus douglasii Alliance",
        "Umbellularia californica Alliance",
        "Arbutus menziesii Alliance",
    )
    by_name = {row["vegetation_type"]: row for row in metrics["per_type"]}
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=160)
    grid = np.linspace(2, 40, 150)
    axes[0].plot(grid, grid, color="black", ls="--", lw=1.2, label="No change")
    axes[1].axhline(0, color="black", ls="--", lw=1.2)
    for name in preferred:
        if name not in by_name:
            continue
        fit = by_name[name]["fit"]
        usable = grid[grid < fit["A"]]
        height = chapman_richards(
            usable, metrics["baseline_years"], fit["A"], fit["k"], fit["c"]
        )
        label = name.replace(" Alliance", "")
        axes[0].plot(usable, height, lw=2, label=label)
        axes[1].plot(usable, height - usable, lw=2, label=label)
    axes[0].set(
        xlabel="2013 p95 canopy height (m)",
        ylabel="Predicted 2022 p95 canopy height (m)",
        title="Fitted height",
    )
    axes[1].set(
        xlabel="2013 p95 canopy height (m)",
        ylabel="Predicted 9-year gain (m)",
        title="Height dependence",
    )
    for axis in axes:
        axis.grid(alpha=0.2)
    axes[0].legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(ensure_parent(path))
    plt.close(fig)


def sensitivity_rows(metrics: dict) -> list[str]:
    rows = [
        "| Block | Target | Cells | Blocks | No change MAE | Median MAE | Curve MAE "
        "| Curve - no change [95% block CI] |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for size, results in metrics["results"].items():
        for target, score in results.items():
            rows.append(
                f"| {size} m | {target} | {score['cells']:,} | {score['blocks']} "
                f"| {score['mae_no_change_m']:.3f} "
                f"| {score['mae_median_growth_m']:.3f} "
                f"| {score['mae_curve_m']:.3f} "
                f"| {interval_text(score['curve_minus_no_change'])} |"
            )
    return rows


def type_rows(metrics: dict) -> list[str]:
    rows = [
        "| Vegetation type | Broad group | Clean cells | Fit scope | A (m) | k (/yr) "
        "| c | No change MAE | Median MAE | Curve MAE | Curve - no change [95% CI] |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in metrics["per_type"]:
        fit = row["fit"]
        name = row["vegetation_type"].replace("|", "/")
        rows.append(
            f"| {name} | {row['broader_group']} | {row['cells']:,} "
            f"| {fit['scope']} | {fit['A']:.2f} | {fit['k']:.4f} | {fit['c']:.2f} "
            f"| {row['mae_no_change_m']:.3f} "
            f"| {row['mae_median_growth_m']:.3f} "
            f"| {row['mae_curve_m']:.3f} "
            f"| {interval_text(row['curve_minus_no_change'])} |"
        )
    return rows


def screen_rows(screen: dict) -> list[str]:
    rows = [
        "| Exclusion, in order | Cells removed at this step | Cells flagged anywhere |",
        "| --- | ---: | ---: |",
    ]
    for name, count in screen["sequential_removed"].items():
        rows.append(
            f"| {name.replace('_', ' ')} | {count:,} "
            f"| {screen['rule_totals'][name]:,} |"
        )
    return rows


def ecology_rows(metrics: dict) -> list[str]:
    selected = {
        row["vegetation_type"]: row
        for row in metrics["per_type"]
        if row["vegetation_type"].startswith(
            (
                "Sequoia",
                "Pseudotsuga",
                "Quercus agrifolia",
                "Quercus douglasii",
                "Umbellularia",
                "Arbutus",
            )
        )
    }
    rows = [
        "| Type | Cells | Gain at 10 m | Gain at 20 m | A bound? |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, row in selected.items():
        fit = row["fit"]
        growth = chapman_richards(
            np.array([10.0, 20.0]),
            metrics["baseline_years"],
            fit["A"],
            fit["k"],
            fit["c"],
        ) - np.array([10.0, 20.0])
        rows.append(
            f"| {name} | {row['cells']:,} | {growth[0]:.2f} m "
            f"| {growth[1]:.2f} m | {'yes' if fit['a_at_upper_bound'] else 'no'} |"
        )
    return rows


def write_growth_report(metrics: dict, forecast: dict) -> None:
    root = project_root()
    settings = forecast["growth_curve"]
    screen_path = root / forecast["clean_screen"]["output_path"]
    screen = json.loads(
        screen_path.with_suffix(".provenance.json").read_text(encoding="utf-8")
    )
    plot_curves(metrics, root / settings["figure_path"])
    primary = metrics["results"][str(settings["primary_block_m"])]["p95"]
    difference = primary["curve_minus_no_change"]
    warnings = [
        row["vegetation_type"]
        for row in metrics["per_type"]
        if row["fit"]["a_at_upper_bound"]
    ]
    median_difference = primary["curve_minus_median_growth"]
    forest = metrics["forest_only"]
    shape_warnings = []
    for row in metrics["per_type"]:
        if not row["vegetation_type"].startswith(
            (
                "Sequoia",
                "Pseudotsuga",
                "Quercus agrifolia",
                "Quercus douglasii",
                "Umbellularia",
                "Arbutus",
            )
        ):
            continue
        fit = row["fit"]
        test_heights = np.array([10.0, 20.0])
        gains = (
            chapman_richards(
                test_heights, metrics["baseline_years"], fit["A"], fit["k"], fit["c"]
            )
            - test_heights
        )
        if gains[1] >= gains[0]:
            shape_warnings.append(row["vegetation_type"])
    lines = [
        "# Growth-curve check, 2013-2022",
        "",
        f"Run: {metrics['generated_utc']}. Issue #8. Base revision: "
        f"{metrics['git_base_revision']}.",
        "",
        "## Gate G3",
        "",
        f"**{metrics['decision']}** under the predeclared rule: the 95% whole-block "
        "bootstrap interval for curve MAE minus no-change MAE must be entirely "
        f"below zero on 2 km blocks for p95. Delta: {interval_text(difference)} m. "
        f"The interval uses {difference['draws']:,} draws with seed "
        f"{settings['seed']}. Smaller MAE is better.",
        "",
        f"The 2 km p95 comparison uses {primary['cells']:,} screened "
        f"cells in {primary['blocks']} blocks and five folds. The time gap is "
        f"{metrics['baseline_years']:.5f} years.",
        "",
        f"Against the training-group median, curve MAE differs by "
        f"{interval_text(median_difference)} m. Its interval "
        + (
            "includes zero; a height-dependent advantage is not established."
            if median_difference["ci_low_m"] <= 0 <= median_difference["ci_high_m"]
            else "excludes zero."
        ),
        f"On forest classes alone ({forest['cells']:,} cells), p95 MAEs are "
        f"{forest['mae_no_change_m']:.3f} m for no change, "
        f"{forest['mae_median_growth_m']:.3f} m for the median and "
        f"{forest['mae_curve_m']:.3f} m for the curve. Curve minus no change: "
        f"{interval_text(forest['curve_minus_no_change'])} m; curve minus "
        f"median: {interval_text(forest['curve_minus_median_growth'])} m.",
        "",
        "## Clean-cell screen",
        "",
        f"The filter retained {screen['clean_cells']:,} of {screen['all_cells']:,} "
        "unique label cells. Counts overlap; removals are sequential.",
        "",
        *screen_rows(screen),
        "",
        "The retained sample is below the prior 200,000-300,000 estimate. "
        "The fire rule removes 324,280 additional canopy cells after the "
        "earlier exclusions; the large Kincade footprint intersects much "
        "of the sampled canopy. No threshold was relaxed to hit the estimate.",
        "",
        "FRAP and MTBS records from 2014-2022 include Kincade, Tubbs, Pocket "
        "and Walbridge. Hansen loss year 14-22 is an independent Landsat screen. "
        f"PR #13's optional wire-suspect archive was "
        f"{'available' if screen['wire_flags_available'] else 'unavailable'}; "
        "the 30 m CEC line exclusion still applied.",
        "",
        "## Held-out comparison",
        "",
        *sensitivity_rows(metrics),
        "",
        "Each 1, 2, or 5 km square block belongs to one fold. Every median "
        "increment and curve was fitted on the other four folds. The 95% "
        "interval resamples blocks, not individual cells. The main target is "
        "2022 p95 from 2013 p95; mean height is secondary.",
        "",
        "## Ecological shape check",
        "",
        *ecology_rows(metrics),
        "",
        f"At 20 m, fitted gain exceeds or equals gain at 10 m for "
        f"{len(shape_warnings)} named types: "
        + (", ".join(shape_warnings) if shape_warnings else "none")
        + ". These fits fail the proposed short-tree-faster sense check.",
        f"Asymptote A reached the configured upper-bound warning for "
        f"{len(warnings)} mapped types: "
        + (", ".join(warnings) if warnings else "none")
        + ". A bound hit limits biological interpretation.",
        "",
        f"![Fitted growth curves]({settings['figure_path'].removeprefix('reports/')})",
        "",
        "## Per-type p95 results",
        "",
        "A, k, and c are fitted on all clean cells in each displayed scope. "
        "MAEs come only from held-out folds. Sparse types pool by broader group.",
        "",
        *type_rows(metrics),
        "",
        "## Source provenance",
        "",
        f"- [Sonoma 2013 vegetation map]"
        f"({forecast['vegetation_join']['source_url']}) supplies MAP_CLASS.",
        f"- [CAL FIRE FRAP]({screen['sources']['frap']['url']}) and "
        f"[MTBS]({screen['sources']['mtbs']['url']}) supply fire perimeters.",
        f"- [Hansen GFC 2024 v1.12]"
        f"({screen['sources']['hansen']['url']}) supplies loss year.",
        f"- [CEC transmission lines]({screen['sources']['cec']['url']}) "
        "supply approximate corridor context.",
        "Raw-file hashes and query settings are in the local provenance files "
        "beside the vegetation and clean-cell Parquet outputs.",
        "",
        "## Interpretation limits",
        "",
        "- Sonoma MAP_CLASS is an alliance or mapping unit, not a pure species "
        "assignment. Centers within 5 m of a map boundary were uncertain.",
        "- The screen uses 2022 LiDAR loss_share to define a conditional "
        "undisturbed subset. It is never a curve predictor. This score applies "
        "to retrospectively screened cells, not to all future cells.",
        "- The prescribed visual audit of persistent forest is outstanding. "
        "FRAP can omit small fires or include unburned islands; MTBS omits "
        "smaller western fires; Hansen detects stand-replacement loss, not every trim.",
        "- CEC lines are approximate corridor context. PR #13's optional "
        "wire-suspect file was unavailable for this run.",
        "- The curve is a candidate ecological baseline. Paper adoption also "
        "requires review of the screen, fit bounds and biological shape.",
        "",
        "## Reproduction",
        "",
        "Run scripts/join_sonoma_veg.py, scripts/build_clean_cells.py, then "
        "scripts/run_growth_curve_check.py with the repo environment.",
        "",
        f"Config: configs/forecasting.yaml. Out-of-fold predictions: "
        f"{settings['oof_path']} (local data). Machine metrics: "
        f"{settings['metrics_path']}.",
        "",
    ]
    ensure_parent(root / settings["report_path"]).write_text(
        "\n".join(lines), encoding="utf-8"
    )
