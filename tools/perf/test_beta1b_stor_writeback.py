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


def storage_system_args() -> argparse.Namespace:
    return argparse.Namespace(
        remote="root@example",
        server_host="192.0.2.1",
        local_build_dir="/local/build",
        remote_build_dir="/remote/build",
        output_dir="tools/perf/results",
        bytes="1073741824",
        bytes_list="",
        buffer_sizes="262144,1048576",
        repeat=3,
        case_timeout=900,
        probe_dirs="",
        skip_fio=False,
        skip_iouring_subset=False,
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


def test_receiver_writeback_runner_dimensions() -> None:
    runner = load_module("tools/perf/run_beta1b_stor_writeback.py")
    specs = runner.receiver_writeback_matrix_step_specs(
        runner_args(),
        bytes_value="268435456",
        repeat=1,
        event_dir=Path("events"),
        storage_csv="storage.csv",
    )
    assert [spec.name for spec in specs] == ["stor_receiver_writeback_optin"]
    command = specs[0].command
    assert "--directions" in command and "stor" in command
    assert "--file-io-backends" in command and "posix" in command
    assert "--connections" in command and "1,4,8" in command
    assert "--checksums" in command and "crc32c,none" in command
    assert "--receiver-write-profiles" in command and "default,bounded" in command
    assert "--receiver-max-pending-bytes-list" in command and "0,67108864,268435456" in command
    assert "--receiver-write-yield-policies" in command and "none,dirty_poll" in command


def flag_value(command: list[str], flag: str) -> str:
    index = command.index(flag)
    return command[index + 1]


def test_receiver_writeback_stability_runner_dimensions() -> None:
    runner = load_module("tools/perf/run_beta1b_stor_writeback.py")
    specs = runner.receiver_writeback_stability_matrix_step_specs(
        runner_args(),
        bytes_value="1073741824",
        repeat=3,
        event_dir=Path("events"),
        storage_csv="storage.csv",
    )
    assert [spec.name for spec in specs] == [
        "stor_receiver_writeback_stability_posix_off_1073741824",
        "stor_receiver_writeback_stability_posix_tls_1073741824",
        "stor_receiver_writeback_stability_iouring_off_1073741824",
    ]
    posix_off, posix_tls, iouring = [spec.command for spec in specs]
    assert flag_value(posix_off, "--bytes") == "1073741824"
    assert flag_value(posix_off, "--repeat") == "3"
    assert flag_value(posix_off, "--tls-modes") == "off"
    assert flag_value(posix_off, "--data-tls-modes") == "off"
    assert flag_value(posix_tls, "--tls-modes") == "required"
    assert flag_value(posix_tls, "--data-tls-modes") == "required"
    assert flag_value(posix_off, "--file-io-backends") == "posix"
    assert flag_value(posix_tls, "--file-io-backends") == "posix"
    assert flag_value(iouring, "--file-io-backends") == "io_uring"
    assert flag_value(iouring, "--connections") == "4"
    assert flag_value(iouring, "--checksums") == "crc32c"
    for command in [posix_off, posix_tls, iouring]:
        assert flag_value(command, "--receiver-write-profiles") == "default,bounded"
        assert flag_value(command, "--receiver-max-pending-bytes-list") == "0,67108864,268435456"
        assert flag_value(command, "--receiver-write-yield-policies") == "none,dirty_poll"


def test_storage_system_probe_defaults() -> None:
    runner = load_module("tools/perf/run_beta1b_storage_system_probe.py")
    args = storage_system_args()
    cases = runner.storage_system_probe_cases(args)
    assert {case.bytes_count for case in cases} == {1073741824}
    assert {"project_temp", "tmp", "target_root"}.issubset({case.dir_label for case in cases})
    assert any(
        case.method == "gridflux_storage_bench"
        and case.operation == "write"
        and case.file_io_backend == "posix"
        and case.preallocate == "full"
        for case in cases
    )
    assert any(case.method == "gridflux_storage_bench" and case.file_io_backend == "io_uring" for case in cases)
    assert any(case.method == "fio" and case.preallocate == "off" for case in cases)


def test_storage_system_probe_bytes_list_and_stor_commands() -> None:
    runner = load_module("tools/perf/run_beta1b_storage_system_probe.py")
    args = storage_system_args()
    args.bytes_list = "268435456,4294967296"
    cases = runner.storage_system_probe_cases(args)
    assert {case.bytes_count for case in cases} == {268435456, 4294967296}
    specs = runner.aligned_stor_step_specs(
        args,
        bytes_values=[1073741824],
        repeat=3,
        event_dir=Path("events"),
        storage_csv="probe.csv",
    )
    assert [spec.name for spec in specs] == [
        "stor_storage_system_posix_off_1073741824",
        "stor_storage_system_posix_tls_1073741824",
    ]
    off, tls = [spec.command for spec in specs]
    assert flag_value(off, "--directions") == "stor"
    assert flag_value(off, "--receiver-write-profiles") == "default"
    assert flag_value(off, "--receiver-write-yield-policies") == "none"
    assert flag_value(off, "--connections") == "1,4,8"
    assert flag_value(off, "--checksums") == "crc32c,none"
    assert flag_value(off, "--tls-modes") == "off"
    assert flag_value(off, "--data-tls-modes") == "off"
    assert flag_value(tls, "--connections") == "4"
    assert flag_value(tls, "--checksums") == "crc32c"
    assert flag_value(tls, "--tls-modes") == "required"
    assert flag_value(tls, "--data-tls-modes") == "required"
    assert "--run-root-base" in off


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
        receiver_write_profiles="default,bounded",
        receiver_max_pending_bytes_list="0,67108864",
        receiver_write_yield_policies="none,dirty_poll",
        final_verify_policy="full",
        final_verify_policies="full",
        tls_modes="off",
        data_tls_modes="off",
        repeat=1,
    )
    cases = matrix.generate_cases(args)
    assert all(not (case.posix_write_strategy == "coalesced" and case.file_io_buffer_size == 0) for case in cases)
    assert any(case.posix_write_strategy == "coalesced" and case.file_io_buffer_size == 262144 for case in cases)
    assert any(
        case.receiver_write_profile == "bounded"
        and case.receiver_max_pending_bytes == 67108864
        and case.receiver_write_yield_policy == "dirty_poll"
        for case in cases
    )
    assert all(
        not (
            case.receiver_write_profile == "default"
            and (case.receiver_max_pending_bytes != 0 or case.receiver_write_yield_policy != "none")
        )
        for case in cases
    )


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


def test_receiver_writeback_analyzer_fixture() -> None:
    analyzer = load_module("tools/perf/analyze_beta1b_receiver_writeback.py")
    with tempfile.TemporaryDirectory() as temp_text:
        temp = Path(temp_text)
        storage = temp / "storage-summary.csv"
        storage.write_text(
            "side,operation,bytes,buffer_size,preallocate,file_io_backend,file_io_buffer_size,file_io_queue_depth,file_io_batch_size,file_io_advice,posix_write_strategy,posix_write_strategy_effective,case_count,pass_count,fail_count,throughput_gbps_median\n"
            "local,write,268435456,262144,off,posix,0,1,1,off,auto,direct,1,1,0,2.000000\n",
            encoding="utf-8",
        )
        raw = temp / "matrix.csv"
        raw.write_text(
            "direction,result,throughput_gbps,receiver_write_profile,receiver_max_pending_bytes,receiver_write_yield_policy,server_dirty_kb_after,server_writeback_kb_after\n"
            "stor,pass,1.000000,default,0,none,1000,0\n"
            "stor,pass,1.050000,bounded,67108864,dirty_poll,2000,4\n",
            encoding="utf-8",
        )
        summary = temp / "matrix-summary.csv"
        summary.write_text(
            "mode,direction,bytes,connections,chunk_size,buffer_size,checksum_algorithm,checksum_backend,preallocate,file_io_backend,file_io_buffer_size,file_io_queue_depth,file_io_batch_size,file_io_advice,posix_write_strategy,posix_write_strategy_effective,receiver_write_profile,receiver_max_pending_bytes,receiver_write_yield_policy,tls_mode,data_tls_mode,manifest_flush_policy,manifest_flush_interval_chunks,commit_sync_policy,final_verify_policy,final_verify_policy_effective,repeat_count,pass_count,fail_count,throughput_gbps_median,throughput_gbps_p95,throughput_gbps_spread_pct,elapsed_median,receiver_temp_write_seconds_median,receiver_data_receive_seconds_median,receiver_backpressure_count_median,receiver_backpressure_seconds_median,receiver_write_yield_count_median\n"
            "smoke,stor,268435456,4,4194304,262144,crc32c,auto,off,posix,0,1,1,off,auto,direct,default,0,none,off,off,every_n_chunks,16,none,full,full,1,1,0,1.000000,1.000000,10.000000,2.000000,1.600000,0.050000,0,0,0\n"
            "smoke,stor,268435456,4,4194304,262144,crc32c,auto,off,posix,0,1,1,off,auto,direct,bounded,67108864,dirty_poll,off,off,every_n_chunks,16,none,full,full,1,1,0,1.050000,1.050000,8.000000,2.000000,1.400000,0.050000,4,0.004,1\n",
            encoding="utf-8",
        )
        output = temp / "report.md"
        old_argv = sys.argv
        try:
            sys.argv = [
                "analyze_beta1b_receiver_writeback.py",
                "--storage-summary-csv",
                str(storage),
                "--matrix-raw-csv",
                str(raw),
                "--matrix-summary-csv",
                str(summary),
                "--output",
                str(output),
            ]
            assert analyzer.main() == 0
        finally:
            sys.argv = old_argv
        report = output.read_text(encoding="utf-8")
        assert "Beta 1B Receiver Writeback Opt-In" in report
        assert "Bounded profile temp-write wall-share" in report
        assert "Dirty/Writeback correlation" in report
        assert "default remains unchanged" in report


def test_receiver_writeback_stability_analyzer_fixture() -> None:
    analyzer = load_module("tools/perf/analyze_beta1b_receiver_writeback_stability.py")
    with tempfile.TemporaryDirectory() as temp_text:
        temp = Path(temp_text)
        storage = temp / "storage-summary.csv"
        storage.write_text(
            "side,operation,bytes,buffer_size,preallocate,file_io_backend,file_io_buffer_size,file_io_queue_depth,file_io_batch_size,file_io_advice,posix_write_strategy,posix_write_strategy_effective,case_count,pass_count,fail_count,throughput_gbps_median\n"
            "local,write,1073741824,262144,off,posix,0,1,1,off,auto,direct,3,3,0,2.000000\n",
            encoding="utf-8",
        )
        raw = temp / "matrix.csv"
        raw.write_text(
            "direction,result,throughput_gbps,receiver_write_profile,receiver_max_pending_bytes,receiver_write_yield_policy,server_dirty_kb_after,server_writeback_kb_after,event_log,server_env_before_log,server_env_after_log\n"
            "stor,pass,1.000000,default,0,none,1000,0,event-default.jsonl,before.log,after.log\n"
            "stor,pass,1.100000,bounded,67108864,none,2000,4,event-bounded.jsonl,before.log,after.log\n"
            "stor,pass,0.900000,bounded,67108864,dirty_poll,3000,8,event-dirty.jsonl,before.log,after.log\n",
            encoding="utf-8",
        )
        summary = temp / "matrix-summary.csv"
        summary.write_text(
            "mode,direction,bytes,connections,chunk_size,buffer_size,checksum_algorithm,checksum_backend,preallocate,file_io_backend,file_io_buffer_size,file_io_queue_depth,file_io_batch_size,file_io_advice,posix_write_strategy,posix_write_strategy_effective,receiver_write_profile,receiver_max_pending_bytes,receiver_write_yield_policy,tls_mode,data_tls_mode,manifest_flush_policy,manifest_flush_interval_chunks,commit_sync_policy,final_verify_policy,final_verify_policy_effective,repeat_count,pass_count,fail_count,throughput_gbps_median,throughput_gbps_p95,throughput_gbps_spread_pct,elapsed_median,receiver_temp_write_seconds_median,receiver_data_receive_seconds_median,receiver_backpressure_count_median,receiver_backpressure_seconds_median,receiver_write_yield_count_median\n"
            "smoke,stor,1073741824,4,4194304,262144,crc32c,auto,off,posix,0,1,1,off,auto,direct,default,0,none,off,off,every_n_chunks,16,none,full,full,3,3,0,1.000000,1.000000,10.000000,2.000000,1.600000,0.050000,0,0,0\n"
            "smoke,stor,1073741824,4,4194304,262144,crc32c,auto,off,posix,0,1,1,off,auto,direct,bounded,67108864,none,off,off,every_n_chunks,16,none,full,full,3,3,0,1.100000,1.100000,8.000000,2.000000,1.400000,0.050000,4,0.004,0\n"
            "smoke,stor,1073741824,4,4194304,262144,crc32c,auto,off,posix,0,1,1,off,auto,direct,bounded,67108864,dirty_poll,off,off,every_n_chunks,16,none,full,full,3,3,0,0.900000,0.900000,12.000000,2.000000,1.500000,0.050000,5,0.005,1\n"
            "smoke,stor,1073741824,4,4194304,262144,crc32c,auto,off,posix,0,1,1,off,auto,direct,default,0,none,required,required,every_n_chunks,16,none,full,full,3,3,0,1.000000,1.000000,10.000000,2.000000,1.600000,0.050000,0,0,0\n"
            "smoke,stor,1073741824,4,4194304,262144,crc32c,auto,off,posix,0,1,1,off,auto,direct,bounded,67108864,dirty_poll,required,required,every_n_chunks,16,none,full,full,3,3,0,0.900000,0.900000,12.000000,2.000000,1.500000,0.050000,5,0.005,1\n",
            encoding="utf-8",
        )
        output = temp / "report.md"
        old_argv = sys.argv
        try:
            sys.argv = [
                "analyze_beta1b_receiver_writeback_stability.py",
                "--storage-summary-csv",
                str(storage),
                "--matrix-raw-csv",
                str(raw),
                "--matrix-summary-csv",
                str(summary),
                "--output",
                str(output),
            ]
            assert analyzer.main() == 0
        finally:
            sys.argv = old_argv
        report = output.read_text(encoding="utf-8")
        assert "Beta 1B Receiver Writeback Stability" in report
        assert "Matched bounded comparisons" in report
        assert "Dirty-poll independent pairs" in report
        assert "TLS/data TLS required" in report
        assert "shift near-term Beta work toward disk" in report


def test_storage_system_analyzer_fixture() -> None:
    analyzer = load_module("tools/perf/analyze_beta1b_storage_system.py")
    with tempfile.TemporaryDirectory() as temp_text:
        temp = Path(temp_text)
        probe_raw = temp / "probe.csv"
        probe_raw.write_text(
            "dir_label,method,operation,bytes,buffer_size,preallocate,file_io_backend,file_io_buffer_size,posix_write_strategy,iteration,aggregate,elapsed_seconds,throughput_gbps,file_io_wait_seconds,write_syscall_count,write_avg_bytes_per_syscall,dirty_kb_after,writeback_kb_after,result\n"
            "project_temp,gridflux_storage_bench,write,1073741824,262144,off,posix,0,auto,1,false,4.0,2.0,1.0,256,4194304,1000,10,pass\n"
            "target_root,gridflux_storage_bench,write,1073741824,262144,off,posix,0,auto,1,false,5.0,1.6,1.1,256,4194304,2000,20,pass\n",
            encoding="utf-8",
        )
        probe_summary = temp / "probe-summary.csv"
        probe_summary.write_text(
            "dir_label,method,operation,bytes,buffer_size,preallocate,file_io_backend,file_io_buffer_size,posix_write_strategy,case_count,pass_count,fail_count,unavailable_count,throughput_gbps_min,throughput_gbps_median,throughput_gbps_max,throughput_gbps_p95,throughput_gbps_spread_pct,elapsed_median,file_io_wait_seconds_median,write_syscall_count_median,write_avg_bytes_per_syscall_median,dirty_writeback_kb_before_median,dirty_writeback_kb_after_median,mount_source,mount_target,mount_fstype,example_sidecar,example_iostat\n"
            "project_temp,gridflux_storage_bench,write,1073741824,262144,off,posix,0,auto,3,3,0,0,1.8,2.0,2.1,2.1,15.0,4.0,1.0,256,4194304,100,1010,/dev/vda1,/,ext4,sidecar.log,sidecar.log\n"
            "project_temp,gridflux_storage_bench,read,1073741824,262144,off,posix,0,auto,3,3,0,0,3.0,3.2,3.4,3.4,10.0,2.5,0,0,0,100,1000,/dev/vda1,/,ext4,sidecar.log,sidecar.log\n"
            "project_temp,gridflux_storage_bench,write,1073741824,262144,full,posix,0,auto,3,3,0,0,1.9,2.1,2.2,2.2,10.0,3.8,1.0,256,4194304,100,1010,/dev/vda1,/,ext4,sidecar.log,sidecar.log\n"
            "project_temp,gridflux_storage_bench,write,1073741824,262144,off,io_uring,0,auto,3,3,0,0,1.7,1.8,1.9,1.9,11.0,4.2,1.2,256,4194304,100,1010,/dev/vda1,/,ext4,sidecar.log,sidecar.log\n"
            "tmp,gridflux_storage_bench,write,1073741824,262144,off,posix,0,auto,3,3,0,0,1.7,1.9,2.0,2.0,12.0,4.1,1.2,256,4194304,100,1010,/dev/vda1,/,ext4,sidecar.log,sidecar.log\n"
            "target_root,gridflux_storage_bench,write,1073741824,262144,off,posix,0,auto,3,3,0,0,1.6,1.8,1.9,1.9,12.0,4.3,1.2,256,4194304,100,1010,/dev/vda1,/,ext4,sidecar.log,sidecar.log\n",
            encoding="utf-8",
        )
        raw = temp / "matrix.csv"
        raw.write_text(
            "direction,result,throughput_gbps,server_dirty_kb_after,server_writeback_kb_after\n"
            "stor,pass,1.5,1000,20\n"
            "stor,pass,1.4,2000,40\n",
            encoding="utf-8",
        )
        summary = temp / "matrix-summary.csv"
        summary.write_text(
            "direction,bytes,connections,checksum_algorithm,tls_mode,data_tls_mode,pass_count,fail_count,throughput_gbps_median,throughput_gbps_spread_pct,elapsed_median,receiver_temp_write_seconds_median,receiver_data_receive_seconds_median,receiver_manifest_flush_seconds_median,receiver_final_verify_seconds_median,receiver_rename_commit_seconds_median\n"
            "stor,1073741824,4,crc32c,off,off,3,0,1.500000,8.000000,5.000000,4.000000,0.100000,0.020000,0.030000,0.010000\n",
            encoding="utf-8",
        )
        output = temp / "report.md"
        old_argv = sys.argv
        try:
            sys.argv = [
                "analyze_beta1b_storage_system.py",
                "--probe-raw-csv",
                str(probe_raw),
                "--probe-summary-csv",
                str(probe_summary),
                "--matrix-raw-csv",
                str(raw),
                "--matrix-summary-csv",
                str(summary),
                "--output",
                str(output),
            ]
            assert analyzer.main() == 0
        finally:
            sys.argv = old_argv
        report = output.read_text(encoding="utf-8")
        assert "Beta 1B Storage/System Writeback Attribution" in report
        assert "Native Storage vs GridFlux STOR" in report
        assert "tmp` versus target root" in report
        assert "Dirty/Writeback correlation" in report
        assert "Default policy remains unchanged" in report


def main() -> int:
    test_runner_command_dimensions()
    test_receiver_writeback_runner_dimensions()
    test_receiver_writeback_stability_runner_dimensions()
    test_matrix_skips_invalid_coalesced_zero()
    test_env_sidecar_parser()
    test_analyzer_fixture()
    test_receiver_writeback_analyzer_fixture()
    test_receiver_writeback_stability_analyzer_fixture()
    test_storage_system_probe_defaults()
    test_storage_system_probe_bytes_list_and_stor_commands()
    test_storage_system_analyzer_fixture()
    print("beta1b stor writeback helper tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
