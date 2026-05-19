#!/usr/bin/env python3
"""Run the Beta 1A private 100G-readiness diagnostic package."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def compact_timestamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def run_step(name: str, command: list[str], log_dir: Path) -> dict[str, object]:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{name}.log"
    start = time.monotonic()
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    elapsed = time.monotonic() - start
    log_path.write_text("$ " + " ".join(command) + "\n\n" + completed.stdout + completed.stderr, encoding="utf-8")
    return {
        "name": name,
        "command": command,
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


def parse_bytes_list(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def default_single_args(args: argparse.Namespace) -> dict[str, str]:
    if args.smoke:
        return {
            "directions": "stor,retr",
            "bytes": args.bytes or "1073741824",
            "connections": "1,4,8",
            "backends": "posix,io_uring",
            "repeat": str(args.repeat),
        }
    return {
        "directions": "stor,retr,stor-resume,retr-resume",
        "bytes": args.bytes or "1073741824,4294967296",
        "connections": "1,2,4,8",
        "backends": "posix,io_uring",
        "repeat": str(args.repeat),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Beta 1A private readiness diagnostics.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--remote", default="root@<redacted>")
    parser.add_argument("--server-host", default="<redacted>")
    parser.add_argument("--local-build-dir", default="/root/projects/GridFlux/build-io-uring-real")
    parser.add_argument("--remote-build-dir", default="/root/projects/GridFlux/build-io-uring-real")
    parser.add_argument("--output-dir", default="tools/perf/results")
    parser.add_argument("--bytes", default="")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--case-timeout", type=int, default=1800)
    parser.add_argument("--include-large-tree", action="store_true")
    parser.add_argument("--skip-host-baseline", action="store_true")
    args = parser.parse_args()
    if args.repeat <= 0:
        raise SystemExit("--repeat must be greater than zero")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = compact_timestamp()
    log_dir = output_dir / f"{run_id}_beta1a-readiness"
    event_dir = log_dir / "events"
    summary_json = output_dir / f"{run_id}_beta1a-readiness.json"
    report_path = Path("docs/perf/BETA1A_100G_READINESS.md")

    steps: list[dict[str, object]] = []
    host_csv = ""
    if not args.skip_host_baseline:
        baseline_bytes = parse_bytes_list(args.bytes or "1073741824")[0]
        step = run_step(
            "host_baseline",
            [
                sys.executable,
                "tools/perf/run_private_host_baseline.py",
                "--remote",
                args.remote,
                "--server-host",
                args.server_host,
                "--local-build-dir",
                args.local_build_dir,
                "--remote-build-dir",
                args.remote_build_dir,
                "--bytes",
                baseline_bytes,
                "--output-dir",
                args.output_dir,
            ],
            log_dir,
        )
        steps.append(step)
        host_csv = extract_path(str(step.get("stdout", "")), "csv")

    single_defaults = default_single_args(args)
    single_step = run_step(
        "single_file_private_matrix",
        [
            sys.executable,
            "tools/perf/run_gridftp_private_matrix.py",
            "--smoke" if args.smoke else "--full",
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
            single_defaults["directions"],
            "--bytes",
            single_defaults["bytes"],
            "--connections",
            single_defaults["connections"],
            "--chunk-sizes",
            "4194304",
            "--buffer-sizes",
            "262144",
            "--checksums",
            "crc32c,none",
            "--checksum-backend",
            "auto",
            "--file-io-backends",
            single_defaults["backends"],
            "--file-io-queue-depths",
            "1",
            "--file-io-batch-sizes",
            "1",
            "--tls-modes",
            "off,required",
            "--data-tls-modes",
            "off,required",
            "--event-log-dir",
            str(event_dir),
            "--repeat",
            single_defaults["repeat"],
            "--case-timeout",
            str(args.case_timeout),
        ],
        log_dir,
    )
    steps.append(single_step)
    single_raw = extract_path(str(single_step.get("stdout", "")), "csv")
    single_summary = extract_path(str(single_step.get("stdout", "")), "summary_csv")

    tree_datasets = "mixed"
    if args.full and args.include_large_tree:
        tree_datasets = "mixed,large"
    tree_step = run_step(
        "tree_private_matrix",
        [
            sys.executable,
            "tools/perf/run_gridftp_tree_private_matrix.py",
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
            "--datasets",
            tree_datasets,
            "--directions",
            "upload,download",
            "--file-parallelisms",
            "1,2,4",
            "--connections",
            "4",
            "--checksums",
            "crc32c,none",
            "--checksum-backend",
            "auto",
            "--tls-modes",
            "off,required",
            "--data-tls-modes",
            "off,required",
            "--file-io-backends",
            "posix,io_uring",
            "--file-io-queue-depths",
            "1",
            "--file-io-batch-sizes",
            "1",
            "--event-log-dir",
            str(event_dir),
            "--repeat",
            str(args.repeat),
            "--chunk-size",
            "4194304",
            "--buffer-size",
            "262144",
            "--case-timeout",
            str(args.case_timeout),
        ],
        log_dir,
    )
    steps.append(tree_step)
    tree_raw = extract_path(str(tree_step.get("stdout", "")), "raw_csv")
    tree_summary = extract_path(str(tree_step.get("stdout", "")), "summary_csv")

    analyze_command = [
        sys.executable,
        "tools/perf/analyze_beta1a.py",
        "--output",
        str(report_path),
    ]
    if host_csv:
        analyze_command.extend(["--host-baseline-csv", host_csv])
    if single_summary:
        analyze_command.extend(["--single-summary-csv", single_summary])
    if tree_summary:
        analyze_command.extend(["--tree-summary-csv", tree_summary])
    analyze_step = run_step("analyze_beta1a", analyze_command, log_dir)
    steps.append(analyze_step)

    failures = [step for step in steps if step["result"] != "pass"]
    result = {
        "timestamp": run_id,
        "mode": "smoke" if args.smoke else "full",
        "result": "pass" if not failures else "fail",
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
        "host_baseline_csv": host_csv,
        "single_raw_csv": single_raw,
        "single_summary_csv": single_summary,
        "tree_raw_csv": tree_raw,
        "tree_summary_csv": tree_summary,
        "report": str(report_path),
        "defaults_unchanged": {
            "auth_mode": "anonymous",
            "tls_mode": "off",
            "data_tls_mode": "off",
            "file_io_backend": "posix",
            "final_verify_policy": "full",
            "manifest_flush_policy": "every_n_chunks",
            "preallocate": "off",
            "posix_write_strategy": "auto",
        },
    }
    summary_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"json={summary_json}")
    print(f"report={report_path}")
    if host_csv:
        print(f"host_baseline_csv={host_csv}")
    print(f"single_raw_csv={single_raw}")
    print(f"single_summary_csv={single_summary}")
    print(f"tree_raw_csv={tree_raw}")
    print(f"tree_summary_csv={tree_summary}")
    print(f"result={result['result']}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
