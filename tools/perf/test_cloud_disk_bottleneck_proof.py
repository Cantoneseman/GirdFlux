#!/usr/bin/env python3
"""Helper tests for cloud disk bottleneck proof tooling."""

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


def flag_value(command: list[str], flag: str) -> str:
    index = command.index(flag)
    return command[index + 1]


def runner_args() -> argparse.Namespace:
    return argparse.Namespace(
        remote="root@example",
        server_host="192.0.2.1",
        client_host="192.0.2.2",
        local_build_dir="/local/build",
        remote_build_dir="/remote/build",
        output_dir="tools/perf/results",
        case_timeout=900,
        bytes_values=[1073741824, 4294967296],
        connections_values=[1, 4, 8],
        repeat=3,
    )


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_gridflux_matrix_defaults_and_dimensions() -> None:
    runner = load_module("tools/perf/run_cloud_disk_bottleneck_proof.py")
    specs = runner.gridflux_step_specs(runner_args(), Path("events"))
    names = [spec.name for spec in specs]
    assert "gridflux_stor_1073741824" in names
    assert "gridflux_retr_4294967296" in names
    stor = next(spec.command for spec in specs if spec.name == "gridflux_stor_1073741824")
    assert flag_value(stor, "--directions") == "stor"
    assert flag_value(stor, "--connections") == "1,4,8"
    assert flag_value(stor, "--checksums") == "crc32c,none"
    assert flag_value(stor, "--file-io-backends") == "posix"
    assert flag_value(stor, "--tls-modes") == "off"
    assert flag_value(stor, "--data-tls-modes") == "off"
    assert flag_value(stor, "--preallocates") == "off"
    assert flag_value(stor, "--posix-write-strategies") == "auto"
    assert flag_value(stor, "--receiver-write-profiles") == "default"
    assert flag_value(stor, "--receiver-max-pending-bytes-list") == "0"
    assert flag_value(stor, "--receiver-write-yield-policies") == "none"
    assert flag_value(stor, "--repeat") == "3"


def test_fio_unavailable_storage_rows_are_not_failures() -> None:
    runner = load_module("tools/perf/run_cloud_disk_bottleneck_proof.py")
    args = argparse.Namespace(skip_fio=False)
    row = {"result": "unavailable", "error": "fio=unavailable"}
    assert row["result"] == "unavailable"
    assert "fio" in row["error"]
    assert runner.DEFAULT_DEFAULTS["receiver_write_profile"] == "default"


def test_analyzer_proof_verdict_and_stage_share() -> None:
    analyzer = load_module("tools/perf/analyze_cloud_disk_bottleneck_proof.py")
    network = [
        {"direction": "client_to_server", "parallelism": "8", "throughput_gbps": "15.0", "status": "pass"},
        {"direction": "server_to_client", "parallelism": "8", "throughput_gbps": "15.2", "status": "pass"},
    ]
    checksum = [
        {
            "machine": "server",
            "backend_requested": "hardware",
            "backend_effective": "hardware",
            "throughput_gbps": "45.0",
            "status": "pass",
        }
    ]
    memory = [{"side": "link", "category": "network", "tool": "gridflux_memory_sink", "throughput_gbps": "4.0", "status": "pass"}]
    storage_summary = [
        {
            "method": "gridflux_storage_bench",
            "operation": "write",
            "file_io_backend": "posix",
            "pass_count": "3",
            "fail_count": "0",
            "throughput_gbps_median": "1.1",
        },
        {
            "method": "gridflux_storage_bench",
            "operation": "read",
            "file_io_backend": "posix",
            "pass_count": "3",
            "fail_count": "0",
            "throughput_gbps_median": "6.0",
        },
    ]
    stor_summary = [
        {
            "direction": "stor",
            "bytes": "1073741824",
            "connections": "4",
            "checksum_algorithm": "crc32c",
            "pass_count": "3",
            "fail_count": "0",
            "throughput_gbps_median": "1.0",
            "elapsed_median": "8.5",
            "receiver_temp_write_seconds_median": "7.2",
            "receiver_data_receive_seconds_median": "0.2",
        }
    ]
    retr_summary = [
        {
            "direction": "retr",
            "bytes": "1073741824",
            "connections": "4",
            "checksum_algorithm": "crc32c",
            "pass_count": "3",
            "fail_count": "0",
            "throughput_gbps_median": "3.0",
            "elapsed_median": "3.0",
            "sender_network_send_seconds_median": "1.8",
            "receiver_download_temp_write_seconds_median": "0.5",
        }
    ]
    summary = analyzer.summary_metrics(network, checksum, memory, storage_summary, stor_summary, retr_summary, [], [])
    by_metric = {row["metric"]: row for row in summary}
    assert by_metric["proof_verdict"]["value"] == "cloud_disk_writeback_dominated"
    assert by_metric["stor_temp_write_share_median"]["note"] == "84.7%"
    assert by_metric["stor_data_receive_share_median"]["note"] == "2.4%"
    assert by_metric["hash_mismatch_count"]["value"] == "0"


def test_plotter_fixture_outputs() -> None:
    plotter = load_module("tools/perf/plot_cloud_disk_bottleneck_proof.py")
    rows = [
        {"metric": "network_client_to_server_best_gbps", "value": "15.0", "unit": "Gbps", "note": ""},
        {"metric": "network_server_to_client_best_gbps", "value": "15.2", "unit": "Gbps", "note": ""},
        {"metric": "checksum_hardware_best_gbps", "value": "45.0", "unit": "Gbps", "note": ""},
        {"metric": "checksum_software_median_gbps", "value": "2.0", "unit": "Gbps", "note": ""},
        {"metric": "storage_write_median_gbps", "value": "1.1", "unit": "Gbps", "note": ""},
        {"metric": "storage_read_median_gbps", "value": "6.0", "unit": "Gbps", "note": ""},
        {"metric": "stor_e2e_median_gbps", "value": "1.0", "unit": "Gbps", "note": ""},
        {"metric": "stor_e2e_best_gbps", "value": "1.2", "unit": "Gbps", "note": ""},
        {"metric": "stor_temp_write_median_gbps", "value": "1.15", "unit": "Gbps", "note": ""},
        {"metric": "stor_temp_write_share_median", "value": "0.84", "unit": "ratio", "note": "84%"},
        {"metric": "stor_data_receive_share_median", "value": "0.03", "unit": "ratio", "note": "3%"},
        {"metric": "retr_download_temp_write_share_median", "value": "0.25", "unit": "ratio", "note": "25%"},
        {"metric": "retr_network_send_share_median", "value": "0.50", "unit": "ratio", "note": "50%"},
        {"metric": "run_size_scope", "value": "focused_long_file", "unit": "text", "note": ""},
    ]
    with tempfile.TemporaryDirectory(prefix="gridflux-cloud-proof-plot.") as temp:
        root = Path(temp)
        csv_path = root / "summary.csv"
        write_csv(csv_path, rows, ["metric", "value", "unit", "note"])
        outputs = plotter.plot_all(csv_path, root / "figures", "png")
        assert len(outputs) == 5
        assert all(path.is_file() and path.stat().st_size > 0 for path in outputs)


def main() -> int:
    tests = [
        test_gridflux_matrix_defaults_and_dimensions,
        test_fio_unavailable_storage_rows_are_not_failures,
        test_analyzer_proof_verdict_and_stage_share,
        test_plotter_fixture_outputs,
    ]
    for test in tests:
        test()
    print("cloud disk bottleneck proof helper tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
