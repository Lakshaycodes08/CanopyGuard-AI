"""Write the evidence-bounded E4/E5 stage-two gate report."""

from __future__ import annotations

from canopyguard.io import ensure_parent, project_root


def _comparison(score: dict, model: str) -> str:
    entry = score[model]
    interval = entry["minus_stage1"]
    return (
        f"{entry['mae_m']:.3f} | {interval['difference_m']:+.3f} "
        f"[{interval['ci_low_m']:+.3f}, {interval['ci_high_m']:+.3f}] | "
        f"{entry['decision']}"
    )


def write_stage2_report(result: dict) -> None:
    """Write both forest screens, all declared sensitivities, and feature weights."""
    settings = result["settings"]
    primary = result["screens"]["forest_loss_off_2000m"]
    lines = [
        "# Stage-two residual check, 2013-2022",
        "",
        f"Run: {result['generated_utc']}. "
        f"Base revision: `{result['git_base_revision']}`.",
        "",
        "## Pre-specified decision",
        "",
        "Each E4 ridge and E5 LightGBM model passes only if the 95% whole-block "
        "interval for its MAE minus the matched training-fold stage-one median "
        "MAE lies entirely below zero on the forest LiDAR-loss-OFF 2 km screen. "
        "The LiDAR-loss-ON screen is a retrospectively selected upper bound. "
        "The loss-OFF screen also uses retrospective fire and Hansen screens; "
        "neither is a fully prospective 2013 evaluation. This rule, feature set, "
        "settings, and sensitivities were frozen in `reports/stage2_gate_prereg.md` "
        "before E4 or E5 fitting.",
        "",
        f"**E4 ridge: {primary['ridge']['decision']}. "
        f"E5 LightGBM: {primary['lightgbm']['decision']}.**",
        "",
        "## Paired spatial comparisons",
        "",
        "Cell-weighted MAE and model-minus-stage-one differences are metres. "
        "Intervals use 2,000 whole-block draws with fold fits fixed; they omit "
        "refit variance. Each row refits the stage-one median and both models "
        "in five spatial training folds on the same retained cells.",
        "",
        "| Screen | Block | Cells | Blocks | Stage 1 MAE | Ridge MAE | "
        "Ridge - stage 1 [95% CI] | Ridge CI below zero? | LightGBM MAE | "
        "LightGBM - stage 1 [95% CI] | LightGBM CI below zero? |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | --- | --- |",
    ]
    for key, score in result["screens"].items():
        name, size = key.rsplit("_", 1)
        ridge = _comparison(score, "ridge").split(" | ")
        lightgbm = _comparison(score, "lightgbm").split(" | ")
        lines.append(
            f"| {name.replace('_', ' ')} | {size} | {score['cells']:,} | "
            f"{score['blocks']} | {score['mae_stage1_m']:.3f} | "
            f"{ridge[0]} | {ridge[1]} | {ridge[2]} | "
            f"{lightgbm[0]} | {lightgbm[1]} | {lightgbm[2]} |"
        )
    lines.extend(
        [
            "",
            "## Inputs, omissions, and fit counts",
            "",
            "The observed 2013-to-2022 p95 height change is the target. The only "
            "predictors are 2013 mean/p95/max LiDAR height, the 2013 Sonoma map "
            "class, and four static 3DEP terrain fields joined by existing 10 m "
            "cell IDs in EPSG:6339. The target residual subtracts the median "
            "increment fitted on each training fold. All preprocessing, including "
            "vegetation vocabulary and numeric imputation, is fit on training "
            "cells only. No 2022 LiDAR or later satellite observation is a predictor.",
            "",
            "Terrain-null exclusions before model fit: "
            + ", ".join(
                f"{name} {count:,}"
                for name, count in result["terrain_excluded"].items()
            )
            + ".",
            "",
            f"Software: scikit-learn {result['versions']['sklearn']}; "
            f"LightGBM {result['versions']['lightgbm']}. Five folds per row; "
            "each fold has one fixed-setting fit per model. "
            "No hyperparameter or feature tuning was performed.",
            "",
            "Primary fold training/test cell counts: "
            + "; ".join(
                f"fold {item['fold']}: {item['train']:,}/{item['test']:,}"
                for item in primary["fold_counts"]
            )
            + ".",
            "",
            "## Primary-screen feature weights",
            "",
            "Ridge coefficients are means across folds after training-fold "
            "standardization of numeric predictors; vegetation indicators are "
            "unscaled. LightGBM values are mean split gain, useful for ranking "
            "within this fitted model only. Zero is used when a category is "
            "absent from a fold's training vocabulary.",
            "",
            "| Encoded feature | Mean ridge coefficient | Mean LightGBM gain |",
            "| --- | ---: | ---: |",
        ]
    )
    weights = result["primary_feature_weights"]
    names = sorted(set(weights["ridge"]) | set(weights["lightgbm"]))
    for name in names:
        lines.append(
            f"| {name} | {weights['ridge'].get(name, 0.0):+.4f} | "
            f"{weights['lightgbm'].get(name, 0.0):.1f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation limit",
            "",
            "The positive LiDAR-loss-ON sensitivity does not rescue either "
            "model's failing pre-specified loss-OFF result. Its screen uses "
            "target-epoch LiDAR loss and is an optimistic upper bound.",
            "",
            "A PASS applies to this screened, spatially blocked comparison and "
            "does not establish future-year forecast skill, causal terrain "
            "effects, species-pure growth, or engineering clearance. A FAIL is "
            "retained as the pre-specified result. Scientific review of the G3 "
            "prior remains pending in issue #19.",
            "",
        ]
    )
    path = ensure_parent(project_root() / settings["report_path"])
    path.write_text("\n".join(lines), encoding="utf-8")
