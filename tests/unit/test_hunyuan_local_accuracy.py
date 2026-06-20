from __future__ import annotations

import json
from pathlib import Path

from scripts.common import parse_log_metric_tables
from scripts.generate_charts import (
    build_hunyuan_image3_accuracy_payload,
    load_hunyuan_local_accuracy_records,
)

# Trimmed-down pytest log: two test cases, grid tables in the real tabulate format.
SAMPLE_LOG = """\
============================= test session starts ==============================
collected 4854 items / 6 selected

tests/e2e/accuracy/test_hunyuan_image3.py::test_image_to_image_alignment_online INFO 06-09 06:17:24 [scheduler.py:239] Chunked prefill is enabled.
Loading text similarity model: BAAI/bge-m3
[ONLINE] +-----------------------------+---------+------------------+
| Metric                      |   Value |   L20x Reference |
+=============================+=========+==================+
| COT similarity to reference |  0.9658 |           0.9644 |
+-----------------------------+---------+------------------+
| COT prefix match            | 29      |          29      |
+-----------------------------+---------+------------------+
| PSNR (dB)                   | 14.05   |          14.1    |
+-----------------------------+---------+------------------+
PASSED
tests/e2e/accuracy/test_hunyuan_image3.py::test_quantized_dit_matches_bf16_accuracy[fp8]
| Metric | Value |
+========+=======+
| SSIM   | 0.28  |
+--------+-------+
PASSED
tests/e2e/accuracy/test_videogen_modelopt_quant.py::test_other_model
| Metric | Value | L20x Reference |
+========+=======+================+
| CLIP   | 0.5   | 0.49           |
+--------+-------+----------------+
PASSED
"""


def test_parse_log_metric_tables_attributes_rows_to_test_cases() -> None:
    rows = parse_log_metric_tables(SAMPLE_LOG)
    assert len(rows) == 5

    first = rows[0]
    assert first["test_file"] == "tests/e2e/accuracy/test_hunyuan_image3.py"
    assert first["test_name"] == "test_image_to_image_alignment_online"
    assert first["metric"] == "COT similarity to reference"
    assert first["value"] == 0.9658
    assert first["reference"] == 0.9644

    # Table without a reference column yields reference=None.
    ssim = rows[3]
    assert ssim["test_name"] == "test_quantized_dit_matches_bf16_accuracy[fp8]"
    assert ssim["metric"] == "SSIM"
    assert ssim["reference"] is None

    # Rows from the second file are attributed to their own test case.
    assert rows[4]["test_file"] == "tests/e2e/accuracy/test_videogen_modelopt_quant.py"


def test_parse_log_metric_tables_ignores_text_without_tables() -> None:
    assert parse_log_metric_tables("no table here\n| stray | line |\n") == []


def test_load_hunyuan_local_accuracy_records(tmp_path: Path) -> None:
    # Filename intentionally has no "hunyuan" in it: discovery must be content-based.
    log_dir = tmp_path / "manual_20260611"
    log_dir.mkdir()
    (log_dir / "local_pytest.log").write_text(SAMPLE_LOG, encoding="utf-8")
    # Non-date directories are skipped.
    other_dir = tmp_path / "manual_notadate"
    other_dir.mkdir()
    (other_dir / "x.log").write_text(SAMPLE_LOG, encoding="utf-8")

    records, labels = load_hunyuan_local_accuracy_records(tmp_path)

    assert len(records) == 2
    online = next(r for r in records if r["test_name"] == "test_image_to_image_alignment_online")
    assert online["date"] == "2026-06-11"
    assert online["cot_similarity_to_reference"] == 0.9658
    assert online["baseline_cot_similarity_to_reference"] == 0.9644
    assert online["psnr_db"] == 14.05
    assert online["config_key"].endswith("::test_image_to_image_alignment_online")

    # Non-hunyuan test rows are filtered out.
    assert all("videogen" not in r["test_file"] for r in records)
    assert labels["psnr_db"] == "PSNR (dB)"
    assert labels["cot_prefix_match"] == "COT prefix match"


def test_build_hunyuan_image3_accuracy_payload(tmp_path: Path, repo_root: Path) -> None:
    log_dir = tmp_path / "manual_20260608"
    log_dir.mkdir()
    (log_dir / "test_hunyuan_image3.log").write_text(SAMPLE_LOG, encoding="utf-8")

    config = json.loads((repo_root / "data" / "config.json").read_text(encoding="utf-8"))
    payload = build_hunyuan_image3_accuracy_payload(config, tmp_path)

    assert payload["record_count"] == 2
    assert payload["group_fields"] == ["test_file", "test_name"]
    group_titles = {group["title"] for group in payload["metric_groups"]}
    assert "PSNR (dB)" in group_titles
    assert "SSIM" in group_titles
    assert payload["filter_options"]["test_name"] == [
        "test_image_to_image_alignment_online",
        "test_quantized_dit_matches_bf16_accuracy[fp8]",
    ]
    assert payload["table_columns"][0] == "date"
    assert "psnr_db" in payload["table_columns"]
