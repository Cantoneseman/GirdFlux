#!/usr/bin/env python3
"""Run Beta 1C RETR stability and beta performance closeout matrix."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shlex
import statistics
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
    "receiver_write_profile": "default",
    "receiver_write_yield_policy": "none",
}


@dataclass(frozen=True)
class StepSpec:
    name: str
    command: list[str]


def compact_timestamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def timestamp_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def parse_size_token(token: str) -> int:
    value = token.strip().lower()
    suffixes = [
        ("gib", 1024**3),
        ("gb", 1000**3),
        ("g", 1024**3),
        ("mib", 1024**2),
        ("mb", 1000**2),
        ("m", 1024**2),
        ("kib", 1024),
        ("kb", 1000),
        ("k", 1024),
    ]
    for suffix, multiplier in suffixes:
        if value.endswith(suffix):
            return int(value[: -len(suffix)]) * multiplier
    return int(value)


def parse_int_list(text: str) -> list[int]:
    return [parse_size_token(part) for part in text.split(",") if part.strip()]


def run_env(remote: str) -> dict[str, str]:
    env = os.environ.copy()
    auth = remote_auth.resolve_auth(remote, ROOT)
    if auth:
        env["GRIDFLUX_SSH_PASSWORD"] = auth.password
        env["SSHPASS"] = auth.password
    return env


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def split_key_value_stdout(stdout: str, key: str) -> str:
    prefix = key + "="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip()
    return ""


def read_csv(path_text: str) -> list[dict[str, str]]:
    if not path_text:
        return []
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
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


def matrix_common(
    args: argparse.Namespace,
    *,
    bytes_value: str,
    repeat: int,
    event_dir: Path,
    tls_mode: str,
    data_tls_mode: str,
    backend: str,
    run_root_base: Path,
) -> list[str]:
    return [
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
        "retr",
        "--bytes",
        bytes_value,
        "--chunk-sizes",
        "4194304",
        "--buffer-sizes",
        "262144",
        "--checksum-backend",
        "auto",
        "--preallocates",
        "off",
        "--file-io-backends",
        backend,
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
        "--manifest-flush-policies",
        "every_n_chunks",
        "--manifest-flush-interval-chunks-list",
        "16",
        "--commit-sync-policies",
        "none",
        "--receiver-write-profiles",
        "default",
        "--receiver-max-pending-bytes-list",
        "0",
        "--receiver-write-yield-policies",
        "none",
        "--tls-modes",
        tls_mode,
        "--data-tls-modes",
        data_tls_mode,
        "--event-log-dir",
        str(event_dir),
        "--repeat",
        str(repeat),
        "--case-timeout",
        str(args.case_timeout),
        "--run-root-base",
        str(run_root_base),
    ]


def retr_stability_step_specs(
    args: argparse.Namespace,
    *,
    bytes_values: list[int],
    repeat: int,
    event_dir: Path,
) -> list[StepSpec]:
    run_root_base = ROOT / args.output_dir / "beta1c-retr-runroots"
    specs: list[StepSpec] = []
    for bytes_value in bytes_values:
        common_off = matrix_common(
            args,
            bytes_value=str(bytes_value),
            repeat=repeat,
            event_dir=event_dir,
            tls_mode="off",
            data_tls_mode="off",
            backend="posix",
            run_root_base=run_root_base,
        )
        specs.append(
            StepSpec(
                f"retr_stability_posix_off_{bytes_value}",
                [
                    *common_off,
                    "--connections",
                    "1,4,8",
                    "--checksums",
                    "crc32c,none",
                    "--final-verify-policies",
                    "full",
                ],
            )
        )

        common_tls = matrix_common(
            args,
            bytes_value=str(bytes_value),
            repeat=repeat,
            event_dir=event_dir,
            tls_mode="required",
            data_tls_mode="required",
            backend="posix",
            run_root_base=run_root_base,
        )
        specs.append(
            StepSpec(
                f"retr_stability_posix_tls_{bytes_value}",
                [
                    *common_tls,
                    "--connections",
                    "4",
                    "--checksums",
                    "crc32c",
                    "--final-verify-policies",
                    "full",
                ],
            )
        )

        common_iouring = matrix_common(
            args,
            bytes_value=str(bytes_value),
            repeat=repeat,
            event_dir=event_dir,
            tls_mode="off",
            data_tls_mode="off",
            backend="io_uring",
            run_root_base=run_root_base,
        )
        specs.append(
            StepSpec(
                f"retr_stability_iouring_off_{bytes_value}",
                [
                    *common_iouring,
                    "--connections",
                    "4",
                    "--checksums",
                    "crc32c",
                    "--final-verify-policies",
                    "full",
                ],
            )
        )

        specs.append(
            StepSpec(
                f"retr_stability_verified_chunks_{bytes_value}",
                [
                    *common_off,
                    "--connections",
                    "4",
                    "--checksums",
                    "crc32c",
                    "--final-verify-policies",
                    "full,verified_chunks",
                ],
            )
        )
    return specs


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
    write_text(log_path, "$ " + " ".join(shlex.quote(part) for part in spec.command) + "\n\n" + completed.stdout + completed.stderr)
    return {
        "name": spec.name,
        "command": spec.command,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "log": str(log_path),
        "stdout": completed.stdout,
        "result": "pass" if completed.returncode == 0 else "fail",
    }


def analyzer_step(*, raw_csvs: list[str], summary_csvs: list[str], report_path: Path) -> StepSpec:
    command = [
        sys.executable,
        "tools/perf/analyze_beta1c_retr_stability.py",
        "--output",
        str(report_path),
    ]
    for raw in raw_csvs:
        command.extend(["--matrix-raw-csv", raw])
    for summary in summary_csvs:
        command.extend(["--matrix-summary-csv", summary])
    return StepSpec("analyze_beta1c_retr_stability", command)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Beta 1C RETR stability closeout matrix.")
    parser.add_argument("--remote", default="root@<redacted>")
    parser.add_argument("--server-host", default="<redacted>")
    parser.add_argument("--local-build-dir", default="/root/projects/GridFlux/build-io-uring-real")
    parser.add_argument("--remote-build-dir", default="/root/projects/GridFlux/build-io-uring-real")
    parser.add_argument("--output-dir", default="tools/perf/results")
    parser.add_argument("--bytes", default="1073741824")
    parser.add_argument("--bytes-list", default="")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--case-timeout", type=int, default=1800)
    parser.add_argument("--skip-retr-matrix", action="store_true")
    args = parser.parse_args()

    if args.repeat <= 0:
        raise SystemExit("--repeat must be greater than zero")
    bytes_values = parse_int_list(args.bytes_list or args.bytes)
    if not bytes_values:
        raise SystemExit("at least one byte size is required")

    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = compact_timestamp()
    run_slug = "beta1c-retr-stability"
    log_dir = output_dir / f"{run_id}_{run_slug}"
    log_dir.mkdir(parents=True, exist_ok=True)
    event_dir = log_dir / "events"
    event_dir.mkdir(parents=True, exist_ok=True)
    report_path = ROOT / "docs" / "perf" / "BETA1C_RETR_STABILITY.md"
    summary_json = output_dir / f"{run_id}_{run_slug}.json"

    env = run_env(args.remote)
    steps: list[dict[str, object]] = []
    retr_raws: list[str] = []
    retr_summaries: list[str] = []

    if not args.skip_retr_matrix:
        for spec in retr_stability_step_specs(
            args,
            bytes_values=bytes_values,
            repeat=args.repeat,
            event_dir=event_dir,
        ):
            step = run_step(spec, log_dir, env=env)
            steps.append(step)
            raw = split_key_value_stdout(str(step.get("stdout", "")), "csv")
            summary = split_key_value_stdout(str(step.get("stdout", "")), "summary_csv")
            if raw:
                retr_raws.append(raw)
            if summary:
                retr_summaries.append(summary)

    analyze = run_step(
        analyzer_step(raw_csvs=retr_raws, summary_csvs=retr_summaries, report_path=report_path),
        log_dir,
        env=env,
    )
    steps.append(analyze)

    retr_cases = 0
    retr_failures = 0
    for step in steps:
        if str(step["name"]).startswith("retr_"):
            cases, failures = parse_cases(str(step.get("stdout", "")))
            retr_cases += cases
            retr_failures += failures
    grouped_failures = summary_fail_count(retr_summaries)
    mismatches = hash_mismatch_count(retr_raws)
    step_failures = [step for step in steps if step["result"] != "pass"]
    result = "pass" if not step_failures and grouped_failures == 0 and mismatches == 0 else "fail"

    summary = {
        "timestamp": timestamp_utc(),
        "result": result,
        "bytes_list": [str(value) for value in bytes_values],
        "repeat": args.repeat,
        "retr_raw_csvs": retr_raws,
        "retr_summary_csvs": retr_summaries,
        "retr_transfer_cases": retr_cases,
        "retr_transfer_failures": retr_failures,
        "grouped_fail_count": grouped_failures,
        "hash_mismatch_count": mismatches,
        "report": str(report_path),
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
        "defaults_unchanged": DEFAULTS_UNCHANGED,
    }
    summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"json={summary_json}")
    print(f"report={report_path}")
    for raw in retr_raws:
        print(f"retr_raw_csv={raw}")
    for summary_path in retr_summaries:
        print(f"retr_summary_csv={summary_path}")
    print(f"retr_transfer_cases={retr_cases} retr_transfer_failures={retr_failures}")
    print(f"grouped_fail_count={grouped_failures}")
    print(f"hash_mismatch_count={mismatches}")
    print(f"result={result}")
    return 0 if result == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
