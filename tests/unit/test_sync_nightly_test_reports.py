"""Tests for nightly report sync (no network)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.sync_nightly_test_reports import build_manifest, sync_nightly_test_reports


def test_build_manifest_from_html_files(tmp_path: Path) -> None:
    source = tmp_path / "nightly_test_report"
    source.mkdir()
    (source / "nightly-report-buildkite-latest-2026-06-17.html").write_text("<html></html>", encoding="utf-8")
    (source / "nightly-report-buildkite-latest-2026-06-18.html").write_text("<html></html>", encoding="utf-8")
    (source / "ignored.txt").write_text("x", encoding="utf-8")

    manifest = build_manifest(source)

    assert len(manifest["nightly"]) == 2
    assert manifest["nightly"][0]["date"] == "2026-06-18"
    assert manifest["nightly"][0]["url"].endswith("nightly-report-buildkite-latest-2026-06-18.html")
    assert manifest["release"] == []


def test_sync_nightly_test_reports_writes_manifest_and_html(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    (source / "nightly-report-buildkite-latest-2026-06-17.html").write_text("<html>ok</html>", encoding="utf-8")

    manifest = sync_nightly_test_reports(source_dir=source, output_dir=output)

    assert (output / "manifest.json").is_file()
    copied = output / "nightly-report-buildkite-latest-2026-06-17.html"
    assert copied.read_text(encoding="utf-8") == "<html>ok</html>"
    on_disk = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk["nightly"][0]["id"] == manifest["nightly"][0]["id"]
