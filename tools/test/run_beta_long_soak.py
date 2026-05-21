#!/usr/bin/env python3
"""Beta long-soak wrapper built from existing local GridFlux smoke tools."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SoakCase:
    name: str
    script: str
    category: str


BASE_CASES = {
    "stor": SoakCase("stor", "tools/test/run_gridftp_control_stor_smoke.py", "transfer"),
    "retr": SoakCase("retr", "tools/test/run_gridftp_control_retr_smoke.py", "transfer"),
    "stor_resume": SoakCase("stor_resume", "tools/test/run_gridftp_control_resume_smoke.py", "resume"),
    "retr_resume": SoakCase("retr_resume", "tools/test/run_gridftp_control_retr_resume_smoke.py", "resume"),
    "tree_upload": SoakCase("tree_upload", "tools/test/run_gridftp_tree_upload_smoke.py", "tree"),
    "tree_download": SoakCase("tree_download", "tools/test/run_gridftp_tree_download_smoke.py", "tree"),
    "token_auth": SoakCase("token_auth", "tools/test/run_gridftp_control_token_smoke.py", "auth"),
    "control_tls": SoakCase("control_tls", "tools/test/run_gridftp_control_tls_smoke.py", "tls"),
    "data_tls": SoakCase("data_tls", "tools/test/run_gridftp_data_tls_smoke.py", "data_tls"),
}

PROFILE_CASE_NAMES = {
    "tiny": ["stor", "retr"],
    "small": ["stor", "retr", "stor_resume", "retr_resume"],
    "standard": [
        "stor",
        "retr",
        "stor_resume",
        "retr_resume",
        "tree_upload",
        "tree_download",
        "token_auth",
        "control_tls",
        "data_tls",
    ],
}


def cases_for_profile(
    profile: str,
    *,
    include_token: bool = False,
    include_tls: bool = False,
    include_data_tls: bool = False,
) -> list[SoakCase]:
    names = list(PROFILE_CASE_NAMES[profile])
    if profile != "standard":
        for enabled, name in [
            (include_token, "token_auth"),
            (include_tls, "control_tls"),
            (include_data_tls, "data_tls"),
        ]:
            if enabled and name not in names:
                names.append(name)
    return [BASE_CASES[name] for name in names]


def case_command(case: SoakCase, build_dir: str) -> list[str]:
    return [sys.executable, str(REPO_ROOT / case.script), "--build-dir", build_dir]


def classify_error(text: str) -> str:
    lowered = text.lower()
    if not lowered:
        return "unknown_error"
    if "checksum" in lowered and ("mismatch" in lowered or "failed" in lowered):
        return "checksum_mismatch"
    if "hash mismatch" in lowered or "sha256" in lowered and "mismatch" in lowered:
        return "hash_mismatch"
    if "token" in lowered or "auth" in lowered or "login" in lowered:
        return "auth_error"
    if any(word in lowered for word in ["tls", "ssl", "certificate", "private key"]):
        return "tls_error"
    if any(word in lowered for word in ["connect", "socket", "recv", "send", "port"]):
        return "network_error"
    if any(word in lowered for word in ["open", "read", "write", "stat"]):
        return "io_error"
    if "timeout" in lowered:
        return "timeout"
    return "unknown_error"


def merge_error_count(target: dict[str, int], key: str) -> None:
    target[key] = target.get(key, 0) + 1


def extract_total_bytes(text: str) -> int:
    total = 0
    for pattern in [r"\btotal_bytes=(\d+)\b", r"\bbytes=(\d+)\b"]:
        for match in re.finditer(pattern, text):
            try:
                total += int(match.group(1))
            except ValueError:
                continue
    return total


def extract_event_log_paths(text: str) -> list[str]:
    paths: set[str] = set()
    for pattern in [r"\bevent_log(?:_path)?=([^\s]+)", r"([^\s]+\.jsonl)"]:
        for match in re.finditer(pattern, text):
            paths.add(match.group(1).strip())
    return sorted(paths)


def write_runner_event(event_log: Path, payload: dict[str, object]) -> None:
    event_log.parent.mkdir(parents=True, exist_ok=True)
    with event_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def run_case(
    *,
    case: SoakCase,
    iteration: int,
    build_dir: str,
    results_dir: Path,
    event_log_dir: Path,
) -> dict[str, object]:
    safe_name = f"iter{iteration:04d}_{case.name}"
    wrapper_log = results_dir / f"{safe_name}.log"
    event_log = event_log_dir / f"{safe_name}.jsonl"
    command = case_command(case, build_dir)
    start = time.monotonic()
    write_runner_event(
        event_log,
        {
            "event": "beta_soak_case_start",
            "case": case.name,
            "iteration": iteration,
            "timestamp": time.time(),
        },
    )
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed = time.monotonic() - start
    combined = completed.stdout + completed.stderr
    wrapper_log.write_text("$ " + " ".join(command) + "\n\n" + combined, encoding="utf-8")
    status = "pass" if completed.returncode == 0 else "fail"
    error_code = "ok" if status == "pass" else classify_error(combined)
    write_runner_event(
        event_log,
        {
            "event": "beta_soak_case_end",
            "case": case.name,
            "elapsed_seconds": elapsed,
            "error_code": error_code,
            "iteration": iteration,
            "returncode": completed.returncode,
            "status": status,
            "timestamp": time.time(),
        },
    )
    parsed_event_logs = extract_event_log_paths(combined)
    event_logs = [str(event_log), *parsed_event_logs]
    return {
        "iteration": iteration,
        "case": case.name,
        "category": case.category,
        "command": " ".join(command),
        "status": status,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "error_code": error_code,
        "bytes": extract_total_bytes(combined),
        "log_path": str(wrapper_log),
        "event_log_paths": event_logs,
        "server_log_paths": [],
        "client_log_paths": [],
    }


def summarize(
    *,
    args: argparse.Namespace,
    cases: list[SoakCase],
    case_results: list[dict[str, object]],
    attempted_iterations: int,
    elapsed: float,
) -> dict[str, object]:
    pass_count = sum(1 for result in case_results if result.get("status") == "pass")
    fail_count = sum(1 for result in case_results if result.get("status") != "pass")
    first_failure = next((result for result in case_results if result.get("status") != "pass"), None)
    error_counts: dict[str, int] = {}
    for result in case_results:
        if result.get("status") != "pass":
            merge_error_count(error_counts, str(result.get("error_code", "unknown_error")))
    event_logs: list[str] = []
    server_logs: list[str] = []
    client_logs: list[str] = []
    for result in case_results:
        event_logs.extend(str(path) for path in result.get("event_log_paths", []) if path)
        server_logs.extend(str(path) for path in result.get("server_log_paths", []) if path)
        client_logs.extend(str(path) for path in result.get("client_log_paths", []) if path)
    return {
        "result": "pass" if fail_count == 0 and attempted_iterations > 0 else "fail",
        "profile": args.profile,
        "requested_iterations": args.iterations,
        "duration_seconds": args.duration_seconds,
        "iterations": attempted_iterations,
        "case_names": [case.name for case in cases],
        "case_count_per_iteration": len(cases),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "first_failure": first_failure,
        "total_bytes": sum(int(result.get("bytes", 0) or 0) for result in case_results),
        "elapsed_seconds": elapsed,
        "error_code_counts": error_counts,
        "event_log_paths": sorted(set(event_logs)),
        "server_log_paths": sorted(set(server_logs)),
        "client_log_paths": sorted(set(client_logs)),
        "case_log_paths": [str(result.get("log_path", "")) for result in case_results],
        "case_results": case_results,
        "default_strategy": {
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
        },
    }


def run_soak(args: argparse.Namespace) -> int:
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    output = Path(args.json_output) if args.json_output else results_dir / f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}_beta-long-soak.json"
    event_log_dir = Path(args.event_log_dir) if args.event_log_dir else results_dir / "beta_long_soak_events"
    event_log_dir.mkdir(parents=True, exist_ok=True)
    cases = cases_for_profile(
        args.profile,
        include_token=args.include_token,
        include_tls=args.include_tls,
        include_data_tls=args.include_data_tls,
    )
    case_results: list[dict[str, object]] = []
    start = time.monotonic()
    attempted_iterations = 0
    for iteration in range(1, args.iterations + 1):
        if args.duration_seconds and attempted_iterations > 0 and time.monotonic() - start >= args.duration_seconds:
            break
        attempted_iterations += 1
        for case in cases:
            result = run_case(
                case=case,
                iteration=iteration,
                build_dir=args.build_dir,
                results_dir=results_dir,
                event_log_dir=event_log_dir,
            )
            case_results.append(result)
            if result.get("status") != "pass":
                summary = summarize(
                    args=args,
                    cases=cases,
                    case_results=case_results,
                    attempted_iterations=attempted_iterations,
                    elapsed=max(time.monotonic() - start, 0.000001),
                )
                output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                print(f"beta_long_soak_json={output}")
                print("result=fail")
                return 1
    summary = summarize(
        args=args,
        cases=cases,
        case_results=case_results,
        attempted_iterations=attempted_iterations,
        elapsed=max(time.monotonic() - start, 0.000001),
    )
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"beta_long_soak_json={output}")
    print(f"result={summary['result']}")
    return 0 if summary["result"] == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local GridFlux beta long soak from existing smoke tools.")
    parser.add_argument("--build-dir", default="build")
    parser.add_argument("--duration-seconds", type=float, default=0.0)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--profile", choices=["tiny", "small", "standard"], default="tiny")
    parser.add_argument("--include-token", action="store_true")
    parser.add_argument("--include-tls", action="store_true")
    parser.add_argument("--include-data-tls", action="store_true")
    parser.add_argument("--json-output", default="")
    parser.add_argument("--event-log-dir", default="")
    parser.add_argument("--results-dir", default="tools/perf/results")
    args = parser.parse_args()
    if args.iterations <= 0:
        raise SystemExit("--iterations must be positive")
    if args.duration_seconds < 0:
        raise SystemExit("--duration-seconds must be non-negative")
    return run_soak(args)


if __name__ == "__main__":
    raise SystemExit(main())
