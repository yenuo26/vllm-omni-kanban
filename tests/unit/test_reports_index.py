from __future__ import annotations

from pathlib import Path

from scripts.mkdocs_hooks import build_reports_index, regenerate_reports_index


def _make_reports(tmp_path: Path) -> Path:
    reports = tmp_path / "docs" / "reports"
    reports.mkdir(parents=True)
    for name in ("2026-03-07", "2026-03-14", "2026-06-01"):
        (reports / f"{name}.md").write_text(f"# Daily Report - {name}\n", encoding="utf-8")
    # Non-report files must be ignored.
    (reports / "index.md").write_text("old\n", encoding="utf-8")
    (reports / "notes.md").write_text("notes\n", encoding="utf-8")
    return reports


def test_build_reports_index_lists_reports_newest_first(tmp_path: Path) -> None:
    reports = _make_reports(tmp_path)
    content = build_reports_index(reports)
    lines = [line for line in content.splitlines() if line.startswith("- [")]
    assert lines == [
        "- [2026-06-01](2026-06-01.md)",
        "- [2026-03-14](2026-03-14.md)",
        "- [2026-03-07](2026-03-07.md)",
    ]
    assert "notes" not in content


def test_build_reports_index_empty_dir(tmp_path: Path) -> None:
    empty = tmp_path / "reports"
    empty.mkdir()
    assert "_No reports archived yet._" in build_reports_index(empty)


def test_regenerate_reports_index_writes_only_on_change(tmp_path: Path) -> None:
    reports = _make_reports(tmp_path)
    index_path = reports / "index.md"

    regenerate_reports_index(tmp_path)
    first = index_path.read_text(encoding="utf-8")
    assert "2026-06-01" in first

    first_mtime = index_path.stat().st_mtime_ns
    regenerate_reports_index(tmp_path)
    assert index_path.stat().st_mtime_ns == first_mtime
