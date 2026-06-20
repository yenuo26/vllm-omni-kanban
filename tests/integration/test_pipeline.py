from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_full_pipeline_happy_path(repo_root: Path, sample_daily_batch: dict, tmp_path: Path) -> None:
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(json.dumps(sample_daily_batch), encoding="utf-8")

    process = subprocess.run(
        [sys.executable, "scripts/process_results.py", "--input", str(batch_path), "--source", "schedule"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    charts = subprocess.run(
        [sys.executable, "scripts/generate_charts.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    alerts = subprocess.run(
        [sys.executable, "scripts/check_alerts.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode == 0
    assert charts.returncode == 0
    assert alerts.returncode == 0
    assert (repo_root / "docs" / "reports" / "2026-03-14.md").exists()
    assert (repo_root / "docs" / "assets" / "charts" / "hardware_status.json").exists()
    assert (repo_root / "data" / "alerts.json").exists()
