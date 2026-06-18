"""MkDocs hooks: sync Buildkite raw JSON into data/results, then regenerate charts.

Uses on_startup (not on_pre_build) so writes under docs/assets/charts/ do not
re-trigger livereload in an endless loop; generate_charts updates generated_at every run.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# (model_name subdirectory under data/results/, keyword matching path or basename under buildkite_nightly_raw)
_BUILDKITE_RAW_SYNCS: tuple[tuple[str, str], ...] = (
    ("qwen3omni", "qwen3_omni"),
    ("qwen3tts", "qwen3_tts"),
    ("qwen_image", "qwen_image"),
    ("qwen_image_edit", "qwen_image_edit"),
    ("qwen_image_edit_2509", "qwen_image_edit_2509"),
    ("qwen_image_edit_2511", "qwen_image_edit_2511"),
    ("wan22", "wan22"),
    ("hunyuan_image3", "hunyuan_image3"),
    ("bagel", "bagel"),
    ("voxcpm2", "voxcpm2"),
)

_LOCAL_RAW_SYNCS: tuple[tuple[str, str], ...] = (
    ("hunyuan_image3", "hunyuan_image"),
)


def _run_sync(repo_root: Path, sync_script: Path, model_name: str, model_keywords: str, raw_root: Path | None = None) -> None:
    cmd = [
        sys.executable,
        str(sync_script),
        "--model-name",
        model_name,
        "--model-keywords",
        model_keywords,
    ]
    if raw_root is not None:
        cmd.extend(["--raw-root", str(raw_root)])
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"sync_buildkite_raw_model_results.py ({model_name}) exited with status {proc.returncode}",
        )


def on_startup(command: str, dirty: bool, **kwargs) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    sync_script = repo_root / "scripts" / "sync_buildkite_raw_model_results.py"
    for model_name, model_keywords in _BUILDKITE_RAW_SYNCS:
        _run_sync(repo_root, sync_script, model_name, model_keywords)

    local_raw_root = repo_root / "data" / "local_nightly_raw"
    for model_name, model_keywords in _LOCAL_RAW_SYNCS:
        _run_sync(repo_root, sync_script, model_name, model_keywords, local_raw_root)

    gen_script = repo_root / "scripts" / "generate_charts.py"
    proc = subprocess.run(
        [sys.executable, str(gen_script)],
        cwd=str(repo_root),
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"generate_charts.py exited with status {proc.returncode}")

    report_sync = repo_root / "scripts" / "sync_nightly_test_reports.py"
    proc = subprocess.run(
        [sys.executable, str(report_sync)],
        cwd=str(repo_root),
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"sync_nightly_test_reports.py exited with status {proc.returncode}")
