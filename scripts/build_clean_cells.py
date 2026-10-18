"""Produce issue 8's independently screened clean-cell table."""

from canopyguard.config import load_config
from canopyguard.evaluation.clean_cells import build_clean_cells
from canopyguard.utils import set_seeds


def main() -> int:
    forecast = load_config("configs/forecasting.yaml")
    set_seeds(int(forecast["seed"]))
    study = load_config("configs/study_area.yaml")
    audit = build_clean_cells(forecast["stage1_growth_model"], study)
    print(f"clean cells: {audit['clean_cells']:,} / {audit['all_cells']:,}")
    for name, count in audit["sequential_removed"].items():
        print(f"{name}: {count:,} removed")
    for name, count in sorted(
        audit["clean_by_type"].items(), key=lambda item: -item[1]
    )[:20]:
        print(f"{name}: {count:,} clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
