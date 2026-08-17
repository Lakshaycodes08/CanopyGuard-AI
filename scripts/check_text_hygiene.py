from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from canopyguard.text_hygiene import find_disallowed_chars, iter_text_files  # noqa: E402


def main() -> int:
    failed = False

    for path in iter_text_files(ROOT):
        text = path.read_text(encoding="utf-8")
        findings = find_disallowed_chars(text)
        for line_number, char, reason in findings:
            relative = path.relative_to(ROOT)
            codepoint = f"U+{ord(char):04X}"
            print(f"{relative}:{line_number}: {codepoint} {reason}")
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
