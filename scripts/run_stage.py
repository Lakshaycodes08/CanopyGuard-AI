from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a named CanopyGuard stage.")
    parser.add_argument("stage", help="Stage name to run after implementation.")
    args = parser.parse_args()
    raise NotImplementedError(f"Stage is not implemented yet: {args.stage}")


if __name__ == "__main__":
    raise SystemExit(main())
