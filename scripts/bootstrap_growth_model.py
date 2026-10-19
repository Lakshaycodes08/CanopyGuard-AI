from __future__ import annotations

import json

import pandas as pd

from canopyguard.config import load_config
from canopyguard.evaluation.bootstrap import excludes_zero, paired_block_bootstrap
from canopyguard.forecasting.growth_model import paired_error_vectors
from canopyguard.io import data_path, ensure_parent, project_root
from canopyguard.provenance import current_commit


def main() -> int:
    config = load_config("configs/growth.yaml")
    settings = config["bootstrap"]
    base = data_path(config["table"]["output"])
    report: dict = {"git_commit": current_commit(), "seed": config["seed"]}
    for factor in settings["scales"]:
        for size in settings["block_sizes_m"]:
            path = base.with_name(f"growth_heldout_x{factor}_b{size}{base.suffix}")
            held_out = pd.read_parquet(path)
            predictions = {
                column.removeprefix("pred_"): held_out[column].to_numpy()
                for column in held_out.columns
                if column.startswith("pred_")
            }
            y = held_out["y"].to_numpy()
            results = {}
            for first, second in settings["pairs"]:
                errors_a, errors_b = paired_error_vectors(y, predictions, first, second)
                result = paired_block_bootstrap(
                    errors_a,
                    errors_b,
                    held_out["block_id"],
                    resamples=int(settings["resamples"]),
                    confidence_level=float(settings["confidence_level"]),
                    seed=int(config["seed"]),
                )
                result["excludes_zero"] = bool(excludes_zero(result))
                results[f"{first}_minus_{second}"] = result
                print(
                    f"x{factor} b{size} {first} - {second}: "
                    f"{result['difference']:+.3f} m "
                    f"[{result['ci_low']:+.3f}, {result['ci_high']:+.3f}] "
                    f"blocks {int(result['blocks'])}",
                    flush=True,
                )
            report[f"scale_x{factor}_block_{size}m"] = results
    output = ensure_parent(project_root() / settings["output"])
    output.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
