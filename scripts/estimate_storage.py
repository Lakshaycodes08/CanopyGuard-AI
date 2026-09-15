from __future__ import annotations

import argparse

from canopyguard.features.cube import estimate_array_gib


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate uncompressed cube storage.")
    parser.add_argument("shape", nargs="+", type=int, help="Array dimensions.")
    parser.add_argument("--dtype", required=True, help="NumPy dtype, such as float32.")
    parser.add_argument("--working-copies", type=int, default=1)
    args = parser.parse_args()

    size_gib = estimate_array_gib(args.shape, args.dtype, args.working_copies)
    print(f"Estimated uncompressed storage: {size_gib:.2f} GiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
