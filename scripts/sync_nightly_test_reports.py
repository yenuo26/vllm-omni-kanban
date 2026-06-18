#!/usr/bin/env python3
"""Copy nightly HTML reports into docs/assets and write manifest.json for the Report page."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "data" / "nightly_test_report"
OUTPUT_DIR = ROOT / "docs" / "assets" / "nightly_reports"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

_REPORT_RE = re.compile(
    r"^nightly-report-buildkite-latest-(?P<date>\d{4}-\d{2}-\d{2})\.html$",
    re.IGNORECASE,
)


def _parse_report(path: Path) -> dict[str, Any] | None:
    match = _REPORT_RE.match(path.name)
    if not match:
        return None
    date_str = match.group("date")
    return {
        "id": date_str,
        "date": date_str,
        "label": f"Nightly report {date_str}",
        "filename": path.name,
        "url": f"assets/nightly_reports/{path.name}",
    }


def build_manifest(source_dir: Path = SOURCE_DIR) -> dict[str, Any]:
    nightly: list[dict[str, Any]] = []
    if source_dir.is_dir():
        for path in sorted(source_dir.glob("*.html"), reverse=True):
            entry = _parse_report(path)
            if entry:
                nightly.append(entry)
    return {
        "generated_at": datetime.now().isoformat(),
        "source_dir": str(source_dir.relative_to(ROOT)) if source_dir.is_relative_to(ROOT) else str(source_dir),
        "nightly": nightly,
        "release": [],
    }


def sync_nightly_test_reports(
    source_dir: Path = SOURCE_DIR,
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(source_dir)

    copied_names: set[str] = set()
    for entry in manifest["nightly"]:
        src = source_dir / entry["filename"]
        dst = output_dir / entry["filename"]
        if src.is_file():
            shutil.copy2(src, dst)
            copied_names.add(entry["filename"])

    for stale in output_dir.glob("*.html"):
        if stale.name not in copied_names:
            stale.unlink()

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    manifest = sync_nightly_test_reports()
    print(f"Synced {len(manifest['nightly'])} nightly report(s) -> {OUTPUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
