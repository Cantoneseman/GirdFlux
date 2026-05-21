#!/usr/bin/env python3
"""Lightweight tests for beta release helper functions."""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import run_alpha_release_gate
import run_beta_release_candidate
import run_beta_freeze_check
import run_beta_release_gate


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_default_strategy_includes_receiver_defaults() -> None:
    defaults = run_beta_release_gate.default_strategy_summary()
    expected = {
        "auth-mode": "anonymous",
        "tls-mode": "off",
        "data-tls-mode": "off",
        "file_io_backend": "posix",
        "final_verify_policy": "full",
        "manifest_flush_policy": "every_n_chunks",
        "preallocate": "off",
        "posix_write_strategy": "auto",
        "receiver_write_profile": "default",
        "receiver_write_yield_policy": "none",
    }
    if defaults != expected:
        raise AssertionError(f"unexpected beta defaults: {defaults}")


def test_iouring_smoke_parser_requires_passed_line() -> None:
    passed_log = "1/1 Test #12: FileIoTest.IoUringContextReadWriteSmokeWhenAvailable ...   Passed 0.01 sec\n"
    skipped_log = "1/1 Test #12: FileIoTest.IoUringContextReadWriteSmokeWhenAvailable ...   Skipped 0.01 sec\n"
    if not run_beta_release_gate.parse_iouring_smoke_passed(passed_log):
        raise AssertionError("io_uring smoke pass was not detected")
    if run_beta_release_gate.parse_iouring_smoke_passed(skipped_log):
        raise AssertionError("io_uring skipped was accepted as passed")


def test_beta1c_smoke_summary_uses_runner_keys() -> None:
    summary = run_beta_release_gate.summarize_beta1c_smoke(
        {
            "retr_transfer_cases": 10,
            "retr_transfer_failures": 0,
            "grouped_fail_count": 0,
            "hash_mismatch_count": 0,
        }
    )
    if not summary["passed"] or summary["raw_pass"] != 10:
        raise AssertionError(f"unexpected beta1c smoke summary: {summary}")


def test_beta_artifact_collection_includes_beta_docs_and_sidecars() -> None:
    with tempfile.TemporaryDirectory(prefix="gridflux-beta-artifacts.") as temp:
        root = Path(temp)
        write(root / "INDEX.md", "index\n")
        write(root / "docs" / "ROADMAP.md", "roadmap\n")
        write(root / "docs" / "PROJECT_STATE.md", "state\n")
        write(root / "docs" / "perf" / "README.md", "perf\n")
        write(root / "docs" / "perf" / "BETA_PERFORMANCE_SUMMARY.md", "summary\n")
        write(root / "docs" / "release" / "BETA_RELEASE_GATE.md", "gate\n")
        write(root / "docs" / "release" / "BETA_LIMITATIONS.md", "limits\n")
        write(root / "docs" / "release" / "BETA_FREEZE.md", "freeze\n")
        write(root / "tools" / "release" / "run_beta_release_gate.py", "print('gate')\n")
        write(root / "tools" / "release" / "run_beta_freeze_check.py", "print('freeze')\n")
        write(root / "tools" / "test" / "run_beta_long_soak.py", "print('soak')\n")
        write(root / "tools" / "perf" / "plot_three_way_comparison.py", "print('plot')\n")
        csv_path = root / "tools" / "perf" / "results" / "beta1c.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["server_log", "event_log", "result"])
            writer.writeheader()
            writer.writerow(
                {
                    "server_log": "tools/perf/results/server.log",
                    "event_log": "tools/perf/results/events.jsonl",
                    "result": "pass",
                }
            )
        write(root / "tools" / "perf" / "results" / "server.log", "server\n")
        write(root / "tools" / "perf" / "results" / "events.jsonl", "{\"event\":\"ok\"}\n")
        gate_json = root / "tools" / "perf" / "results" / "gate.json"
        write(gate_json, "{}\n")
        paths = run_beta_release_gate.collect_beta_artifact_paths(
            root=root,
            gate_json=gate_json,
            gate_markdown=root / "docs" / "release" / "BETA_RELEASE_GATE.md",
            beta1c_raws=[str(csv_path)],
            beta1c_summaries=[],
        )
        for expected in {
            "docs/perf/BETA_PERFORMANCE_SUMMARY.md",
            "docs/release/BETA_LIMITATIONS.md",
            "docs/release/BETA_FREEZE.md",
            "tools/release/run_beta_release_gate.py",
            "tools/release/run_beta_freeze_check.py",
            "tools/test/run_beta_long_soak.py",
            "tools/perf/plot_three_way_comparison.py",
            "tools/perf/results/beta1c.csv",
            "tools/perf/results/server.log",
            "tools/perf/results/events.jsonl",
        }:
            if expected not in paths:
                raise AssertionError(f"missing beta artifact {expected}: {paths}")


def test_candidate_extracts_three_way_best_values() -> None:
    with tempfile.TemporaryDirectory(prefix="gridflux-beta-perf.") as temp:
        root = Path(temp)
        summary = root / "tools" / "perf" / "results" / "20260520T120942Z_ftp-gridftp-gridflux-summary.csv"
        summary.parent.mkdir(parents=True, exist_ok=True)
        with summary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "protocol",
                    "direction",
                    "size_bytes",
                    "parallelism",
                    "connections",
                    "checksum",
                    "median_Gbps",
                    "best_Gbps",
                    "sha256_mismatch_count",
                    "fail_count",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "protocol": "gridflux",
                    "direction": "retr",
                    "size_bytes": "1073741824",
                    "connections": "8",
                    "checksum": "none",
                    "median_Gbps": "5.0",
                    "best_Gbps": "5.5",
                    "sha256_mismatch_count": "0",
                    "fail_count": "0",
                }
            )
        perf = run_beta_release_candidate.extract_three_way_performance(root)
        best = perf["gridflux_1g_retr_best"]
        if not isinstance(best, dict) or best.get("best_Gbps") != 5.5:
            raise AssertionError(f"failed to extract three-way best: {perf}")


def test_candidate_parses_beta_gate_paths_and_summary() -> None:
    paths = run_beta_release_candidate.parse_gate_paths_from_log(
        "\n".join(
            [
                "beta_release_gate_report=/tmp/beta.md",
                "beta_release_gate_json=/tmp/beta.json",
                "beta_artifact_manifest=/tmp/beta-artifacts.json",
                "result=pass",
            ]
        )
    )
    if paths.get("beta_release_gate_json") != "/tmp/beta.json":
        raise AssertionError(f"gate paths not parsed: {paths}")
    steps = [
        run_alpha_release_gate.StepResult("one", "pass", 0, "one.log", 0.1),
        run_alpha_release_gate.StepResult("two", "fail", 1, "two.log", 0.2, "io_error"),
    ]
    summary = run_beta_release_candidate.summarize_steps(steps)
    if summary["passed"] or summary["failed_steps"] != 1:
        raise AssertionError(f"unexpected step summary: {summary}")


def test_candidate_soak_summary_and_require_soak_failure() -> None:
    with tempfile.TemporaryDirectory(prefix="gridflux-beta-soak-summary.") as temp:
        root = Path(temp)
        soak = root / "tools" / "perf" / "results" / "20260521T000000Z_beta-long-soak.json"
        write(
            soak,
            json.dumps(
                {
                    "result": "pass",
                    "profile": "standard",
                    "iterations": 2,
                    "pass_count": 18,
                    "fail_count": 0,
                }
            )
            + "\n",
        )
        summary = run_beta_release_candidate.summarize_beta_long_soak(soak)
        if not summary["passed"] or summary["profile"] != "standard":
            raise AssertionError(f"unexpected soak summary: {summary}")
        report = {"beta_release_gate": {"passed": True}, "beta_long_soak": {"passed": False}}
        finalized = run_beta_release_candidate.finalize_report(
            report=report,
            steps=[],
            require_remote_artifacts=False,
            require_soak=True,
        )
        if finalized["passed"] or "beta_long_soak" not in finalized["failures"]:
            raise AssertionError(f"require-soak did not fail: {finalized}")


def test_freeze_check_parses_artifact_verify_and_docs() -> None:
    payload = {"status": "pass", "missing": 0, "mismatch": 0, "failures": 0}
    if not run_beta_freeze_check.artifact_verify_pass(payload):
        raise AssertionError("artifact final verify pass was not accepted")
    bad = dict(payload)
    bad["mismatch"] = 1
    if run_beta_freeze_check.artifact_verify_pass(bad):
        raise AssertionError("artifact final verify mismatch was accepted")


def main() -> int:
    test_default_strategy_includes_receiver_defaults()
    test_iouring_smoke_parser_requires_passed_line()
    test_beta1c_smoke_summary_uses_runner_keys()
    test_beta_artifact_collection_includes_beta_docs_and_sidecars()
    test_candidate_extracts_three_way_best_values()
    test_candidate_parses_beta_gate_paths_and_summary()
    test_candidate_soak_summary_and_require_soak_failure()
    test_freeze_check_parses_artifact_verify_and_docs()
    print("beta release helper tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
