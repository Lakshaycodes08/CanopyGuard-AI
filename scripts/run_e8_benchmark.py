"""Run the preregistered ECHOSAT 2022 product-height comparison."""

from canopyguard.config import load_config
from canopyguard.evaluation.product_benchmark import run_e8_benchmark
from canopyguard.utils import set_seeds


def main() -> int:
    settings = load_config("configs/product_benchmark.yaml")["echosat_benchmark"]
    set_seeds(settings["seed"])
    result = run_e8_benchmark()
    print(f"E8 paired cells: {result['primary']['cells']:,}")
    print(f"Report: {settings['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
