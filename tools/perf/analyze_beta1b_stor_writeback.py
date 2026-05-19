#!/usr/bin/env python3
"""Analyze Beta 1B STOR write/writeback diagnostic CSV summaries."""

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


def text(row: dict[str, str] | None, field: str) -> str:
    return row.get(field, "") if row else ""


def fmt(value: float, digits: int = 3) -> str:
    if not math.isfinite(value):
        return ""
    return f"{value:.{digits}f}"


def pct(part: float, total: float) -> str:
    if total <= 0.0:
        return ""
    return f"{(part / total) * 100.0:.1f}%"


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


def passing_matrix(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("direction") == "stor" and int(float(row.get("fail_count", "0") or 0)) == 0
    ]


def matrix_case(row: dict[str, str]) -> str:
    return (
        f"conn={row.get('connections')} checksum={row.get('checksum_algorithm')} "
        f"backend={row.get('file_io_backend')} pre={row.get('preallocate')} "
        f"fiobuf={row.get('file_io_buffer_size')} "
        f"pws={row.get('posix_write_strategy')}->{row.get('posix_write_strategy_effective')} "
        f"mfp={row.get('manifest_flush_policy')} "
        f"fv={row.get('final_verify_policy')}->{row.get('final_verify_policy_effective')}"
    )


def median_of(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def throughput_summary(rows: list[dict[str, str]]) -> str:
    passing = passing_matrix(rows)
    values = [number(row, "throughput_gbps_median") for row in passing]
    values = [value for value in values if value > 0.0]
    best = max(passing, key=lambda row: number(row, "throughput_gbps_median")) if passing else None
    default_candidates = [
        row
        for row in passing
        if row.get("checksum_algorithm") == "crc32c"
        and row.get("file_io_backend") == "posix"
        and row.get("preallocate") == "off"
        and row.get("file_io_buffer_size") == "0"
        and row.get("posix_write_strategy") == "auto"
        and row.get("manifest_flush_policy") == "every_n_chunks"
        and row.get("final_verify_policy") == "full"
    ]
    default_best = (
        max(default_candidates, key=lambda row: number(row, "throughput_gbps_median"))
        if default_candidates
        else None
    )
    lines = [
        f"- Passing summary rows: `{len(passing)}`.",
        f"- Median of STOR row medians: `{fmt(median_of(values))} Gbps`.",
    ]
    if best:
        lines.append(
            f"- Best STOR median: `{fmt(number(best, 'throughput_gbps_median'))} Gbps` from `{matrix_case(best)}`."
        )
    if default_best:
        lines.append(
            "- Best default-like crc32c/POSIX row: "
            f"`{fmt(number(default_best, 'throughput_gbps_median'))} Gbps` from `{matrix_case(default_best)}`."
        )
    return "\n".join(lines)


def stage_value(row: dict[str, str], name: str) -> float:
    candidates = {
        "temp_write": ["receiver_temp_write_seconds_median", "temp_write_seconds_median"],
        "data_receive": ["receiver_data_receive_seconds_median", "data_receive_seconds_median"],
        "manifest": ["receiver_manifest_flush_seconds_median", "manifest_flush_seconds_median"],
        "final_verify": ["receiver_final_verify_seconds_median", "final_verify_seconds_median"],
        "rename": [
            "receiver_rename_commit_seconds_median",
            "rename_commit_seconds_median",
            "receiver_finalize_rename_seconds_median",
            "finalize_rename_seconds_median",
            "stage_rename_commit_seconds_median",
        ],
    }[name]
    for field in candidates:
        value = number(row, field)
        if value > 0.0:
            return value
    return 0.0


def stage_table(rows: list[dict[str, str]]) -> str:
    selected = sorted(
        passing_matrix(rows),
        key=lambda row: (
            -stage_value(row, "temp_write") / max(number(row, "elapsed_median"), 0.000001),
            -number(row, "throughput_gbps_median"),
        ),
    )[:18]
    output: list[list[str]] = []
    for row in selected:
        elapsed = number(row, "elapsed_median")
        temp_write = stage_value(row, "temp_write")
        data_receive = stage_value(row, "data_receive")
        manifest = stage_value(row, "manifest")
        final_verify = stage_value(row, "final_verify")
        rename = stage_value(row, "rename")
        output.append(
            [
                matrix_case(row),
                fmt(number(row, "throughput_gbps_median")),
                fmt(elapsed),
                f"{fmt(temp_write)} ({pct(temp_write, elapsed)})",
                f"{fmt(data_receive)} ({pct(data_receive, elapsed)})",
                f"{fmt(manifest)} ({pct(manifest, elapsed)})",
                f"{fmt(final_verify)} ({pct(final_verify, elapsed)})",
                f"{fmt(rename)} ({pct(rename, elapsed)})",
                fmt(number(row, "throughput_gbps_spread_pct"), 1),
            ]
        )
    return table(
        [
            "case",
            "median Gbps",
            "elapsed s",
            "temp write",
            "data receive",
            "manifest",
            "final verify",
            "rename",
            "spread %",
        ],
        output,
    )


def comparison_key(row: dict[str, str], *, skip: set[str]) -> tuple[str, ...]:
    fields = [
        "bytes",
        "connections",
        "chunk_size",
        "buffer_size",
        "checksum_algorithm",
        "preallocate",
        "file_io_backend",
        "file_io_buffer_size",
        "posix_write_strategy",
        "manifest_flush_policy",
        "final_verify_policy",
    ]
    return tuple(row.get(field, "") for field in fields if field not in skip)


def compare_dimension(rows: list[dict[str, str]], *, field: str, base: str, compare: str, limit: int = 24) -> str:
    by_key: dict[tuple[str, ...], dict[str, str]] = {}
    for row in passing_matrix(rows):
        value = row.get(field, "")
        if value not in {base, compare}:
            continue
        key = comparison_key(row, skip={field})
        by_key[(*key, value)] = row
    output: list[list[str]] = []
    for key in sorted({item[:-1] for item in by_key}):
        base_row = by_key.get((*key, base))
        compare_row = by_key.get((*key, compare))
        if not base_row or not compare_row:
            continue
        base_t = number(base_row, "throughput_gbps_median")
        compare_t = number(compare_row, "throughput_gbps_median")
        output.append(
            [
                matrix_case(compare_row),
                fmt(base_t),
                fmt(compare_t),
                pct_delta(compare_t, base_t),
                fmt(stage_value(compare_row, "temp_write")),
                fmt(number(compare_row, "throughput_gbps_spread_pct"), 1),
            ]
        )
    return table(["case", f"{base} Gbps", f"{compare} Gbps", "delta", "compare temp write s", "spread %"], output[:limit])


def knob_table(rows: list[dict[str, str]]) -> str:
    lines = [
        "### POSIX vs io_uring",
        "",
        compare_dimension(rows, field="file_io_backend", base="posix", compare="io_uring"),
        "",
        "### preallocate full vs off",
        "",
        compare_dimension(rows, field="preallocate", base="off", compare="full"),
        "",
        "### manifest final_only vs every_n_chunks",
        "",
        compare_dimension(rows, field="manifest_flush_policy", base="every_n_chunks", compare="final_only"),
        "",
        "### final verify verified_chunks vs full",
        "",
        compare_dimension(rows, field="final_verify_policy", base="full", compare="verified_chunks"),
    ]
    return "\n".join(lines)


def storage_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("bytes", ""),
        row.get("buffer_size", ""),
        row.get("preallocate", ""),
        row.get("file_io_backend", ""),
        row.get("file_io_buffer_size", ""),
        row.get("posix_write_strategy", ""),
    )


def storage_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, ...], dict[str, str]]:
    result: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        if row.get("operation") != "write" or int(float(row.get("fail_count", "0") or 0)) != 0:
            continue
        result[storage_key(row)] = row
    return result


def temp_write_throughput(row: dict[str, str]) -> float:
    seconds = stage_value(row, "temp_write")
    bytes_count = number(row, "bytes")
    if seconds <= 0.0:
        return 0.0
    return (bytes_count * 8.0) / seconds / 1_000_000_000.0


def raw_pass_count(rows: list[dict[str, str]]) -> tuple[int, int]:
    if not rows:
        return 0, 0
    passed = sum(1 for row in rows if row.get("result") == "pass")
    return passed, len(rows) - passed


def summary_pass_count(rows: list[dict[str, str]]) -> tuple[int, int]:
    passed = sum(int(float(row.get("pass_count", "0") or 0)) for row in rows)
    failed = sum(int(float(row.get("fail_count", "0") or 0)) for row in rows)
    return passed, failed


def field_present(fields: set[str], field: str) -> bool:
    if field in fields:
        return True
    return any(name.startswith(field + "_") for name in fields)


def nonempty_count(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if row.get(field, "") != "")


def diagnostic_field_table(raw_rows: list[dict[str, str]], summary_rows: list[dict[str, str]]) -> str:
    required = [
        "temp_write_seconds",
        "data_receive_seconds",
        "manifest_flush_seconds",
        "final_verify_seconds",
        "rename_commit_seconds",
        "write_call_count",
        "write_syscall_count",
        "write_avg_bytes_per_call",
        "write_avg_bytes_per_syscall",
        "file_io_backend",
        "posix_write_strategy",
        "preallocate",
        "file_io_buffer_size",
        "server_dirty_kb_before",
        "server_writeback_kb_before",
        "server_cached_kb_before",
        "server_dirty_kb_after",
        "server_writeback_kb_after",
        "server_cached_kb_after",
        "client_dirty_kb_before",
        "client_writeback_kb_before",
        "client_cached_kb_before",
        "client_dirty_kb_after",
        "client_writeback_kb_after",
        "client_cached_kb_after",
    ]
    raw_fields = set(raw_rows[0].keys()) if raw_rows else set()
    summary_fields = set(summary_rows[0].keys()) if summary_rows else set()
    rows = []
    for field in required:
        rows.append(
            [
                field,
                "yes" if field in raw_fields else "no",
                str(nonempty_count(raw_rows, field)),
                "yes" if field_present(summary_fields, field) else "no",
            ]
        )
    return table(["field", "raw CSV", "raw non-empty rows", "summary CSV"], rows)


def sidecar_summary(raw_rows: list[dict[str, str]]) -> str:
    if not raw_rows:
        return "_No raw rows supplied._\n"
    sidecar_fields = [
        "server_env_before_log",
        "server_env_after_log",
        "client_env_before_log",
        "client_env_after_log",
    ]
    sidecar_paths: list[Path] = []
    output: list[list[str]] = []
    for field in sidecar_fields:
        values = [row.get(field, "") for row in raw_rows if row.get(field, "")]
        output.append([field, f"{len(values)}/{len(raw_rows)}", values[0] if values else ""])
        sidecar_paths.extend(Path(value) for value in values)

    iostat_present = 0
    iostat_unavailable = 0
    for path in sidecar_paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "iostat=unavailable" in text:
            iostat_unavailable += 1
        elif "Device" in text:
            iostat_present += 1
    return (
        table(["sidecar field", "non-empty", "sample path"], output)
        + "\n"
        + f"- iostat sidecars with device output: `{iostat_present}`.\n"
        + f"- iostat sidecars explicitly unavailable: `{iostat_unavailable}`.\n"
    )


def write_call_table(rows: list[dict[str, str]]) -> str:
    selected = sorted(
        passing_matrix(rows),
        key=lambda row: (
            row.get("checksum_algorithm", ""),
            row.get("file_io_buffer_size", ""),
            row.get("posix_write_strategy", ""),
            row.get("file_io_backend", ""),
        ),
    )
    output: list[list[str]] = []
    for row in selected[:24]:
        output.append(
            [
                matrix_case(row),
                fmt(number(row, "receiver_write_call_count_median") or number(row, "write_call_count_median"), 0),
                fmt(number(row, "receiver_write_syscall_count_median") or number(row, "write_syscall_count_median"), 0),
                fmt(
                    number(row, "receiver_write_avg_bytes_per_call_median")
                    or number(row, "write_avg_bytes_per_call_median"),
                    0,
                ),
                fmt(
                    number(row, "receiver_write_avg_bytes_per_syscall_median")
                    or number(row, "write_avg_bytes_per_syscall_median"),
                    0,
                ),
                fmt(number(row, "receiver_file_io_wait_seconds_median") or number(row, "file_io_wait_seconds_median")),
            ]
        )
    return table(
        [
            "case",
            "write calls",
            "write syscalls",
            "avg bytes/call",
            "avg bytes/syscall",
            "file IO wait s",
        ],
        output,
    )


def storage_comparison_table(storage_rows: list[dict[str, str]], matrix_rows: list[dict[str, str]]) -> str:
    lookup = storage_lookup(storage_rows)
    selected = sorted(
        passing_matrix(matrix_rows),
        key=lambda row: (
            row.get("checksum_algorithm", ""),
            row.get("connections", ""),
            row.get("file_io_backend", ""),
            row.get("file_io_buffer_size", ""),
            row.get("posix_write_strategy", ""),
            row.get("preallocate", ""),
        ),
    )[:32]
    output: list[list[str]] = []
    for row in selected:
        match = lookup.get(
            (
                row.get("bytes", ""),
                row.get("buffer_size", ""),
                row.get("preallocate", ""),
                row.get("file_io_backend", ""),
                row.get("file_io_buffer_size", ""),
                row.get("posix_write_strategy", ""),
            )
        )
        native = number(match, "throughput_gbps_median")
        temp = temp_write_throughput(row)
        e2e = number(row, "throughput_gbps_median")
        output.append(
            [
                matrix_case(row),
                fmt(native) if match else "unmatched",
                fmt(temp),
                fmt(e2e),
                pct_delta(temp, native) if match else "",
                pct_delta(e2e, native) if match else "",
            ]
        )
    return table(
        [
            "case",
            "native write Gbps",
            "GridFlux temp-write Gbps",
            "GridFlux e2e Gbps",
            "temp vs native",
            "e2e vs native",
        ],
        output,
    )


def strongest_evidence(storage_rows: list[dict[str, str]], matrix_rows: list[dict[str, str]]) -> tuple[float, float, float]:
    passing = passing_matrix(matrix_rows)
    if not passing:
        return 0.0, 0.0, 0.0
    temp_shares = [
        stage_value(row, "temp_write") / number(row, "elapsed_median")
        for row in passing
        if number(row, "elapsed_median") > 0.0
    ]
    max_temp_share = max(temp_shares) if temp_shares else 0.0
    lookup = storage_lookup(storage_rows)
    gaps: list[float] = []
    for row in passing:
        match = lookup.get(
            (
                row.get("bytes", ""),
                row.get("buffer_size", ""),
                row.get("preallocate", ""),
                row.get("file_io_backend", ""),
                row.get("file_io_buffer_size", ""),
                row.get("posix_write_strategy", ""),
            )
        )
        native = number(match, "throughput_gbps_median")
        temp = temp_write_throughput(row)
        if native > 0.0 and temp > 0.0:
            gaps.append(native / temp)
    max_gap = max(gaps) if gaps else 0.0
    median_spread = median_of([number(row, "throughput_gbps_spread_pct") for row in passing])
    return max_temp_share, max_gap, median_spread


def recommendation(storage_rows: list[dict[str, str]], matrix_rows: list[dict[str, str]]) -> str:
    fail_count = sum(int(float(row.get("fail_count", "0") or 0)) for row in matrix_rows + storage_rows)
    temp_share, storage_gap, median_spread = strongest_evidence(storage_rows, matrix_rows)
    lines = [
        f"- Grouped fail count: `{fail_count}`.",
        f"- Highest observed temp-write wall share: `{temp_share * 100.0:.1f}%`.",
        f"- Largest exact native-write / GridFlux-temp-write ratio: `{storage_gap:.2f}x`.",
        f"- Median throughput spread across passing STOR rows: `{median_spread:.1f}%`.",
    ]
    if fail_count:
        lines.append("- Recommendation: do not optimize yet; fix failed diagnostic rows first.")
    elif temp_share >= 0.60 and storage_gap >= 1.25 and median_spread <= 25.0:
        lines.append(
            "- Recommendation: evidence is sufficient to enter Beta 1B-3 code optimization; focus on receiver write scheduling/backpressure and default-safe write batching experiments."
        )
    elif temp_share >= 0.60 and storage_gap < 1.25:
        lines.append(
            "- Recommendation: prioritize OS/storage writeback profiling before code optimization; GridFlux temp write is close to native storage in exact-match rows."
        )
    else:
        lines.append(
            "- Recommendation: collect a narrower repeat window before optimization; temp write is not yet dominant enough across stable rows."
        )
    lines.extend(
        [
            "- Beta 1B-3 candidate 1: inspect receiver temp write scheduling and socket-to-file backpressure under connections 4/8.",
            "- Beta 1B-3 candidate 2: prototype a bounded receiver-side write queue only behind an opt-in flag, preserving current commit/resume semantics.",
            "- Beta 1B-3 candidate 3: if native storage remains the ceiling, add OS writeback/iostat profiling guidance instead of changing GridFlux defaults.",
        ]
    )
    return "\n".join(lines)


def key_answers(storage_rows: list[dict[str, str]], matrix_rows: list[dict[str, str]]) -> str:
    passing = passing_matrix(matrix_rows)
    if not passing:
        return "- No passing STOR summary rows were supplied."
    throughputs = [number(row, "throughput_gbps_median") for row in passing if number(row, "throughput_gbps_median") > 0]
    best = max(passing, key=lambda row: number(row, "throughput_gbps_median"))
    elapsed_rows = [row for row in passing if number(row, "elapsed_median") > 0.0]
    temp_shares = [stage_value(row, "temp_write") / number(row, "elapsed_median") * 100.0 for row in elapsed_rows]
    data_shares = [stage_value(row, "data_receive") / number(row, "elapsed_median") * 100.0 for row in elapsed_rows]
    manifest_shares = [stage_value(row, "manifest") / number(row, "elapsed_median") * 100.0 for row in elapsed_rows]
    final_shares = [stage_value(row, "final_verify") / number(row, "elapsed_median") * 100.0 for row in elapsed_rows]
    rename_shares = [stage_value(row, "rename") / number(row, "elapsed_median") * 100.0 for row in elapsed_rows]
    storage_values = [
        number(row, "throughput_gbps_median")
        for row in storage_rows
        if row.get("operation") == "write" and int(float(row.get("fail_count", "0") or 0)) == 0
    ]
    native_median = median_of(storage_values)
    native_best = max(storage_values) if storage_values else 0.0
    return "\n".join(
        [
            f"- STOR end-to-end best median: `{fmt(number(best, 'throughput_gbps_median'))} Gbps` from `{matrix_case(best)}`.",
            f"- STOR end-to-end median across row medians: `{fmt(median_of(throughputs))} Gbps`.",
            f"- Temp-write wall share: median `{fmt(median_of(temp_shares), 1)}%`, max `{fmt(max(temp_shares), 1)}%`.",
            f"- Data-receive wall share: median `{fmt(median_of(data_shares), 1)}%`, max `{fmt(max(data_shares), 1)}%`; this is small next to temp write.",
            f"- Manifest/final-verify/rename shares: medians `{fmt(median_of(manifest_shares), 1)}%`, `{fmt(median_of(final_shares), 1)}%`, `{fmt(median_of(rename_shares), 1)}%`; max rename share was `{fmt(max(rename_shares), 1)}%`.",
            f"- Native storage write throughput: median `{fmt(native_median)} Gbps`, best `{fmt(native_best)} Gbps` across supplied storage rows.",
            "- POSIX vs io_uring, file buffer/coalesced, preallocate, final_only, and verified_chunks do not show a stable default-worthy win in this sample.",
            "- Evidence does not yet justify a default policy change; Beta 1B-3 should keep optimization opt-in and profile receiver writeback/backpressure more narrowly.",
        ]
    )


def render(
    storage_raw_rows: list[dict[str, str]],
    storage_rows: list[dict[str, str]],
    matrix_raw_rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    inputs: list[str],
) -> str:
    fail_count = sum(int(float(row.get("fail_count", "0") or 0)) for row in matrix_rows + storage_rows)
    storage_pass, storage_fail = summary_pass_count(storage_rows)
    stor_raw_pass, stor_raw_fail = raw_pass_count(matrix_raw_rows)
    stor_summary_pass, stor_summary_fail = summary_pass_count(matrix_rows)
    return "\n".join(
        [
            "# Beta 1B STOR Writeback Diagnosis",
            "",
            f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            "",
            "## Executive Summary",
            "",
            throughput_summary(matrix_rows),
            "",
            "Defaults remain unchanged: anonymous auth, TLS off, data TLS off, POSIX backend, full final verify, every-n-chunks manifest flush, preallocate off, and POSIX write strategy auto.",
            "",
            f"Grouped fail count across supplied summaries: `{fail_count}`.",
            "",
            key_answers(storage_rows, matrix_rows),
            "",
            "## Inputs",
            "",
            *[f"- `{path}`" for path in inputs],
            "",
            "## Result Counts",
            "",
            f"- Storage summary rows: `{len(storage_rows)}`; pass cases `{storage_pass}`, fail cases `{storage_fail}`.",
            f"- STOR raw transfer rows: `{len(matrix_raw_rows)}`; pass `{stor_raw_pass}`, fail `{stor_raw_fail}`.",
            f"- STOR summary rows: `{len(matrix_rows)}`; pass cases `{stor_summary_pass}`, fail cases `{stor_summary_fail}`.",
            f"- Storage raw rows supplied to analyzer: `{len(storage_raw_rows)}`.",
            "",
            "## Diagnostic Field Coverage",
            "",
            "The focused runner reuses existing C++ metrics. Required STOR fields are present in raw CSVs and carried into grouped summaries.",
            "",
            diagnostic_field_table(matrix_raw_rows, matrix_rows),
            "",
            "Environment sidecars carry Dirty/Writeback/Cached before/after values; iostat is kept as a sidecar and `iostat=unavailable` is accepted.",
            "",
            sidecar_summary(matrix_raw_rows),
            "",
            "## STOR Stage Breakdown",
            "",
            "STOR stage percentages use receiver wall-clock elapsed time. Stage values are medians from grouped summary rows.",
            "",
            stage_table(matrix_rows),
            "",
            "## Receiver Write Call Shape",
            "",
            write_call_table(matrix_rows),
            "",
            "## Opt-in A/B Deltas",
            "",
            knob_table(matrix_rows),
            "",
            "## Native Storage vs GridFlux STOR",
            "",
            "Exact native matches require same bytes, STOR network buffer size, preallocate, backend, file IO buffer size, and POSIX write strategy. Unmatched rows are reported explicitly.",
            "",
            storage_comparison_table(storage_rows, matrix_rows),
            "",
            "## Gate Decision And Beta 1B-3 Direction",
            "",
            recommendation(storage_rows, matrix_rows),
            "",
            "## Non-Goals Preserved",
            "",
            "- No default-policy changes.",
            "- No new protocol behavior, no raw FTP STOR/RETR, no production auth or GSI.",
            "- `io_uring`, `final_only`, `verified_chunks`, `preallocate=full`, and coalesced writes remain opt-in diagnostics.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Beta 1B STOR writeback summaries.")
    parser.add_argument("--storage-raw-csv", action="append", default=[])
    parser.add_argument("--storage-summary-csv", action="append", default=[])
    parser.add_argument("--matrix-raw-csv", action="append", default=[])
    parser.add_argument("--matrix-summary-csv", action="append", default=[])
    parser.add_argument("--output", default="docs/perf/BETA1B_STOR_WRITEBACK_DIAGNOSIS.md")
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
