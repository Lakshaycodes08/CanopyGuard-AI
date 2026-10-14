"""Run issue 8's spatial growth-curve gate and write its report."""

from canopyguard.config import load_config
from canopyguard.evaluation.growth_gate import run_growth_gate
from canopyguard.utils import set_seeds


def main() -> int:
    forecast = load_config("configs/forecasting.yaml")
    set_seeds(int(forecast["seed"]))
    result = run_growth_gate(forecast["stage1_growth_model"])
    print(f"G3: {result['decision']}")
    print(f"report: {result['settings']['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
