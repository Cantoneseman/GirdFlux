#!/usr/bin/env python3
"""Analyze cloud disk/writeback bottleneck proof artifacts."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUMMARY_FIELDS = ["metric", "value", "unit", "note"]


def timestamp_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_csv(path_text: str | Path) -> list[dict[str, str]]:
    if not path_text:
        return []
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["_source_csv"] = str(path)
    return rows


def read_many(paths: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        rows.extend(read_csv(path))
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def number(row: dict[str, str] | None, field: str) -> float:
    if not row:
        return 0.0
    try:
        value = float(row.get(field, "") or "0")
        return 0.0 if math.isnan(value) or math.isinf(value) else value
    except ValueError:
        return 0.0


def integer(row: dict[str, str] | None, field: str) -> int:
    if not row:
        return 0
    try:
        return int(float(row.get(field, "") or "0"))
    except ValueError:
        return 0


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}" if math.isfinite(value) else ""


def pct(value: float) -> str:
    return f"{value * 100.0:.1f}%" if math.isfinite(value) else ""


def pct_delta(value: float, base: float) -> str:
    if base <= 0.0:
        return ""
    return f"{((value - base) / base) * 100.0:+.1f}%"


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) * 95 + 99) / 100) - 1))
    return ordered[index]


def table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_暂无有效数据。_\n"
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    output.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(output) + "\n"


def size_label(value: str) -> str:
    try:
        size = int(float(value))
    except ValueError:
        return value
    if size % (1024**3) == 0:
        return f"{size // (1024**3)}GiB"
    if size % (1024**2) == 0:
        return f"{size // (1024**2)}MiB"
    return str(size)


def pass_count(row: dict[str, str]) -> int:
    return integer(row, "pass_count")


def fail_count(row: dict[str, str]) -> int:
    return integer(row, "fail_count")


def valid_matrix_summary(rows: list[dict[str, str]], direction: str) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("direction") == direction
        and pass_count(row) > 0
        and fail_count(row) == 0
        and number(row, "throughput_gbps_median") > 0.0
    ]


def stage_value(row: dict[str, str], stage: str) -> float:
    fields = {
        "temp_write": ["receiver_temp_write_seconds_median", "temp_write_seconds_median"],
        "data_receive": ["receiver_data_receive_seconds_median", "data_receive_seconds_median"],
        "manifest": ["receiver_manifest_flush_seconds_median", "manifest_flush_seconds_median"],
        "final_verify": ["receiver_final_verify_seconds_median", "final_verify_seconds_median"],
        "rename": [
            "receiver_rename_commit_seconds_median",
            "rename_commit_seconds_median",
            "stage_rename_commit_seconds_median",
            "receiver_finalize_rename_seconds_median",
        ],
        "source_read": ["sender_source_read_seconds_median", "source_read_seconds_median"],
        "network_send": ["sender_network_send_seconds_median", "network_send_seconds_median"],
        "download_temp_write": [
            "receiver_download_temp_write_seconds_median",
            "download_temp_write_seconds_median",
            "receiver_temp_write_seconds_median",
        ],
    }[stage]
    for field in fields:
        value = number(row, field)
        if value > 0.0:
            return value
    return 0.0


def throughput_from_stage(row: dict[str, str], stage: str) -> float:
    seconds = stage_value(row, stage)
    bytes_count = number(row, "bytes")
    return (bytes_count * 8.0 / seconds) / 1_000_000_000.0 if seconds > 0.0 else 0.0


def valid_storage_summary(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("method") == "gridflux_storage_bench"
        and row.get("file_io_backend") == "posix"
        and pass_count(row) > 0
        and fail_count(row) == 0
    ]


def storage_limits(rows: list[dict[str, str]]) -> dict[str, float]:
    valid = valid_storage_summary(rows)
    writes = [number(row, "throughput_gbps_median") for row in valid if row.get("operation") == "write"]
    reads = [number(row, "throughput_gbps_median") for row in valid if row.get("operation") == "read"]
    return {
        "write_median": median(writes),
        "write_best": max(writes or [0.0]),
        "read_median": median(reads),
        "read_best": max(reads or [0.0]),
    }


def matrix_limits(rows: list[dict[str, str]], direction: str) -> dict[str, float]:
    valid = valid_matrix_summary(rows, direction)
    throughputs = [number(row, "throughput_gbps_median") for row in valid]
    stage = "temp_write" if direction == "stor" else "download_temp_write"
    stage_throughputs = [throughput_from_stage(row, stage) for row in valid if throughput_from_stage(row, stage) > 0.0]
    elapsed = [number(row, "elapsed_median") for row in valid]
    if direction == "stor":
        temp_shares = [
            stage_value(row, "temp_write") / number(row, "elapsed_median")
            for row in valid
            if number(row, "elapsed_median") > 0.0 and stage_value(row, "temp_write") > 0.0
        ]
        data_shares = [
            stage_value(row, "data_receive") / number(row, "elapsed_median")
            for row in valid
            if number(row, "elapsed_median") > 0.0 and stage_value(row, "data_receive") > 0.0
        ]
    else:
        temp_shares = [
            stage_value(row, "download_temp_write") / number(row, "elapsed_median")
            for row in valid
            if number(row, "elapsed_median") > 0.0 and stage_value(row, "download_temp_write") > 0.0
        ]
        data_shares = [
            stage_value(row, "network_send") / number(row, "elapsed_median")
            for row in valid
            if number(row, "elapsed_median") > 0.0 and stage_value(row, "network_send") > 0.0
        ]
    return {
        "median": median(throughputs),
        "best": max(throughputs or [0.0]),
        "p95": p95(throughputs),
        "stage_throughput_median": median(stage_throughputs),
        "stage_share_median": median(temp_shares),
        "secondary_share_median": median(data_shares),
        "elapsed_median": median(elapsed),
    }


def best_network(rows: list[dict[str, str]], direction: str = "") -> tuple[float, float]:
    values = [
        number(row, "throughput_gbps")
        for row in rows
        if row.get("status") == "pass" and (not direction or row.get("direction") == direction)
    ]
    return median(values), max(values or [0.0])


def checksum_limits(rows: list[dict[str, str]]) -> dict[str, float]:
    hardware = [
        number(row, "throughput_gbps")
        for row in rows
        if row.get("status") == "pass"
        and (row.get("backend_requested") == "hardware" or row.get("backend_effective") == "hardware")
    ]
    software = [
        number(row, "throughput_gbps")
        for row in rows
        if row.get("status") == "pass"
        and (row.get("backend_requested") == "software" or row.get("backend_effective") == "software")
    ]
    auto = [number(row, "throughput_gbps") for row in rows if row.get("status") == "pass" and row.get("backend_requested") == "auto"]
    return {
        "hardware_median": median(hardware),
        "hardware_best": max(hardware or [0.0]),
        "software_median": median(software),
        "software_best": max(software or [0.0]),
        "auto_median": median(auto),
        "auto_best": max(auto or [0.0]),
    }


def memory_limit(rows: list[dict[str, str]]) -> tuple[float, float, str]:
    values = [
        number(row, "throughput_gbps")
        for row in rows
        if row.get("status") == "pass" and row.get("category") in {"network", "memory_or_sink"}
    ]
    if values:
        return median(values), max(values), "available"
    unavailable = any(row.get("status") == "unavailable" for row in rows)
    return 0.0, 0.0, "unavailable" if unavailable else "missing"


def dirty_correlation(storage_raw: list[dict[str, str]], matrix_raw: list[dict[str, str]]) -> str:
    xs: list[float] = []
    ys: list[float] = []
    for row in storage_raw:
        if row.get("result") != "pass":
            continue
        dirty = number(row, "dirty_kb_after") + number(row, "writeback_kb_after")
        throughput = number(row, "throughput_gbps")
        if dirty > 0.0 and throughput > 0.0:
            xs.append(dirty)
            ys.append(throughput)
    for row in matrix_raw:
        if row.get("result") != "pass":
            continue
        dirty = number(row, "server_dirty_kb_after") + number(row, "server_writeback_kb_after")
        throughput = number(row, "throughput_gbps")
        if dirty > 0.0 and throughput > 0.0:
            xs.append(dirty)
            ys.append(throughput)
    if len(xs) < 2:
        return f"样本不足（可用 paired rows={len(xs)}）"
    x_avg = statistics.mean(xs)
    y_avg = statistics.mean(ys)
    numerator = sum((x - x_avg) * (y - y_avg) for x, y in zip(xs, ys, strict=True))
    x_den = math.sqrt(sum((x - x_avg) ** 2 for x in xs))
    y_den = math.sqrt(sum((y - y_avg) ** 2 for y in ys))
    if x_den == 0.0 or y_den == 0.0:
        return f"样本方差不足（paired rows={len(xs)}）"
    return f"Pearson r={numerator / (x_den * y_den):.3f}，paired rows={len(xs)}"


def stage_rows(summary_rows: list[dict[str, str]], direction: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in sorted(
        valid_matrix_summary(summary_rows, direction),
        key=lambda item: (int(item.get("bytes", "0") or "0"), int(item.get("connections", "0") or "0"), item.get("checksum_algorithm", "")),
    ):
        elapsed = number(row, "elapsed_median")
        if direction == "stor":
            stages = [
                ("temp_write", stage_value(row, "temp_write")),
                ("data_receive", stage_value(row, "data_receive")),
                ("manifest", stage_value(row, "manifest")),
                ("final_verify", stage_value(row, "final_verify")),
                ("rename", stage_value(row, "rename")),
            ]
        else:
            stages = [
                ("source_read", stage_value(row, "source_read")),
                ("network_send", stage_value(row, "network_send")),
                ("download_temp_write", stage_value(row, "download_temp_write")),
                ("final_verify", stage_value(row, "final_verify")),
                ("rename", stage_value(row, "rename")),
            ]
        rows.append(
            [
                f"{size_label(row.get('bytes',''))} conn={row.get('connections','')} checksum={row.get('checksum_algorithm','')}",
                fmt(number(row, "throughput_gbps_median")),
                *[pct(value / elapsed) if elapsed > 0.0 and value > 0.0 else "" for _name, value in stages],
            ]
        )
    return rows


def storage_table(rows: list[dict[str, str]]) -> str:
    output: list[list[str]] = []
    for row in valid_storage_summary(rows):
        output.append(
            [
                row.get("dir_label", ""),
                row.get("operation", ""),
                size_label(row.get("bytes", "")),
                row.get("buffer_size", ""),
                row.get("preallocate", ""),
                fmt(number(row, "throughput_gbps_median")),
                fmt(number(row, "throughput_gbps_p95")),
                row.get("mount_target", ""),
                row.get("example_iostat", ""),
            ]
        )
    return table(["目录", "方向", "大小", "buffer", "preallocate", "median Gbps", "p95 Gbps", "挂载点", "iostat"], output)


def summary_metrics(
    network_rows: list[dict[str, str]],
    checksum_rows: list[dict[str, str]],
    memory_rows: list[dict[str, str]],
    storage_summary: list[dict[str, str]],
    stor_summary: list[dict[str, str]],
    retr_summary: list[dict[str, str]],
    storage_raw: list[dict[str, str]],
    matrix_raw: list[dict[str, str]],
) -> list[dict[str, str]]:
    network_median, network_best = best_network(network_rows)
    c2s_median, c2s_best = best_network(network_rows, "client_to_server")
    s2c_median, s2c_best = best_network(network_rows, "server_to_client")
    checksum = checksum_limits(checksum_rows)
    memory_median, memory_best, memory_status = memory_limit(memory_rows)
    storage = storage_limits(storage_summary)
    stor = matrix_limits(stor_summary, "stor")
    retr = matrix_limits(retr_summary, "retr")
    hash_mismatches = hash_mismatch_count(matrix_raw)
    observed_sizes = [
        int(number(row, "bytes") or number(row, "size_bytes"))
        for row in [*storage_summary, *stor_summary, *retr_summary]
        if (number(row, "bytes") or number(row, "size_bytes")) > 0.0
    ]
    max_observed_size = max(observed_sizes or [0])
    size_scope = "smoke_short_file_only" if max_observed_size and max_observed_size <= 256 * 1024**2 else "focused_long_file"
    rows = [
        {"metric": "network_median_gbps", "value": fmt(network_median), "unit": "Gbps", "note": "all iperf3 pass rows"},
        {"metric": "network_best_gbps", "value": fmt(network_best), "unit": "Gbps", "note": "all iperf3 pass rows"},
        {"metric": "network_client_to_server_median_gbps", "value": fmt(c2s_median), "unit": "Gbps", "note": "upload direction"},
        {"metric": "network_client_to_server_best_gbps", "value": fmt(c2s_best), "unit": "Gbps", "note": "upload direction"},
        {"metric": "network_server_to_client_median_gbps", "value": fmt(s2c_median), "unit": "Gbps", "note": "download direction"},
        {"metric": "network_server_to_client_best_gbps", "value": fmt(s2c_best), "unit": "Gbps", "note": "download direction"},
        {"metric": "checksum_hardware_median_gbps", "value": fmt(checksum["hardware_median"]), "unit": "Gbps", "note": "gridflux-checksum-bench"},
        {"metric": "checksum_hardware_best_gbps", "value": fmt(checksum["hardware_best"]), "unit": "Gbps", "note": "gridflux-checksum-bench"},
        {"metric": "checksum_software_median_gbps", "value": fmt(checksum["software_median"]), "unit": "Gbps", "note": "gridflux-checksum-bench"},
        {"metric": "memory_sink_median_gbps", "value": fmt(memory_median), "unit": "Gbps", "note": memory_status},
        {"metric": "memory_sink_best_gbps", "value": fmt(memory_best), "unit": "Gbps", "note": memory_status},
        {"metric": "storage_write_median_gbps", "value": fmt(storage["write_median"]), "unit": "Gbps", "note": "gridflux-storage-bench POSIX write"},
        {"metric": "storage_write_best_gbps", "value": fmt(storage["write_best"]), "unit": "Gbps", "note": "gridflux-storage-bench POSIX write"},
        {"metric": "storage_read_median_gbps", "value": fmt(storage["read_median"]), "unit": "Gbps", "note": "gridflux-storage-bench POSIX read"},
        {"metric": "storage_read_best_gbps", "value": fmt(storage["read_best"]), "unit": "Gbps", "note": "gridflux-storage-bench POSIX read"},
        {"metric": "stor_e2e_median_gbps", "value": fmt(stor["median"]), "unit": "Gbps", "note": "GridFlux STOR summary"},
        {"metric": "stor_e2e_best_gbps", "value": fmt(stor["best"]), "unit": "Gbps", "note": "GridFlux STOR summary"},
        {"metric": "stor_temp_write_median_gbps", "value": fmt(stor["stage_throughput_median"]), "unit": "Gbps", "note": "bytes / temp_write_seconds"},
        {"metric": "stor_temp_write_share_median", "value": fmt(stor["stage_share_median"]), "unit": "ratio", "note": pct(stor["stage_share_median"])},
        {"metric": "stor_data_receive_share_median", "value": fmt(stor["secondary_share_median"]), "unit": "ratio", "note": pct(stor["secondary_share_median"])},
        {"metric": "retr_e2e_median_gbps", "value": fmt(retr["median"]), "unit": "Gbps", "note": "GridFlux RETR summary"},
        {"metric": "retr_e2e_best_gbps", "value": fmt(retr["best"]), "unit": "Gbps", "note": "GridFlux RETR summary"},
        {"metric": "retr_download_temp_write_share_median", "value": fmt(retr["stage_share_median"]), "unit": "ratio", "note": pct(retr["stage_share_median"])},
        {"metric": "retr_network_send_share_median", "value": fmt(retr["secondary_share_median"]), "unit": "ratio", "note": pct(retr["secondary_share_median"])},
        {"metric": "hash_mismatch_count", "value": str(hash_mismatches), "unit": "count", "note": "GridFlux raw transfer rows"},
        {"metric": "max_observed_size_bytes", "value": str(max_observed_size), "unit": "bytes", "note": size_label(str(max_observed_size)) if max_observed_size else ""},
        {"metric": "run_size_scope", "value": size_scope, "unit": "text", "note": "64MiB/256MiB rows are smoke only; 1GiB/4GiB rows are formal attribution"},
        {"metric": "dirty_writeback_correlation", "value": "", "unit": "text", "note": dirty_correlation(storage_raw, matrix_raw)},
    ]
    verdict = proof_verdict(rows)
    rows.append({"metric": "proof_verdict", "value": verdict[0], "unit": "text", "note": verdict[1]})
    return rows


def metric_value(rows: list[dict[str, str]], metric: str) -> float:
    for row in rows:
        if row.get("metric") == metric:
            return number(row, "value")
    return 0.0


def metric_note(rows: list[dict[str, str]], metric: str) -> str:
    for row in rows:
        if row.get("metric") == metric:
            return row.get("note", "")
    return ""


def proof_verdict(summary_rows: list[dict[str, str]]) -> tuple[str, str]:
    network = metric_value(summary_rows, "network_client_to_server_best_gbps") or metric_value(summary_rows, "network_best_gbps")
    checksum = metric_value(summary_rows, "checksum_hardware_best_gbps")
    memory = metric_value(summary_rows, "memory_sink_best_gbps")
    storage_write = metric_value(summary_rows, "storage_write_median_gbps")
    stor = metric_value(summary_rows, "stor_e2e_median_gbps")
    temp_share = metric_value(summary_rows, "stor_temp_write_share_median")
    data_share = metric_value(summary_rows, "stor_data_receive_share_median")
    hash_mismatches = metric_value(summary_rows, "hash_mismatch_count")
    size_scope = next((row.get("value", "") for row in summary_rows if row.get("metric") == "run_size_scope"), "")
    network_clear = network > 0.0 and stor > 0.0 and network >= stor * 4.0
    checksum_clear = checksum > 0.0 and stor > 0.0 and checksum >= stor * 4.0
    memory_clear = memory == 0.0 or (stor > 0.0 and memory >= stor * 2.0)
    storage_same_order = storage_write > 0.0 and stor > 0.0 and 0.4 <= stor / storage_write <= 2.5
    stage_clear = temp_share >= 0.60 and data_share < 0.10
    hash_clear = hash_mismatches == 0.0
    focused_clear = size_scope == "focused_long_file"
    if network_clear and checksum_clear and memory_clear and storage_same_order and stage_clear and hash_clear and focused_clear:
        return (
            "cloud_disk_writeback_dominated",
            "正式 focused 数据满足：网络和 CRC32C 明显高于 STOR，storage write 与 STOR 同量级，temp_write 占比超过 60%，data_receive 低于 10%，hash mismatch 为 0。",
        )
    missing: list[str] = []
    if not focused_clear:
        missing.append("当前输入不是 1GiB/4GiB focused 长文件样本")
    if not network_clear:
        missing.append("network best 未达到 STOR 的 4x 以上")
    if not checksum_clear:
        missing.append("CRC32C hardware best 未达到 STOR 的 4x 以上")
    if not memory_clear:
        missing.append("memory/sink 对照未明显高于 STOR")
    if not storage_same_order:
        missing.append("storage write 与 STOR 不在同一数量级")
    if temp_share < 0.60:
        missing.append("STOR temp_write share 未超过 60%")
    if data_share >= 0.10:
        missing.append("STOR data_receive share 未低于 10%")
    if not hash_clear:
        missing.append("hash mismatch 非 0")
    return (
        "inconclusive_or_mixed",
        "证据链不足以单独归因到云盘/writeback；缺失或未满足：" + "；".join(missing) + "。",
    )


def metric_table(rows: list[dict[str, str]]) -> str:
    selected = [
        ("network_client_to_server_best_gbps", "上传方向 TCP best"),
        ("network_server_to_client_best_gbps", "下载方向 TCP best"),
        ("checksum_hardware_best_gbps", "CRC32C hardware best"),
        ("memory_sink_best_gbps", "memory/sink best"),
        ("storage_write_median_gbps", "storage write median"),
        ("storage_read_median_gbps", "storage read median"),
        ("stor_e2e_median_gbps", "STOR e2e median"),
        ("stor_temp_write_median_gbps", "STOR temp-write median"),
        ("stor_temp_write_share_median", "STOR temp-write 占比"),
        ("stor_data_receive_share_median", "STOR data_receive 占比"),
        ("hash_mismatch_count", "hash mismatch"),
        ("run_size_scope", "数据范围"),
        ("retr_e2e_median_gbps", "RETR e2e median"),
        ("retr_download_temp_write_share_median", "RETR temp-write 占比"),
        ("retr_network_send_share_median", "RETR network_send 占比"),
        ("proof_verdict", "归因结论"),
    ]
    output = []
    by_metric = {row["metric"]: row for row in rows}
    for key, label in selected:
        row = by_metric.get(key, {})
        value = row.get("value", "")
        if row.get("unit") == "ratio":
            value = row.get("note", value)
        output.append([label, value, row.get("unit", ""), row.get("note", "")])
    return table(["指标", "数值", "单位", "说明"], output)


def hash_mismatch_count(rows: list[dict[str, str]]) -> int:
    mismatches = 0
    for row in rows:
        source = row.get("source_sha256", "")
        dest = row.get("dest_sha256", "")
        if source and dest and source != dest:
            mismatches += 1
    return mismatches


def evidence_chain_table(rows: list[dict[str, str]]) -> str:
    by_metric = {row["metric"]: row for row in rows}

    def value(metric: str, *, ratio: bool = False) -> str:
        row = by_metric.get(metric, {})
        if ratio:
            return row.get("note", row.get("value", ""))
        if row.get("unit") == "Gbps":
            return f"{row.get('value', '')} Gbps"
        if row.get("unit") == "count":
            return row.get("value", "")
        return row.get("value", "")

    output = [
        ["iperf3 best", "much higher than STOR", value("network_client_to_server_best_gbps")],
        ["CRC32C hardware best", "much higher than STOR", value("checksum_hardware_best_gbps")],
        ["storage write median", "same order as STOR", value("storage_write_median_gbps")],
        ["STOR e2e median", "close to storage write", value("stor_e2e_median_gbps")],
        ["STOR temp-write share", ">60%, ideally >70%", value("stor_temp_write_share_median", ratio=True)],
        ["STOR data_receive share", "small, ideally <10%", value("stor_data_receive_share_median", ratio=True)],
        ["hash mismatch", "0", value("hash_mismatch_count")],
    ]
    return table(["evidence", "expected if disk bottleneck", "observed"], output)


def network_table(rows: list[dict[str, str]]) -> str:
    return table(
        ["方向", "并发", "时长", "Gbps", "状态"],
        [
            [
                row.get("direction", ""),
                row.get("parallelism", ""),
                row.get("duration_seconds", ""),
                row.get("throughput_gbps", ""),
                row.get("status", ""),
            ]
            for row in rows
        ],
    )


def checksum_table(rows: list[dict[str, str]]) -> str:
    return table(
        ["<redacted>", "backend", "effective", "大小", "iterations", "Gbps", "状态"],
        [
            [
                row.get("machine", ""),
                row.get("backend_requested", ""),
                row.get("backend_effective", ""),
                size_label(row.get("size_bytes", "")),
                row.get("iterations", ""),
                row.get("throughput_gbps", ""),
                row.get("status", ""),
            ]
            for row in rows
        ],
    )


def render_report(
    *,
    summary_rows: list[dict[str, str]],
    network_rows: list[dict[str, str]],
    checksum_rows: list[dict[str, str]],
    memory_rows: list[dict[str, str]],
    storage_summary: list[dict[str, str]],
    stor_summary: list[dict[str, str]],
    retr_summary: list[dict[str, str]],
    inputs: list[str],
) -> str:
    verdict = next((row for row in summary_rows if row.get("metric") == "proof_verdict"), {})
    observed_sizes = [
        int(number(row, "bytes") or number(row, "size_bytes"))
        for row in [*storage_summary, *stor_summary, *retr_summary]
        if (number(row, "bytes") or number(row, "size_bytes")) > 0.0
    ]
    max_observed_size = max(observed_sizes or [0])
    scope_note = (
        "本次输入只包含 256MiB 或更小的 smoke 短文件，page cache/短文件效应很强；它只能验证工具闭环，不能作为长文件写盘瓶颈证明。"
        if max_observed_size and max_observed_size <= 256 * 1024**2
        else "本次输入包含长文件样本，可用于 focused 归因；仍需结合 repeat 稳定性和 hash 一致性判断。"
    )
    return "\n".join(
        [
            "# Cloud Disk Bottleneck Proof",
            "",
            f"生成时间：`{timestamp_utc()}`",
            "",
            "## 1. 实验目的",
            "",
            "本实验在当前两台阿里云云服务器私网环境下做分层对照，目标是判断 GridFlux 长文件 STOR 主要瓶颈是否符合云盘、文件系统、Linux page cache/writeback 限制，而不是网络、CPU、CRC32C 指令算力或 GridFlux 协议本身。",
            "",
            "## 2. 实验假设",
            "",
            "- H1：当前 STOR 主瓶颈在云服务器硬盘写入 / 文件系统 / OS writeback。",
            "- H0：当前 STOR 主瓶颈在网络 / CPU / checksum / GridFlux 协议调度。",
            "",
            "## 3. 输入文件",
            "",
            *[f"- `{path}`" for path in inputs if path],
            "",
            "## 4. 关键结果",
            "",
            metric_table(summary_rows),
            "",
            f"> 数据范围提示：{scope_note}",
            "",
            "## 5. 正式 Focused 结果与证据链总表",
            "",
            "正式 focused 归因使用 `1GiB/4GiB repeat=3`；64MiB smoke 只用于工具链闭环验证，不作为瓶颈归因结论。",
            "",
            evidence_chain_table(summary_rows),
            "",
            "判定规则：只有 network 和 CRC32C 明显高于 STOR、storage write 与 STOR 同量级、STOR temp-write share 超过 60%、data_receive share 低于 10%、hash mismatch 为 0，且输入包含 focused 长文件样本时，verdict 才会变为 `cloud_disk_writeback_dominated`。",
            "",
            "## 6. 网络上限对照",
            "",
            network_table(network_rows),
            "",
            "如果上传方向 iperf3 明显高于 STOR 长文件吞吐，例如十几 Gbps 对 1-2 Gbps，则网络不是当前 STOR 主瓶颈。",
            "",
            "## 7. CRC32C / CPU 对照",
            "",
            checksum_table(checksum_rows),
            "",
            "这里证明的是 CRC32C 指令算力不是主瓶颈；checksum 集成路径仍可能存在局部开销，需要通过 `crc32c` 与 `none` 的传输行继续观察。",
            "",
            "## 8. Memory / Sink 对照",
            "",
            table(
                ["side", "category", "tool", "bytes", "Gbps", "status"],
                [
                    [
                        row.get("side", ""),
                        row.get("category", ""),
                        row.get("tool", ""),
                        size_label(row.get("bytes", "")),
                        row.get("throughput_gbps", ""),
                        row.get("status", ""),
                    ]
                    for row in memory_rows
                ],
            ),
            "",
            "memory/sink 对照不可用时不作为失败项；它只是用来辅助判断协议和内存路径的潜在上限。",
            "",
            "## 9. 原生存储写入/读取对照",
            "",
            storage_table(storage_summary),
            "",
            "storage write 与 STOR e2e/temp-write 如果长期处于同一数量级，说明继续优化 GridFlux 协议本身的收益可能被云盘/writeback 天花板吸收。",
            "",
            "## 10. GridFlux STOR 阶段拆解",
            "",
            table(
                ["case", "median Gbps", "temp_write", "data_receive", "manifest", "final_verify", "rename"],
                stage_rows(stor_summary, "stor"),
            ),
            "",
            "判定重点是 `temp_write_seconds` 是否占大头，以及 `data_receive_seconds` 是否很小。若 temp_write 超过 60%-70%，STOR 的 wall time 更符合 receiver 写盘/writeback 限制。",
            "",
            "## 11. GridFlux RETR 阶段拆解",
            "",
            table(
                ["case", "median Gbps", "source_read", "network_send", "download_temp_write", "final_verify", "rename"],
                stage_rows(retr_summary, "retr"),
            ),
            "",
            "RETR 不强行归因到写盘：需要分别看 source read、sender network send、receiver download temp write 和 final verify。",
            "",
            "## 12. 证据链结论",
            "",
            f"- Verdict: `{verdict.get('value', '')}`。",
            f"- 说明：{verdict.get('note', '')}",
            f"- Dirty/Writeback 相关性：{metric_note(summary_rows, 'dirty_writeback_correlation')}",
            "",
            "当前结论只针对这组阿里云服务器和本次测试窗口。它不是 100G 外推，也不是证明 GridFlux 在更强硬件上不会遇到网络、CPU、checksum、内存拷贝或协议实现瓶颈。",
            "",
            "## 13. 局限性",
            "",
            "- 当前云服务器裸 TCP 不是 100G 环境。",
            "- 云盘、文件系统、page cache 状态会影响 storage 和 STOR 结果。",
            "- fio 缺失时只记录 unavailable，不安装系统依赖。",
            "- memory/sink 不可用时，协议非落盘路径证据会弱一些。",
            "- 所有传输结论只使用 hash 一致且 status pass 的 GridFlux rows。",
            "",
            "## 14. 后续 R750 / 100G 验证计划",
            "",
            "- 先跑 iperf3 双向 p1/p4/p8/p16，确认链路上限。",
            "- 再跑 NVMe/fio/storage bench，确认写入和读取上限是否达到预期。",
            "- 跑 memory sink 与 CRC32C benchmark，确认 CPU/checksum 余量。",
            "- 先做 10GiB GridFlux smoke，再做 100GiB repeat；观察瓶颈是否从写盘转移到网络、CPU、checksum 或数据面。",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network-csv", default="")
    parser.add_argument("--checksum-csv", default="")
    parser.add_argument("--memory-csv", default="")
    parser.add_argument("--storage-raw-csv", default="")
    parser.add_argument("--storage-summary-csv", default="")
    parser.add_argument("--stor-raw-csv", action="append", default=[])
    parser.add_argument("--stor-summary-csv", action="append", default=[])
    parser.add_argument("--retr-raw-csv", action="append", default=[])
    parser.add_argument("--retr-summary-csv", action="append", default=[])
    parser.add_argument("--output", default="docs/perf/CLOUD_DISK_BOTTLENECK_PROOF.md")
    parser.add_argument("--summary-output", default="")
    args = parser.parse_args()

    network_rows = read_csv(args.network_csv)
    checksum_rows = read_csv(args.checksum_csv)
    memory_rows = read_csv(args.memory_csv)
    storage_raw = read_csv(args.storage_raw_csv)
    storage_summary = read_csv(args.storage_summary_csv)
    stor_raw = read_many(args.stor_raw_csv)
    stor_summary = read_many(args.stor_summary_csv)
    retr_raw = read_many(args.retr_raw_csv)
    retr_summary = read_many(args.retr_summary_csv)
    matrix_raw = stor_raw + retr_raw
    summary_rows = summary_metrics(
        network_rows,
        checksum_rows,
        memory_rows,
        storage_summary,
        stor_summary,
        retr_summary,
        storage_raw,
        matrix_raw,
    )
    summary_output = Path(args.summary_output) if args.summary_output else ROOT / "tools" / "perf" / "results" / "cloud-disk-proof-attribution-summary.csv"
    if not summary_output.is_absolute():
        summary_output = ROOT / summary_output
    write_csv(summary_output, summary_rows, SUMMARY_FIELDS)

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_report(
            summary_rows=summary_rows,
            network_rows=network_rows,
            checksum_rows=checksum_rows,
            memory_rows=memory_rows,
            storage_summary=storage_summary,
            stor_summary=stor_summary,
            retr_summary=retr_summary,
            inputs=[
                args.network_csv,
                args.checksum_csv,
                args.memory_csv,
                args.storage_raw_csv,
                args.storage_summary_csv,
                *args.stor_raw_csv,
                *args.stor_summary_csv,
                *args.retr_raw_csv,
                *args.retr_summary_csv,
            ],
        ),
        encoding="utf-8",
    )
    print(f"summary_csv={summary_output}")
    print(f"report={output}")
    print(f"verdict={next((row.get('value','') for row in summary_rows if row.get('metric') == 'proof_verdict'), '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
