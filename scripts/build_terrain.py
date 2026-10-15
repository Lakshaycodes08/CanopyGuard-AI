"""Build 10 m static terrain predictors on the LiDAR cell identifiers."""

from canopyguard.config import load_config
from canopyguard.features.terrain import build_terrain_table


def main() -> int:
    forecast = load_config("configs/forecasting.yaml")
    study = load_config("configs/study_area.yaml")
    label_crs = load_config("configs/lidar.yaml")["harmonization"]["target_crs"]
    print(build_terrain_table(forecast, study, label_crs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
