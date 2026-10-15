"""Recompute post hoc forest-population and objective sensitivities."""

from canopyguard.config import load_config
from canopyguard.evaluation.posthoc_forest import run_posthoc_forest
from canopyguard.utils import set_seeds


def main() -> int:
    forecast = load_config("configs/forecasting.yaml")
    outputs = load_config("configs/posthoc_forest.yaml")
    set_seeds(int(forecast["seed"]))
    result = run_posthoc_forest(forecast["stage1_growth_model"], outputs)
    primary = str(forecast["stage1_growth_model"]["growth_curve"]["primary_block_m"])
    print(f"Post hoc forest cells: {result['all_forest'][primary]['cells']:,}")
    print(f"Report: {outputs['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
