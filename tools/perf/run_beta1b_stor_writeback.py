#!/usr/bin/env python3
"""Run the Beta 1B-2 focused STOR write/writeback diagnostic package."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "release"))
import remote_auth  # noqa: E402


DEFAULTS_UNCHANGED = {
    "auth_mode": "anonymous",
    "tls_mode": "off",
    "data_tls_mode": "off",
    "file_io_backend": "posix",
    "final_verify_policy": "full",
    "manifest_flush_policy": "every_n_chunks",
    "preallocate": "off",
    "posix_write_strategy": "auto",
}


@dataclass(frozen=True)
class StepSpec:
    name: str
    command: list[str]


def compact_timestamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def timestamp_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run_env(remote: str) -> dict[str, str]:
    env = os.environ.copy()
    auth = remote_auth.resolve_auth(remote, ROOT)
    if auth:
        env["GRIDFLUX_SSH_PASSWORD"] = auth.password
        env["SSHPASS"] = auth.password
    return env


def run_step(spec: StepSpec, log_dir: Path, *, env: dict[str, str]) -> dict[str, object]:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{spec.name}.log"
    start = time.monotonic()
    completed = subprocess.run(
        spec.command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    elapsed = time.monotonic() - start
    log_path.write_text(
        "$ " + " ".join(spec.command) + "\n\n" + completed.stdout + completed.stderr,
        encoding="utf-8",
    )
    return {
        "name": spec.name,
        "command": spec.command,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "log": str(log_path),
        "stdout": completed.stdout,
        "result": "pass" if completed.returncode == 0 else "fail",
    }


def extract_path(stdout: str, key: str) -> str:
    prefix = key + "="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip()
    return ""


def parse_cases(stdout: str) -> tuple[int, int]:
    cases = 0
    failures = 0
    for line in stdout.splitlines():
        if not line.startswith("cases="):
            continue
        for part in line.split():
            if part.startswith("cases="):
                cases = int(part.split("=", 1)[1])
            elif part.startswith("failures="):
                failures = int(part.split("=", 1)[1])
    return cases, failures


def read_csv(path_text: str) -> list[dict[str, str]]:
    if not path_text:
        return []
    path = Path(path_text)
    if not path.is_file():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def summary_fail_count(paths: list[str]) -> int:
    total = 0
    for path in paths:
        for row in read_csv(path):
            try:
                total += int(float(row.get("fail_count", "0") or "0"))
            except ValueError:
                total += 1
    return total


def hash_mismatch_count(paths: list[str]) -> int:
    mismatches = 0
    for path in paths:
        for row in read_csv(path):
            source = row.get("source_sha256", "")
            dest = row.get("dest_sha256", "")
            if source and dest and source != dest:
                mismatches += 1
    return mismatches


def storage_command(args: argparse.Namespace, bytes_value: str, repeat: int) -> StepSpec:
    return StepSpec(
        "storage_bench",
        [
            sys.executable,
            "tools/benchmark/run_storage_bench.py",
            "--side",
            "local",
            "--build-dir",
            args.local_build_dir,
            "--output-dir",
            args.output_dir,
            "--bytes",
            bytes_value,
            "--modes",
            "write",
            "--buffer-sizes",
            "262144,1048576",
            "--preallocates",
            "off,full",
            "--file-io-backends",
            "posix,io_uring",
            "--file-io-buffer-sizes",
            "0,262144,1048576",
            "--file-io-queue-depths",
            "1",
            "--file-io-batch-sizes",
            "1",
            "--file-io-advices",
            "off",
            "--posix-write-strategies",
            "auto,direct,coalesced",
            "--iterations",
            str(repeat),
            "--timeout",
            str(args.case_timeout),
        ],
    )


def receiver_writeback_storage_command(
    args: argparse.Namespace, bytes_value: str, repeat: int
) -> StepSpec:
    return StepSpec(
        "storage_bench",
        [
            sys.executable,
            "tools/benchmark/run_storage_bench.py",
            "--side",
            "local",
            "--build-dir",
            args.local_build_dir,
            "--output-dir",
            args.output_dir,
            "--bytes",
            bytes_value,
            "--modes",
            "write",
            "--buffer-sizes",
            "262144",
            "--preallocates",
            "off",
            "--file-io-backends",
            "posix",
            "--file-io-buffer-sizes",
            "0",
            "--file-io-queue-depths",
            "1",
            "--file-io-batch-sizes",
            "1",
            "--file-io-advices",
            "off",
            "--posix-write-strategies",
            "auto",
            "--iterations",
            str(repeat),
            "--timeout",
            str(args.case_timeout),
        ],
    )


def matrix_common(
    args: argparse.Namespace,
    *,
    bytes_value: str,
    repeat: int,
    event_dir: Path,
    storage_csv: str,
) -> list[str]:
    command = [
        sys.executable,
        "tools/perf/run_gridftp_private_matrix.py",
        "--smoke",
        "--remote",
        args.remote,
        "--server-host",
        args.server_host,
        "--local-build-dir",
        args.local_build_dir,
        "--remote-build-dir",
        args.remote_build_dir,
        "--output-dir",
        args.output_dir,
        "--directions",
        "stor",
        "--bytes",
        bytes_value,
        "--chunk-sizes",
        "4194304",
        "--buffer-sizes",
        "262144",
        "--checksum-backend",
        "auto",
        "--file-io-queue-depths",
        "1",
        "--file-io-batch-sizes",
        "1",
        "--file-io-advices",
        "off",
        "--manifest-flush-interval-chunks-list",
        "16",
        "--commit-sync-policies",
        "none",
        "--tls-modes",
        "off",
        "--data-tls-modes",
        "off",
        "--event-log-dir",
        str(event_dir),
        "--repeat",
        str(repeat),
        "--case-timeout",
        str(args.case_timeout),
    ]
    if storage_csv:
        command.extend(["--storage-bench-csv", storage_csv])
    return command


def matrix_step_specs(
    args: argparse.Namespace,
    *,
    bytes_value: str,
    repeat: int,
    event_dir: Path,
    storage_csv: str,
) -> list[StepSpec]:
    common = matrix_common(
        args,
        bytes_value=bytes_value,
        repeat=repeat,
        event_dir=event_dir,
        storage_csv=storage_csv,
    )
    return [
        StepSpec(
            "stor_backend_connections",
            [
                *common,
                "--connections",
                "1,4,8",
                "--checksums",
                "crc32c,none",
                "--file-io-backends",
                "posix,io_uring",
                "--file-io-buffer-sizes",
                "0",
                "--posix-write-strategies",
                "auto",
                "--preallocates",
                "off",
                "--manifest-flush-policies",
                "every_n_chunks",
                "--final-verify-policies",
                "full",
            ],
        ),
        StepSpec(
            "stor_write_strategy_buffer",
            [
                *common,
                "--connections",
                "4",
                "--checksums",
                "crc32c,none",
                "--file-io-backends",
                "posix",
                "--file-io-buffer-sizes",
                "0,262144,1048576",
                "--posix-write-strategies",
                "auto,direct,coalesced",
                "--preallocates",
                "off",
                "--manifest-flush-policies",
                "every_n_chunks",
                "--final-verify-policies",
                "full",
            ],
        ),
        StepSpec(
            "stor_preallocate_manifest",
            [
                *common,
                "--connections",
                "4",
                "--checksums",
                "crc32c,none",
                "--file-io-backends",
                "posix",
                "--file-io-buffer-sizes",
                "0",
                "--posix-write-strategies",
                "auto",
                "--preallocates",
                "off,full",
                "--manifest-flush-policies",
                "every_n_chunks,final_only",
                "--final-verify-policies",
                "full",
            ],
        ),
        StepSpec(
            "stor_final_verify_opt_in",
            [
                *common,
                "--connections",
                "4",
                "--checksums",
                "crc32c",
                "--file-io-backends",
                "posix",
                "--file-io-buffer-sizes",
                "0",
                "--posix-write-strategies",
                "auto",
                "--preallocates",
                "off",
                "--manifest-flush-policies",
                "every_n_chunks,final_only",
                "--final-verify-policies",
                "full,verified_chunks",
            ],
        ),
    ]


def receiver_writeback_matrix_step_specs(
    args: argparse.Namespace,
    *,
    bytes_value: str,
    repeat: int,
    event_dir: Path,
    storage_csv: str,
) -> list[StepSpec]:
    common = matrix_common(
        args,
        bytes_value=bytes_value,
        repeat=repeat,
        event_dir=event_dir,
        storage_csv=storage_csv,
    )
    return [
        StepSpec(
            "stor_receiver_writeback_optin",
            [
                *common,
                "--connections",
                "1,4,8",
                "--checksums",
                "crc32c,none",
                "--file-io-backends",
                "posix",
                "--file-io-buffer-sizes",
                "0",
                "--posix-write-strategies",
                "auto",
                "--preallocates",
                "off",
                "--manifest-flush-policies",
                "every_n_chunks",
                "--final-verify-policies",
                "full",
                "--receiver-write-profiles",
                "default,bounded",
                "--receiver-max-pending-bytes-list",
                "0,67108864,268435456",
                "--receiver-write-yield-policies",
                "none,dirty_poll",
            ],
        )
    ]


def analyze_command(
    *,
    storage_raw: str,
    storage_summary: str,
    matrix_raws: list[str],
    matrix_summaries: list[str],
    report_path: Path,
) -> StepSpec:
    command = [
        sys.executable,
        "tools/perf/analyze_beta1b_stor_writeback.py",
        "--output",
        str(report_path),
    ]
    if storage_raw:
        command.extend(["--storage-raw-csv", storage_raw])
    if storage_summary:
        command.extend(["--storage-summary-csv", storage_summary])
    for raw in matrix_raws:
        command.extend(["--matrix-raw-csv", raw])
    for summary in matrix_summaries:
        command.extend(["--matrix-summary-csv", summary])
    return StepSpec("analyze_beta1b_stor_writeback", command)


def analyze_receiver_writeback_command(
    *,
    storage_raw: str,
    storage_summary: str,
    matrix_raws: list[str],
    matrix_summaries: list[str],
    report_path: Path,
) -> StepSpec:
    command = [
        sys.executable,
        "tools/perf/analyze_beta1b_receiver_writeback.py",
        "--output",
        str(report_path),
    ]
    if storage_raw:
        command.extend(["--storage-raw-csv", storage_raw])
    if storage_summary:
        command.extend(["--storage-summary-csv", storage_summary])
    for raw in matrix_raws:
        command.extend(["--matrix-raw-csv", raw])
    for summary in matrix_summaries:
        command.extend(["--matrix-summary-csv", summary])
    return StepSpec("analyze_beta1b_receiver_writeback", command)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Beta 1B-2 STOR write/writeback diagnostics.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true")
    mode.add_argument("--focused", action="store_true")
    parser.add_argument("--remote", default="root@<redacted>")
    parser.add_argument("--server-host", default="<redacted>")
    parser.add_argument("--local-build-dir", default="/root/projects/GridFlux/build-io-uring-real")
    parser.add_argument("--remote-build-dir", default="/root/projects/GridFlux/build-io-uring-real")
    parser.add_argument("--output-dir", default="tools/perf/results")
    parser.add_argument("--bytes", default="")
    parser.add_argument("--repeat", type=int, default=0)
    parser.add_argument("--case-timeout", type=int, default=900)
    parser.add_argument("--skip-storage-bench", action="store_true")
    parser.add_argument(
        "--receiver-writeback-optin",
        action="store_true",
        help="run the Beta 1B-3 opt-in drain-budget receiver writeback matrix",
    )
    args = parser.parse_args()

    if args.repeat < 0:
        raise SystemExit("--repeat must not be negative")
    bytes_value = args.bytes or ("268435456" if args.smoke else "1073741824")
    repeat = args.repeat or (1 if args.smoke else 3)

    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = compact_timestamp()
    run_slug = "beta1b-receiver-writeback-optin" if args.receiver_writeback_optin else "beta1b-stor-writeback"
    log_dir = output_dir / f"{run_id}_{run_slug}"
    event_dir = log_dir / "events"
    event_dir.mkdir(parents=True, exist_ok=True)
    summary_json = output_dir / f"{run_id}_{run_slug}.json"
    report_path = ROOT / "docs" / "perf" / (
        "BETA1B_RECEIVER_WRITEBACK_OPTIN.md"
        if args.receiver_writeback_optin
        else "BETA1B_STOR_WRITEBACK_DIAGNOSIS.md"
    )

    env = run_env(args.remote)
    steps: list[dict[str, object]] = []
    storage_raw = ""
    storage_summary = ""

    if not args.skip_storage_bench:
        storage_spec = (
            receiver_writeback_storage_command(args, bytes_value, repeat)
            if args.receiver_writeback_optin
            else storage_command(args, bytes_value, repeat)
        )
        storage_step = run_step(storage_spec, log_dir, env=env)
        steps.append(storage_step)
        storage_raw = extract_path(str(storage_step.get("stdout", "")), "csv")
        storage_summary = extract_path(str(storage_step.get("stdout", "")), "summary_csv")

    matrix_raws: list[str] = []
    matrix_summaries: list[str] = []
    specs = (
        receiver_writeback_matrix_step_specs(
            args,
            bytes_value=bytes_value,
            repeat=repeat,
            event_dir=event_dir,
            storage_csv=storage_raw,
        )
        if args.receiver_writeback_optin
        else matrix_step_specs(
            args,
            bytes_value=bytes_value,
            repeat=repeat,
            event_dir=event_dir,
            storage_csv=storage_raw,
        )
    )
    for spec in specs:
        step = run_step(spec, log_dir, env=env)
        steps.append(step)
        raw = extract_path(str(step.get("stdout", "")), "csv")
        summary = extract_path(str(step.get("stdout", "")), "summary_csv")
        if raw:
            matrix_raws.append(raw)
        if summary:
            matrix_summaries.append(summary)

    analyze_spec = (
        analyze_receiver_writeback_command(
            storage_raw=storage_raw,
            storage_summary=storage_summary,
            matrix_raws=matrix_raws,
            matrix_summaries=matrix_summaries,
            report_path=report_path,
        )
        if args.receiver_writeback_optin
        else analyze_command(
            storage_raw=storage_raw,
            storage_summary=storage_summary,
            matrix_raws=matrix_raws,
            matrix_summaries=matrix_summaries,
            report_path=report_path,
        )
    )
    analyze_step = run_step(analyze_spec, log_dir, env=env)
    steps.append(analyze_step)

    storage_cases = 0
    storage_case_failures = 0
    stor_transfer_cases = 0
    stor_transfer_failures = 0
    for step in steps:
        step_cases, step_failures = parse_cases(str(step.get("stdout", "")))
        if step["name"] == "storage_bench":
            storage_cases += step_cases
            storage_case_failures += step_failures
        elif str(step["name"]).startswith("stor_"):
            stor_transfer_cases += step_cases
            stor_transfer_failures += step_failures
    grouped_failures = summary_fail_count(matrix_summaries)
    mismatches = hash_mismatch_count(matrix_raws)
    failures = [step for step in steps if step["result"] != "pass"]
    result = {
        "timestamp": timestamp_utc(),
        "mode": "smoke" if args.smoke else "focused",
        "receiver_writeback_optin": args.receiver_writeback_optin,
        "result": "pass" if not failures and grouped_failures == 0 and mismatches == 0 else "fail",
        "bytes": bytes_value,
        "repeat": repeat,
        "steps": [
            {
                "name": step["name"],
                "result": step["result"],
                "returncode": step["returncode"],
                "elapsed_seconds": step["elapsed_seconds"],
                "log": step["log"],
            }
            for step in steps
        ],
        "storage_raw_csv": storage_raw,
        "storage_summary_csv": storage_summary,
        "stor_raw_csvs": matrix_raws,
        "stor_summary_csvs": matrix_summaries,
        "report": str(report_path),
        "storage_cases": storage_cases,
        "storage_case_failures": storage_case_failures,
        "stor_transfer_cases": stor_transfer_cases,
        "stor_transfer_failures": stor_transfer_failures,
        "matrix_cases": stor_transfer_cases,
        "matrix_case_failures": stor_transfer_failures,
        "grouped_fail_count": grouped_failures,
        "hash_mismatch_count": mismatches,
        "defaults_unchanged": DEFAULTS_UNCHANGED,
    }
    summary_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"json={summary_json}")
    print(f"report={report_path}")
    if storage_raw:
        print(f"storage_raw_csv={storage_raw}")
    if storage_summary:
        print(f"storage_summary_csv={storage_summary}")
    for raw in matrix_raws:
        print(f"stor_raw_csv={raw}")
    for summary in matrix_summaries:
        print(f"stor_summary_csv={summary}")
    print(f"storage_cases={storage_cases} storage_failures={storage_case_failures}")
    print(f"stor_transfer_cases={stor_transfer_cases} stor_transfer_failures={stor_transfer_failures}")
    print(f"matrix_cases={stor_transfer_cases} matrix_failures={stor_transfer_failures}")
    print(f"grouped_fail_count={grouped_failures}")
    print(f"hash_mismatch_count={mismatches}")
    print(f"result={result['result']}")
    return 0 if result["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
