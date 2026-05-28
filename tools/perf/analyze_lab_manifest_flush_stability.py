#!/usr/bin/env python3
"""Analyze Lab Beta 2D manifest flush interval stability CSVs."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]

SUMMARY_FIELDS = [
    "size_label",
    "bytes",
    "direction",
    "checksum",
    "final_verify_policy",
    "connections",
    "interval",
    "sample_count",
    "pass_count",
    "fail_count",
    "sha_mismatch_count",
    "throughput_median_gbps",
    "throughput_best_gbps",
    "throughput_p95_gbps",
    "throughput_spread_pct",
    "manifest_flush_median_s",
    "manifest_sort_median_s",
    "manifest_serialize_median_s",
    "manifest_write_median_s",
    "manifest_bytes_written_median",
]

DELTA_FIELDS = [
    "size_label",
    "bytes",
    "direction",
    "checksum",
    "final_verify_policy",
    "connections",
    "baseline_interval",
    "candidate_interval",
    "baseline_samples",
    "candidate_samples",
    "baseline_fail_count",
    "candidate_fail_count",
    "baseline_sha_mismatch_count",
    "candidate_sha_mismatch_count",
    "throughput_baseline_median_gbps",
    "throughput_candidate_median_gbps",
    "throughput_delta_pct",
    "manifest_flush_baseline_median_s",
    "manifest_flush_candidate_median_s",
    "manifest_flush_reduction_pct",
    "manifest_sort_baseline_median_s",
    "manifest_sort_candidate_median_s",
    "manifest_serialize_baseline_median_s",
    "manifest_serialize_candidate_median_s",
    "manifest_write_baseline_median_s",
    "manifest_write_candidate_median_s",
    "manifest_bytes_written_baseline_median",
    "manifest_bytes_written_candidate_median",
    "gate_pass",
    "gate_notes",
]


def read_rows(paths: Iterable[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        actual = path if path.is_absolute() else ROOT / path
        with actual.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                row["_source_csv"] = str(actual)
                rows.append(row)
    return rows


def number(row: dict[str, str], field: str) -> float:
    text = row.get(field, "")
    if text == "":
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def integer(row: dict[str, str], field: str) -> int:
    return int(number(row, field))


def fmt_float(value: float, digits: int = 3) -> str:
    if not math.isfinite(value):
        return ""
    return f"{value:.{digits}f}"


def fmt_int(value: float) -> str:
    if not math.isfinite(value):
        return ""
    return str(int(round(value)))


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def pct_delta(candidate: float, baseline: float) -> float:
    if baseline <= 0.0:
        return 0.0
    return (candidate - baseline) / baseline * 100.0


def pct_reduction(candidate: float, baseline: float) -> float:
    if baseline <= 0.0:
        return 0.0
    return (baseline - candidate) / baseline * 100.0


def size_label(size_bytes: int) -> str:
    gib = size_bytes / float(1024**3)
    if abs(gib - round(gib)) < 0.001:
        return f"{int(round(gib))}GiB"
    return f"{gib:.2f}GiB"


def final_verify(row: dict[str, str]) -> str:
    return (
        row.get("final_verify_policy_effective")
        or row.get("final_verify_policy")
        or row.get("final_verify_policy_requested")
        or ""
    )


def checksum(row: dict[str, str]) -> str:
    return row.get("checksum_algorithm") or row.get("checksum") or ""


def row_sha_mismatch(row: dict[str, str]) -> bool:
    source = row.get("source_sha256", "")
    dest = row.get("dest_sha256", "")
    return bool(source and dest and source != dest)


def row_passes(row: dict[str, str]) -> bool:
    return row.get("result") == "pass" and not row_sha_mismatch(row)


def group_key(row: dict[str, str], include_interval: bool) -> tuple[str, ...]:
    parts = [
        str(integer(row, "bytes")),
        row.get("direction", ""),
        checksum(row),
        final_verify(row),
        str(integer(row, "connections")),
    ]
    if include_interval:
        parts.append(str(integer(row, "manifest_flush_interval_chunks")))
    return tuple(parts)


def summarize_group(rows: list[dict[str, str]]) -> dict[str, str]:
    first = rows[0]
    passing = [row for row in rows if row_passes(row)]
    throughputs = [number(row, "throughput_gbps") for row in passing if number(row, "throughput_gbps") > 0.0]
    spread = 0.0
    if throughputs and median(throughputs) > 0.0:
        spread = (max(throughputs) - min(throughputs)) / median(throughputs) * 100.0
    values = {
        "manifest_flush_median_s": median([number(row, "manifest_flush_seconds") for row in passing]),
        "manifest_sort_median_s": median([number(row, "manifest_sort_seconds") for row in passing]),
        "manifest_serialize_median_s": median([number(row, "manifest_serialize_seconds") for row in passing]),
        "manifest_write_median_s": median([number(row, "manifest_write_seconds") for row in passing]),
        "manifest_bytes_written_median": median([number(row, "manifest_bytes_written") for row in passing]),
    }
    output = {
        "size_label": size_label(integer(first, "bytes")),
        "bytes": str(integer(first, "bytes")),
        "direction": first.get("direction", ""),
        "checksum": checksum(first),
        "final_verify_policy": final_verify(first),
        "connections": str(integer(first, "connections")),
        "interval": str(integer(first, "manifest_flush_interval_chunks")),
        "sample_count": str(len(rows)),
        "pass_count": str(len(passing)),
        "fail_count": str(sum(1 for row in rows if row.get("result") != "pass")),
        "sha_mismatch_count": str(sum(1 for row in rows if row_sha_mismatch(row))),
        "throughput_median_gbps": fmt_float(median(throughputs)),
        "throughput_best_gbps": fmt_float(max(throughputs or [0.0])),
        "throughput_p95_gbps": fmt_float(p95(throughputs)),
        "throughput_spread_pct": fmt_float(spread, 1),
        "manifest_flush_median_s": fmt_float(values["manifest_flush_median_s"]),
        "manifest_sort_median_s": fmt_float(values["manifest_sort_median_s"]),
        "manifest_serialize_median_s": fmt_float(values["manifest_serialize_median_s"]),
        "manifest_write_median_s": fmt_float(values["manifest_write_median_s"]),
        "manifest_bytes_written_median": fmt_int(values["manifest_bytes_written_median"]),
    }
    return output


def summary_number(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "") or "0")
    except ValueError:
        return 0.0


def compare_intervals(
    summaries: list[dict[str, str]],
    baseline_interval: int,
    candidate_interval: int,
    flush_reduction_threshold: float,
    throughput_regression_threshold: float,
) -> list[dict[str, str]]:
    grouped: dict[tuple[str, ...], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in summaries:
        key = (
            row["bytes"],
            row["direction"],
            row["checksum"],
            row["final_verify_policy"],
            row["connections"],
        )
        grouped[key][row["interval"]] = row

    deltas: list[dict[str, str]] = []
    for key, by_interval in sorted(grouped.items()):
        base = by_interval.get(str(baseline_interval))
        cand = by_interval.get(str(candidate_interval))
        if not base or not cand:
            continue
        base_tp = summary_number(base, "throughput_median_gbps")
        cand_tp = summary_number(cand, "throughput_median_gbps")
        base_flush = summary_number(base, "manifest_flush_median_s")
        cand_flush = summary_number(cand, "manifest_flush_median_s")
        throughput_delta = pct_delta(cand_tp, base_tp)
        flush_reduction = pct_reduction(cand_flush, base_flush)
        fail_count = (
            int(base["fail_count"])
            + int(cand["fail_count"])
            + int(base["sha_mismatch_count"])
            + int(cand["sha_mismatch_count"])
        )
        notes: list[str] = []
        if fail_count:
            notes.append("failure_or_sha_mismatch")
        if flush_reduction < flush_reduction_threshold * 100.0:
            notes.append("manifest_flush_reduction_below_threshold")
        if key[2] == "crc32c" and throughput_delta < -throughput_regression_threshold * 100.0:
            notes.append("crc32c_throughput_regression")
        deltas.append(
            {
                "size_label": size_label(int(key[0])),
                "bytes": key[0],
                "direction": key[1],
                "checksum": key[2],
                "final_verify_policy": key[3],
                "connections": key[4],
                "baseline_interval": str(baseline_interval),
                "candidate_interval": str(candidate_interval),
                "baseline_samples": base["sample_count"],
                "candidate_samples": cand["sample_count"],
                "baseline_fail_count": base["fail_count"],
                "candidate_fail_count": cand["fail_count"],
                "baseline_sha_mismatch_count": base["sha_mismatch_count"],
                "candidate_sha_mismatch_count": cand["sha_mismatch_count"],
                "throughput_baseline_median_gbps": base["throughput_median_gbps"],
                "throughput_candidate_median_gbps": cand["throughput_median_gbps"],
                "throughput_delta_pct": fmt_float(throughput_delta, 1),
                "manifest_flush_baseline_median_s": base["manifest_flush_median_s"],
                "manifest_flush_candidate_median_s": cand["manifest_flush_median_s"],
                "manifest_flush_reduction_pct": fmt_float(flush_reduction, 1),
                "manifest_sort_baseline_median_s": base["manifest_sort_median_s"],
                "manifest_sort_candidate_median_s": cand["manifest_sort_median_s"],
                "manifest_serialize_baseline_median_s": base["manifest_serialize_median_s"],
                "manifest_serialize_candidate_median_s": cand["manifest_serialize_median_s"],
                "manifest_write_baseline_median_s": base["manifest_write_median_s"],
                "manifest_write_candidate_median_s": cand["manifest_write_median_s"],
                "manifest_bytes_written_baseline_median": base["manifest_bytes_written_median"],
                "manifest_bytes_written_candidate_median": cand["manifest_bytes_written_median"],
                "gate_pass": "yes" if not notes else "no",
                "gate_notes": ",".join(notes),
            }
        )
    return deltas


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(fields: list[str], rows: list[dict[str, str]], limit: int = 80) -> str:
    visible = rows[:limit]
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in visible:
        lines.append("| " + " | ".join(row.get(field, "") for field in fields) + " |")
    if len(rows) > limit:
        lines.append(f"\n_Only showing first {limit} of {len(rows)} rows._")
    return "\n".join(lines)


def build_markdown(
    summaries: list[dict[str, str]],
    deltas: list[dict[str, str]],
    baseline_interval: int,
    candidate_interval: int,
) -> str:
    total_fail = sum(int(row["fail_count"]) for row in summaries)
    total_mismatch = sum(int(row["sha_mismatch_count"]) for row in summaries)
    failed_delta = [row for row in deltas if row["gate_pass"] != "yes"]
    candidate = "yes" if total_fail == 0 and total_mismatch == 0 and not failed_delta else "no"
    delta_fields = [
        "size_label",
        "direction",
        "checksum",
        "final_verify_policy",
        "connections",
        "throughput_baseline_median_gbps",
        "throughput_candidate_median_gbps",
        "throughput_delta_pct",
        "manifest_flush_baseline_median_s",
        "manifest_flush_candidate_median_s",
        "manifest_flush_reduction_pct",
        "gate_pass",
    ]
    summary_fields = [
        "size_label",
        "direction",
        "checksum",
        "final_verify_policy",
        "connections",
        "interval",
        "sample_count",
        "fail_count",
        "sha_mismatch_count",
        "throughput_median_gbps",
        "throughput_spread_pct",
        "manifest_flush_median_s",
        "manifest_serialize_median_s",
        "manifest_write_median_s",
    ]
    return "\n".join(
        [
            "# Lab Beta 2D Manifest Flush Stability Analysis",
            "",
            f"- Baseline interval: `{baseline_interval}`.",
            f"- Candidate interval: `{candidate_interval}`.",
            f"- Grouped rows: `{len(summaries)}`; matched deltas: `{len(deltas)}`.",
            f"- Total fail count: `{total_fail}`; total sha mismatch count: `{total_mismatch}`.",
            f"- Candidate gate pass: `{candidate}`.",
            "",
            "## 16 vs 256 Deltas",
            "",
            markdown_table(delta_fields, deltas),
            "",
            "## Grouped Summary",
            "",
            markdown_table(summary_fields, summaries),
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Lab Beta 2D manifest flush stability.")
    parser.add_argument("--csv", nargs="+", required=True, help="Combined raw CSV path(s).")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--prefix", default="lab-beta2d-manifest-flush-stability")
    parser.add_argument("--baseline-interval", type=int, default=16)
    parser.add_argument("--candidate-interval", type=int, default=256)
    parser.add_argument("--flush-reduction-threshold", type=float, default=0.80)
    parser.add_argument("--throughput-regression-threshold", type=float, default=0.05)
    parser.add_argument("--fail-on-gate-fail", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_rows([Path(path) for path in args.csv])
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[group_key(row, include_interval=True)].append(row)
    summaries = [summarize_group(items) for _, items in sorted(grouped.items())]
    deltas = compare_intervals(
        summaries,
        args.baseline_interval,
        args.candidate_interval,
        args.flush_reduction_threshold,
        args.throughput_regression_threshold,
    )

    total_fail = sum(int(row["fail_count"]) for row in summaries)
    total_mismatch = sum(int(row["sha_mismatch_count"]) for row in summaries)
    failed_delta = [row for row in deltas if row["gate_pass"] != "yes"]
    gate_pass = total_fail == 0 and total_mismatch == 0 and not failed_delta
    payload = {
        "input_csv": args.csv,
        "baseline_interval": args.baseline_interval,
        "candidate_interval": args.candidate_interval,
        "row_count": len(rows),
        "summary_group_count": len(summaries),
        "matched_delta_count": len(deltas),
        "total_fail_count": total_fail,
        "total_sha_mismatch_count": total_mismatch,
        "failed_delta_count": len(failed_delta),
        "gate_pass": gate_pass,
        "default_value_candidate": gate_pass,
        "summaries": summaries,
        "deltas": deltas,
    }

    summary_csv = output_dir / f"{args.prefix}-summary.csv"
    delta_csv = output_dir / f"{args.prefix}-deltas.csv"
    json_path = output_dir / f"{args.prefix}.json"
    markdown_path = output_dir / f"{args.prefix}.md"
    write_csv(summary_csv, SUMMARY_FIELDS, summaries)
    write_csv(delta_csv, DELTA_FIELDS, deltas)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(
        build_markdown(summaries, deltas, args.baseline_interval, args.candidate_interval),
        encoding="utf-8",
    )

    print(f"summary_csv={summary_csv}")
    print(f"delta_csv={delta_csv}")
    print(f"json={json_path}")
    print(f"markdown={markdown_path}")
    print(
        f"gate_pass={str(gate_pass).lower()} fail_count={total_fail} "
        f"sha_mismatch={total_mismatch} failed_delta_count={len(failed_delta)}"
    )
    if args.fail_on_gate_fail and not gate_pass:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
