from __future__ import annotations

import json

import pandas as pd

from canopyguard.config import load_config
from canopyguard.forecasting.growth_contrasts import bootstrap_pairs
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
            results = bootstrap_pairs(
                pd.read_parquet(path), settings, int(config["seed"])
            )
            report[f"scale_x{factor}_block_{size}m"] = results
            for name, result in results.items():
                print(
                    f"x{factor} b{size} {name}: {result['difference']:+.3f} m "
                    f"[{result['ci_low']:+.3f}, {result['ci_high']:+.3f}] "
                    f"blocks {int(result['blocks'])}",
                    flush=True,
                )
    output = ensure_parent(project_root() / settings["output"])
    output.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
