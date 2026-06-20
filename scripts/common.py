from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

# pytest verbose test id at line start, e.g. "tests/e2e/accuracy/test_x.py::test_case[fp8] PASSED"
_PYTEST_CASE_RE = re.compile(r"^(?P<file>tests/\S+?\.py)::(?P<name>[^\s]+)")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def flatten_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in metrics.items():
        if key not in {"stability", "performance", "accuracy", "custom"} and not isinstance(value, dict):
            flat[key] = value
    for section in ("stability", "performance", "accuracy", "custom"):
        payload = metrics.get(section, {})
        if isinstance(payload, dict):
            flat.update(payload)
    return flat


def _parse_float(raw: str) -> float | None:
    try:
        return float(raw)
    except ValueError:
        return None


def parse_log_metric_tables(log_text: str) -> list[dict[str, Any]]:
    """Extract metric tables from a pytest log.

    Tests print accuracy results as a tabulate grid table::

        | Metric                      |   Value |   L20x Reference |
        +=============================+=========+==================+
        | COT similarity to reference |  0.9658 |           0.9644 |

    Each metric row is attributed to the nearest preceding pytest test id line
    (``tests/<path>.py::<case>``), so a single log covering multiple tests keeps
    metrics separated per test case.

    Returns a list of dicts with keys ``test_file``, ``test_name``, ``metric``,
    ``value`` and ``reference`` (the optional reference column, ``None`` when absent).
    """
    rows: list[dict[str, Any]] = []
    current_file: str | None = None
    current_name: str | None = None
    in_table = False

    for raw_line in log_text.splitlines():
        line = raw_line.strip()
        case_match = _PYTEST_CASE_RE.match(line)
        if case_match:
            current_file = case_match.group("file")
            current_name = case_match.group("name")
            in_table = False
            continue

        if line.startswith("+"):
            # Grid separator rows (+---+ / +===+) keep the current table open.
            continue
        if not line.startswith("|"):
            in_table = False
            continue

        cols = [col.strip() for col in line.strip("|").split("|")]
        if len(cols) < 2:
            in_table = False
            continue
        if cols[0] == "Metric" and cols[1] == "Value":
            in_table = True
            continue
        if not in_table:
            continue

        value = _parse_float(cols[1])
        if value is None:
            continue
        reference = _parse_float(cols[2]) if len(cols) > 2 and cols[2] else None
        rows.append(
            {
                "test_file": current_file,
                "test_name": current_name,
                "metric": cols[0],
                "value": value,
                "reference": reference,
            }
        )

    return rows
