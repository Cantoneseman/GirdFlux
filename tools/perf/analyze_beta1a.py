#!/usr/bin/env python3
"""Analyze Beta 1A private readiness CSVs and write a Markdown report."""

from __future__ import annotations

import argparse
import csv
import math
import time
from pathlib import Path


def read_csv(path: str | Path) -> list[dict[str, str]]:
    if not path:
        return []
    csv_path = Path(path)
    if not csv_path.is_file():
        return []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def number(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "") or "0")
    except ValueError:
        return 0.0


def pct(value: float, base: float) -> str:
    if base == 0:
        return ""
    return f"{((value - base) / base) * 100.0:+.1f}%"


def fmt(value: float) -> str:
    if not math.isfinite(value):
        return ""
    return f"{value:.3f}"


def phase_bottleneck(row: dict[str, str]) -> str:
    direction = row.get("direction", "")
    candidates: list[tuple[str, float]] = []
    if direction.startswith("stor"):
        candidates = [
            ("receiver temp write", number(row, "receiver_temp_write_seconds_median") or number(row, "temp_write_seconds_median")),
            ("receiver checksum", number(row, "receiver_checksum_seconds_median") or number(row, "checksum_seconds_median")),
            ("receiver manifest", number(row, "receiver_manifest_flush_seconds_median") or number(row, "manifest_flush_seconds_median")),
            ("receiver finalize", number(row, "receiver_finalize_rename_seconds_median") or number(row, "finalize_rename_seconds_median")),
            ("sender read", number(row, "sender_stage_read_seconds_median")),
        ]
    elif direction.startswith("retr"):
        candidates = [
            ("sender network send", number(row, "sender_network_send_seconds_median")),
            ("sender source read", number(row, "sender_source_read_seconds_median")),
            ("receiver temp write", number(row, "receiver_download_temp_write_seconds_median")),
            ("receiver final verify", number(row, "receiver_final_verify_seconds_median")),
            ("receiver finalize", number(row, "receiver_finalize_rename_seconds_median")),
        ]
    candidates = [(name, value) for name, value in candidates if value > 0]
    if not candidates:
        return "unknown"
    name, value = max(candidates, key=lambda item: item[1])
    elapsed = number(row, "elapsed_median")
    share = f" ({value / elapsed * 100.0:.1f}% of elapsed)" if elapsed > 0 else ""
    return f"{name}{share}"


def table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_No data._\n"
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def single_rows(rows: list[dict[str, str]]) -> str:
    selected = sorted(
        rows,
        key=lambda row: (
            row.get("direction", ""),
            int(row.get("bytes", "0") or "0"),
            int(row.get("connections", "0") or "0"),
            row.get("checksum_algorithm", ""),
            row.get("tls_mode", ""),
            row.get("data_tls_mode", ""),
            row.get("file_io_backend", ""),
        ),
    )
    table_rows: list[list[str]] = []
    for row in selected[:80]:
        table_rows.append(
            [
                row.get("direction", ""),
                row.get("bytes", ""),
                row.get("connections", ""),
                row.get("checksum_algorithm", ""),
                row.get("tls_mode", ""),
                row.get("data_tls_mode", ""),
                row.get("file_io_backend", ""),
                row.get("final_verify_policy_effective", row.get("final_verify_policy", "")),
                fmt(number(row, "throughput_gbps_median")),
                fmt(number(row, "throughput_gbps_spread_pct")),
                row.get("fail_count", "0"),
                phase_bottleneck(row),
            ]
        )
    return table(
        [
            "direction",
            "bytes",
            "conn",
            "checksum",
            "TLS",
            "data TLS",
            "backend",
            "final verify",
            "median Gbps",
            "spread %",
            "fail",
            "dominant measured stage",
        ],
        table_rows,
    )


def relative_delta_rows(rows: list[dict[str, str]], dimension: str, baseline_value: str, compare_value: str) -> str:
    by_key: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = (
            row.get("direction", ""),
            row.get("bytes", ""),
            row.get("connections", ""),
            row.get("checksum_algorithm", ""),
            row.get("tls_mode", "") if dimension != "tls" else "",
            row.get("data_tls_mode", "") if dimension != "tls" else "",
            row.get("file_io_backend", "") if dimension != "backend" else "",
            row.get("final_verify_policy_effective", row.get("final_verify_policy", "")),
        )
        if dimension == "tls":
            value = f"{row.get('tls_mode', '')}/{row.get('data_tls_mode', '')}"
        else:
            value = row.get("file_io_backend", "")
        by_key[(*key, value)] = row
    rows_out: list[list[str]] = []
    keys = sorted({key[:-1] for key in by_key})
    for key in keys:
        base = by_key.get((*key, baseline_value))
        comp = by_key.get((*key, compare_value))
        if not base or not comp:
            continue
        base_t = number(base, "throughput_gbps_median")
        comp_t = number(comp, "throughput_gbps_median")
        rows_out.append(
            [
                key[0],
                key[1],
                key[2],
                key[3],
                baseline_value,
                compare_value,
                fmt(base_t),
                fmt(comp_t),
                pct(comp_t, base_t),
            ]
        )
    return table(
        ["direction", "bytes", "conn", "checksum", "base", "compare", "base Gbps", "compare Gbps", "delta"],
        rows_out[:60],
    )


def tree_rows(rows: list[dict[str, str]]) -> str:
    table_rows: list[list[str]] = []
    for row in sorted(
        rows,
        key=lambda item: (
            item.get("dataset", ""),
            item.get("direction", ""),
            item.get("file_parallelism", ""),
            item.get("checksum_algorithm", ""),
            item.get("tls_mode", ""),
            item.get("file_io_backend", ""),
        ),
    )[:80]:
        table_rows.append(
            [
                row.get("dataset", ""),
                row.get("direction", ""),
                row.get("file_parallelism", ""),
                row.get("connections", ""),
                row.get("checksum_algorithm", ""),
                row.get("tls_mode", ""),
                row.get("data_tls_mode", ""),
                row.get("file_io_backend", ""),
                fmt(number(row, "throughput_gbps_median")),
                row.get("fail_count", "0"),
                row.get("tree_hash_mismatch_count", "0"),
            ]
        )
    return table(
        ["dataset", "direction", "fp", "conn", "checksum", "TLS", "data TLS", "backend", "median Gbps", "fail", "hash mismatch"],
        table_rows,
    )


def host_rows(rows: list[dict[str, str]]) -> str:
    table_rows = [
        [
            row.get("side", ""),
            row.get("category", ""),
            row.get("tool", ""),
            row.get("bytes", ""),
            row.get("throughput_gbps", ""),
            row.get("result", ""),
        ]
        for row in rows
    ]
    return table(["side", "category", "tool", "bytes", "Gbps", "result"], table_rows)


def conclusion(single: list[dict[str, str]]) -> str:
    if not single:
        return "No single-file summary was provided; 100G readiness cannot be assessed."
    best = max((number(row, "throughput_gbps_median") for row in single), default=0.0)
    gap = (100.0 / best) if best > 0 else 0.0
    bottlenecks = {}
    for row in single:
        if row.get("fail_count", "0") != "0":
            continue
        key = phase_bottleneck(row).split(" (", 1)[0]
        bottlenecks[key] = bottlenecks.get(key, 0) + 1
    dominant = ", ".join(f"{name}={count}" for name, count in sorted(bottlenecks.items(), key=lambda item: -item[1])[:4])
    return (
        f"Best observed median throughput in the supplied summaries is {best:.3f} Gbps, "
        f"about {gap:.1f}x below 100 Gbps. Dominant measured stages by row: {dominant or 'unknown'}. "
        "Treat this as a readiness diagnosis, not a default-policy change."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Beta 1A readiness CSVs.")
    parser.add_argument("--host-baseline-csv", default="")
    parser.add_argument("--single-summary-csv", action="append", default=[])
    parser.add_argument("--tree-summary-csv", action="append", default=[])
    parser.add_argument("--output", default="docs/perf/BETA1A_100G_READINESS.md")
    args = parser.parse_args()

    host = read_csv(args.host_baseline_csv)
    single: list[dict[str, str]] = []
    for path in args.single_summary_csv:
        single.extend(read_csv(path))
    tree: list[dict[str, str]] = []
    for path in args.tree_summary_csv:
        tree.extend(read_csv(path))

    lines = [
        "# Beta 1A 100G Readiness Diagnosis",
        "",
        f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        "",
        "## Executive Summary",
        "",
        conclusion(single),
        "",
        "Defaults remain unchanged: anonymous auth, TLS off, data TLS off, POSIX backend, full final verify, every-n-chunks manifest flush, preallocate off, and POSIX write strategy auto.",
        "",
        "## Host / Link / Storage Baseline",
        "",
        host_rows(host),
        "",
        "## Single-file STOR/RETR Matrix",
        "",
        single_rows(single),
        "",
        "## TLS and Data TLS Delta",
        "",
        relative_delta_rows(single, "tls", "off/off", "required/required"),
        "",
        "## POSIX vs io_uring Delta",
        "",
        relative_delta_rows(single, "backend", "posix", "io_uring"),
        "",
        "## Directory Matrix",
        "",
        tree_rows(tree),
        "",
        "## Readiness Gate",
        "",
        "- 100G is not considered ready unless repeat median approaches link baseline with low spread and zero hash mismatches.",
        "- Failed rows, hash mismatches, or high spread must be investigated from the referenced raw CSV logs and JSONL event logs.",
        "- LIST/NLST listing data TLS remains outside the Phase 6D/Beta 1A data TLS scope; Beta 1A TLS conclusions cover STOR/RETR framed file data only.",
    ]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
