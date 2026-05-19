#!/usr/bin/env python3
"""Lightweight tests for Beta 1B STOR writeback helpers."""

from __future__ import annotations

import argparse
import importlib.util
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


def runner_args() -> argparse.Namespace:
    return argparse.Namespace(
        remote="root@example",
        server_host="192.0.2.1",
        local_build_dir="/local/build",
        remote_build_dir="/remote/build",
        output_dir="tools/perf/results",
        case_timeout=900,
    )


def test_runner_command_dimensions() -> None:
    runner = load_module("tools/perf/run_beta1b_stor_writeback.py")
    specs = runner.matrix_step_specs(
        runner_args(),
        bytes_value="268435456",
        repeat=1,
        event_dir=Path("events"),
        storage_csv="storage.csv",
    )
    assert [spec.name for spec in specs] == [
        "stor_backend_connections",
        "stor_write_strategy_buffer",
        "stor_preallocate_manifest",
        "stor_final_verify_opt_in",
    ]
    commands = {spec.name: spec.command for spec in specs}
    assert "1,4,8" in commands["stor_backend_connections"]
    assert "posix,io_uring" in commands["stor_backend_connections"]
    assert "0,262144,1048576" in commands["stor_write_strategy_buffer"]
    assert "auto,direct,coalesced" in commands["stor_write_strategy_buffer"]
    assert "off,full" in commands["stor_preallocate_manifest"]
    assert "every_n_chunks,final_only" in commands["stor_preallocate_manifest"]
    assert "full,verified_chunks" in commands["stor_final_verify_opt_in"]


def test_matrix_skips_invalid_coalesced_zero() -> None:
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
        file_io_buffer_sizes="0,262144",
        file_io_queue_depths="1",
        file_io_batch_sizes="",
        file_io_advices="off",
        posix_write_strategies="auto,direct,coalesced",
        final_verify_policy="full",
        final_verify_policies="full",
        tls_modes="off",
        data_tls_modes="off",
        repeat=1,
    )
    cases = matrix.generate_cases(args)
    assert all(not (case.posix_write_strategy == "coalesced" and case.file_io_buffer_size == 0) for case in cases)
    assert any(case.posix_write_strategy == "coalesced" and case.file_io_buffer_size == 262144 for case in cases)


def test_env_sidecar_parser() -> None:
    matrix = load_module("tools/perf/run_gridftp_private_matrix.py")
    with tempfile.TemporaryDirectory() as temp_text:
        path = Path(temp_text) / "env.log"
        path.write_text(
            "section=meminfo\n"
            "Dirty:              12 kB\n"
            "Writeback:          34 kB\n"
            "Cached:             56 kB\n"
            "section=iostat\n"
            "iostat=unavailable\n",
            encoding="utf-8",
        )
        values = matrix.env_sidecar_meminfo(path)
        assert values == {"dirty_kb": "12", "writeback_kb": "34", "cached_kb": "56"}


def test_analyzer_fixture() -> None:
    analyzer = load_module("tools/perf/analyze_beta1b_stor_writeback.py")
    with tempfile.TemporaryDirectory() as temp_text:
        temp = Path(temp_text)
        storage = temp / "storage-summary.csv"
        storage.write_text(
            "side,operation,bytes,buffer_size,preallocate,file_io_backend,file_io_buffer_size,file_io_queue_depth,file_io_batch_size,file_io_advice,posix_write_strategy,posix_write_strategy_effective,case_count,pass_count,fail_count,throughput_gbps_median\n"
            "local,write,268435456,262144,off,posix,0,1,1,off,auto,direct,1,1,0,4.000000\n",
            encoding="utf-8",
        )
        matrix = temp / "matrix-summary.csv"
        matrix.write_text(
            "mode,direction,bytes,connections,chunk_size,buffer_size,checksum_algorithm,checksum_backend,preallocate,file_io_backend,file_io_buffer_size,file_io_queue_depth,file_io_batch_size,file_io_advice,posix_write_strategy,posix_write_strategy_effective,tls_mode,data_tls_mode,manifest_flush_policy,manifest_flush_interval_chunks,commit_sync_policy,final_verify_policy,final_verify_policy_effective,repeat_count,pass_count,fail_count,throughput_gbps_median,throughput_gbps_spread_pct,elapsed_median,receiver_temp_write_seconds_median,receiver_data_receive_seconds_median,receiver_manifest_flush_seconds_median,receiver_final_verify_seconds_median,receiver_rename_commit_seconds_median\n"
            "smoke,stor,268435456,4,4194304,262144,crc32c,hardware,off,posix,0,1,1,off,auto,direct,off,off,every_n_chunks,16,none,full,full,1,1,0,1.000000,0.000000,2.000000,1.600000,0.050000,0.100000,0.200000,0.010000\n",
            encoding="utf-8",
        )
        output = temp / "report.md"
        old_argv = sys.argv
        try:
            sys.argv = [
                "analyze_beta1b_stor_writeback.py",
                "--storage-summary-csv",
                str(storage),
                "--matrix-summary-csv",
                str(matrix),
                "--output",
                str(output),
            ]
            assert analyzer.main() == 0
        finally:
            sys.argv = old_argv
        report = output.read_text(encoding="utf-8")
        assert "Beta 1B STOR Writeback Diagnosis" in report
        assert "temp-write wall share" in report
        assert "Native Storage vs GridFlux STOR" in report
        assert "Beta 1B-3" in report


def main() -> int:
    test_runner_command_dimensions()
    test_matrix_skips_invalid_coalesced_zero()
    test_env_sidecar_parser()
    test_analyzer_fixture()
    print("beta1b stor writeback helper tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
