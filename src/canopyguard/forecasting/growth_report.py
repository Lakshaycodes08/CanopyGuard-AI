"""Render the issue 8 growth-prior gate report."""

from __future__ import annotations

import json

import numpy as np

from canopyguard.forecasting.growth_curve import chapman_richards
from canopyguard.forecasting.growth_plot import plot_curves
from canopyguard.io import ensure_parent, project_root


def interval_text(result: dict | None) -> str:
    if result is None:
        return "n/a (one block)"
    return (
        f"{result['difference_m']:+.3f} "
        f"[{result['ci_low_m']:+.3f}, {result['ci_high_m']:+.3f}]"
    )


def _score_row(label: str, score: dict, model: str) -> str:
    return (
        f"| {label} | {model} | {score['cells']:,} | {score['blocks']} "
        f"| {score['mae_no_change_m']:.3f} | {score['mae_median_growth_m']:.3f} "
        f"| {score['mae_curve_m']:.3f} "
        f"| {interval_text(score['median_minus_no_change'])} "
        f"| {interval_text(score['curve_minus_no_change'])} "
        f"| {interval_text(score['curve_minus_median_growth'])} |"
    )


def _score_table(rows: list[tuple[str, dict, str]]) -> list[str]:
    output = [
        "| Scope | A mode | Cells | Blocks | No change MAE | Median MAE | Curve MAE "
        "| Median - no change [95% block CI] "
        "| Curve - no change [95% block CI] | Curve - median [95% block CI] |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    return output + [_score_row(*row) for row in rows]


def _type_rows(metrics: dict) -> list[str]:
    rows = [
        "| Forest map class | Cells | Curve fit scope | Full-fit empirical A (m) "
        "| Fold empirical A range (m) "
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


def _median_prior_rows(metrics: dict) -> list[str]:
    rows = [
        "| Forest map class | Fit scope | Training cells | Median increment (m) |",
        "| --- | --- | ---: | ---: |",
    ]
    for item in metrics["per_type"]:
        name = item["vegetation_type"]
        prior = metrics["median_growth_prior"][name]
        rows.append(
            f"| {name} | {prior['fit_scope']} | {prior['training_cells']:,} "
            f"| {prior['median_increment_m']:+.3f} |"
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
    growth_only = metrics["screens"]["forest_loss_on"]
    loss_off = metrics["screens"]["forest_loss_off"]
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
    fallback = [
        f"{name.replace('_', ' ')}: {score['literature_fallback_cells']:,} cells "
        f"({', '.join(score['literature_fallback_classes'])})"
        for name, score in (
            list(metrics["screens"].items())
            + [
                (f"forest loss on {size} m", score)
                for size, score in metrics["spatial_sensitivities"].items()
            ]
        )
        if score["literature_fallback_cells"]
    ]
    acer = next(
        item
        for item in metrics["per_type"]
        if item["vegetation_type"].startswith("Acer macrophyllum ")
    )
    lines = [
        "# Growth-prior check, 2013-2022",
        "",
        "**Post hoc empirical height ceiling by map class.** The original "
        "literature-only A preflight exceeded 0.5% in nine classes. The "
        "Chapman-Richards sensitivity uses the maximum of the "
        "literature typical-upper value and the 99.5th percentile of "
        "max(2013 p95, 2022 p95), calculated within each spatial training fold. "
        "The 2022 heights in a held-out fold never set that fold's A. This A "
        "is an empirical map-class cutoff, not a biological maximum or a "
        "species asymptote. The rule was selected after seeing exceedances "
        "and must not be presented as predeclared. Promoting the median "
        "increment and treating both forest screens as co-primary were also "
        "decisions made after inspecting the earlier curve results.",
        "",
        f"Run: {metrics['generated_utc']}. Issue #8. Base revision: "
        f"{metrics['git_base_revision']}.",
        "",
        "## Gate G3: co-primary forest median-increment prior",
        "",
        f"**{metrics['decision']}**: the type-specific or pooled broad-group "
        "median increment beats no change on both forest screens when each "
        "95% whole-block interval is entirely below zero.",
        f"LiDAR-loss screen off ({loss_off['cells']:,} cells): median MAE "
        f"{loss_off['mae_median_growth_m']:.3f} m versus no change "
        f"{loss_off['mae_no_change_m']:.3f} m; median minus no change "
        f"{interval_text(loss_off['median_minus_no_change'])} m.",
        f"LiDAR-loss screen on ({growth_only['cells']:,} cells): median MAE "
        f"{growth_only['mae_median_growth_m']:.3f} m versus no change "
        f"{growth_only['mae_no_change_m']:.3f} m; median minus no change "
        f"{interval_text(growth_only['median_minus_no_change'])} m. "
        "This retrospectively selected growth-only subset is an upper bound "
        "on performance for undisturbed canopy.",
        f"Curve minus median is "
        f"{interval_text(loss_off['curve_minus_median_growth'])} m with the "
        "LiDAR-loss screen off and "
        f"{interval_text(growth_only['curve_minus_median_growth'])} m with it on. "
        "Neither establishes a height-dependent advantage.",
        f"The co-primary comparisons use five folds, 2 km blocks, "
        f"{settings['bootstrap_draws']:,} whole-block bootstrap draws and "
        f"{metrics['baseline_years']:.5f} years between surveys.",
        "The loss-off subset still uses retrospective fire and Hansen screens; "
        "it is less conditioned on target-epoch LiDAR but is not a fully "
        "prospective 2013 forecast evaluation.",
        "",
        "## Forecast growth prior",
        "",
        "The selected stage-one prior is the training-group median p95 "
        "increment. Mapped classes with fewer than 500 training cells use "
        "their broad forest group. These full-sample increments are fitted "
        "on the forest LiDAR-loss-off subset for later forecasting; the G3 "
        "scores above use held-out-fold medians. "
        "Height-bin medians were not tested and require their own held-out "
        "comparison before adoption.",
        "",
        *_median_prior_rows(metrics),
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
        "If an entire map class lies in a held-out spatial fold, its training "
        "fold has no class-specific height percentile. That class uses its "
        "literature A for that fold; the affected cells and classes are "
        "recorded in the machine metrics. This does not affect the main "
        "forest-loss-on 2 km result.",
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
        "Absent-class literature-A fallbacks: "
        + ("; ".join(fallback) if fallback else "none")
        + ". The primary forest-loss-on 2 km result has zero fallbacks.",
        "",
        "## Forest map classes and empirical height ceilings",
        "",
        "Before any fold's A is computed, the selection masks remove cells "
        f"within {forecast['clean_screen']['near_line_m']:g} m of a CEC "
        "transmission line, PR #13 wire suspects, and cells within "
        f"{settings['p95_wire_exclusion_m']:g} m of a mapped line under the "
        "max/p95 wire rule. Each A then uses training-fold rows only. The "
        f"{forecast['clean_screen']['near_line_m']:g} m buffer covers "
        "transmission lines only.",
        "The post hoc empirical A is fixed within each training fold before "
        "fitting k and c. In this curve sensitivity, cells starting at or "
        "above A are forced to no growth. "
        "Mixed classes use the largest member literature A; pooled fits share "
        "k and c while each class keeps its own fold A. The table reports "
        "held-out exceedance after the selection and wire exclusions. Its share "
        "need not equal 0.5%, because held-out blocks can have taller trees.",
        "",
        *_type_rows(metrics),
        "",
        "Fitted k/c bound warnings: " + (", ".join(bound) if bound else "none") + ".",
        f"{len(bound)} of {len(metrics['per_type'])} class fits touch a k or c "
        "bound. Their fitted shape parameters should not be interpreted "
        "biologically. Literature-only and record-tree A curves are worse "
        "than the type-median baseline at their 95% intervals; the post hoc "
        "curve ties it. Do not tune the curve further or use its shape as "
        "the growth prior.",
        "",
        "## Curve-shape diagnostic, not ecological support",
        "",
        "The 10 m versus 20 m check partly follows from forcing no growth "
        "when starting height reaches A. Quercus douglasii has A = 20 m, "
        "so its 20 m gain is zero by construction. Nearly flat gains and "
        "the mixed Eucalyptus reversal also limit interpretation. A "
        "'shorter gains more' entry does not validate tree biology.",
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
        "Several empirical map-class A values exceed the cited typical-upper "
        "species heights. Taller crowns of other species within polygons "
        "and residual LiDAR outliers are possible explanations, not verified "
        "causes. The empirical A is not a biological ceiling.",
        f"The Acer macrophyllum literature A of "
        f"{settings['max_height_m'][acer['vegetation_type']]} m uses a 2011 Oregon "
        "champion tree, an explicit exception to the typical-upper source "
        "rule. Held-out Acer exceedance was "
        f"{acer['saturation']['at_or_above_A']}/{acer['cells']}; the class "
        f"uses {acer['fit']['scope']} for curve fitting.",
        "Whole-block bootstrap intervals resample spatial blocks while "
        "holding the fitted fold models fixed; they omit refit variance "
        "and may therefore be too narrow.",
        "The LiDAR-loss screen selects a retrospective subset; it is never "
        "a forecast feature. No random visual audit of persistent forest "
        "cells has been completed. Fire, Hansen and LiDAR screens alone do "
        "not verify continuous undisturbed forest, so the growth-only sample "
        "and its upper-bound interpretation remain provisional.",
        "The mixed Eucalyptus literature A is 55 m from FEIS E. globulus. "
        "Kew and ANBG describe E. camaldulensis up to 45 m in its native "
        "Australian range; a person still needs to verify the Jepson entry. "
        "The exact excerpts and source dates are in reports/claims_log.md.",
        "An offline test changes a held-out fold's 2022 heights and confirms "
        "that fold's A and predictions do not change. "
        f"{settings['reviewer_spot_check']['reviewer']} reviewed the A-rule "
        f"implementation at {settings['reviewer_spot_check']['commit']} "
        f"during {settings['reviewer_spot_check']['review_window_utc']} "
        f"({settings['reviewer_spot_check']['session']}). This was an AI code "
        "spot-check by a reviewer who proposed the rule, not an independent "
        "human review; human sign-off remains pending.",
        "The same AI reviewer re-reviewed the post-review hardening through "
        f"commit {settings['reviewer_spot_check_followup']['commit']} during "
        f"{settings['reviewer_spot_check_followup']['review_window_utc']}. "
        "The six reviewer-authored adversarial tests, including a non-vacuity "
        "check, are retained in "
        f"{settings['reviewer_spot_check_followup']['evidence']}.",
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
