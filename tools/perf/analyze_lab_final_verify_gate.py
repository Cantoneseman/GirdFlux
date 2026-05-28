#!/usr/bin/env python3
"""Analyze Lab Beta final-verify gate CSV output."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path


PAIR_FIELDS = ("bytes", "direction", "checksum_algorithm", "connections")
POLICY_FIELDS = (
    "final_verify_policy_requested",
    "final_verify_policy_effective",
)


def parse_paths(values: list[str]) -> list[Path]:
    paths: list[Path] = []
    for value in values:
        for item in value.split(","):
            text = item.strip()
            if text:
                paths.append(Path(text))
    return paths


def read_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                row["_source_csv"] = str(path)
                rows.append(row)
    return rows


def to_float(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "") or 0.0)
    except ValueError:
        return 0.0


def median(rows: list[dict[str, str]], field: str) -> float:
    values = [to_float(row, field) for row in rows]
    return statistics.median(values) if values else 0.0


def hash_mismatch_count(rows: list[dict[str, str]]) -> int:
    mismatches = 0
    for row in rows:
        source = row.get("source_sha256", "")
        dest = row.get("dest_sha256", "")
        if source and dest and source != dest:
            mismatches += 1
    return mismatches


def group_key(row: dict[str, str], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(row.get(field, "") for field in fields)


def summarize_group(rows: list[dict[str, str]]) -> dict[str, object]:
    first = rows[0]
    return {
        "bytes": int(float(first.get("bytes", "0") or 0)),
        "direction": first.get("direction", ""),
        "checksum_algorithm": first.get("checksum_algorithm", ""),
        "connections": int(float(first.get("connections", "0") or 0)),
        "final_verify_policy_requested": first.get("final_verify_policy_requested", ""),
        "final_verify_policy_effective": first.get("final_verify_policy_effective", ""),
        "sample_count": len(rows),
        "pass_count": sum(1 for row in rows if row.get("result") == "pass"),
        "fail_count": sum(1 for row in rows if row.get("result") != "pass"),
        "sha_mismatch": hash_mismatch_count(rows),
        "throughput_gbps_median": median(rows, "throughput_gbps"),
        "elapsed_seconds_median": median(rows, "elapsed"),
        "final_verify_seconds_median": median(rows, "final_verify_seconds"),
        "bytes_final_verified_median": median(rows, "bytes_final_verified"),
        "bytes_checksummed_median": median(rows, "bytes_checksummed"),
        "manifest_flush_seconds_median": median(rows, "manifest_flush_seconds"),
    }


def build_summaries(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(group_key(row, PAIR_FIELDS + POLICY_FIELDS), []).append(row)
    return [summarize_group(group_rows) for group_rows in groups.values()]


def build_deltas(summaries: list[dict[str, object]]) -> list[dict[str, object]]:
    by_pair: dict[tuple[object, ...], dict[str, dict[str, object]]] = {}
    for summary in summaries:
        key = tuple(summary[field] for field in PAIR_FIELDS)
        by_pair.setdefault(key, {})[str(summary["final_verify_policy_requested"])] = summary

    deltas: list[dict[str, object]] = []
    for key, policies in by_pair.items():
        full = policies.get("full")
        verified = policies.get("verified_chunks")
        if not full or not verified:
            continue
        full_tput = float(full["throughput_gbps_median"])
        verified_tput = float(verified["throughput_gbps_median"])
        full_final = float(full["final_verify_seconds_median"])
        verified_final = float(verified["final_verify_seconds_median"])
        deltas.append(
            {
                "bytes": key[0],
                "direction": key[1],
                "checksum_algorithm": key[2],
                "connections": key[3],
                "full_throughput_gbps_median": full_tput,
                "verified_throughput_gbps_median": verified_tput,
                "throughput_delta_pct": ((verified_tput - full_tput) / full_tput * 100.0)
                if full_tput
                else 0.0,
                "full_final_verify_seconds_median": full_final,
                "verified_final_verify_seconds_median": verified_final,
                "final_verify_seconds_reduction": full_final - verified_final,
                "full_bytes_final_verified_median": full["bytes_final_verified_median"],
                "verified_bytes_final_verified_median": verified["bytes_final_verified_median"],
            }
        )
    return deltas


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Lab Beta final-verify gate CSVs.")
    parser.add_argument("--csv", action="append", required=True, help="CSV path or comma list")
    parser.add_argument("--output-dir", default="tools/perf/results/final-verify-analysis")
    parser.add_argument("--label", default="lab-final-verify-gate")
    args = parser.parse_args()

    rows = read_rows(parse_paths(args.csv))
    summaries = build_summaries(rows)
    deltas = build_deltas(summaries)
    fail_count = sum(1 for row in rows if row.get("result") != "pass")
    sha_mismatch = hash_mismatch_count(rows)
    policy_mismatch_count = sum(
        1
        for row in rows
        if row.get("final_verify_policy_requested", "")
        and row.get("final_verify_policy_effective", "")
        and row.get("checksum_algorithm") == "crc32c"
        and row.get("final_verify_policy_requested") != row.get("final_verify_policy_effective")
    )
    fallback_rows = [
        row
        for row in rows
        if row.get("final_verify_policy_requested") == "verified_chunks"
        and row.get("final_verify_policy_effective") == "full"
    ]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = output_dir / f"{args.label}-summary.csv"
    delta_csv = output_dir / f"{args.label}-deltas.csv"
    summary_json = output_dir / f"{args.label}.json"
    write_csv(summary_csv, summaries)
    write_csv(delta_csv, deltas)
    result = {
        "label": args.label,
        "row_count": len(rows),
        "summary_count": len(summaries),
        "matched_delta_count": len(deltas),
        "fail_count": fail_count,
        "sha_mismatch": sha_mismatch,
        "crc32c_policy_mismatch_count": policy_mismatch_count,
        "fallback_row_count": len(fallback_rows),
        "gate_pass": fail_count == 0 and sha_mismatch == 0 and policy_mismatch_count == 0,
        "summary_csv": str(summary_csv),
        "delta_csv": str(delta_csv),
        "summaries": summaries,
        "deltas": deltas,
    }
    summary_json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"summary_json={summary_json}")
    print(f"summary_csv={summary_csv}")
    print(f"delta_csv={delta_csv}")
    print(f"gate_pass={str(result['gate_pass']).lower()}")
    return 0 if result["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
