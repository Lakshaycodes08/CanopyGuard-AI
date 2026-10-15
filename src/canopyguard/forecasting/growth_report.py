"""Render the issue 8 gate report and forest growth-curve figure."""

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
    """Plot full forest curves, including the no-growth region above A."""
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
        height = chapman_richards(
            grid, metrics["baseline_years"], fit["A"], fit["k"], fit["c"]
        )
        label = name.replace(" Alliance", "")
        axes[0].plot(grid, height, lw=2, label=label)
        axes[1].plot(grid, height - grid, lw=2, label=label)
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


def _score_row(label: str, score: dict, model: str) -> str:
    return (
        f"| {label} | {model} | {score['cells']:,} | {score['blocks']} "
        f"| {score['mae_no_change_m']:.3f} | {score['mae_median_growth_m']:.3f} "
        f"| {score['mae_curve_m']:.3f} "
        f"| {interval_text(score['curve_minus_no_change'])} "
        f"| {interval_text(score['curve_minus_median_growth'])} |"
    )


def _score_table(rows: list[tuple[str, dict, str]]) -> list[str]:
    output = [
        "| Scope | A mode | Cells | Blocks | No change MAE | Median MAE | Curve MAE "
        "| Curve - no change [95% block CI] | Curve - median [95% block CI] |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    return output + [_score_row(*row) for row in rows]


def _type_rows(metrics: dict) -> list[str]:
    rows = [
        "| Forest map class | Cells | Fit scope | Full-fit A (m) | Fold A range (m) "
        "| Held-out 2013 p95 >= fold A "
        "| k (/yr) | c | No change MAE | Median MAE | Curve MAE | Bound? |",
        "| --- | ---: | --- | ---: | --- | --- | ---: | ---: | ---: "
        "| ---: | ---: | --- |",
    ]
    for item in metrics["per_type"]:
        fit = item["fit"]
        saturation = item["saturation"]
        bound = fit["k_at_bound"] or fit["c_at_bound"]
        rows.append(
            f"| {item['vegetation_type']} | {item['cells']:,} | {fit['scope']} "
            f"| {fit['A']:.1f} "
            f"| {saturation['A_min_m']:.1f}-{saturation['A_max_m']:.1f} "
            f"| {saturation['at_or_above_A']}/{saturation['cells']} "
            f"({saturation['share']:.2%}) "
            f"| {fit['k']:.4f} | {fit['c']:.2f} "
            f"| {item['mae_no_change_m']:.3f} "
            f"| {item['mae_median_growth_m']:.3f} "
            f"| {item['mae_curve_m']:.3f} "
            f"| {'yes' if bound else 'no'} |"
        )
    return rows


def _shape_rows(metrics: dict) -> list[str]:
    rows = [
        "| Forest map class | Gain at 10 m | Gain at 20 m | Shorter gains more? |",
        "| --- | ---: | ---: | --- |",
    ]
    for item in metrics["per_type"]:
        fit = item["fit"]
        test_height = np.array([10.0, 20.0])
        gain = (
            chapman_richards(
                test_height, metrics["baseline_years"], fit["A"], fit["k"], fit["c"]
            )
            - test_height
        )
        rows.append(
            f"| {item['vegetation_type']} | {gain[0]:.2f} m | {gain[1]:.2f} m "
            f"| {'yes' if gain[0] > gain[1] else 'no'} |"
        )
    return rows


def write_growth_report(metrics: dict, forecast: dict) -> None:
    """Write a reproducible report with the forest gate as the main result."""
    root = project_root()
    settings = forecast["growth_curve"]
    screen_path = root / forecast["clean_screen"]["output_path"]
    screen = json.loads(
        screen_path.with_suffix(".provenance.json").read_text(encoding="utf-8")
    )
    plot_curves(metrics, root / settings["figure_path"])
    main = metrics["screens"]["forest_loss_on"]
    comparison = [
        (name.replace("_", " "), score, score["model"])
        for name, score in metrics["screens"].items()
    ]
    comparison += [
        ("forest loss on", score, mode)
        for mode, score in metrics["height_sensitivities"].items()
    ]
    bound = [
        item["vegetation_type"]
        for item in metrics["per_type"]
        if item["fit"]["k_at_bound"] or item["fit"]["c_at_bound"]
    ]
    lines = [
        "# Growth-curve check, 2013-2022",
        "",
        "**Post hoc A rule.** The original literature-only A preflight exceeded "
        "0.5% in nine classes. The revised primary A is the maximum of the "
        "literature typical-upper value and the 99.5th percentile of "
        "max(2013 p95, 2022 p95), calculated within each spatial training fold. "
        "The 2022 heights in a held-out fold never set that fold's A. This "
        "revised gate is exploratory and must not be presented as predeclared.",
        "",
        f"Run: {metrics['generated_utc']}. Issue #8. Base revision: "
        f"{metrics['git_base_revision']}.",
        "",
        "## Gate G3: forest, LiDAR-loss screen on",
        "",
        f"**{metrics['decision']}**: curve minus no-change p95 MAE is "
        f"{interval_text(main['curve_minus_no_change'])} m on 2 km blocks. "
        "The 95% interval must lie entirely below zero to pass.",
        f"Curve minus training-group median p95 MAE is "
        f"{interval_text(main['curve_minus_median_growth'])} m. "
        "A negative interval that excludes zero supports a height-dependent advantage.",
        f"The main comparison uses {main['cells']:,} conifer and hardwood cells "
        f"in {main['blocks']} spatial blocks, five folds, "
        f"{settings['bootstrap_draws']:,} whole-block bootstrap draws and "
        f"{metrics['baseline_years']:.5f} years between surveys.",
        "",
        "## Selection and A sensitivity",
        "",
        *_score_table(comparison),
        "",
        "The LiDAR-loss-off rows keep the fire and Hansen screens. "
        "All-class rows are secondary and use the former free-A model because "
        "literature A values were specified for forest alliances only. "
        "The literature-only row keeps Douglas-fir and redwood at 76 and 91 m. "
        "The record-tree row uses 101 and 111 m for those classes; all other "
        "classes keep their literature A. The free-A row is the former fit.",
        "",
        "## Spatial sensitivity and mean-height check",
        "",
        *_score_table(
            [
                (f"forest loss on, {size} m", score, settings["primary_a_mode"])
                for size, score in metrics["spatial_sensitivities"].items()
            ]
            + [("forest mean, 2 km", metrics["mean_secondary"], "literature")]
        ),
        "",
        "## Forest map classes and height ceilings",
        "",
        "The post hoc A is fixed within each training fold before fitting k "
        "and c. Cells starting at or above A are predicted to have no growth. "
        "Mixed classes use the largest member literature A; pooled fits share "
        "k and c while each class keeps its own fold A. The table reports "
        "held-out exceedance after wire and 10 m line exclusions. Its share "
        "need not equal 0.5%, because held-out blocks can have taller trees.",
        "",
        *_type_rows(metrics),
        "",
        "Fitted k/c bound warnings: " + (", ".join(bound) if bound else "none") + ".",
        "",
        "## Ecological shape check",
        "",
        *_shape_rows(metrics),
        "",
        f"![Fitted growth curves]({settings['figure_path'].removeprefix('reports/')})",
        "",
        "## Evidence and limits",
        "",
        f"The original clean screen retained {screen['clean_cells']:,} of "
        f"{screen['all_cells']:,} label cells. The revised selections and "
        "wire exclusions are recorded in the machine metrics and preflight JSON.",
        f"2013 vegetation groups come from the [Sonoma Veg Map]"
        f"({forecast['vegetation_join']['source_url']}); fire from "
        f"[FRAP]({screen['sources']['frap']['url']}) and "
        f"[MTBS]({screen['sources']['mtbs']['url']}); Hansen supplies "
        f"[loss year]({screen['sources']['hansen']['url']}).",
        "Sonoma MAP_CLASS is a mapping unit, not a species-pure cell label. "
        "The LiDAR-loss screen selects a retrospective subset; it is never a "
        "forecast feature. The persistent-forest visual audit remains outstanding.",
        "",
        "## Reproduction",
        "",
        "Run scripts/join_sonoma_veg.py, scripts/build_clean_cells.py, "
        "scripts/flag_wire_suspects.py, then scripts/run_growth_curve_check.py "
        "with the configured environment. Local inputs and hashes are listed "
        "in the machine metrics and provenance files.",
        "",
    ]
    ensure_parent(root / settings["report_path"]).write_text(
        "\n".join(lines), encoding="utf-8"
    )
