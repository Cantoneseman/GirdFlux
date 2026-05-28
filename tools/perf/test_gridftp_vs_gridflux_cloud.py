#!/usr/bin/env python3
"""Helper tests for GridFTP vs GridFlux cloud comparison tooling."""

from __future__ import annotations

import argparse
import csv
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
        client_host="192.0.2.2",
        local_build_dir="/local/build",
        remote_build_dir="/remote/build",
        iouring_local_build_dir="/local/build-iouring",
        iouring_remote_build_dir="/remote/build-iouring",
        output_dir="tools/perf/results",
        case_timeout=900,
        parallelism_values=[1, 4, 8, 16],
        smoke=False,
        repeat_short=1,
        repeat_1gib=3,
        repeat_4gib=1,
        repeat_10gib=1,
        skip_iouring_subset=False,
        skip_tls_subset=False,
    )


def flag_value(command: list[str], flag: str) -> str:
    index = command.index(flag)
    return command[index + 1]


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summary_fixture() -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    summary = [
        {
            "protocol": "native_gridftp",
            "direction": "upload",
            "size_bytes": "1073741824",
            "parallelism": "16",
            "connections": "",
            "checksum": "",
            "file_io_backend": "",
            "tls_mode": "",
            "data_tls_mode": "",
            "median_Gbps": "1.500",
            "best_Gbps": "1.600",
            "fail_count": "0",
            "sha256_mismatch_count": "0",
        },
        {
            "protocol": "native_gridftp",
            "direction": "download",
            "size_bytes": "1073741824",
            "parallelism": "16",
            "connections": "",
            "checksum": "",
            "file_io_backend": "",
            "tls_mode": "",
            "data_tls_mode": "",
            "median_Gbps": "2.000",
            "best_Gbps": "2.100",
            "fail_count": "0",
            "sha256_mismatch_count": "0",
        },
        {
            "protocol": "gridflux",
            "direction": "stor",
            "size_bytes": "1073741824",
            "parallelism": "",
            "connections": "16",
            "checksum": "none",
            "file_io_backend": "posix",
            "tls_mode": "off",
            "data_tls_mode": "off",
            "median_Gbps": "1.800",
            "best_Gbps": "1.900",
            "fail_count": "0",
            "sha256_mismatch_count": "0",
        },
        {
            "protocol": "gridflux",
            "direction": "stor",
            "size_bytes": "1073741824",
            "parallelism": "",
            "connections": "16",
            "checksum": "crc32c",
            "file_io_backend": "posix",
            "tls_mode": "off",
            "data_tls_mode": "off",
            "median_Gbps": "1.600",
            "best_Gbps": "1.700",
            "fail_count": "0",
            "sha256_mismatch_count": "0",
        },
        {
            "protocol": "gridflux",
            "direction": "retr",
            "size_bytes": "1073741824",
            "parallelism": "",
            "connections": "16",
            "checksum": "none",
            "file_io_backend": "posix",
            "tls_mode": "off",
            "data_tls_mode": "off",
            "median_Gbps": "3.000",
            "best_Gbps": "3.200",
            "fail_count": "0",
            "sha256_mismatch_count": "0",
        },
        {
            "protocol": "gridflux",
            "direction": "retr",
            "size_bytes": "1073741824",
            "parallelism": "",
            "connections": "16",
            "checksum": "crc32c",
            "file_io_backend": "posix",
            "tls_mode": "off",
            "data_tls_mode": "off",
            "median_Gbps": "2.700",
            "best_Gbps": "2.800",
            "fail_count": "0",
            "sha256_mismatch_count": "0",
        },
    ]
    host = [
        {
            "kind": "iperf3",
            "machine": "client_to_server",
            "operation": "tcp",
            "parallelism": "16",
            "size_bytes": "",
            "elapsed_seconds": "10",
            "MBps": "",
            "Gbps": "15.000",
            "status": "pass",
            "log_path": "",
            "notes": "",
        },
        {
            "kind": "storage",
            "machine": "server",
            "operation": "write",
            "parallelism": "1",
            "size_bytes": "1073741824",
            "elapsed_seconds": "8",
            "MBps": "128",
            "Gbps": "1.024",
            "status": "pass",
            "log_path": "",
            "notes": "",
        },
    ]
    checksum = [
        {
            "machine": "server",
            "backend": "hardware",
            "size_bytes": "1073741824",
            "iterations": "3",
            "elapsed_seconds": "0.1",
            "throughput_Gbps": "70.000",
            "status": "pass",
            "log_path": "",
            "notes": "",
        }
    ]
    return summary, host, checksum


def test_gridflux_step_specs_cover_required_dimensions() -> None:
    runner = load_module("tools/perf/run_gridftp_vs_gridflux_cloud_matrix.py")
    args = runner_args()
    sizes = [268435456, 1073741824, 4294967296, 10737418240]
    specs = runner.gridflux_step_specs(args, sizes, Path("events"))
    names = [spec.name for spec in specs]
    assert "gridflux_posix_off_1073741824" in names
    assert "gridflux_iouring_off_1073741824" in names
    assert "gridflux_posix_tls_1073741824" in names
    main = next(spec.command for spec in specs if spec.name == "gridflux_posix_off_1073741824")
    assert flag_value(main, "--connections") == "1,4,8,16"
    assert flag_value(main, "--checksums") == "crc32c,none"
    assert flag_value(main, "--file-io-backends") == "posix"
    assert flag_value(main, "--tls-modes") == "off"
    assert flag_value(main, "--data-tls-modes") == "off"
    assert flag_value(main, "--receiver-write-profiles") == "default"
    assert flag_value(main, "--receiver-write-yield-policies") == "none"
    assert flag_value(main, "--repeat") == "3"
    four_gib = next(spec.command for spec in specs if spec.name == "gridflux_posix_off_4294967296")
    assert flag_value(four_gib, "--repeat") == "1"
    iouring = next(spec.command for spec in specs if spec.name == "gridflux_iouring_off_1073741824")
    assert flag_value(iouring, "--file-io-backends") == "io_uring"
    assert flag_value(iouring, "--connections") == "8"
    tls = next(spec.command for spec in specs if spec.name == "gridflux_posix_tls_1073741824")
    assert flag_value(tls, "--tls-modes") == "required"
    assert flag_value(tls, "--data-tls-modes") == "required"


def test_repeat_policy_and_smoke_matrix() -> None:
    runner = load_module("tools/perf/run_gridftp_vs_gridflux_cloud_matrix.py")
    args = runner_args()
    assert runner.repeat_for_size(1073741824, args) == 3
    assert runner.repeat_for_size(4294967296, args) == 1
    assert runner.repeat_for_size(10737418240, args) == 1
    args.smoke = True
    assert runner.repeat_for_size(1073741824, args) == 1


def test_analyzer_matched_and_checksum_delta() -> None:
    analyzer = load_module("tools/perf/analyze_gridftp_vs_gridflux_cloud.py")
    summary, _host, _checksum = summary_fixture()
    rows = analyzer.comparison_rows(summary)
    upload_none = next(row for row in rows if row["direction"] == "upload/stor" and row["checksum"] == "none")
    assert upload_none["status"] == "matched"
    assert upload_none["delta_pct"] == "+20.0%"
    checksum_rows = analyzer.checksum_impact_rows(summary)
    stor = next(row for row in checksum_rows if row[0] == "STOR")
    assert stor[-1] == "-11.1%"


def test_plotter_fixture_outputs_png() -> None:
    plotter = load_module("tools/perf/plot_gridftp_vs_gridflux_cloud.py")
    summary, host, checksum = summary_fixture()
    fields = [
        "protocol",
        "direction",
        "size_bytes",
        "parallelism",
        "connections",
        "checksum",
        "file_io_backend",
        "tls_mode",
        "data_tls_mode",
        "median_Gbps",
        "best_Gbps",
        "fail_count",
        "sha256_mismatch_count",
    ]
    host_fields = ["kind", "machine", "operation", "parallelism", "size_bytes", "elapsed_seconds", "MBps", "Gbps", "status", "log_path", "notes"]
    checksum_fields = ["machine", "backend", "size_bytes", "iterations", "elapsed_seconds", "throughput_Gbps", "status", "log_path", "notes"]
    with tempfile.TemporaryDirectory(prefix="gridflux-cloud-plot.") as temp:
        root = Path(temp)
        summary_csv = root / "summary.csv"
        host_csv = root / "host.csv"
        checksum_csv = root / "checksum.csv"
        write_csv(summary_csv, summary, fields)
        write_csv(host_csv, host, host_fields)
        write_csv(checksum_csv, checksum, checksum_fields)
        outputs = plotter.plot_all(summary_csv, host_csv, checksum_csv, root / "figures", "png")
        assert outputs
        assert all(path.is_file() and path.stat().st_size > 0 for path in outputs)


def main() -> int:
    tests = [
        test_gridflux_step_specs_cover_required_dimensions,
        test_repeat_policy_and_smoke_matrix,
        test_analyzer_matched_and_checksum_delta,
        test_plotter_fixture_outputs_png,
    ]
    for test in tests:
        test()
    print("gridftp vs gridflux cloud helper tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
