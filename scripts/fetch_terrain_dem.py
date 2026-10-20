"""Download the pinned public 3DEP tile for static terrain features."""

from canopyguard.config import load_config
from canopyguard.data.terrain_dem import fetch_terrain_dem


def main() -> int:
    forecast = load_config("configs/forecasting.yaml")
    study = load_config("configs/study_area.yaml")
    print(fetch_terrain_dem(forecast, study))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
