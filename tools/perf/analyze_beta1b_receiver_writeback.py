#!/usr/bin/env python3
"""Analyze Beta 1B-3 opt-in receiver writeback/backpressure focused runs."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import time
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


def table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_No data._\n"
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    output.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(output) + "\n"


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def passing_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("direction") == "stor" and int(float(row.get("fail_count", "0") or "0")) == 0
    ]


def raw_passing_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("direction") == "stor" and row.get("result") == "pass"]


def row_label(row: dict[str, str]) -> str:
    return (
        f"conn={row.get('connections')} checksum={row.get('checksum_algorithm')} "
        f"profile={row.get('receiver_write_profile')} "
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
    elapsed = number(row, "elapsed_median")
    if elapsed <= 0.0:
        elapsed = number(row, "receiver_elapsed_median")
    return temp_write_seconds(row) / elapsed if elapsed > 0.0 else 0.0


def data_receive_share(row: dict[str, str]) -> float:
    elapsed = number(row, "elapsed_median")
    data_receive = number(row, "receiver_data_receive_seconds_median") or number(
        row, "data_receive_seconds_median"
    )
    return data_receive / elapsed if elapsed > 0.0 else 0.0


def comparison_key(row: dict[str, str]) -> tuple[str, str]:
    return (row.get("connections", ""), row.get("checksum_algorithm", ""))


def is_baseline(row: dict[str, str]) -> bool:
    return (
        row.get("receiver_write_profile", "default") == "default"
        and row.get("receiver_max_pending_bytes", "0") in {"", "0", "0.000000"}
        and row.get("receiver_write_yield_policy", "none") == "none"
    )


def baseline_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    result: dict[tuple[str, str], dict[str, str]] = {}
    for row in passing_rows(rows):
        if is_baseline(row):
            result[comparison_key(row)] = row
    return result


def optin_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in passing_rows(rows) if not is_baseline(row)]


def compare_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    baselines = baseline_lookup(rows)
    comparisons: list[dict[str, object]] = []
    for row in optin_rows(rows):
        base = baselines.get(comparison_key(row))
        if not base:
            continue
        throughput = number(row, "throughput_gbps_median")
        baseline_throughput = number(base, "throughput_gbps_median")
        p95 = number(row, "throughput_gbps_p95")
        baseline_p95 = number(base, "throughput_gbps_p95")
        spread = number(row, "throughput_gbps_spread_pct")
        baseline_spread = number(base, "throughput_gbps_spread_pct")
        share = temp_share(row)
        baseline_share = temp_share(base)
        throughput_delta = (throughput - baseline_throughput) / baseline_throughput if baseline_throughput > 0 else 0.0
        temp_share_delta = share - baseline_share
        spread_delta = spread - baseline_spread
        comparisons.append(
            {
                "row": row,
                "baseline": base,
                "throughput_delta": throughput_delta,
                "temp_share_delta": temp_share_delta,
                "spread_delta": spread_delta,
                "p95_delta": (p95 - baseline_p95) / baseline_p95 if baseline_p95 > 0 else 0.0,
            }
        )
    return comparisons


def storage_write_median(rows: list[dict[str, str]]) -> float:
    values = [
        number(row, "throughput_gbps_median")
        for row in rows
        if row.get("operation") == "write" and int(float(row.get("fail_count", "0") or "0")) == 0
    ]
    return median([value for value in values if value > 0.0])


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
    for row in raw_passing_rows(raw_rows):
        dirty = number(row, "server_dirty_kb_after") + number(row, "server_writeback_kb_after")
        throughput = number(row, "throughput_gbps")
        if dirty > 0.0 and throughput > 0.0:
            xs.append(dirty)
            ys.append(throughput)
    corr = pearson(xs, ys)
    if corr is None:
        return f"insufficient paired Dirty/Writeback samples (`{len(xs)}` usable rows)", None
    return f"Pearson r `{fmt(corr, 3)}` across `{len(xs)}` raw rows", corr


def summary_counts(summary_rows: list[dict[str, str]], raw_rows: list[dict[str, str]]) -> str:
    summary_fail = sum(int(float(row.get("fail_count", "0") or "0")) for row in summary_rows)
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
    passing = passing_rows(summary_rows)
    comparisons = compare_rows(summary_rows)
    throughputs = [number(row, "throughput_gbps_median") for row in passing if number(row, "throughput_gbps_median") > 0.0]
    p95s = [number(row, "throughput_gbps_p95") for row in passing if number(row, "throughput_gbps_p95") > 0.0]
    spreads = [number(row, "throughput_gbps_spread_pct") for row in passing]
    shares = [temp_share(row) for row in passing if temp_share(row) > 0.0]
    data_shares = [data_receive_share(row) for row in passing if data_receive_share(row) > 0.0]
    best_temp_improvement = min(
        [float(item["temp_share_delta"]) for item in comparisons],
        default=0.0,
    )
    regressions = [
        item for item in comparisons if float(item["throughput_delta"]) < -0.05
    ]
    dirty_text, _ = dirty_writeback_correlation(raw_rows)
    native = storage_write_median(storage_rows)
    baseline_values = [
        number(row, "throughput_gbps_median") for row in passing if is_baseline(row)
    ]
    optin_values = [
        number(row, "throughput_gbps_median") for row in passing if not is_baseline(row)
    ]
    return "\n".join(
        [
            f"- Bounded profile temp-write wall-share best delta versus matched baseline: `{best_temp_improvement * 100.0:+.1f}` percentage points.",
            f"- STOR median throughput across all rows: `{fmt(median(throughputs))} Gbps`; p95 median `{fmt(median(p95s))} Gbps`; spread median `{fmt(median(spreads), 1)}%`.",
            f"- Baseline median throughput: `{fmt(median(baseline_values))} Gbps`; opt-in median throughput: `{fmt(median(optin_values))} Gbps`.",
            f"- Temp-write wall share median: `{pct(median(shares))}`; data-receive wall share median: `{pct(median(data_shares))}`.",
            f"- Throughput regressions beyond 5%: `{len(regressions)}` matched opt-in rows.",
            f"- Dirty/Writeback correlation: {dirty_text}.",
            f"- Native storage write median for aligned POSIX/default policy rows: `{fmt(native)} Gbps`.",
        ]
    )


def comparison_table(summary_rows: list[dict[str, str]]) -> str:
    rows: list[list[str]] = []
    for item in sorted(
        compare_rows(summary_rows),
        key=lambda entry: (
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
                row_label(row),
                fmt(number(baseline, "throughput_gbps_median")),
                fmt(number(row, "throughput_gbps_median")),
                pct_delta(number(row, "throughput_gbps_median"), number(baseline, "throughput_gbps_median")),
                pct(temp_share(baseline)),
                pct(temp_share(row)),
                f"{float(item['temp_share_delta']) * 100.0:+.1f} pp",
                fmt(number(baseline, "throughput_gbps_spread_pct"), 1),
                fmt(number(row, "throughput_gbps_spread_pct"), 1),
                fmt(number(row, "receiver_backpressure_count_median"), 0),
                fmt(number(row, "receiver_backpressure_seconds_median")),
                fmt(number(row, "receiver_write_yield_count_median"), 0),
            ]
        )
    return table(
        [
            "opt-in case",
            "base Gbps",
            "opt Gbps",
            "throughput delta",
            "base temp share",
            "opt temp share",
            "temp-share delta",
            "base spread %",
            "opt spread %",
            "backpressure count",
            "backpressure s",
            "yield count",
        ],
        rows,
    )


def config_coverage_table(summary_rows: list[dict[str, str]]) -> str:
    rows: list[list[str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in passing_rows(summary_rows):
        key = (
            row.get("receiver_write_profile", ""),
            row.get("receiver_max_pending_bytes", ""),
            row.get("receiver_write_yield_policy", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append([key[0], key[1], key[2]])
    return table(["receiver profile", "max pending bytes", "yield policy"], rows)


def recommendation(summary_rows: list[dict[str, str]]) -> str:
    fail_count = sum(int(float(row.get("fail_count", "0") or "0")) for row in summary_rows)
    comparisons = compare_rows(summary_rows)
    regressions = [item for item in comparisons if float(item["throughput_delta"]) < -0.05]
    stable_wins = [
        item
        for item in comparisons
        if float(item["throughput_delta"]) >= -0.05
        and (
            float(item["temp_share_delta"]) <= -0.05
            or float(item["spread_delta"]) <= -10.0
            or float(item["p95_delta"]) >= 0.05
        )
    ]
    lines = [
        f"- Grouped fail count: `{fail_count}`.",
        f"- Matched opt-in comparisons: `{len(comparisons)}`.",
        f"- Matched opt-in rows with >5% throughput regression: `{len(regressions)}`.",
        f"- Matched opt-in rows with temp-share/spread/p95 signal and no >5% regression: `{len(stable_wins)}`.",
    ]
    if fail_count:
        lines.append("- Recommendation: fix correctness failures before expanding the matrix.")
    elif stable_wins and len(regressions) <= max(1, len(comparisons) // 4):
        lines.append(
            "- Recommendation: keep bounded receiver writeback as opt-in and run a larger matrix; default remains unchanged."
        )
    elif regressions and not stable_wins:
        lines.append(
            "- Recommendation: keep the code behind opt-in only and do not expand yet; this sample shows regression risk without a clear benefit."
        )
    else:
        lines.append(
            "- Recommendation: keep the opt-in implementation for more evidence, but do not change defaults or promote to a larger matrix yet."
        )
    lines.append(
        "- Beta 1B-3 next step: compare only the best bounded budget/yield rows against the same storage bench window before considering a user-space queue experiment."
    )
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
            "# Beta 1B Receiver Writeback Opt-In",
            "",
            f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            "",
            "## Executive Summary",
            "",
            "Beta 1B-3 tests the drain-budget form of `receiver_write_profile=bounded`. The default remains unchanged: the default profile keeps the old receive/write path with no drain budget, no Dirty/Writeback polling, and no yield.",
            "",
            key_answers(storage_rows, matrix_rows, matrix_raw_rows),
            "",
            "## Inputs",
            "",
            *[f"- `{path}`" for path in inputs],
            "",
            "## Result Counts",
            "",
            summary_counts(matrix_rows, matrix_raw_rows),
            f"- Storage summary rows: `{len(storage_rows)}`; storage raw rows: `{len(storage_raw_rows)}`.",
            "",
            "## Opt-In Coverage",
            "",
            "The `dirty_poll` threshold is intentionally bound to `receiver_max_pending_bytes`; Beta 1B-3 does not add a separate Dirty/Writeback threshold flag.",
            "",
            config_coverage_table(matrix_rows),
            "",
            "## Matched Baseline Comparisons",
            "",
            "Each opt-in row is compared against the same connections/checksum baseline with `default + none + max_pending=0`.",
            "",
            comparison_table(matrix_rows),
            "",
            "## Required Answers",
            "",
            "- Bounded profile temp-write wall share: see the matched temp-share delta column; negative values are improvements.",
            "- STOR median / p95 / spread: reported in the executive summary and matched comparison table.",
            "- Throughput regression rule: any matched median throughput delta below `-5%` is counted as a regression.",
            "- Dirty/Writeback relation to throughput: Dirty+Writeback after-sidecar values are correlated with raw transfer throughput when enough paired samples exist.",
            "- Evidence for larger matrix: decided below from correctness, regression count, temp-share delta, spread delta, and p95 delta.",
            "",
            "## Gate Decision",
            "",
            recommendation(matrix_rows),
            "",
            "## Non-Goals Preserved",
            "",
            "- No default policy changes.",
            "- No independent user-space write queue or worker pool.",
            "- No frame, checksum, manifest, resume, final verify, TLS, or auth semantic changes.",
            "- `dirty_poll` remains opt-in and reuses `receiver_max_pending_bytes` as the Dirty+Writeback budget.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Beta 1B-3 receiver writeback opt-in summaries.")
    parser.add_argument("--storage-raw-csv", action="append", default=[])
    parser.add_argument("--storage-summary-csv", action="append", default=[])
    parser.add_argument("--matrix-raw-csv", action="append", default=[])
    parser.add_argument("--matrix-summary-csv", action="append", default=[])
    parser.add_argument("--output", default="docs/perf/BETA1B_RECEIVER_WRITEBACK_OPTIN.md")
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
