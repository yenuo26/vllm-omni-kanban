from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_render_charts_js_unit_tests(repo_root: Path) -> None:
    if shutil.which("node") is None:
        pytest.skip("node is required for render_charts.js unit tests")

    result = subprocess.run(
        ["node", "--test", "tests/js/render_charts.test.js"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
