#!/usr/bin/env python3
"""Lightweight tests for alpha release helper functions."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import check_remote_artifact_sync
import run_alpha_release_gate


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_source_tree_hash_excludes_private_and_build() -> None:
    with tempfile.TemporaryDirectory(prefix="gridflux-alpha-hash.") as temp:
        root = Path(temp)
        write(root / "src" / "main.cpp", "int main() { return 0; }\n")
        first = run_alpha_release_gate.source_tree_hash(root)
        write(root / "AGENTS.md", "private password\n")
        write(root / "build-private" / "artifact.txt", "binary-ish\n")
        write(root / "tools" / "perf" / "results" / "sample.csv", "secret\n")
        second = run_alpha_release_gate.source_tree_hash(root)
        if first != second:
            raise AssertionError("source tree hash included private/build/result files")


def test_csv_sidecar_extraction() -> None:
    with tempfile.TemporaryDirectory(prefix="gridflux-alpha-csv.") as temp:
        root = Path(temp)
        csv_path = root / "tools" / "perf" / "results" / "matrix.csv"
        csv_path.parent.mkdir(parents=True)
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["server_log", "client_env_before_log", "absolute_log", "result"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "server_log": "tools/perf/results/server.log",
                    "client_env_before_log": "tools/perf/results/client-env.log",
                    "absolute_log": str(root / "tools" / "perf" / "results" / "abs.log"),
                    "result": "pass",
                }
            )
        paths = check_remote_artifact_sync.paths_from_csv(csv_path, root)
        expected = {
            "tools/perf/results/matrix.csv",
            "tools/perf/results/server.log",
            "tools/perf/results/client-env.log",
            "tools/perf/results/abs.log",
        }
        if paths != expected:
            raise AssertionError(f"unexpected sidecar paths: {paths}")
        gate_paths = set(run_alpha_release_gate.csv_referenced_artifacts(str(csv_path), root))
        if gate_paths != expected:
            raise AssertionError(f"unexpected gate sidecar paths: {gate_paths}")


def test_matrix_summary_default_baseline() -> None:
    with tempfile.TemporaryDirectory(prefix="gridflux-alpha-summary.") as temp:
        summary = Path(temp) / "summary.csv"
        fields = [
            "file_io_backend",
            "file_io_buffer_size",
            "posix_write_strategy",
            "manifest_flush_policy",
            "manifest_flush_interval_chunks",
            "commit_sync_policy",
            "final_verify_policy",
            "checksum_algorithm",
            "fail_count",
            "direction",
            "throughput_gbps_median",
            "throughput_gbps_spread_pct",
        ]
        with summary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(
                {
                    "file_io_backend": "posix",
                    "file_io_buffer_size": "0",
                    "posix_write_strategy": "auto",
                    "manifest_flush_policy": "every_n_chunks",
                    "manifest_flush_interval_chunks": "16",
                    "commit_sync_policy": "none",
                    "final_verify_policy": "full",
                    "checksum_algorithm": "crc32c",
                    "fail_count": "0",
                    "direction": "stor",
                    "throughput_gbps_median": "1.0",
                    "throughput_gbps_spread_pct": "10.0",
                }
            )
        result = run_alpha_release_gate.parse_matrix_summary(summary)
        if result["status"] != "pass" or result["fail_count"] != 0:
            raise AssertionError(f"unexpected matrix summary status: {result}")
        baseline = result["default_baseline"]
        if not isinstance(baseline, list) or len(baseline) != 1:
            raise AssertionError(f"default baseline not detected: {result}")


def main() -> int:
    test_source_tree_hash_excludes_private_and_build()
    test_csv_sidecar_extraction()
    test_matrix_summary_default_baseline()
    print("alpha release helper tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
