from pathlib import Path

from canopyguard.text_hygiene import find_disallowed_chars, iter_text_files


def test_find_disallowed_chars_reports_em_dash() -> None:
    findings = find_disallowed_chars("bad\u2014dash")

    assert findings == [(1, "\u2014", "em dash")]


def test_iter_text_files_skips_agents_directory(tmp_path: Path) -> None:
    keep = tmp_path / "README.md"
    keep.write_text("ok", encoding="utf-8")
    ignored_dir = tmp_path / ".agents" / "skills"
    ignored_dir.mkdir(parents=True)
    ignored = ignored_dir / "SKILL.md"
    ignored.write_text("ignore", encoding="utf-8")

    assert iter_text_files(tmp_path) == [keep]
