#!/usr/bin/env python3
"""Lightweight Beta 1A helper tests that do not require SSH."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_module(relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def test_single_matrix_case_generation() -> None:
    matrix = load_module("tools/perf/run_gridftp_private_matrix.py")
    args = argparse.Namespace(
        smoke=True,
        directions="stor",
        bytes="1MiB",
        connections="1",
        chunk_sizes="1MiB",
        buffer_sizes="64KiB",
        checksums="crc32c",
        preallocates="off",
        manifest_flush_policy="every_n_chunks",
        manifest_flush_policies="every_n_chunks",
        manifest_flush_interval_chunks=16,
        manifest_flush_interval_chunks_list="16",
        commit_sync_policy="none",
        commit_sync_policies="none",
        file_io_backends="posix",
        file_io_buffer_sizes="0",
        file_io_queue_depths="1",
        file_io_batch_sizes="",
        file_io_advices="off",
        posix_write_strategies="auto",
        final_verify_policy="full",
        final_verify_policies="full",
        tls_modes="off,required",
        data_tls_modes="off,required",
        repeat=1,
    )
    cases = matrix.generate_cases(args)
    combos = {(case.tls_mode, case.data_tls_mode) for case in cases}
    assert ("off", "required") not in combos
    assert combos == {("off", "off"), ("required", "off"), ("required", "required")}


def test_event_error_counts() -> None:
    matrix = load_module("tools/perf/run_gridftp_private_matrix.py")
    with tempfile.TemporaryDirectory() as temp_text:
        path = Path(temp_text) / "events.jsonl"
        path.write_text(
            json.dumps({"result": "fail", "error_code": "data_tls_failed"}) + "\n"
            + json.dumps({"result": "fail", "error_code": "checksum_mismatch"}) + "\n",
            encoding="utf-8",
        )
        counts = json.loads(matrix.event_error_code_counts(path))
        assert counts == {"checksum_mismatch": 1, "data_tls_failed": 1}


def test_tree_matrix_case_generation() -> None:
    tree = load_module("tools/perf/run_gridftp_tree_private_matrix.py")
    args = argparse.Namespace(
        datasets="mixed",
        directions="upload",
        file_parallelisms="1",
        connections="2",
        checksums="crc32c",
        tls_modes="off,required",
        data_tls_modes="off,required",
        file_io_backends="posix,io_uring",
        file_io_queue_depths="1",
        file_io_batch_sizes="",
        resume=False,
        repeat=1,
    )
    cases = tree.build_cases(args)
    assert len(cases) == 6
    assert all(not (case.tls_mode == "off" and case.data_tls_mode == "required") for case in cases)
    assert {case.file_io_backend for case in cases} == {"posix", "io_uring"}


def test_analyzer_writes_report() -> None:
    analyzer = load_module("tools/perf/analyze_beta1a.py")
    with tempfile.TemporaryDirectory() as temp_text:
        temp = Path(temp_text)
        summary = temp / "single-summary.csv"
        summary.write_text(
            "mode,direction,bytes,connections,chunk_size,buffer_size,checksum_algorithm,checksum_backend,preallocate,file_io_backend,file_io_buffer_size,file_io_queue_depth,file_io_batch_size,file_io_advice,posix_write_strategy,posix_write_strategy_effective,tls_mode,data_tls_mode,manifest_flush_policy,manifest_flush_interval_chunks,commit_sync_policy,final_verify_policy,final_verify_policy_effective,repeat_count,pass_count,fail_count,throughput_gbps_median,throughput_gbps_spread_pct,elapsed_median,receiver_temp_write_seconds_median\n"
            "smoke,stor,1048576,1,1048576,65536,crc32c,hardware,off,posix,0,1,1,off,auto,direct,off,off,every_n_chunks,16,none,full,full,1,1,0,1.25,0,1.0,0.8\n",
            encoding="utf-8",
        )
        output = temp / "report.md"
        assert analyzer.main.__module__
        old_argv = sys.argv
        try:
            sys.argv = [
                "analyze_beta1a.py",
                "--single-summary-csv",
                str(summary),
                "--output",
                str(output),
            ]
            assert analyzer.main() == 0
        finally:
            sys.argv = old_argv
        text = output.read_text(encoding="utf-8")
        assert "Beta 1A 100G Readiness Diagnosis" in text
        assert "receiver temp write" in text


def main() -> int:
    test_single_matrix_case_generation()
    test_event_error_counts()
    test_tree_matrix_case_generation()
    test_analyzer_writes_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
