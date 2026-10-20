"""Run the pre-specified E4/E5 residual gate on local data."""

from canopyguard.config import load_config
from canopyguard.evaluation.stage2_gate import run_stage2_gate
from canopyguard.utils import set_seeds


def main() -> int:
    forecast = load_config("configs/forecasting.yaml")
    study = load_config("configs/study_area.yaml")
    set_seeds(int(forecast["seed"]))
    result = run_stage2_gate(forecast, study)
    primary = result["screens"]["forest_loss_off_2000m"]
    print({name: primary[name]["decision"] for name in ("ridge", "lightgbm")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
