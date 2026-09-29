"""Produce the configured unique-cell archive from the full LiDAR labels."""

from canopyguard.config import load_config
from canopyguard.lidar.label_quality import build_unique_archive


def main() -> int:
    audit = build_unique_archive(load_config("configs/lidar.yaml"))
    print(f"unique valid cells: {audit['unique_valid_cells']:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
