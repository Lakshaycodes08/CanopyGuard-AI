"""Run issue 8's spatial growth-curve gate or its no-fit preflight."""

import argparse

from canopyguard.config import load_config
from canopyguard.evaluation.growth_gate import growth_preflight, run_growth_gate
from canopyguard.utils import set_seeds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    forecast = load_config("configs/forecasting.yaml")
    set_seeds(int(forecast["seed"]))
    if args.preflight_only:
        growth_preflight(forecast["stage1_growth_model"])
        path = forecast["stage1_growth_model"]["growth_curve"]["preflight_path"]
        print(f"preflight: {path}")
        return 0
    result = run_growth_gate(forecast["stage1_growth_model"])
    print(f"G3: {result['decision']}")
    print(f"report: {result['settings']['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
