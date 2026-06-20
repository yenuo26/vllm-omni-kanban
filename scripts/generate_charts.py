from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.common import flatten_metrics, load_json, parse_log_metric_tables, save_json

DATA_DIR = ROOT / "data"
RESULTS_DIR = DATA_DIR / "results"
INDEX_PATH = DATA_DIR / "index.json"
CONFIG_PATH = DATA_DIR / "config.json"
CHARTS_DIR = ROOT / "docs" / "assets" / "charts"
QWEN3_OMNI_HISTORY_PATH = CHARTS_DIR / "qwen3_omni_history.json"
QWEN3_TTS_HISTORY_PATH = CHARTS_DIR / "qwen3_tts_history.json"
QWEN_IMAGE_HISTORY_PATH = CHARTS_DIR / "qwen_image_history.json"
QWEN_IMAGE_LAYERED_HISTORY_PATH = CHARTS_DIR / "qwen_image_layered_history.json"
QWEN_IMAGE_EDIT_HISTORY_PATH = CHARTS_DIR / "qwen_image_edit_history.json"
QWEN_IMAGE_EDIT_2509_HISTORY_PATH = CHARTS_DIR / "qwen_image_edit_2509_history.json"
QWEN_IMAGE_EDIT_2511_HISTORY_PATH = CHARTS_DIR / "qwen_image_edit_2511_history.json"
WAN22_HISTORY_PATH = CHARTS_DIR / "wan22_history.json"
HUNYUAN_IMAGE3_HISTORY_PATH = CHARTS_DIR / "hunyuan_image3_history.json"
HUNYUAN_IMAGE3_ACCURACY_PATH = CHARTS_DIR / "hunyuan_image3_accuracy.json"
LOCAL_RAW_DIR = DATA_DIR / "local_nightly_raw"
BAGEL_HISTORY_PATH = CHARTS_DIR / "bagel_history.json"
VOXCPM2_HISTORY_PATH = CHARTS_DIR / "voxcpm2_history.json"
DEFAULT_RESULT_DATASETS = frozenset({"random", "random-mm"})
QWEN3_OMNI_DATASETS = set(DEFAULT_RESULT_DATASETS)  # backward compat
QWEN3_OMNI_GROUP_FIELDS = (
    "endpoint_type",
    "backend",
    "model_id",
    "tokenizer_id",
    "test_name",
    "dataset_name",
    "random_input_len",
    "random_output_len",
    "max_concurrency",
    "num_prompts",
    # Same CI scenario can emit two rows differing only by whether audio RTF/TTFP/duration metrics exist.
    # Without this dimension, frontend line charts merge them and latest-per-day hides the other path.
    "omni_metrics_profile",
)
QWEN3_TTS_GROUP_FIELDS = (
    "endpoint_type",
    "backend",
    "model_id",
    "tokenizer_id",
    "test_name",
    "dataset_name",
    "max_concurrency",
    "num_prompts",
)
QWEN_IMAGE_GROUP_FIELDS = (
    "test_name",
    "backend",
    "hardware",
    "model_id",
    "benchmark_name",
    "dataset_name",
    "max_concurrency",
    "num_prompts",
)
HUNYUAN_ACCURACY_GROUP_FIELDS = (
    "test_file",
    "test_name",
)
MODEL_METRICS = {
    "Qwen3-Omni": [
        ("ttft_ms", None, None),
        ("tpot_ms", None, None),
        ("ttfp_ms", None, None),
        ("real_time_factor", None, None),
        ("throughput_tokens_per_sec", None, None),
    ],
    "Qwen3-TTS": [
        ("ttft_ms", None, None),
        ("tpot_ms", None, None),
        ("ttfp_ms", None, None),
        ("real_time_factor", None, None),
        ("throughput_tokens_per_sec", None, None),
    ],
    "Qwen-image": [
        ("e2e_latency_ms", None, None),
        ("peak_memory_gb", None, None),
    ],
    "Qwen-Image-edit": [
        ("e2e_latency_ms", None, None),
        ("peak_memory_gb", None, None),
    ],
    "Qwen-Image-edit-2509": [
        ("e2e_latency_ms", None, None),
        ("peak_memory_gb", None, None),
    ],
    "Qwen-Image-edit-2511": [
        ("e2e_latency_ms", None, None),
        ("peak_memory_gb", None, None),
    ],
    "WAN2.2": [
        ("e2e_latency_ms", None, None),
        ("peak_memory_gb", None, None),
    ],
    "Hunyuan-Image3": [
        ("e2e_latency_ms", None, None),
        ("peak_memory_gb", None, None),
    ],
    "BAGEL": [
        ("e2e_latency_ms", None, None),
        ("peak_memory_gb", None, None),
    ],
    "VoxCPM2": [
        ("ttfp_ms", None, None),
        ("real_time_factor", None, None),
        ("throughput_tokens_per_sec", None, None),
    ],
}
RANGE_WINDOWS = {"1d": 1, "7d": 7, "30d": 30}


def save_chart(name: str, option: dict[str, Any]) -> None:
    save_json(CHARTS_DIR / f"{name}.json", option)


def average_metric(results: list[dict[str, Any]], metric: str) -> float | None:
    values = [value for result in results if isinstance((value := flatten_metrics(result["metrics"]).get(metric)), (int, float))]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def chart_slug(value: str) -> str:
    return value.lower().replace(".", "").replace(" ", "_").replace("-", "_")


def _strip_io_length_suffix_before_timestamp(name: str) -> str:
    """Strip _in*_out*_ before the trailing _YYYYMMDD-HHMMSS segment.

    Matches numeric IO lengths (_in100_out100) and TTS-style placeholders (_inna_outna).
    """
    return re.sub(r"_in[^_]+_out[^_]+(?=_\d{8}-\d{6}$)", "", name)


def parse_result_test_filename(
    path: Path,
    dataset_allowlist: frozenset[str] | set[str] | None = None,
) -> dict[str, Any] | None:
    allow = frozenset(dataset_allowlist) if dataset_allowlist is not None else DEFAULT_RESULT_DATASETS
    stem = path.stem
    prefix = "result_test_"
    if not stem.startswith(prefix):
        return None
    middle = _strip_io_length_suffix_before_timestamp(stem[len(prefix) :])
    parts = middle.split("_")
    if len(parts) < 5:
        return None
    timestamp = parts[-1]
    try:
        parsed_ts = datetime.strptime(timestamp, "%Y%m%d-%H%M%S")
        num_prompts = int(parts[-2])
    except ValueError:
        return None

    mc_token = parts[-3]
    try:
        max_concurrency = int(mc_token)
    except ValueError:
        try:
            float(mc_token)
        except ValueError:
            return None
        max_concurrency = None

    dataset_name = parts[-4]
    test_name = "_".join(parts[:-4])
    if not test_name:
        return None
    if dataset_name not in allow:
        dataset_name = ""

    return {
        "test_name": test_name,
        "dataset_name": dataset_name,
        "max_concurrency": max_concurrency,
        "num_prompts": num_prompts,
        "timestamp_key": timestamp,
        "sort_timestamp": parsed_ts.isoformat(),
        "date": parsed_ts.strftime("%Y-%m-%d %H:%M:%S"),
    }


def parse_qwen3_omni_filename(path: Path) -> dict[str, Any] | None:
    return parse_result_test_filename(path, DEFAULT_RESULT_DATASETS)


def infer_omni_metrics_profile(payload: dict[str, Any]) -> str:
    """Label for chart grouping: audio-series present vs text-oriented aggregate only.

    Nightly payloads may include two measurements for an otherwise identical workload
    (endpoint, concurrency, prompts, lengths) where only one fills ``mean_audio_rtf`` /
    TTFP / audio duration columns. Previously they shared one series key and
    ``pickLatestPerCalendarDay`` kept only the latest timestamp.
    """

    probe_keys = (
        "mean_audio_rtf",
        "median_audio_rtf",
        "p99_audio_rtf",
        "mean_audio_ttfp_ms",
        "median_audio_ttfp_ms",
        "p99_audio_ttfp_ms",
        "mean_audio_duration_s",
        "median_audio_duration_s",
        "p99_audio_duration_s",
    )
    for key in probe_keys:
        raw = payload.get(key)
        if isinstance(raw, (int, float)) and math.isfinite(float(raw)):
            return "audio_metrics"
        if isinstance(raw, str) and raw.strip():
            try:
                val = float(raw)
            except ValueError:
                continue
            if math.isfinite(val):
                return "audio_metrics"
    return "text_only_metrics"


def load_result_test_history(
    source_dir: Path,
    dataset_allowlist: frozenset[str] | set[str] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(source_dir.rglob("result_test_*.json")):
        parsed = parse_result_test_filename(path, dataset_allowlist)
        if parsed is None:
            continue
        payload = load_json(path, {})
        if not isinstance(payload, dict):
            continue
        merged = {**payload, **parsed}
        record: dict[str, Any] = {
            "source_file": path.name,
            **payload,
            **parsed,
        }
        record["test_name"] = parsed["test_name"]
        record["dataset_name"] = parsed["dataset_name"]
        record["max_concurrency"] = parsed["max_concurrency"]
        record["num_prompts"] = parsed["num_prompts"]
        record["date"] = parsed["date"]
        record["sort_timestamp"] = parsed["sort_timestamp"]
        cr = merged.get("completed_requests")
        if cr is None:
            cr = merged.get("completed")
        fr = merged.get("failed_requests")
        if fr is None:
            fr = merged.get("failed")
        record["completed_requests"] = cr
        record["failed_requests"] = fr
        baseline_obj = merged.get("baseline")
        if isinstance(baseline_obj, dict):
            for bk, bv in baseline_obj.items():
                if isinstance(bk, str) and bk and isinstance(bv, (int, float)):
                    record[f"baseline_{bk}"] = float(bv)
        record["omni_metrics_profile"] = infer_omni_metrics_profile(record)
        record["config_key"] = " | ".join("" if record.get(field) is None else str(record.get(field)) for field in QWEN3_OMNI_GROUP_FIELDS)
        records.append(record)

    def _group_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
        return tuple("" if item.get(field) is None else str(item.get(field)) for field in QWEN3_OMNI_GROUP_FIELDS)

    records.sort(
        key=lambda item: (
            _group_sort_key(item),
            item["sort_timestamp"],
        ),
        reverse=False,
    )
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        key = _group_sort_key(record)
        grouped.setdefault(key, []).append(record)

    ordered_records: list[dict[str, Any]] = []
    for key in sorted(grouped):
        items = sorted(grouped[key], key=lambda item: item["sort_timestamp"], reverse=True)
        ordered_records.extend(items)
    return ordered_records


def load_qwen3_omni_history(source_dir: Path) -> list[dict[str, Any]]:
    return load_result_test_history(source_dir, DEFAULT_RESULT_DATASETS)


def _slug_stage_name(stage: str) -> str:
    return stage.replace(".", "_")


def _slug_serve_arg_key(key: str) -> str:
    return key.replace("-", "_").replace(".", "_")


def _serialize_serve_arg_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    return json.dumps(value, ensure_ascii=False)


def _normalize_hardware(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    hardware = value.strip()
    if not hardware:
        return None
    return hardware.upper()


def _load_diffusion_benchmark_records(sorted_paths: list[Path]) -> list[dict[str, Any]]:
    """Parse diffusion/benchmark perf JSON arrays (shared by Qwen Image and WAN 2.2 pages)."""
    raw_rows: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    stage_keys: set[str] = set()
    serve_arg_keys: set[str] = set()
    for path in sorted_paths:
        data = load_json(path, [])
        if not isinstance(data, list):
            continue
        for raw in data:
            if not isinstance(raw, dict):
                continue
            res = raw.get("result")
            if not isinstance(res, dict):
                continue
            ts = raw.get("timestamp") or ""
            try:
                parsed_ts = datetime.strptime(ts, "%Y%m%d-%H%M%S")
            except ValueError:
                continue
            bp = raw.get("benchmark_params") if isinstance(raw.get("benchmark_params"), dict) else {}
            sp = raw.get("server_params") if isinstance(raw.get("server_params"), dict) else {}
            sort_timestamp = parsed_ts.isoformat()
            date = parsed_ts.strftime("%Y-%m-%d %H:%M:%S")
            lm = res.get("latency_mean")
            e2e_ms = float(lm) * 1000.0 if isinstance(lm, (int, float)) else None
            med = res.get("latency_median")
            e2e_med_ms = float(med) * 1000.0 if isinstance(med, (int, float)) else None
            p99v = res.get("latency_p99")
            e2e_p99_ms = float(p99v) * 1000.0 if isinstance(p99v, (int, float)) else None
            pmem = res.get("peak_memory_mb_mean")
            peak_gb = float(pmem) / 1024.0 if isinstance(pmem, (int, float)) else None
            for dkey in ("stage_durations_mean", "stage_durations_p50", "stage_durations_p99"):
                block = res.get(dkey)
                if isinstance(block, dict):
                    stage_keys.update(block.keys())
            sa = sp.get("serve_args")
            if isinstance(sa, dict):
                serve_arg_keys.update(sa.keys())
            record = {
                "test_name": raw.get("test_name"),
                "backend": raw.get("backend"),
                "hardware": _normalize_hardware(raw.get("hardware") or raw.get("Hardware")),
                "model_id": sp.get("model"),
                "benchmark_name": str(bp.get("name") or ""),
                "dataset_name": str(bp.get("dataset") or ""),
                "max_concurrency": bp.get("max-concurrency"),
                "num_prompts": bp.get("num-prompts"),
                "task": bp.get("task"),
                "width": bp.get("width"),
                "height": bp.get("height"),
                "completed_requests": res.get("completed_requests"),
                "failed_requests": res.get("failed_requests"),
                "e2e_latency_ms": e2e_ms,
                "e2e_latency_median_ms": e2e_med_ms,
                "e2e_latency_p99_ms": e2e_p99_ms,
                "throughput_qps": res.get("throughput_qps"),
                "peak_memory_gb": peak_gb,
                "peak_memory_mb_mean": res.get("peak_memory_mb_mean"),
                "peak_memory_mb_median": res.get("peak_memory_mb_median"),
                "peak_memory_mb_max": res.get("peak_memory_mb_max"),
                "timestamp_key": ts,
                "sort_timestamp": sort_timestamp,
                "date": date,
                "source_file": path.name,
            }
            bench_bl = bp.get("baseline") if isinstance(bp.get("baseline"), dict) else {}
            bl_lm = bench_bl.get("latency_mean")
            if isinstance(bl_lm, (int, float)):
                record["baseline_e2e_latency_ms"] = float(bl_lm) * 1000.0
            bl_tpq = bench_bl.get("throughput_qps")
            if isinstance(bl_tpq, (int, float)):
                record["baseline_throughput_qps"] = float(bl_tpq)
            bl_pmem = bench_bl.get("peak_memory_mb_mean")
            if isinstance(bl_pmem, (int, float)):
                record["baseline_peak_memory_gb"] = float(bl_pmem) / 1024.0
            raw_rows.append((record, res, sp))

    ordered_serve = sorted(serve_arg_keys)
    ordered_stages = sorted(stage_keys)
    records: list[dict[str, Any]] = []
    for record, res, sp in raw_rows:
        sa = sp.get("serve_args") if isinstance(sp.get("serve_args"), dict) else {}
        for name in ordered_serve:
            slug = _slug_serve_arg_key(name)
            val = sa.get(name) if isinstance(sa, dict) else None
            record[f"serve_args_{slug}"] = _serialize_serve_arg_value(val)
        mean = res.get("stage_durations_mean") if isinstance(res.get("stage_durations_mean"), dict) else {}
        p50 = res.get("stage_durations_p50") if isinstance(res.get("stage_durations_p50"), dict) else {}
        p99d = res.get("stage_durations_p99") if isinstance(res.get("stage_durations_p99"), dict) else {}
        for name in ordered_stages:
            slug = _slug_stage_name(name)
            record[f"stage_mean_{slug}"] = mean.get(name) if isinstance(mean, dict) else None
            record[f"stage_p50_{slug}"] = p50.get(name) if isinstance(p50, dict) else None
            record[f"stage_p99_{slug}"] = p99d.get(name) if isinstance(p99d, dict) else None
        record["config_key"] = " | ".join(str(record.get(field, "")) for field in QWEN_IMAGE_GROUP_FIELDS)
        records.append(record)

    def _group_field_sort_value(value: Any) -> tuple[int, int, Any]:
        if value is None:
            return (1, 0, 0)
        if isinstance(value, bool):
            return (0, 1, int(value))
        if isinstance(value, (int, float)):
            return (0, 1, value)
        return (0, 2, str(value))

    def _group_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(_group_field_sort_value(item.get(field)) for field in QWEN_IMAGE_GROUP_FIELDS)

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        key = _group_sort_key(record)
        grouped.setdefault(key, []).append(record)
    ordered: list[dict[str, Any]] = []
    for key in sorted(grouped):
        items = sorted(grouped[key], key=lambda item: item["sort_timestamp"], reverse=True)
        ordered.extend(items)
    return ordered


def load_qwen_image_benchmark_history(source_dir: Path) -> list[dict[str, Any]]:
    """Load CI perf arrays from diffusion_* / benchmark_results_*.json (Qwen Image diffusion bench)."""
    bench_paths: set[Path] = set()
    for pattern in ("diffusion_result_*.json", "benchmark_results_*.json"):
        bench_paths.update(source_dir.rglob(pattern))
    return _load_diffusion_benchmark_records(sorted(bench_paths, key=lambda p: str(p)))


def load_wan22_benchmark_history(source_dir: Path) -> list[dict[str, Any]]:
    """Load CI perf arrays from diffusion_result*.json basenames that contain wan22."""
    bench_paths: list[Path] = []
    for path in source_dir.rglob("diffusion_result*.json"):
        if not path.is_file():
            continue
        if "wan22" not in path.name.casefold():
            continue
        bench_paths.append(path)
    return _load_diffusion_benchmark_records(sorted(bench_paths, key=lambda p: str(p)))


def _history_payload_from_records(
    config: dict[str, Any],
    source_dir: Path,
    page_key: str,
    display_name: str,
    group_fields: tuple[str, ...],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    def _normalize_filter_fields(item: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(item)
        if normalized.get("qps") in (None, ""):
            normalized["qps"] = normalized.get("request_rate")
        if normalized.get("input_len") in (None, ""):
            normalized["input_len"] = normalized.get("random_input_len")
        if normalized.get("output_len") in (None, ""):
            normalized["output_len"] = normalized.get("random_output_len")
        return normalized

    records = [_normalize_filter_fields(record) for record in records]
    page_config = config.get("kanban_pages", {}).get(page_key, {})
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        key = tuple(record.get(field) for field in group_fields)
        groups.setdefault(key, []).append(record)

    grouped_payload = []
    for key in sorted(groups, key=lambda k: tuple("" if v is None else str(v) for v in k)):
        items = sorted(groups[key], key=lambda item: item["sort_timestamp"], reverse=True)
        grouped_payload.append(
            {
                "key": dict(zip(group_fields, key)),
                "config_key": items[0]["config_key"],
                "record_count": len(items),
                "records": items,
            }
        )

    filter_fields = page_config.get("filters", [])
    filter_options = {
        field: sorted(
            {item.get(field) for item in records if item.get(field) not in (None, "")},
            key=lambda value: str(value),
        )
        for field in filter_fields
    }

    try:
        source_dir_display = str(source_dir.relative_to(ROOT))
    except ValueError:
        source_dir_display = str(source_dir)

    return {
        "title": display_name,
        "source_dir": source_dir_display,
        "generated_at": datetime.now().isoformat(),
        "filters": filter_fields,
        "filter_options": filter_options,
        "table_columns": page_config.get("table_columns", []),
        "metric_groups": page_config.get("metric_groups", []),
        "group_fields": list(group_fields),
        "chart_point_per_day": bool(page_config.get("chart_point_per_day", True)),
        "default_visible_series": page_config.get("default_visible_series"),
        "record_count": len(records),
        "group_count": len(grouped_payload),
        "records": records,
        "groups": grouped_payload,
    }


def build_result_test_history_payload(
    config: dict[str, Any],
    source_dir: Path,
    page_key: str,
    display_name: str,
) -> dict[str, Any]:
    page_config = config.get("kanban_pages", {}).get(page_key, {})
    ds_names = page_config.get("dataset_names", ["random", "random-mm"])
    dataset_allowlist = frozenset(ds_names)
    records = load_result_test_history(source_dir, dataset_allowlist) if source_dir.is_dir() else []
    return _history_payload_from_records(config, source_dir, page_key, display_name, QWEN3_OMNI_GROUP_FIELDS, records)


def build_qwen3_omni_history_payload(config: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    display = config.get("models", {}).get("Qwen3-Omni", {}).get("display_name", "Qwen3 Omni")
    return build_result_test_history_payload(config, source_dir, "qwen3_omni_history", display)


def build_qwen3_tts_history_payload(config: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    display = config.get("models", {}).get("Qwen3-TTS", {}).get("display_name", "Qwen3 TTS")
    page_config = config.get("kanban_pages", {}).get("qwen3_tts_history", {})
    ds_names = page_config.get("dataset_names", ["random", "random-mm"])
    dataset_allowlist = frozenset(ds_names)
    records = load_result_test_history(source_dir, dataset_allowlist) if source_dir.is_dir() else []
    return _history_payload_from_records(config, source_dir, "qwen3_tts_history", display, QWEN3_TTS_GROUP_FIELDS, records)


def build_qwen_image_family_history_payload(
    config: dict[str, Any],
    source_dir: Path,
    *,
    page_key: str,
    model_key: str,
    fallback_display: str,
    test_name_filter: Callable[[str], bool] | None = None,
    records_loader: Callable[[Path], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    display = config.get("models", {}).get(model_key, {}).get("display_name", fallback_display)
    loader = records_loader or load_qwen_image_benchmark_history
    records = loader(source_dir) if source_dir.is_dir() else []
    if test_name_filter is not None:
        records = [r for r in records if test_name_filter(str(r.get("test_name") or ""))]
    payload = _history_payload_from_records(config, source_dir, page_key, display, QWEN_IMAGE_GROUP_FIELDS, records)
    page_config = config.get("kanban_pages", {}).get(page_key, {})
    legacy_stage_json = frozenset({"stage_durations_mean", "stage_durations_p50", "stage_durations_p99"})
    base = [c for c in page_config.get("table_columns", []) if c not in legacy_stage_json]
    serve_cols = sorted({k for r in records for k in r if k.startswith("serve_args_")})
    if "model_id" in base and serve_cols:
        idx_m = base.index("model_id") + 1
        base = base[:idx_m] + serve_cols + base[idx_m:]
    dynamic: list[str] = []
    if page_config.get("include_stage_columns", True):
        stage_slug_set: set[str] = set()
        for rec in records:
            for k in rec:
                if k.startswith("stage_mean_"):
                    stage_slug_set.add(k[len("stage_mean_") :])
        slugs: list[str] = sorted(stage_slug_set)
        # qwen-image-edit page: keep one pipeline family to avoid duplicate display labels after prefix trimming.
        if page_key == "qwen_image_history":
            slugs = [s for s in slugs if "QwenImagePipeline_" in s]
        elif page_key == "qwen_image_layered_history":
            slugs = [s for s in slugs if "QwenImageLayeredPipeline_" in s]
        elif page_key == "qwen_image_edit_history":
            slugs = [s for s in slugs if "QwenImageEditPipeline_" in s]
        elif page_key in {"qwen_image_edit_2509_history", "qwen_image_edit_2511_history"}:
            slugs = [s for s in slugs if "QwenImageEditPlusPipeline_" in s]
        if page_config.get("p99_stage_columns_last", False):
            for slug in slugs:
                dynamic.extend([f"stage_mean_{slug}", f"stage_p50_{slug}"])
            for slug in slugs:
                dynamic.append(f"stage_p99_{slug}")
        else:
            for slug in slugs:
                dynamic.extend([f"stage_mean_{slug}", f"stage_p50_{slug}", f"stage_p99_{slug}"])
    anchor = "peak_memory_mb_max"
    if anchor in base:
        idx = base.index(anchor) + 1
        payload["table_columns"] = base[:idx] + dynamic + base[idx:]
    else:
        payload["table_columns"] = base + dynamic
    return payload


def build_qwen_image_history_payload(config: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    return build_qwen_image_family_history_payload(
        config,
        source_dir,
        page_key="qwen_image_history",
        model_key="Qwen-image",
        fallback_display="Qwen Image",
        test_name_filter=lambda name: (
            "qwen_image_edit" not in name
            and "qwen_image_layered" not in name
            and "qwen_image" in name
        ),
    )


def build_qwen_image_layered_history_payload(config: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    return build_qwen_image_family_history_payload(
        config,
        source_dir,
        page_key="qwen_image_layered_history",
        model_key="Qwen-image-layered",
        fallback_display="Qwen Image Layered",
        test_name_filter=lambda name: "qwen_image_layered" in name,
    )


def build_qwen_image_edit_history_payload(config: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    return build_qwen_image_family_history_payload(
        config,
        source_dir,
        page_key="qwen_image_edit_history",
        model_key="Qwen-Image-edit",
        fallback_display="Qwen Image Edit",
        test_name_filter=lambda name: (
            "qwen_image_edit_2509" not in name
            and "qwen_image_edit_2511" not in name
            and "qwen_image_edit" in name
        ),
    )


def build_qwen_image_edit_2509_history_payload(config: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    return build_qwen_image_family_history_payload(
        config,
        source_dir,
        page_key="qwen_image_edit_2509_history",
        model_key="Qwen-Image-edit-2509",
        fallback_display="Qwen Image Edit 2509",
        test_name_filter=lambda name: "qwen_image_edit_2509" in name,
    )


def build_qwen_image_edit_2511_history_payload(config: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    return build_qwen_image_family_history_payload(
        config,
        source_dir,
        page_key="qwen_image_edit_2511_history",
        model_key="Qwen-Image-edit-2511",
        fallback_display="Qwen Image Edit 2511",
        test_name_filter=lambda name: "qwen_image_edit_2511" in name,
    )


def build_wan22_history_payload(config: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    return build_qwen_image_family_history_payload(
        config,
        source_dir,
        page_key="wan22_history",
        model_key="WAN2.2",
        fallback_display="WAN 2.2",
        records_loader=load_wan22_benchmark_history,
    )


def build_hunyuan_image3_history_payload(config: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    return build_qwen_image_family_history_payload(
        config,
        source_dir,
        page_key="hunyuan_image3_history",
        model_key="Hunyuan-Image3",
        fallback_display="Hunyuan Image 3",
        test_name_filter=lambda name: "hunyuan_image" in name,
    )


def _metric_field_name(label: str) -> str:
    """Map a table metric label to a record field key, e.g. "PSNR (dB)" -> "psnr_db"."""
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", label.lower())).strip("_")


def load_hunyuan_local_accuracy_records(raw_root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Load accuracy metric tables from local manual pytest logs.

    Scans every ``manual_YYYYMMDD/*.log`` under ``raw_root`` (filenames vary, so no
    name-based filtering) and keeps rows attributed to hunyuan test files. The table
    reference column (L20x Reference) is stored as ``baseline_<metric>`` so the chart
    renderer draws it as the baseline line.

    Returns ``(records, metric_labels)`` where ``metric_labels`` maps the sanitized
    field key back to the original table label for chart titles.
    """
    records: list[dict[str, Any]] = []
    metric_labels: dict[str, str] = {}
    if not raw_root.is_dir():
        return records, metric_labels

    for log_path in sorted(raw_root.glob("manual_*/*.log")):
        date_match = re.fullmatch(r"manual_(\d{8})", log_path.parent.name)
        if not date_match:
            continue
        raw_date = date_match.group(1)
        date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        by_case: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in parse_log_metric_tables(text):
            test_file = str(row.get("test_file") or "")
            if "hunyuan" not in test_file:
                continue
            by_case.setdefault((test_file, str(row.get("test_name") or "")), []).append(row)

        for (test_file, test_name), case_rows in sorted(by_case.items()):
            record: dict[str, Any] = {
                "date": date,
                "sort_timestamp": f"{date}T00:00:00",
                "test_file": test_file,
                "test_name": test_name,
                "source_file": log_path.name,
                "config_key": f"{test_file}::{test_name}",
            }
            for row in case_rows:
                field = _metric_field_name(row["metric"])
                metric_labels[field] = row["metric"]
                record[field] = row["value"]
                if row["reference"] is not None:
                    record[f"baseline_{field}"] = row["reference"]
            records.append(record)

    return records, metric_labels


def build_hunyuan_image3_accuracy_payload(config: dict[str, Any], raw_root: Path) -> dict[str, Any]:
    records, metric_labels = load_hunyuan_local_accuracy_records(raw_root)
    payload = _history_payload_from_records(
        config,
        raw_root,
        "hunyuan_image3_accuracy",
        "Hunyuan Image 3 - Local Accuracy",
        HUNYUAN_ACCURACY_GROUP_FIELDS,
        records,
    )
    metric_fields = sorted(metric_labels)
    payload["metric_groups"] = [
        {"id": field, "title": metric_labels[field], "metrics": [field]} for field in metric_fields
    ]
    payload["table_columns"] = ["date", "test_file", "test_name", *metric_fields, "source_file"]
    return payload


def build_bagel_history_payload(config: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    return build_qwen_image_family_history_payload(
        config,
        source_dir,
        page_key="bagel_history",
        model_key="BAGEL",
        fallback_display="BAGEL",
        test_name_filter=lambda name: "bagel" in name,
    )


def build_voxcpm2_history_payload(config: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    display = config.get("models", {}).get("VoxCPM2", {}).get("display_name", "VoxCPM2")
    page_config = config.get("kanban_pages", {}).get("voxcpm2_history", {})
    ds_names = page_config.get("dataset_names", ["seed-tts", "seed-tts-text"])
    records = load_result_test_history(source_dir, frozenset(ds_names)) if source_dir.is_dir() else []
    return _history_payload_from_records(config, source_dir, "voxcpm2_history", display, QWEN3_TTS_GROUP_FIELDS, records)


def build_multi_series_chart(
    dates: list[str],
    hardware_items: list[tuple[str, str]],
    day_results: dict[str, list[dict[str, Any]]],
    model: str,
    metric: str,
    y_min: float | None = None,
    y_max: float | None = None,
) -> dict[str, Any]:
    series = []
    for hardware, hardware_label in hardware_items:
        values = []
        for date in dates:
            match = next(
                (item for item in day_results.get(date, []) if item["model"] == model and item["hardware"] == hardware),
                None,
            )
            flat = flatten_metrics(match["metrics"]) if match else {}
            values.append(flat.get(metric))
        if any(value is not None for value in values):
            series.append({"name": hardware_label, "type": "line", "data": values, "smooth": True})

    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"type": "scroll", "top": 0, "left": 0, "right": 0, "textStyle": {"fontSize": 12}},
        "grid": {"left": 56, "right": 24, "top": 54, "bottom": 42},
        "xAxis": {"type": "category", "data": dates, "axisLabel": {"color": "#5b6775"}},
        "yAxis": {"type": "value", "min": y_min, "max": y_max, "axisLabel": {"color": "#5b6775"}},
        "series": series,
    }


def build_hardware_status(config: dict[str, Any], latest_results: list[dict[str, Any]]) -> dict[str, Any]:
    hardware_status = []
    for hardware_key, hardware_config in config.get("hardware", {}).items():
        hw_results = [r for r in latest_results if r.get("hardware") == hardware_key]
        if not hw_results:
            continue
        pass_rate = average_metric(hw_results, "pass_rate")
        latency_p99 = average_metric(hw_results, "latency_p99_ms")
        if pass_rate is None:
            status = "unknown"
        elif pass_rate >= 0.9:
            status = "healthy"
        elif pass_rate >= 0.8:
            status = "warning"
        else:
            status = "critical"
        hardware_status.append({
            "hardware_key": hardware_key,
            "display_name": hardware_config["display_name"],
            "pass_rate": pass_rate,
            "latency_p99_ms": latency_p99,
            "status": status,
        })
    return {"hardware": hardware_status}


def main() -> int:
    config = load_json(CONFIG_PATH, {})
    index = load_json(INDEX_PATH, {"dates": []})
    dates = sorted(index.get("dates", []))
    day_results = {date: load_json(RESULTS_DIR / f"{date}.json", {"results": []}).get("results", []) for date in dates}

    hardware_items = [(key, value["display_name"]) for key, value in config.get("hardware", {}).items()]

    latest_results = day_results[dates[-1]] if dates else []
    save_chart("hardware_status", build_hardware_status(config, latest_results))
    qwen3_omni_source_dir = RESULTS_DIR / config.get("kanban_pages", {}).get("qwen3_omni_history", {}).get("source_dir", "qwen3omni")
    save_json(QWEN3_OMNI_HISTORY_PATH, build_qwen3_omni_history_payload(config, qwen3_omni_source_dir))
    qwen3_tts_source_dir = RESULTS_DIR / config.get("kanban_pages", {}).get("qwen3_tts_history", {}).get("source_dir", "qwen3tts")
    save_json(QWEN3_TTS_HISTORY_PATH, build_qwen3_tts_history_payload(config, qwen3_tts_source_dir))
    qwen_image_source_dir = RESULTS_DIR / config.get("kanban_pages", {}).get("qwen_image_history", {}).get("source_dir", "qwen_image")
    save_json(QWEN_IMAGE_HISTORY_PATH, build_qwen_image_history_payload(config, qwen_image_source_dir))
    qwen_image_layered_source_dir = RESULTS_DIR / config.get("kanban_pages", {}).get("qwen_image_layered_history", {}).get("source_dir", "qwen_image_layered")
    save_json(QWEN_IMAGE_LAYERED_HISTORY_PATH, build_qwen_image_layered_history_payload(config, qwen_image_layered_source_dir))
    qwen_image_edit_source_dir = RESULTS_DIR / config.get("kanban_pages", {}).get("qwen_image_edit_history", {}).get("source_dir", "qwen_image_edit")
    save_json(QWEN_IMAGE_EDIT_HISTORY_PATH, build_qwen_image_edit_history_payload(config, qwen_image_edit_source_dir))
    qwen_image_edit_2509_source_dir = RESULTS_DIR / config.get("kanban_pages", {}).get("qwen_image_edit_2509_history", {}).get("source_dir", "qwen_image_edit_2509")
    save_json(QWEN_IMAGE_EDIT_2509_HISTORY_PATH, build_qwen_image_edit_2509_history_payload(config, qwen_image_edit_2509_source_dir))
    qwen_image_edit_2511_source_dir = RESULTS_DIR / config.get("kanban_pages", {}).get("qwen_image_edit_2511_history", {}).get("source_dir", "qwen_image_edit_2511")
    save_json(QWEN_IMAGE_EDIT_2511_HISTORY_PATH, build_qwen_image_edit_2511_history_payload(config, qwen_image_edit_2511_source_dir))
    wan22_source_dir = RESULTS_DIR / config.get("kanban_pages", {}).get("wan22_history", {}).get("source_dir", "wan22")
    save_json(WAN22_HISTORY_PATH, build_wan22_history_payload(config, wan22_source_dir))
    hunyuan_image3_source_dir = RESULTS_DIR / config.get("kanban_pages", {}).get("hunyuan_image3_history", {}).get("source_dir", "hunyuan_image3")
    save_json(HUNYUAN_IMAGE3_HISTORY_PATH, build_hunyuan_image3_history_payload(config, hunyuan_image3_source_dir))
    save_json(HUNYUAN_IMAGE3_ACCURACY_PATH, build_hunyuan_image3_accuracy_payload(config, LOCAL_RAW_DIR))
    bagel_source_dir = RESULTS_DIR / config.get("kanban_pages", {}).get("bagel_history", {}).get("source_dir", "bagel")
    save_json(BAGEL_HISTORY_PATH, build_bagel_history_payload(config, bagel_source_dir))
    voxcpm2_source_dir = RESULTS_DIR / config.get("kanban_pages", {}).get("voxcpm2_history", {}).get("source_dir", "voxcpm2")
    save_json(VOXCPM2_HISTORY_PATH, build_voxcpm2_history_payload(config, voxcpm2_source_dir))
    for model, model_config in config.get("models", {}).items():
        available_metrics = set(model_config["metrics"]["required"]) | set(model_config["metrics"]["optional"])
        for metric, y_min, y_max in MODEL_METRICS.get(model, []):
            if metric not in available_metrics:
                continue
            for range_key, window in RANGE_WINDOWS.items():
                save_chart(
                    f"{chart_slug(model)}_{metric}_{range_key}",
                    build_multi_series_chart(
                        dates[-window:],
                        hardware_items,
                        day_results,
                        model,
                        metric,
                        y_min=y_min,
                        y_max=y_max,
                    ),
                )
    print(f"generated {len(list(CHARTS_DIR.glob('*.json')))} chart files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
