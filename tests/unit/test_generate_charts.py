from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.generate_charts import (
    build_hunyuan_image3_history_payload,
    build_qwen3_omni_history_payload,
    load_qwen_image_benchmark_history,
    load_wan22_benchmark_history,
    parse_qwen3_omni_filename,
    parse_result_test_filename,
)


def test_parse_qwen3_omni_filename_supports_expected_layout() -> None:
    parsed = parse_qwen3_omni_filename(Path("result_test_qwen3_omni_chunk_random_4_40_20260310-182556.json"))
    assert parsed == {
        "test_name": "qwen3_omni_chunk",
        "dataset_name": "random",
        "max_concurrency": 4,
        "num_prompts": 40,
        "timestamp_key": "20260310-182556",
        "sort_timestamp": "2026-03-10T18:25:56",
        "date": "2026-03-10 18:25:56",
    }


def test_parse_result_test_filename_strips_in_out_suffix_before_timestamp() -> None:
    parsed = parse_result_test_filename(
        Path("result_test_qwen3_omni_random_1_10_in100_out100_20260415-183805.json"),
    )
    assert parsed is not None
    assert parsed["test_name"] == "qwen3_omni"
    assert parsed["dataset_name"] == "random"
    assert parsed["max_concurrency"] == 1
    assert parsed["num_prompts"] == 10
    assert parsed["timestamp_key"] == "20260415-183805"


def test_parse_result_test_filename_strips_variable_in_out_lengths() -> None:
    parsed = parse_result_test_filename(
        Path("result_test_qwen3_omni_chunk_random_4_16_in2500_out900_20260415-192114.json"),
    )
    assert parsed is not None
    assert parsed["test_name"] == "qwen3_omni_chunk"
    assert parsed["max_concurrency"] == 4
    assert parsed["num_prompts"] == 16


def test_parse_result_test_filename_accepts_float_request_rate_token_for_random_mm() -> None:
    parsed = parse_result_test_filename(
        Path("result_test_qwen3_omni_random-mm_0.1_10_in100_out100_20260415-183805.json"),
    )
    assert parsed is not None
    assert parsed["test_name"] == "qwen3_omni"
    assert parsed["dataset_name"] == "random-mm"
    assert parsed["max_concurrency"] is None
    assert parsed["num_prompts"] == 10
    assert parsed["timestamp_key"] == "20260415-183805"


def test_parse_result_test_filename_strips_tts_inna_outna_placeholder_suffix() -> None:
    """Qwen3-TTS customvoice runs use _inna_outna instead of _in100_out100 before the timestamp."""
    parsed = parse_result_test_filename(
        Path(
            "result_test_qwen3_tts_customvoice_seed-tts-design_8_80_inna_outna_20260428-181951.json",
        ),
        frozenset({"random", "random-mm", "seed-tts-design", "seed-tts-text"}),
    )
    assert parsed is not None
    assert parsed["test_name"] == "qwen3_tts_customvoice"
    assert parsed["dataset_name"] == "seed-tts-design"
    assert parsed["max_concurrency"] == 8
    assert parsed["num_prompts"] == 80
    assert parsed["timestamp_key"] == "20260428-181951"


def test_qwen3_omni_history_groups_and_sorts_by_config_and_time(repo_root: Path, tmp_path: Path) -> None:
    source_dir = tmp_path / "qwen3omni"
    source_dir.mkdir()
    first = {
        "date": "20260308-181548",
        "endpoint_type": "openai-chat-omni",
        "backend": "openai-chat-omni",
        "model_id": "Qwen/Qwen3-Omni-30B-A3B-Instruct",
        "tokenizer_id": "Qwen/Qwen3-Omni-30B-A3B-Instruct",
        "request_rate": "inf",
        "request_throughput": 0.12,
        "output_throughput": 12.2,
        "total_token_throughput": 24.4,
        "mean_ttft_ms": 60.5,
        "p99_ttft_ms": 222.1,
        "mean_e2el_ms": 8188.9,
    }
    second = dict(first)
    second["mean_ttft_ms"] = 58.1
    third = dict(first)
    third["mean_ttft_ms"] = 80.4
    third["max_concurrency"] = 4
    third["num_prompts"] = 40

    (source_dir / "result_test_qwen3_omni_random_1_10_20260308-181548.json").write_text(json.dumps(first), encoding="utf-8")
    (source_dir / "result_test_qwen3_omni_random_1_10_20260309-181745.json").write_text(json.dumps(second), encoding="utf-8")
    (source_dir / "result_test_qwen3_omni_random_4_40_20260310-181940.json").write_text(json.dumps(third), encoding="utf-8")

    config = json.loads((repo_root / "data" / "config.json").read_text(encoding="utf-8"))
    payload = build_qwen3_omni_history_payload(config, source_dir)

    assert payload["record_count"] == 3
    assert payload["group_count"] == 2
    assert [item["source_file"] for item in payload["records"]] == [
        "result_test_qwen3_omni_random_1_10_20260309-181745.json",
        "result_test_qwen3_omni_random_1_10_20260308-181548.json",
        "result_test_qwen3_omni_random_4_40_20260310-181940.json",
    ]
    assert payload["groups"][0]["record_count"] == 2
    assert [item["date"] for item in payload["groups"][0]["records"]] == [
        "2026-03-09 18:17:45",
        "2026-03-08 18:15:48",
    ]
    assert payload["records"][0]["qps"] == "inf"
    assert payload["filter_options"]["qps"] == ["inf"]


def test_wan22_benchmark_only_loads_diffusion_result_with_wan22_in_name(tmp_path: Path) -> None:
    source_dir = tmp_path / "wan22"
    source_dir.mkdir()
    row = [
        {
            "test_name": "wan22_bench",
            "backend": "b",
            "timestamp": "20260401-120000",
            "server_params": {"model": "m"},
            "benchmark_params": {"name": "n", "dataset": "d"},
            "result": {
                "completed_requests": 1,
                "failed_requests": 0,
                "latency_mean": 1.5,
                "throughput_qps": 0.2,
                "peak_memory_mb_mean": 4096,
            },
        }
    ]
    (source_dir / "diffusion_result_test_wan22_vllm_20260401-120000.json").write_text(json.dumps(row), encoding="utf-8")
    (source_dir / "diffusion_result_test_qwen_image_20260401-120000.json").write_text(json.dumps(row), encoding="utf-8")
    (source_dir / "benchmark_results_test_wan22_20260401-120000.json").write_text(json.dumps(row), encoding="utf-8")
    records = load_wan22_benchmark_history(source_dir)
    assert len(records) == 1
    assert records[0]["test_name"] == "wan22_bench"


def test_qwen_image_benchmark_baseline_mapped_to_record_fields(tmp_path: Path) -> None:
    source_dir = tmp_path / "qwen_image"
    source_dir.mkdir()
    row = [
        {
            "test_name": "t",
            "backend": "b",
            "timestamp": "20260401-120000",
            "server_params": {"model": "m"},
            "benchmark_params": {
                "name": "n",
                "dataset": "random",
                "max-concurrency": 1,
                "num-prompts": 10,
                "baseline": {
                    "throughput_qps": 0.3,
                    "latency_mean": 3.5,
                    "peak_memory_mb_mean": 10240,
                },
            },
            "result": {
                "completed_requests": 1,
                "failed_requests": 0,
                "latency_mean": 2.0,
                "latency_median": 2.0,
                "latency_p99": 2.1,
                "throughput_qps": 0.4,
                "peak_memory_mb_mean": 8192,
            },
        }
    ]
    (source_dir / "diffusion_result_x.json").write_text(json.dumps(row), encoding="utf-8")
    records = load_qwen_image_benchmark_history(source_dir)
    assert len(records) == 1
    r0 = records[0]
    assert r0["baseline_throughput_qps"] == 0.3
    assert r0["baseline_e2e_latency_ms"] == 3500.0
    assert abs(r0["baseline_peak_memory_gb"] - 10.0) < 1e-6


def test_qwen_image_benchmark_sorts_numeric_group_fields_numerically(tmp_path: Path) -> None:
    source_dir = tmp_path / "qwen_image"
    source_dir.mkdir()
    rows = [
        {
            "test_name": "t",
            "backend": "b",
            "timestamp": "20260401-120000",
            "server_params": {"model": "m"},
            "benchmark_params": {"name": "n", "dataset": "random", "max-concurrency": 10, "num-prompts": 10},
            "result": {"completed_requests": 1, "failed_requests": 0, "latency_mean": 1.0},
        },
        {
            "test_name": "t",
            "backend": "b",
            "timestamp": "20260401-121000",
            "server_params": {"model": "m"},
            "benchmark_params": {"name": "n", "dataset": "random", "max-concurrency": 2, "num-prompts": 10},
            "result": {"completed_requests": 1, "failed_requests": 0, "latency_mean": 1.0},
        },
    ]
    (source_dir / "diffusion_result_sorting.json").write_text(json.dumps(rows), encoding="utf-8")

    records = load_qwen_image_benchmark_history(source_dir)

    assert [record["max_concurrency"] for record in records] == [2, 10]


def test_hunyuan_image3_history_payload_maps_diffusion_records(tmp_path: Path, repo_root: Path) -> None:
    source_dir = tmp_path / "hunyuan_image3"
    source_dir.mkdir()
    row = [
        {
            "test_name": "test_hunyuan_image3_ti2i_tp4_tp4_inline",
            "backend": "vllm-omni",
            "Hardware": "h200",
            "timestamp": "20260525-141005",
            "server_params": {
                "model": "tencent/HunyuanImage-3.0-Instruct",
                "serve_args": {"enable-diffusion-pipeline-profiler": True},
            },
            "benchmark_params": {
                "name": "inline_dataset_5_requests",
                "dataset": "custom",
                "task": "ti2i",
                "max-concurrency": 4,
                "num-prompts": 16,
            },
            "result": {
                "completed_requests": 16,
                "failed_requests": 0,
                "throughput_qps": 0.10495291600140096,
                "latency_mean": 35.56606174609624,
                "latency_median": 35.946332490071654,
                "latency_p99": 44.45902248136699,
                "peak_memory_mb_mean": 0,
            },
        }
    ]
    (source_dir / "diffusion_result_test_hunyuan_image3_it2i_20260525-140555.json").write_text(json.dumps(row), encoding="utf-8")
    config = json.loads((repo_root / "data" / "config.json").read_text(encoding="utf-8"))

    payload = build_hunyuan_image3_history_payload(config, source_dir)

    assert payload["record_count"] == 1
    rec = payload["records"][0]
    assert rec["model_id"] == "tencent/HunyuanImage-3.0-Instruct"
    assert rec["task"] == "ti2i"
    assert rec["completed_requests"] == 16
    assert abs(rec["throughput_qps"] - 0.10495291600140096) < 1e-12
    assert abs(rec["e2e_latency_ms"] - 35566.06174609624) < 1e-9
    assert "hardware" in rec
    assert "hardware" in payload["filters"]
    assert "hardware" in payload["table_columns"]
    assert "serve_args_enable_diffusion_pipeline_profiler" in payload["table_columns"]


def test_result_test_optional_baseline_object(tmp_path: Path, repo_root: Path) -> None:
    source_dir = tmp_path / "qwen3omni"
    source_dir.mkdir()
    first = {
        "baseline": {"mean_ttft_ms": 42.5, "output_throughput": 9.9},
        "endpoint_type": "openai-chat-omni",
        "backend": "openai-chat-omni",
        "model_id": "Qwen/Qwen3-Omni-30B-A3B-Instruct",
        "tokenizer_id": "Qwen/Qwen3-Omni-30B-A3B-Instruct",
        "request_throughput": 0.12,
        "output_throughput": 12.2,
        "total_token_throughput": 24.4,
        "mean_ttft_ms": 60.5,
    }
    (source_dir / "result_test_qwen3_omni_random_1_10_20260308-181548.json").write_text(json.dumps(first), encoding="utf-8")
    config = json.loads((repo_root / "data" / "config.json").read_text(encoding="utf-8"))
    payload = build_qwen3_omni_history_payload(config, source_dir)
    rec = payload["records"][0]
    assert rec["baseline_mean_ttft_ms"] == 42.5
    assert rec["baseline_output_throughput"] == 9.9


def test_output_files_created(repo_root: Path) -> None:
    result = subprocess.run(
        [sys.executable, "scripts/generate_charts.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert (repo_root / "docs" / "assets" / "charts" / "qwen3_omni_throughput_tokens_per_sec_1d.json").exists()
    assert (repo_root / "docs" / "assets" / "charts" / "qwen3_omni_throughput_tokens_per_sec_7d.json").exists()
    assert (repo_root / "docs" / "assets" / "charts" / "qwen3_omni_throughput_tokens_per_sec_30d.json").exists()
    assert (repo_root / "docs" / "assets" / "charts" / "qwen3_omni_tpot_ms_7d.json").exists()
    assert (repo_root / "docs" / "assets" / "charts" / "qwen3_omni_history.json").exists()
    assert (repo_root / "docs" / "assets" / "charts" / "qwen3_tts_history.json").exists()
    assert (repo_root / "docs" / "assets" / "charts" / "qwen_image_history.json").exists()
    assert (repo_root / "docs" / "assets" / "charts" / "qwen_image_edit_history.json").exists()
    assert (repo_root / "docs" / "assets" / "charts" / "qwen_image_edit_2509_history.json").exists()
    assert (repo_root / "docs" / "assets" / "charts" / "wan22_history.json").exists()
    assert (repo_root / "docs" / "assets" / "charts" / "qwen3_tts_real_time_factor_7d.json").exists()
    assert (repo_root / "docs" / "assets" / "charts" / "qwen_image_e2e_latency_ms_7d.json").exists()
    assert (repo_root / "docs" / "assets" / "charts" / "wan22_peak_memory_gb_7d.json").exists()
