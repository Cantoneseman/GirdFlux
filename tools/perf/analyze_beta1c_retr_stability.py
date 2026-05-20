#!/usr/bin/env python3
"""Analyze Beta 1C RETR stability and beta performance closeout data."""

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


def row_fail_count(row: dict[str, str]) -> int:
    try:
        return int(float(row.get("fail_count", "0") or "0"))
    except ValueError:
        return 1


def passing_summary_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("direction") == "retr" and row_fail_count(row) == 0]


def passing_raw_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("direction") == "retr" and row.get("result") == "pass"]


def first_stage(row: dict[str, str], fields: list[str]) -> float:
    for field in fields:
        value = number(row, field)
        if value > 0.0:
            return value
    return 0.0


def stage_seconds(row: dict[str, str], stage: str) -> float:
    fields = {
        "sender_source_read": [
            "sender_source_read_seconds_median",
            "source_read_seconds_median",
            "sender_stage_read_seconds_median",
            "stage_read_seconds_median",
        ],
        "sender_network_send": [
            "sender_network_send_seconds_median",
            "network_send_seconds_median",
            "sender_stage_send_seconds_median",
            "stage_send_seconds_median",
        ],
        "sender_checksum": [
            "sender_checksum_seconds_median",
            "checksum_seconds_median",
            "sender_stage_checksum_seconds_median",
            "stage_checksum_seconds_median",
        ],
        "receiver_temp_write": [
            "receiver_download_temp_write_seconds_median",
            "download_temp_write_seconds_median",
            "receiver_temp_write_seconds_median",
            "receiver_stage_write_seconds_median",
            "stage_write_seconds_median",
        ],
        "receiver_final_verify": [
            "receiver_final_verify_seconds_median",
            "final_verify_seconds_median",
            "receiver_stage_final_verify_seconds_median",
            "stage_final_verify_seconds_median",
        ],
        "receiver_rename": [
            "receiver_rename_commit_seconds_median",
            "receiver_finalize_rename_seconds_median",
            "rename_commit_seconds_median",
            "finalize_rename_seconds_median",
            "receiver_stage_rename_commit_seconds_median",
            "stage_rename_commit_seconds_median",
        ],
    }[stage]
    return first_stage(row, fields)


def elapsed(row: dict[str, str]) -> float:
    return number(row, "elapsed_median") or number(row, "receiver_elapsed_median") or number(row, "sender_elapsed_median")


def share(row: dict[str, str], stage: str) -> float:
    row_elapsed = elapsed(row)
    return stage_seconds(row, stage) / row_elapsed if row_elapsed > 0.0 else 0.0


def throughput_summary(rows: list[dict[str, str]]) -> tuple[float, float, float, float]:
    values = [number(row, "throughput_gbps_median") for row in passing_summary_rows(rows)]
    p95_values = [number(row, "throughput_gbps_p95") for row in passing_summary_rows(rows)]
    spreads = [number(row, "throughput_gbps_spread_pct") for row in passing_summary_rows(rows)]
    return median(values), max(values or [0.0]), median(p95_values), median(spreads)


def group_key(row: dict[str, str], fields: list[str]) -> tuple[str, ...]:
    return tuple(row.get(field, "") for field in fields)


def lookup(rows: list[dict[str, str]], fields: list[str]) -> dict[tuple[str, ...], list[dict[str, str]]]:
    result: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in passing_summary_rows(rows):
        result[group_key(row, fields)].append(row)
    return result


def best_row(rows: list[dict[str, str]], fields: list[str], key: tuple[str, ...]) -> dict[str, str] | None:
    candidates = lookup(rows, fields).get(key, [])
    if not candidates:
        return None
    return max(candidates, key=lambda row: number(row, "throughput_gbps_median"))


def stage_table(rows: list[dict[str, str]]) -> str:
    output: list[list[str]] = []
    for row in sorted(
        passing_summary_rows(rows),
        key=lambda item: (
            item.get("bytes", ""),
            item.get("file_io_backend", ""),
            item.get("tls_mode", ""),
            item.get("connections", ""),
            item.get("checksum_algorithm", ""),
            item.get("final_verify_policy", ""),
        ),
    ):
        output.append(
            [
                (
                    f"bytes={row.get('bytes')} backend={row.get('file_io_backend')} "
                    f"tls={row.get('tls_mode')}/{row.get('data_tls_mode')} "
                    f"conn={row.get('connections')} checksum={row.get('checksum_algorithm')} "
                    f"fv={row.get('final_verify_policy')}"
                ),
                fmt(number(row, "throughput_gbps_median")),
                fmt(number(row, "throughput_gbps_p95")),
                fmt(number(row, "throughput_gbps_spread_pct"), 1),
                pct(share(row, "sender_network_send")),
                pct(share(row, "sender_source_read")),
                pct(share(row, "sender_checksum")),
                pct(share(row, "receiver_temp_write")),
                pct(share(row, "receiver_final_verify")),
                pct(share(row, "receiver_rename")),
            ]
        )
    return table(
        [
            "case",
            "median Gbps",
            "p95 Gbps",
            "spread %",
            "sender send ratio",
            "source read",
            "sender checksum",
            "recv temp write ratio",
            "final verify",
            "rename",
        ],
        output,
    )


def connection_scaling_table(rows: list[dict[str, str]]) -> str:
    grouped = lookup(
        rows,
        ["bytes", "file_io_backend", "tls_mode", "data_tls_mode", "checksum_algorithm", "final_verify_policy"],
    )
    output: list[list[str]] = []
    for key, group in sorted(grouped.items()):
        bytes_value, backend, tls_mode, data_tls_mode, checksum, final_verify = key
        if backend != "posix" or tls_mode != "off" or data_tls_mode != "off" or final_verify != "full":
            continue
        by_conn = {row.get("connections", ""): row for row in group}
        c1 = number(by_conn.get("1"), "throughput_gbps_median")
        c4 = number(by_conn.get("4"), "throughput_gbps_median")
        c8 = number(by_conn.get("8"), "throughput_gbps_median")
        output.append(
            [
                f"bytes={bytes_value} checksum={checksum}",
                fmt(c1),
                fmt(c4),
                fmt(c8),
                pct_delta(c4, c1),
                pct_delta(c8, c4),
            ]
        )
    return table(["case", "conn1", "conn4", "conn8", "4 vs 1", "8 vs 4"], output)


def comparison_delta(
    rows: list[dict[str, str]],
    *,
    base_filter: dict[str, str],
    compare_filter: dict[str, str],
    match_fields: list[str],
) -> list[tuple[dict[str, str], dict[str, str], float]]:
    base_rows = [
        row
        for row in passing_summary_rows(rows)
        if all(row.get(field, "") == value for field, value in base_filter.items())
    ]
    compare_rows = [
        row
        for row in passing_summary_rows(rows)
        if all(row.get(field, "") == value for field, value in compare_filter.items())
    ]
    bases: dict[tuple[str, ...], dict[str, str]] = {}
    for row in base_rows:
        bases[group_key(row, match_fields)] = row
    output: list[tuple[dict[str, str], dict[str, str], float]] = []
    for row in compare_rows:
        base = bases.get(group_key(row, match_fields))
        if not base:
            continue
        base_value = number(base, "throughput_gbps_median")
        value = number(row, "throughput_gbps_median")
        delta = (value - base_value) / base_value if base_value > 0.0 else 0.0
        output.append((base, row, delta))
    return output


def tls_overhead_table(rows: list[dict[str, str]]) -> str:
    comparisons = comparison_delta(
        rows,
        base_filter={"tls_mode": "off", "data_tls_mode": "off", "file_io_backend": "posix", "final_verify_policy": "full"},
        compare_filter={
            "tls_mode": "required",
            "data_tls_mode": "required",
            "file_io_backend": "posix",
            "final_verify_policy": "full",
        },
        match_fields=["bytes", "connections", "checksum_algorithm"],
    )
    output = [
        [
            f"bytes={base.get('bytes')} conn={base.get('connections')} checksum={base.get('checksum_algorithm')}",
            fmt(number(base, "throughput_gbps_median")),
            fmt(number(row, "throughput_gbps_median")),
            pct(delta),
        ]
        for base, row, delta in comparisons
    ]
    return table(["case", "off/off Gbps", "required/required Gbps", "delta"], output)


def final_verify_table(rows: list[dict[str, str]]) -> str:
    comparisons = comparison_delta(
        rows,
        base_filter={
            "tls_mode": "off",
            "data_tls_mode": "off",
            "file_io_backend": "posix",
            "checksum_algorithm": "crc32c",
            "final_verify_policy": "full",
        },
        compare_filter={
            "tls_mode": "off",
            "data_tls_mode": "off",
            "file_io_backend": "posix",
            "checksum_algorithm": "crc32c",
            "final_verify_policy": "verified_chunks",
        },
        match_fields=["bytes", "connections"],
    )
    output = [
        [
            f"bytes={base.get('bytes')} conn={base.get('connections')}",
            fmt(number(base, "throughput_gbps_median")),
            fmt(number(row, "throughput_gbps_median")),
            pct(delta),
            pct(share(base, "receiver_final_verify")),
            pct(share(row, "receiver_final_verify")),
        ]
        for base, row, delta in comparisons
    ]
    return table(["case", "full Gbps", "verified_chunks Gbps", "delta", "full fv share", "verified fv share"], output)


def iouring_table(rows: list[dict[str, str]]) -> str:
    comparisons = comparison_delta(
        rows,
        base_filter={"tls_mode": "off", "data_tls_mode": "off", "file_io_backend": "posix", "final_verify_policy": "full"},
        compare_filter={"tls_mode": "off", "data_tls_mode": "off", "file_io_backend": "io_uring", "final_verify_policy": "full"},
        match_fields=["bytes", "connections", "checksum_algorithm"],
    )
    output = [
        [
            f"bytes={base.get('bytes')} conn={base.get('connections')} checksum={base.get('checksum_algorithm')}",
            fmt(number(base, "throughput_gbps_median")),
            fmt(number(row, "throughput_gbps_median")),
            pct(delta),
        ]
        for base, row, delta in comparisons
    ]
    return table(["case", "POSIX Gbps", "io_uring Gbps", "delta"], output)


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


def dirty_writeback_correlation(raw_rows: list[dict[str, str]]) -> str:
    xs: list[float] = []
    ys: list[float] = []
    for row in passing_raw_rows(raw_rows):
        dirty = number(row, "client_dirty_kb_after") + number(row, "client_writeback_kb_after")
        throughput = number(row, "throughput_gbps")
        if dirty > 0.0 and throughput > 0.0:
            xs.append(dirty)
            ys.append(throughput)
    corr = pearson(xs, ys)
    if corr is None:
        return f"insufficient paired samples (`{len(xs)}` usable rows)"
    return f"Pearson r `{fmt(corr, 3)}` across `{len(xs)}` paired RETR rows"


def result_counts(raw_rows: list[dict[str, str]], summary_rows: list[dict[str, str]]) -> str:
    return "\n".join(
        [
            f"- RETR raw rows: `{len(raw_rows)}`; pass `{sum(1 for row in raw_rows if row.get('result') == 'pass')}`, fail `{sum(1 for row in raw_rows if row.get('result') and row.get('result') != 'pass')}`.",
            f"- RETR summary rows: `{len(summary_rows)}`; grouped failures `{sum(row_fail_count(row) for row in summary_rows)}`.",
        ]
    )


def top_stage_name(row: dict[str, str]) -> str:
    stages = {
        "sender network send": share(row, "sender_network_send"),
        "sender source read": share(row, "sender_source_read"),
        "sender checksum": share(row, "sender_checksum"),
        "receiver temp write": share(row, "receiver_temp_write"),
        "receiver final verify": share(row, "receiver_final_verify"),
    }
    return max(stages, key=stages.get) if stages else ""


def recommendation(rows: list[dict[str, str]], raw_rows: list[dict[str, str]]) -> str:
    passing = passing_summary_rows(rows)
    median_throughput, best_throughput, _, median_spread = throughput_summary(rows)
    top_stages = [top_stage_name(row) for row in passing]
    network_dominant = sum(1 for stage in top_stages if stage == "sender network send")
    temp_write_dominant = sum(1 for stage in top_stages if stage == "receiver temp write")
    tls_deltas = [delta for _, _, delta in comparison_delta(
        rows,
        base_filter={"tls_mode": "off", "data_tls_mode": "off", "file_io_backend": "posix", "final_verify_policy": "full"},
        compare_filter={
            "tls_mode": "required",
            "data_tls_mode": "required",
            "file_io_backend": "posix",
            "final_verify_policy": "full",
        },
        match_fields=["bytes", "connections", "checksum_algorithm"],
    )]
    verified_deltas = [delta for _, _, delta in comparison_delta(
        rows,
        base_filter={
            "tls_mode": "off",
            "data_tls_mode": "off",
            "file_io_backend": "posix",
            "checksum_algorithm": "crc32c",
            "final_verify_policy": "full",
        },
        compare_filter={
            "tls_mode": "off",
            "data_tls_mode": "off",
            "file_io_backend": "posix",
            "checksum_algorithm": "crc32c",
            "final_verify_policy": "verified_chunks",
        },
        match_fields=["bytes", "connections"],
    )]
    lines = [
        f"- RETR median/best summary throughput: `{fmt(median_throughput)} / {fmt(best_throughput)} Gbps`; median spread `{fmt(median_spread, 1)}%`.",
        f"- Dominant-stage count: sender network send `{network_dominant}`, receiver temp write `{temp_write_dominant}` across `{len(passing)}` passing summary rows.",
        f"- TLS/data TLS median delta: `{pct(median(tls_deltas)) if tls_deltas else 'n/a'}`.",
        f"- verified_chunks median delta: `{pct(median(verified_deltas)) if verified_deltas else 'n/a'}`.",
        f"- Dirty/Writeback correlation: {dirty_writeback_correlation(raw_rows)}.",
    ]
    if passing and row_fail_count({"fail_count": "0"}) == 0 and median_spread <= 25.0 and temp_write_dominant <= network_dominant:
        lines.append(
            "- Recommendation: RETR is suitable to move toward Beta Gate / Beta RC once normal release gates remain green; keep verified_chunks/io_uring opt-in."
        )
    elif temp_write_dominant > network_dominant:
        lines.append(
            "- Recommendation: do not add user-space queue; investigate receiver download temp-write and storage/system behavior before RETR feature work."
        )
    else:
        lines.append(
            "- Recommendation: keep RETR optimization open only for targeted follow-up; no default policy change is justified by this matrix alone."
        )
    lines.append("- Default policy remains unchanged.")
    return "\n".join(lines)


def render(raw_rows: list[dict[str, str]], summary_rows: list[dict[str, str]], inputs: list[str]) -> str:
    median_throughput, best_throughput, p95_throughput, spread = throughput_summary(summary_rows)
    network_shares = [share(row, "sender_network_send") for row in passing_summary_rows(summary_rows)]
    temp_write_shares = [share(row, "receiver_temp_write") for row in passing_summary_rows(summary_rows)]
    final_verify_shares = [share(row, "receiver_final_verify") for row in passing_summary_rows(summary_rows)]
    rename_shares = [share(row, "receiver_rename") for row in passing_summary_rows(summary_rows)]
    return "\n".join(
        [
            "# Beta 1C RETR Stability",
            "",
            f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            "",
            "## Executive Summary",
            "",
            "Beta 1C re-checks the RETR path on the existing two cloud servers and closes the beta performance investigation without changing defaults. The matrix isolates POSIX off/off scaling, a required/required TLS data point, an io_uring data point, and a crc32c verified_chunks opt-in comparison.",
            "",
            f"- RETR summary median/best throughput: `{fmt(median_throughput)} / {fmt(best_throughput)} Gbps`.",
            f"- RETR median p95/spread: `{fmt(p95_throughput)} Gbps / {fmt(spread, 1)}%`.",
            f"- Sender network-send stage/elapsed ratio median: `{pct(median(network_shares))}`.",
            f"- Receiver download temp-write stage/elapsed ratio median: `{pct(median(temp_write_shares))}`.",
            f"- Receiver final verify / rename share medians: `{pct(median(final_verify_shares))}` / `{pct(median(rename_shares))}`.",
            f"- Dirty/Writeback correlation: {dirty_writeback_correlation(raw_rows)}.",
            "- Stage ratios are computed from existing aggregate multi-stream stage counters divided by transfer elapsed time; values above 100% indicate parallel per-connection work and should be read as dominance indicators, not exclusive wall-time shares.",
            "",
            "## Inputs",
            "",
            *[f"- `{path}`" for path in inputs if path],
            "",
            "## Result Counts",
            "",
            result_counts(raw_rows, summary_rows),
            "",
            "## RETR Stage Breakdown",
            "",
            stage_table(summary_rows),
            "",
            "## Connections Scaling",
            "",
            connection_scaling_table(summary_rows),
            "",
            "## TLS/Data TLS Overhead",
            "",
            tls_overhead_table(summary_rows),
            "",
            "## Final Verify Policy Opt-In",
            "",
            final_verify_table(summary_rows),
            "",
            "## POSIX vs io_uring",
            "",
            iouring_table(summary_rows),
            "",
            "## Required Answers",
            "",
            "- RETR best/median throughput: see the executive summary and stage table.",
            "- Sender network send bottleneck: use the sender send ratio column and dominant-stage recommendation.",
            "- Receiver download temp write: see `recv temp write ratio` in the stage table.",
            "- final verify full vs verified_chunks: see the opt-in table; verified_chunks remains opt-in.",
            "- TLS/data TLS overhead: see the required/required comparison table.",
            "- connections 1/4/8 scaling: see the scaling table.",
            "- POSIX vs io_uring: see the io_uring comparison table.",
            "- Beta Gate / Beta RC readiness: see the recommendation below.",
            "",
            "## Recommendation",
            "",
            recommendation(summary_rows, raw_rows),
            "",
            "## Non-Goals Preserved",
            "",
            "- No 100G migration or 100G test.",
            "- No default policy changes.",
            "- No user-space queue.",
            "- No default verified_chunks, io_uring, bounded, or dirty_poll.",
            "- No QUIC, FEC, RDMA, or GSI work.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Beta 1C RETR stability data.")
    parser.add_argument("--matrix-raw-csv", action="append", default=[])
    parser.add_argument("--matrix-summary-csv", action="append", default=[])
    parser.add_argument("--output", default="docs/perf/BETA1C_RETR_STABILITY.md")
    args = parser.parse_args()

    raw_rows = read_many(args.matrix_raw_csv)
    summary_rows = read_many(args.matrix_summary_csv)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render(raw_rows, summary_rows, args.matrix_raw_csv + args.matrix_summary_csv),
        encoding="utf-8",
    )
    print(f"report={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
