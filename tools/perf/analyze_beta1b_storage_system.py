#!/usr/bin/env python3
"""Analyze Beta 1B-5 storage/system writeback attribution data."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import time
from collections import defaultdict
from pathlib import Path


def read_csv(path_text: str) -> list[dict[str, str]]:
    if not path_text:
        return []
    path = Path(path_text)
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


def number(row: dict[str, str] | None, field: str) -> float:
    if not row:
        return 0.0
    try:
        value = float(row.get(field, "") or "0")
        return 0.0 if math.isnan(value) or math.isinf(value) else value
    except ValueError:
        return 0.0


def fmt(value: float, digits: int = 3) -> str:
    if not math.isfinite(value):
        return ""
    return f"{value:.{digits}f}"


def pct(value: float) -> str:
    if not math.isfinite(value):
        return ""
    return f"{value * 100.0:.1f}%"


def pct_delta(value: float, base: float) -> str:
    if base <= 0.0:
        return ""
    return f"{((value - base) / base) * 100.0:+.1f}%"


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_No data._\n"
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    output.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(output) + "\n"


def fail_count(row: dict[str, str]) -> int:
    try:
        return int(float(row.get("fail_count", "0") or "0"))
    except ValueError:
        return 1


def pass_count(row: dict[str, str]) -> int:
    try:
        return int(float(row.get("pass_count", "0") or "0"))
    except ValueError:
        return 0


def passing_probe_summary(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if pass_count(row) > 0 and fail_count(row) == 0]


def passing_stor_summary(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("direction") == "stor" and pass_count(row) > 0 and fail_count(row) == 0]


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
        ],
    }[stage]
    for field in fields:
        value = number(row, field)
        if value > 0.0:
            return value
    return 0.0


def temp_write_throughput(row: dict[str, str]) -> float:
    seconds = stage_value(row, "temp_write")
    bytes_count = number(row, "bytes")
    return (bytes_count * 8.0 / seconds) / 1_000_000_000.0 if seconds > 0.0 else 0.0


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    x_avg = statistics.mean(xs)
    y_avg = statistics.mean(ys)
    numerator = sum((x - x_avg) * (y - y_avg) for x, y in zip(xs, ys, strict=True))
    x_den = math.sqrt(sum((x - x_avg) ** 2 for x in xs))
    y_den = math.sqrt(sum((y - y_avg) ** 2 for y in ys))
    if x_den == 0.0 or y_den == 0.0:
        return None
    return numerator / (x_den * y_den)


def dirty_writeback_correlation(probe_raw: list[dict[str, str]], matrix_raw: list[dict[str, str]]) -> str:
    xs: list[float] = []
    ys: list[float] = []
    for row in probe_raw:
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
    corr = pearson(xs, ys)
    if corr is None:
        return f"insufficient paired samples (`{len(xs)}` usable rows)"
    return f"Pearson r `{fmt(corr, 3)}` across `{len(xs)}` paired rows"


def native_limits(rows: list[dict[str, str]]) -> tuple[float, float, float, float]:
    passing = [
        row
        for row in passing_probe_summary(rows)
        if row.get("method") == "gridflux_storage_bench" and row.get("file_io_backend") == "posix"
    ]
    writes = [number(row, "throughput_gbps_median") for row in passing if row.get("operation") == "write"]
    reads = [number(row, "throughput_gbps_median") for row in passing if row.get("operation") == "read"]
    return median(writes), max(writes or [0.0]), median(reads), max(reads or [0.0])


def stor_limits(rows: list[dict[str, str]]) -> tuple[float, float, float, float]:
    passing = passing_stor_summary(rows)
    e2e = [number(row, "throughput_gbps_median") for row in passing]
    temp = [temp_write_throughput(row) for row in passing if temp_write_throughput(row) > 0.0]
    shares = [
        stage_value(row, "temp_write") / number(row, "elapsed_median")
        for row in passing
        if number(row, "elapsed_median") > 0.0 and stage_value(row, "temp_write") > 0.0
    ]
    return median(e2e), max(e2e or [0.0]), median(temp), median(shares)


def mount_table(rows: list[dict[str, str]]) -> str:
    seen: dict[str, dict[str, str]] = {}
    for row in rows:
        if row.get("dir_label") not in seen and row.get("mount_target"):
            seen[row.get("dir_label", "")] = row
    output: list[list[str]] = []
    for label, row in sorted(seen.items()):
        output.append(
            [
                label,
                row.get("mount_source", ""),
                row.get("mount_target", ""),
                row.get("mount_fstype", ""),
                row.get("example_sidecar", ""),
            ]
        )
    labels = sorted(seen)
    same_tmp_target = ""
    if "tmp" in seen and "target_root" in seen:
        same_tmp_target = (
            "yes"
            if (
                seen["tmp"].get("mount_source") == seen["target_root"].get("mount_source")
                and seen["tmp"].get("mount_target") == seen["target_root"].get("mount_target")
            )
            else "no"
        )
        output.append(["/tmp vs target_root same mount?", same_tmp_target, "", "", ""])
    if "project_temp" in labels and "target_root" in labels:
        same_project_target = (
            "yes"
            if (
                seen["project_temp"].get("mount_source") == seen["target_root"].get("mount_source")
                and seen["project_temp"].get("mount_target") == seen["target_root"].get("mount_target")
            )
            else "no"
        )
        output.append(["project_temp vs target_root same mount?", same_project_target, "", "", ""])
    return table(["dir", "source", "target", "fstype", "sidecar"], output)


def compare_probe_dimension(rows: list[dict[str, str]], *, field: str, base: str, compare: str) -> list[dict[str, object]]:
    passing = [
        row
        for row in passing_probe_summary(rows)
        if row.get("method") == "gridflux_storage_bench" and row.get("operation") == "write"
    ]
    key_fields = [
        "dir_label",
        "operation",
        "bytes",
        "buffer_size",
        "preallocate",
        "file_io_backend",
        "file_io_buffer_size",
        "posix_write_strategy",
    ]
    key_fields = [name for name in key_fields if name != field]
    by_key: dict[tuple[str, ...], dict[str, str]] = {}
    for row in passing:
        key = tuple(row.get(name, "") for name in key_fields)
        by_key[key + (row.get(field, ""),)] = row
    output: list[dict[str, object]] = []
    for key in sorted({key[:-1] for key in by_key}):
        base_row = by_key.get(key + (base,))
        compare_row = by_key.get(key + (compare,))
        if not base_row or not compare_row:
            continue
        base_value = number(base_row, "throughput_gbps_median")
        compare_value = number(compare_row, "throughput_gbps_median")
        delta = (compare_value - base_value) / base_value if base_value > 0.0 else 0.0
        output.append({"base": base_row, "compare": compare_row, "delta": delta})
    return output


def dimension_table(rows: list[dict[str, str]]) -> str:
    output: list[list[str]] = []
    for name, field, base, compare in [
        ("preallocate full", "preallocate", "off", "full"),
        ("io_uring", "file_io_backend", "posix", "io_uring"),
    ]:
        comparisons = compare_probe_dimension(rows, field=field, base=base, compare=compare)
        deltas = [float(item["delta"]) for item in comparisons]
        wins = sum(1 for delta in deltas if delta >= 0.05)
        regressions = sum(1 for delta in deltas if delta <= -0.05)
        output.append(
            [
                name,
                str(len(comparisons)),
                str(wins),
                str(regressions),
                f"{median(deltas) * 100.0:+.1f}%" if deltas else "",
            ]
        )
    return table(["dimension", "matched rows", ">=5% wins", "<=-5% regressions", "median delta"], output)


def stage_table(rows: list[dict[str, str]]) -> str:
    output: list[list[str]] = []
    for row in sorted(
        passing_stor_summary(rows),
        key=lambda item: (item.get("tls_mode", ""), item.get("connections", ""), item.get("checksum_algorithm", "")),
    ):
        elapsed = number(row, "elapsed_median")
        temp = stage_value(row, "temp_write")
        data = stage_value(row, "data_receive")
        manifest = stage_value(row, "manifest")
        final_verify = stage_value(row, "final_verify")
        rename = stage_value(row, "rename")
        output.append(
            [
                f"bytes={row.get('bytes')} tls={row.get('tls_mode')}/{row.get('data_tls_mode')} conn={row.get('connections')} checksum={row.get('checksum_algorithm')}",
                fmt(number(row, "throughput_gbps_median")),
                fmt(temp_write_throughput(row)),
                f"{pct(temp / elapsed) if elapsed > 0 else ''}",
                f"{pct(data / elapsed) if elapsed > 0 else ''}",
                f"{pct(manifest / elapsed) if elapsed > 0 else ''}",
                f"{pct(final_verify / elapsed) if elapsed > 0 else ''}",
                f"{pct(rename / elapsed) if elapsed > 0 else ''}",
                fmt(number(row, "throughput_gbps_spread_pct"), 1),
            ]
        )
    return table(
        [
            "case",
            "e2e Gbps",
            "temp-write Gbps",
            "temp share",
            "data recv",
            "manifest",
            "final verify",
            "rename",
            "spread %",
        ],
        output,
    )


def native_vs_stor_table(probe_rows: list[dict[str, str]], stor_rows: list[dict[str, str]]) -> str:
    native_write_median, native_write_best, native_read_median, native_read_best = native_limits(probe_rows)
    stor_median, stor_best, temp_median, temp_share_median = stor_limits(stor_rows)
    rows = [
        ["native storage write median", fmt(native_write_median), "gridflux-storage-bench POSIX write"],
        ["native storage write best", fmt(native_write_best), "best POSIX write summary row"],
        ["native storage read median", fmt(native_read_median), "gridflux-storage-bench POSIX read"],
        ["native storage read best", fmt(native_read_best), "best POSIX read summary row"],
        ["GridFlux STOR e2e median", fmt(stor_median), "aligned STOR summary rows"],
        ["GridFlux STOR e2e best", fmt(stor_best), "aligned STOR summary rows"],
        ["GridFlux STOR temp-write median", fmt(temp_median), "bytes / receiver temp-write seconds"],
        ["Temp-write wall share median", pct(temp_share_median), "receiver temp-write / elapsed"],
    ]
    if native_write_median > 0.0 and temp_median > 0.0:
        rows.append(["temp-write vs native write", pct_delta(temp_median, native_write_median), "positive can reflect cache/writeback timing"])
    if temp_median > 0.0 and stor_median > 0.0:
        rows.append(["STOR e2e vs temp-write", pct_delta(stor_median, temp_median), "negative is non-write-path overhead plus overlap effects"])
    return table(["metric", "value", "note"], rows)


def result_counts(probe_raw: list[dict[str, str]], probe_summary: list[dict[str, str]], matrix_raw: list[dict[str, str]], matrix_summary: list[dict[str, str]]) -> str:
    return "\n".join(
        [
            f"- Probe raw rows: `{len(probe_raw)}`; pass `{sum(1 for row in probe_raw if row.get('result') == 'pass')}`, fail `{sum(1 for row in probe_raw if row.get('result') == 'fail')}`, unavailable `{sum(1 for row in probe_raw if row.get('result') == 'unavailable')}`.",
            f"- Probe summary rows: `{len(probe_summary)}`.",
            f"- STOR raw rows: `{len(matrix_raw)}`; pass `{sum(1 for row in matrix_raw if row.get('result') == 'pass')}`, fail `{sum(1 for row in matrix_raw if row.get('result') and row.get('result') != 'pass')}`.",
            f"- STOR summary rows: `{len(matrix_summary)}`; grouped failures `{sum(fail_count(row) for row in matrix_summary)}`.",
        ]
    )


def recommendation(probe_rows: list[dict[str, str]], stor_rows: list[dict[str, str]], probe_raw: list[dict[str, str]], matrix_raw: list[dict[str, str]]) -> str:
    native_write_median, native_write_best, _, _ = native_limits(probe_rows)
    stor_median, _, temp_median, temp_share_median = stor_limits(stor_rows)
    preallocate = compare_probe_dimension(probe_rows, field="preallocate", base="off", compare="full")
    iouring = compare_probe_dimension(probe_rows, field="file_io_backend", base="posix", compare="io_uring")
    pre_wins = sum(1 for item in preallocate if float(item["delta"]) >= 0.05)
    pre_regress = sum(1 for item in preallocate if float(item["delta"]) <= -0.05)
    io_wins = sum(1 for item in iouring if float(item["delta"]) >= 0.05)
    io_regress = sum(1 for item in iouring if float(item["delta"]) <= -0.05)
    lines = [
        f"- Native POSIX write median/best: `{fmt(native_write_median)} / {fmt(native_write_best)} Gbps`.",
        f"- GridFlux STOR e2e median: `{fmt(stor_median)} Gbps`; temp-write median: `{fmt(temp_median)} Gbps`; temp-write share median: `{pct(temp_share_median)}`.",
        f"- Preallocate matched wins/regressions: `{pre_wins}/{pre_regress}`.",
        f"- io_uring matched wins/regressions: `{io_wins}/{io_regress}`.",
        f"- Dirty/Writeback correlation: {dirty_writeback_correlation(probe_raw, matrix_raw)}.",
    ]
    if temp_share_median >= 0.5 and native_write_median > 0.0 and abs(temp_median - native_write_median) / native_write_median <= 0.35:
        lines.append(
            "- Recommendation: current STOR behavior is close enough to the observed native storage/writeback envelope that Beta should prioritize disk/filesystem/cloud-volume validation before user-space queue design."
        )
    elif temp_share_median >= 0.5 and native_write_median > 0.0 and temp_median < native_write_median * 0.65:
        lines.append(
            "- Recommendation: investigate GridFlux receiver temp-write path overhead with profile/perf before changing architecture; user-space queue remains premature."
        )
    else:
        lines.append(
            "- Recommendation: keep receiver bounded/dirty_poll opt-in only and continue storage/system attribution; do not change defaults."
        )
    lines.append("- Default policy remains unchanged.")
    return "\n".join(lines)


def render(
    probe_raw: list[dict[str, str]],
    probe_summary: list[dict[str, str]],
    matrix_raw: list[dict[str, str]],
    matrix_summary: list[dict[str, str]],
    inputs: list[str],
) -> str:
    native_write_median, native_write_best, native_read_median, native_read_best = native_limits(probe_summary)
    stor_median, stor_best, temp_median, temp_share_median = stor_limits(matrix_summary)
    return "\n".join(
        [
            "# Beta 1B Storage/System Writeback Attribution",
            "",
            f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            "",
            "## Executive Summary",
            "",
            "Beta 1B-5 attributes the STOR receiver write/writeback bottleneck against native GridFlux storage bench, optional fio, mount metadata, Linux Dirty/Writeback/Cached samples, and an aligned STOR matrix. Defaults remain unchanged and receiver writeback bounded/dirty_poll stays opt-in only.",
            "",
            f"- Native storage write median/best: `{fmt(native_write_median)} / {fmt(native_write_best)} Gbps`.",
            f"- Native storage read median/best: `{fmt(native_read_median)} / {fmt(native_read_best)} Gbps`.",
            f"- GridFlux STOR e2e median/best: `{fmt(stor_median)} / {fmt(stor_best)} Gbps`.",
            f"- GridFlux STOR temp-write median: `{fmt(temp_median)} Gbps`; temp-write wall share median `{pct(temp_share_median)}`.",
            f"- Dirty/Writeback correlation: {dirty_writeback_correlation(probe_raw, matrix_raw)}.",
            "",
            "## Inputs",
            "",
            *[f"- `{path}`" for path in inputs if path],
            "",
            "## Result Counts",
            "",
            result_counts(probe_raw, probe_summary, matrix_raw, matrix_summary),
            "",
            "## Native Storage vs GridFlux STOR",
            "",
            native_vs_stor_table(probe_summary, matrix_summary),
            "",
            "## Mount And Directory Attribution",
            "",
            mount_table(probe_summary),
            "",
            "## Storage Knob Stability",
            "",
            dimension_table(probe_summary),
            "",
            "## STOR Stage Attribution",
            "",
            stage_table(matrix_summary),
            "",
            "## Required Answers",
            "",
            "- Native storage write/read upper bound: see the native rows in the comparison table.",
            "- GridFlux temp-write vs native: see `temp-write vs native write`; positive values can occur when page cache timing makes native write and STOR temp-write windows differ.",
            "- STOR end-to-end vs temp-write: see `STOR e2e vs temp-write`; the stage table keeps final verify, manifest, and rename shares visible.",
            "- Dirty/Writeback explanation: use the correlation line plus per-case sidecars in the probe and matrix CSVs.",
            "- `/tmp` versus target root: see the mount table and same-mount rows.",
            "- Preallocate and POSIX/io_uring value: see the storage knob stability table.",
            "- Hardware/cloud ceiling: treat as likely only when native write/read and STOR temp-write converge and Dirty/Writeback remains strongly coupled to throughput.",
            "- User-space queue: not recommended unless GridFlux temp-write remains well below native storage after storage/system limits are ruled out.",
            "",
            "## Recommendation",
            "",
            recommendation(probe_summary, matrix_summary, probe_raw, matrix_raw),
            "",
            "## Non-Goals Preserved",
            "",
            "- No 100G migration or 100G test.",
            "- No default policy changes.",
            "- No independent user-space queue.",
            "- No default bounded/dirty_poll.",
            "- No QUIC, FEC, RDMA, or GSI work.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Beta 1B-5 storage/system attribution data.")
    parser.add_argument("--probe-raw-csv", action="append", default=[])
    parser.add_argument("--probe-summary-csv", action="append", default=[])
    parser.add_argument("--matrix-raw-csv", action="append", default=[])
    parser.add_argument("--matrix-summary-csv", action="append", default=[])
    parser.add_argument("--output", default="docs/perf/BETA1B_STORAGE_SYSTEM_ATTRIBUTION.md")
    args = parser.parse_args()

    probe_raw = read_many(args.probe_raw_csv)
    probe_summary = read_many(args.probe_summary_csv)
    matrix_raw = read_many(args.matrix_raw_csv)
    matrix_summary = read_many(args.matrix_summary_csv)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render(
            probe_raw,
            probe_summary,
            matrix_raw,
            matrix_summary,
            args.probe_raw_csv + args.probe_summary_csv + args.matrix_raw_csv + args.matrix_summary_csv,
        ),
        encoding="utf-8",
    )
    print(f"report={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
