from __future__ import annotations

import json

from canopyguard.config import load_config
from canopyguard.lidar.harmonize import admitted_names, sample_radius_for, screen_epochs


def main() -> int:
    lidar_config = load_config("configs/lidar.yaml")
    results = screen_epochs(lidar_config)
    print(json.dumps(results, indent=2))
    admitted = admitted_names(results)
    if not admitted:
        print("No epoch passed the admission screen")
        return 1
    print(f"Admitted: {', '.join(admitted)}")
    print(f"Sample radius: {sample_radius_for(lidar_config, results):.4f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
