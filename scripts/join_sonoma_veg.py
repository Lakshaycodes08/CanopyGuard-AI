"""Join the official Sonoma vegetation map to the local LiDAR label cells."""

from canopyguard.config import load_config
from canopyguard.data.sonoma_veg import build_vegetation_table


def main() -> int:
    forecast = load_config("configs/forecasting.yaml")["stage1_growth_model"]
    study = load_config("configs/study_area.yaml")
    audit = build_vegetation_table(forecast, study)
    print(f"cells: {audit['cells']:,}")
    print(
        f"uncertain: {audit['uncertain_cells']:,} ({audit['uncertain_fraction']:.1%})"
    )
    print(f"pooled cells: {audit['pooled_cells']:,}")
    for name, count in sorted(
        audit["vegetation_type_counts"].items(), key=lambda item: -item[1]
    )[:15]:
        print(f"{name}: {count:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
