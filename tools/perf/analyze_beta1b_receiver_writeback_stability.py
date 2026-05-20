#!/usr/bin/env python3
"""Analyze Beta 1B-4 receiver writeback stability candidate runs."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import time
from collections import defaultdict
from pathlib import Path


MATCH_FIELDS = [
    "bytes",
    "file_io_backend",
    "connections",
    "checksum_algorithm",
    "tls_mode",
    "data_tls_mode",
    "preallocate",
    "file_io_buffer_size",
    "posix_write_strategy",
    "manifest_flush_policy",
    "manifest_flush_interval_chunks",
    "commit_sync_policy",
    "final_verify_policy",
]


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
    return [row for row in rows if row.get("direction") == "stor" and row_fail_count(row) == 0]


def passing_raw_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("direction") == "stor" and row.get("result") == "pass"]


def is_baseline(row: dict[str, str]) -> bool:
    return (
        row.get("receiver_write_profile", "default") == "default"
        and row.get("receiver_max_pending_bytes", "0") in {"", "0", "0.000000"}
        and row.get("receiver_write_yield_policy", "none") == "none"
    )


def match_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row.get(field, "") for field in MATCH_FIELDS)


def candidate_label(row: dict[str, str]) -> str:
    tls_pair = f"{row.get('tls_mode')}/{row.get('data_tls_mode')}"
    return (
        f"bytes={row.get('bytes')} backend={row.get('file_io_backend')} "
        f"tls={tls_pair} conn={row.get('connections')} "
        f"checksum={row.get('checksum_algorithm')} "
        f"budget={row.get('receiver_max_pending_bytes')} "
        f"yield={row.get('receiver_write_yield_policy')}"
    )


def temp_write_seconds(row: dict[str, str]) -> float:
    return (
        number(row, "receiver_temp_write_seconds_median")
        or number(row, "temp_write_seconds_median")
        or number(row, "stage_write_seconds_median")
    )


def temp_share(row: dict[str, str]) -> float:
    elapsed = number(row, "elapsed_median") or number(row, "receiver_elapsed_median")
    return temp_write_seconds(row) / elapsed if elapsed > 0.0 else 0.0


def data_receive_share(row: dict[str, str]) -> float:
    elapsed = number(row, "elapsed_median") or number(row, "receiver_elapsed_median")
    data_receive = number(row, "receiver_data_receive_seconds_median") or number(
        row, "data_receive_seconds_median"
    )
    return data_receive / elapsed if elapsed > 0.0 else 0.0


def baseline_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, ...], dict[str, str]]:
    result: dict[tuple[str, ...], dict[str, str]] = {}
    for row in passing_summary_rows(rows):
        if is_baseline(row):
            result[match_key(row)] = row
    return result


def compare_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    baselines = baseline_lookup(rows)
    comparisons: list[dict[str, object]] = []
    for row in passing_summary_rows(rows):
        if is_baseline(row):
            continue
        baseline = baselines.get(match_key(row))
        if not baseline:
            continue
        throughput = number(row, "throughput_gbps_median")
        base_throughput = number(baseline, "throughput_gbps_median")
        p95 = number(row, "throughput_gbps_p95")
        base_p95 = number(baseline, "throughput_gbps_p95")
        spread = number(row, "throughput_gbps_spread_pct")
        base_spread = number(baseline, "throughput_gbps_spread_pct")
        throughput_delta = (throughput - base_throughput) / base_throughput if base_throughput > 0.0 else 0.0
        p95_delta = (p95 - base_p95) / base_p95 if base_p95 > 0.0 else 0.0
        comparisons.append(
            {
                "row": row,
                "baseline": baseline,
                "throughput_delta": throughput_delta,
                "p95_delta": p95_delta,
                "spread_delta": spread - base_spread,
                "temp_share_delta": temp_share(row) - temp_share(baseline),
            }
        )
    return comparisons


def dirty_poll_pairs(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], dict[str, str]] = {}
    for row in passing_summary_rows(rows):
        if row.get("receiver_write_profile") != "bounded":
            continue
        key = match_key(row) + (row.get("receiver_max_pending_bytes", ""),)
        grouped[key + (row.get("receiver_write_yield_policy", ""),)] = row

    pairs: list[dict[str, object]] = []
    base_keys = sorted({key[:-1] for key in grouped})
    for key in base_keys:
        none_row = grouped.get(key + ("none",))
        dirty_row = grouped.get(key + ("dirty_poll",))
        if not none_row or not dirty_row:
            continue
        none_throughput = number(none_row, "throughput_gbps_median")
        dirty_throughput = number(dirty_row, "throughput_gbps_median")
        delta = (dirty_throughput - none_throughput) / none_throughput if none_throughput > 0.0 else 0.0
        pairs.append({"none": none_row, "dirty": dirty_row, "throughput_delta": delta})
    return pairs


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


def dirty_writeback_correlation(raw_rows: list[dict[str, str]]) -> tuple[str, float | None]:
    xs: list[float] = []
    ys: list[float] = []
    for row in passing_raw_rows(raw_rows):
        dirty = number(row, "server_dirty_kb_after") + number(row, "server_writeback_kb_after")
        throughput = number(row, "throughput_gbps")
        if dirty > 0.0 and throughput > 0.0:
            xs.append(dirty)
            ys.append(throughput)
    corr = pearson(xs, ys)
    if corr is None:
        return f"insufficient paired Dirty/Writeback samples (`{len(xs)}` usable rows)", None
    return f"Pearson r `{fmt(corr, 3)}` across `{len(xs)}` raw rows", corr


def storage_write_median(rows: list[dict[str, str]]) -> float:
    values = [
        number(row, "throughput_gbps_median")
        for row in rows
        if row.get("operation") == "write" and row_fail_count(row) == 0
    ]
    return median([value for value in values if value > 0.0])


def result_counts(summary_rows: list[dict[str, str]], raw_rows: list[dict[str, str]]) -> str:
    summary_fail = sum(row_fail_count(row) for row in summary_rows)
    raw_pass = sum(1 for row in raw_rows if row.get("result") == "pass")
    raw_fail = sum(1 for row in raw_rows if row.get("result") and row.get("result") != "pass")
    return "\n".join(
        [
            f"- STOR summary rows: `{len(summary_rows)}`; grouped failures `{summary_fail}`.",
            f"- STOR raw rows: `{len(raw_rows)}`; pass `{raw_pass}`, fail `{raw_fail}`.",
        ]
    )


def key_answers(
    storage_rows: list[dict[str, str]],
    summary_rows: list[dict[str, str]],
    raw_rows: list[dict[str, str]],
) -> str:
    passing = passing_summary_rows(summary_rows)
    comparisons = compare_rows(summary_rows)
    improvements = [item for item in comparisons if float(item["throughput_delta"]) >= 0.05]
    regressions = [item for item in comparisons if float(item["throughput_delta"]) <= -0.05]
    dirty_pairs = dirty_poll_pairs(summary_rows)
    dirty_improve = [item for item in dirty_pairs if float(item["throughput_delta"]) >= 0.05]
    dirty_regress = [item for item in dirty_pairs if float(item["throughput_delta"]) <= -0.05]
    tls_required = [
        item
        for item in comparisons
        if item["row"].get("tls_mode") == "required" and item["row"].get("data_tls_mode") == "required"
    ]
    tls_regress = [item for item in tls_required if float(item["throughput_delta"]) <= -0.05]
    throughputs = [number(row, "throughput_gbps_median") for row in passing if number(row, "throughput_gbps_median") > 0.0]
    p95s = [number(row, "throughput_gbps_p95") for row in passing if number(row, "throughput_gbps_p95") > 0.0]
    spreads = [number(row, "throughput_gbps_spread_pct") for row in passing]
    shares = [temp_share(row) for row in passing if temp_share(row) > 0.0]
    data_shares = [data_receive_share(row) for row in passing if data_receive_share(row) > 0.0]
    dirty_text, _ = dirty_writeback_correlation(raw_rows)
    native = storage_write_median(storage_rows)
    return "\n".join(
        [
            f"- STOR median throughput across summary rows: `{fmt(median(throughputs))} Gbps`; p95 median `{fmt(median(p95s))} Gbps`; spread median `{fmt(median(spreads), 1)}%`.",
            f"- Temp-write wall share median: `{pct(median(shares))}`; data-receive wall share median: `{pct(median(data_shares))}`.",
            f"- Matched bounded comparisons: `{len(comparisons)}`; improvements `>=5%`: `{len(improvements)}`; regressions `<=-5%`: `{len(regressions)}`.",
            f"- Dirty-poll matched pairs: `{len(dirty_pairs)}`; improvements `>=5%`: `{len(dirty_improve)}`; regressions `<=-5%`: `{len(dirty_regress)}`.",
            f"- TLS/data TLS required matched bounded rows: `{len(tls_required)}`; regressions `<=-5%`: `{len(tls_regress)}`.",
            f"- Dirty/Writeback correlation: {dirty_text}.",
            f"- Native storage write median for aligned receiver-side bench rows: `{fmt(native)} Gbps`.",
        ]
    )


def comparison_table(summary_rows: list[dict[str, str]]) -> str:
    rows: list[list[str]] = []
    for item in sorted(
        compare_rows(summary_rows),
        key=lambda entry: (
            entry["row"].get("bytes", ""),
            entry["row"].get("file_io_backend", ""),
            entry["row"].get("tls_mode", ""),
            entry["row"].get("connections", ""),
            entry["row"].get("checksum_algorithm", ""),
            entry["row"].get("receiver_max_pending_bytes", ""),
            entry["row"].get("receiver_write_yield_policy", ""),
        ),
    ):
        row = item["row"]
        baseline = item["baseline"]
        rows.append(
            [
                candidate_label(row),
                fmt(number(baseline, "throughput_gbps_median")),
                fmt(number(row, "throughput_gbps_median")),
                pct_delta(number(row, "throughput_gbps_median"), number(baseline, "throughput_gbps_median")),
                fmt(number(baseline, "throughput_gbps_p95")),
                fmt(number(row, "throughput_gbps_p95")),
                fmt(number(baseline, "throughput_gbps_spread_pct"), 1),
                fmt(number(row, "throughput_gbps_spread_pct"), 1),
                pct(temp_share(baseline)),
                pct(temp_share(row)),
                f"{float(item['temp_share_delta']) * 100.0:+.1f} pp",
                fmt(number(row, "receiver_backpressure_count_median"), 0),
                fmt(number(row, "receiver_backpressure_seconds_median")),
                fmt(number(row, "receiver_write_yield_count_median"), 0),
            ]
        )
    return table(
        [
            "bounded case",
            "base Gbps",
            "bounded Gbps",
            "median delta",
            "base p95",
            "bounded p95",
            "base spread %",
            "bounded spread %",
            "base temp share",
            "bounded temp share",
            "temp delta",
            "backpressure count",
            "backpressure s",
            "yield count",
        ],
        rows,
    )


def dirty_poll_table(summary_rows: list[dict[str, str]]) -> str:
    rows: list[list[str]] = []
    for item in sorted(
        dirty_poll_pairs(summary_rows),
        key=lambda entry: candidate_label(entry["dirty"]),
    ):
        none_row = item["none"]
        dirty_row = item["dirty"]
        rows.append(
            [
                candidate_label(dirty_row),
                fmt(number(none_row, "throughput_gbps_median")),
                fmt(number(dirty_row, "throughput_gbps_median")),
                pct_delta(number(dirty_row, "throughput_gbps_median"), number(none_row, "throughput_gbps_median")),
                fmt(number(none_row, "throughput_gbps_spread_pct"), 1),
                fmt(number(dirty_row, "throughput_gbps_spread_pct"), 1),
                fmt(number(dirty_row, "receiver_write_yield_count_median"), 0),
            ]
        )
    return table(
        [
            "dirty_poll case",
            "none Gbps",
            "dirty_poll Gbps",
            "delta",
            "none spread %",
            "dirty spread %",
            "yield count",
        ],
        rows,
    )


def aggregate_table(summary_rows: list[dict[str, str]]) -> str:
    comparisons = compare_rows(summary_rows)
    buckets: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for item in comparisons:
        row = item["row"]
        key = (
            row.get("file_io_backend", ""),
            f"{row.get('tls_mode')}/{row.get('data_tls_mode')}",
            row.get("receiver_max_pending_bytes", ""),
            row.get("receiver_write_yield_policy", ""),
        )
        buckets[key].append(item)
    rows: list[list[str]] = []
    for key, items in sorted(buckets.items()):
        deltas = [float(item["throughput_delta"]) for item in items]
        temp_deltas = [float(item["temp_share_delta"]) for item in items]
        regressions = sum(1 for delta in deltas if delta <= -0.05)
        improvements = sum(1 for delta in deltas if delta >= 0.05)
        rows.append(
            [
                key[0],
                key[1],
                key[2],
                key[3],
                str(len(items)),
                str(improvements),
                str(regressions),
                f"{median(deltas) * 100.0:+.1f}%",
                f"{median(temp_deltas) * 100.0:+.1f} pp",
            ]
        )
    return table(
        [
            "backend",
            "tls pair",
            "budget bytes",
            "yield policy",
            "matched rows",
            ">=5% wins",
            "<=-5% regressions",
            "median delta",
            "median temp-share delta",
        ],
        rows,
    )


def artifact_examples(raw_rows: list[dict[str, str]]) -> str:
    rows: list[list[str]] = []
    for row in passing_raw_rows(raw_rows)[:8]:
        rows.append(
            [
                row.get("event_log") or row.get("server_event_log", ""),
                row.get("server_env_before_log", ""),
                row.get("server_env_after_log", ""),
                row.get("server_iostat_log", "")
                or row.get("iostat_log", "")
                or (row.get("server_env_after_log", "") + "#section=iostat" if row.get("server_env_after_log") else ""),
            ]
        )
    return table(["event log", "server env before", "server env after", "iostat"], rows)


def recommendation(summary_rows: list[dict[str, str]]) -> str:
    fail_count = sum(row_fail_count(row) for row in summary_rows)
    comparisons = compare_rows(summary_rows)
    improvements = [item for item in comparisons if float(item["throughput_delta"]) >= 0.05]
    regressions = [item for item in comparisons if float(item["throughput_delta"]) <= -0.05]
    dirty_pairs = dirty_poll_pairs(summary_rows)
    dirty_improve = [item for item in dirty_pairs if float(item["throughput_delta"]) >= 0.05]
    dirty_regress = [item for item in dirty_pairs if float(item["throughput_delta"]) <= -0.05]
    tls_required = [
        item
        for item in comparisons
        if item["row"].get("tls_mode") == "required" and item["row"].get("data_tls_mode") == "required"
    ]
    tls_regress = [item for item in tls_required if float(item["throughput_delta"]) <= -0.05]
    lines = [
        f"- Grouped fail count: `{fail_count}`.",
        f"- Matched bounded comparisons: `{len(comparisons)}`.",
        f"- Median-throughput improvements `>=5%`: `{len(improvements)}`.",
        f"- Median-throughput regressions `<=-5%`: `{len(regressions)}`.",
        f"- Dirty-poll independent pairs: `{len(dirty_pairs)}`; wins `{len(dirty_improve)}`, regressions `{len(dirty_regress)}`.",
        f"- TLS/data TLS required bounded rows: `{len(tls_required)}`; regressions `{len(tls_regress)}`.",
    ]
    if fail_count:
        lines.append("- Recommendation: fix correctness failures before expanding performance experiments.")
    elif len(improvements) > len(regressions) and (
        not tls_required or len(tls_regress) <= len(tls_required) // 4
    ):
        lines.append(
            "- Recommendation: keep bounded receiver writeback opt-in and expand only the winning budget/yield rows before designing an independent user-space queue."
        )
    elif len(regressions) >= len(improvements):
        lines.append(
            "- Recommendation: keep bounded/dirty_poll opt-in only and shift near-term Beta work toward disk, filesystem, cloud volume, and OS writeback analysis."
        )
    else:
        lines.append(
            "- Recommendation: keep the opt-in code for evidence gathering; do not change defaults and do not start user-space queue design yet."
        )
    lines.append("- Default policy remains unchanged.")
    return "\n".join(lines)


def render(
    storage_raw_rows: list[dict[str, str]],
    storage_rows: list[dict[str, str]],
    matrix_raw_rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    inputs: list[str],
) -> str:
    return "\n".join(
        [
            "# Beta 1B Receiver Writeback Stability",
            "",
            f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            "",
            "## Executive Summary",
            "",
            "Beta 1B-4 expands the opt-in drain-budget receiver writeback candidate matrix. It does not change the receiver data path, defaults, frame format, checksum, manifest, resume, final verify, TLS, or auth semantics.",
            "",
            key_answers(storage_rows, matrix_rows, matrix_raw_rows),
            "",
            "## Inputs",
            "",
            *[f"- `{path}`" for path in inputs],
            "",
            "## Result Counts",
            "",
            result_counts(matrix_rows, matrix_raw_rows),
            f"- Storage summary rows: `{len(storage_rows)}`; storage raw rows: `{len(storage_raw_rows)}`.",
            "",
            "## Candidate Aggregate",
            "",
            "Wins and regressions use matched default-vs-bounded rows. `>= +5%` median throughput is an improvement; `<= -5%` is a regression.",
            "",
            aggregate_table(matrix_rows),
            "",
            "## Matched Default vs Bounded",
            "",
            "Each bounded row is matched against the same bytes/backend/connections/checksum/TLS pair and fixed storage policy with `receiver_write_profile=default`, budget `0`, and yield policy `none`.",
            "",
            comparison_table(matrix_rows),
            "",
            "## Dirty Poll Independent Value",
            "",
            "`dirty_poll` is compared with `none` for the same bounded budget and matched transfer dimensions. The Dirty+Writeback threshold remains tied to `receiver_max_pending_bytes`.",
            "",
            dirty_poll_table(matrix_rows),
            "",
            "## Dirty/Writeback And Artifacts",
            "",
            "Dirty, Writeback, and Cached values are read from the existing environment sidecars before and after each case. Event logs and iostat sidecars remain per-case artifacts.",
            "",
            artifact_examples(matrix_raw_rows),
            "",
            "## Required Answers",
            "",
            "- Stable improvements: see the aggregate table `>=5% wins` and the matched comparison table.",
            "- Stable regressions: see the aggregate table `<=-5% regressions` and matched median deltas.",
            "- Dirty-poll value: see the dirty_poll independent table; value requires wins without matching regressions.",
            "- TLS/data TLS impact: required/required rows are counted in the executive summary and gate decision.",
            "- User-space queue: only recommended if bounded wins clearly dominate regressions and TLS required/required does not net regress.",
            "- Storage/system direction: recommended when bounded regressions match or exceed wins.",
            "",
            "## Gate Decision",
            "",
            recommendation(matrix_rows),
            "",
            "## Non-Goals Preserved",
            "",
            "- No default policy changes.",
            "- No independent user-space write queue or worker pool.",
            "- No QUIC, FEC, RDMA, or GSI work.",
            "- No root-only OS tuning.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Beta 1B-4 receiver writeback stability summaries.")
    parser.add_argument("--storage-raw-csv", action="append", default=[])
    parser.add_argument("--storage-summary-csv", action="append", default=[])
    parser.add_argument("--matrix-raw-csv", action="append", default=[])
    parser.add_argument("--matrix-summary-csv", action="append", default=[])
    parser.add_argument("--output", default="docs/perf/BETA1B_RECEIVER_WRITEBACK_STABILITY.md")
    args = parser.parse_args()

    storage_raw_rows = read_many(args.storage_raw_csv)
    storage_rows = read_many(args.storage_summary_csv)
    matrix_raw_rows = read_many(args.matrix_raw_csv)
    matrix_rows = read_many(args.matrix_summary_csv)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render(
            storage_raw_rows,
            storage_rows,
            matrix_raw_rows,
            matrix_rows,
            args.storage_raw_csv + args.storage_summary_csv + args.matrix_raw_csv + args.matrix_summary_csv,
        ),
        encoding="utf-8",
    )
    print(f"report={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
