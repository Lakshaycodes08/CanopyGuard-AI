import argparse

from canopyguard.io import extract_dumps


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract base64 file dumps from a colab_bootstrap.py log."
    )
    parser.add_argument("log_path")
    parser.add_argument("out_dir")
    args = parser.parse_args()
    for name in extract_dumps(args.log_path, args.out_dir):
        print(name)


if __name__ == "__main__":
    main()
