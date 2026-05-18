#!/usr/bin/env python3
"""Run the GridFlux alpha release gate by orchestrating existing checks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path


EXCLUDED_HASH_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "tools/perf/results",
}
EXCLUDED_HASH_NAMES = {
    "AGENTS.md",
    "CMakeCache.txt",
    "CTestTestfile.cmake",
    "build.ninja",
    "cmake_install.cmake",
    "compile_commands.json",
}


@dataclass
class StepResult:
    name: str
    status: str
    returncode: int
    log: str
    elapsed_seconds: float


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def compact_timestamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def timestamp_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def is_build_like(part: str) -> bool:
    return part == "build" or part.startswith("build-") or part.startswith("cmake-build-")


def should_hash_file(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    joined = "/".join(relative.parts)
    if any(part in EXCLUDED_HASH_PARTS or is_build_like(part) for part in relative.parts):
        return False
    if joined.startswith("tools/perf/results/"):
        return False
    if path.name in EXCLUDED_HASH_NAMES:
        return False
    if path.suffix in {".pyc", ".o", ".a", ".so", ".log", ".tmp", ".bin"}:
        return False
    return path.is_file()


def source_tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not should_hash_file(path, root):
            continue
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8") + b"\0")
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def git_status(root: Path) -> dict[str, str]:
    def run_git(args: list[str]) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else ""

    return {
        "head": run_git(["rev-parse", "HEAD"]),
        "status_short": run_git(["status", "--short"]),
    }


def run_step(name: str, command: list[str], log_dir: Path, *, cwd: Path) -> StepResult:
    log_path = log_dir / f"{name}.log"
    start = time.monotonic()
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    elapsed = time.monotonic() - start
    log_path.write_text(
        "$ " + " ".join(command) + "\n\n" + completed.stdout + completed.stderr,
        encoding="utf-8",
    )
    return StepResult(
        name=name,
        status="pass" if completed.returncode == 0 else "fail",
        returncode=completed.returncode,
        log=str(log_path),
        elapsed_seconds=elapsed,
    )


def ctest_counts(log_path: Path) -> dict[str, int | str]:
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    match = re.search(r"(\d+)% tests passed, (\d+) tests failed out of (\d+)", text)
    if match:
        return {
            "passed_percent": int(match.group(1)),
            "failed": int(match.group(2)),
            "total": int(match.group(3)),
        }
    match = re.search(r"Total Test time.*\n\n(?:.*\n)*?(\d+)% tests passed", text)
    return {"summary": match.group(0) if match else ""}


def parse_matrix_summary(path: Path) -> dict[str, str | int | list[dict[str, str]]]:
    if not path.exists():
        return {"status": "missing", "rows": 0, "fail_count": -1, "default_baseline": []}
    rows: list[dict[str, str]]
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    fail_count = 0
    for row in rows:
        try:
            fail_count += int(row.get("fail_count", "0") or "0")
        except ValueError:
            fail_count += 1
    default_rows = [
        row
        for row in rows
        if row.get("file_io_backend") == "posix"
        and row.get("file_io_buffer_size") == "0"
        and row.get("posix_write_strategy") == "auto"
        and row.get("manifest_flush_policy") == "every_n_chunks"
        and row.get("manifest_flush_interval_chunks") == "16"
        and row.get("commit_sync_policy") == "none"
        and row.get("final_verify_policy") == "full"
        and row.get("checksum_algorithm") == "crc32c"
    ]
    return {
        "status": "pass" if fail_count == 0 and rows else "fail",
        "rows": len(rows),
        "fail_count": fail_count,
        "default_baseline": default_rows,
    }


def find_latest_matrix_csvs(results_dir: Path, before: set[Path]) -> tuple[str, str]:
    after = set(results_dir.glob("*_gridftp-private-matrix-*.csv"))
    new_files = sorted(after - before, key=lambda path: path.stat().st_mtime)
    raw = [path for path in new_files if not path.name.endswith("-summary.csv")]
    summary = [path for path in new_files if path.name.endswith("-summary.csv")]
    return (str(raw[-1]) if raw else "", str(summary[-1]) if summary else "")


def ssh_prefix(remote: str) -> list[str]:
    if os.environ.get("GRIDFLUX_SSH_PASSWORD"):
        return ["sshpass", "-e", "ssh", "-o", "StrictHostKeyChecking=no", remote]
    return ["ssh", "-o", "StrictHostKeyChecking=no", remote]


def run_remote_process_check(remote: str | None) -> dict[str, str]:
    pattern = "'[g]ridflux-gridftp-server|[g]ridflux-file-'"
    local = subprocess.run(
        ["bash", "-lc", f"pgrep -af {pattern} || true"],
        text=True,
        capture_output=True,
        check=False,
    ).stdout.strip()
    remote_text = ""
    if remote:
        env = os.environ.copy()
        if env.get("GRIDFLUX_SSH_PASSWORD") and not env.get("SSHPASS"):
            env["SSHPASS"] = env["GRIDFLUX_SSH_PASSWORD"]
        remote_text = subprocess.run(
            ssh_prefix(remote) + [f"pgrep -af {pattern} || true"],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        ).stdout.strip()
    return {"local": local, "remote": remote_text}


def sync_artifacts(remote: str, remote_root: str, root: Path, artifacts: list[str]) -> StepResult:
    log_dir = root / "tools" / "perf" / "results"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{compact_timestamp()}_alpha-artifact-rsync.log"
    existing = [artifact for artifact in artifacts if (root / artifact).exists()]
    if not existing:
        log_path.write_text("no artifacts to sync\n", encoding="utf-8")
        return StepResult("artifact_rsync", "pass", 0, str(log_path), 0.0)
    command = [
        "rsync",
        "-az",
        "-e",
        "ssh -o StrictHostKeyChecking=no",
        "--relative",
        *existing,
        f"{remote}:{remote_root.rstrip('/')}/",
    ]
    if os.environ.get("GRIDFLUX_SSH_PASSWORD"):
        command = ["sshpass", "-e", *command]
    start = time.monotonic()
    env = os.environ.copy()
    if env.get("GRIDFLUX_SSH_PASSWORD") and not env.get("SSHPASS"):
        env["SSHPASS"] = env["GRIDFLUX_SSH_PASSWORD"]
    completed = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    elapsed = time.monotonic() - start
    log_path.write_text(
        "$ " + " ".join(command) + "\n\n" + completed.stdout + completed.stderr,
        encoding="utf-8",
    )
    return StepResult(
        "artifact_rsync",
        "pass" if completed.returncode == 0 else "fail",
        completed.returncode,
        str(log_path),
        elapsed,
    )


def normalize_artifact_path(value: str, root: Path) -> str | None:
    if not value:
        return None
    parsed = Path(value)
    if parsed.is_absolute():
        try:
            return parsed.resolve().relative_to(root).as_posix()
        except ValueError:
            return None
    if ".." in parsed.parts:
        return None
    return parsed.as_posix()


def csv_referenced_artifacts(csv_text: str, root: Path) -> list[str]:
    normalized = normalize_artifact_path(csv_text, root)
    if not normalized:
        return []
    path = root / normalized
    result = {normalized}
    if not path.exists():
        return sorted(result)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            for field, value in row.items():
                if field.endswith("_log") or field in {
                    "server_log",
                    "client_log",
                    "server_env_before_log",
                    "server_env_after_log",
                    "client_env_before_log",
                    "client_env_after_log",
                }:
                    referenced = normalize_artifact_path(value.strip(), root)
                    if referenced:
                        result.add(referenced)
    return sorted(result)


def write_markdown_report(path: Path, report: dict[str, object]) -> None:
    steps = report["steps"]  # type: ignore[index]
    assert isinstance(steps, list)
    private_matrix = report.get("private_matrix", {})
    residual = report.get("residual_process_check", {})
    lines = [
        "# GridFlux Alpha Release Gate",
        "",
        f"- Timestamp: `{report['timestamp']}`",
        f"- Mode: `{report['mode']}`",
        f"- Source tree hash: `{report['source_tree_hash']}`",
        f"- Result: `{'pass' if report['passed'] else 'fail'}`",
        "",
        "## Step Results",
        "",
        "| Step | Status | Seconds | Log |",
        "|------|--------|---------|-----|",
    ]
    for step in steps:
        lines.append(
            f"| `{step['name']}` | `{step['status']}` | `{step['elapsed_seconds']:.2f}` | `{step['log']}` |"
        )
    lines.extend(["", "## Private Baseline", ""])
    if isinstance(private_matrix, dict) and private_matrix:
        lines.extend(
            [
                f"- Raw CSV: `{private_matrix.get('raw_csv', '')}`",
                f"- Summary CSV: `{private_matrix.get('summary_csv', '')}`",
                f"- Fail count: `{private_matrix.get('fail_count', '')}`",
                f"- Summary rows: `{private_matrix.get('rows', '')}`",
            ]
        )
        default_rows = private_matrix.get("default_baseline", [])
        if isinstance(default_rows, list) and default_rows:
            lines.extend(["", "Default baseline rows:", ""])
            for row in default_rows:
                if isinstance(row, dict):
                    lines.append(
                        "- "
                        f"direction={row.get('direction')} "
                        f"throughput_median={row.get('throughput_gbps_median')} "
                        f"spread_pct={row.get('throughput_gbps_spread_pct')}"
                    )
    else:
        lines.append("- Not run in quick mode.")
    lines.extend(
        [
            "",
            "## Alpha Readiness",
            "",
            "- Alpha scope is demonstrable GridFTP-like framed STOR/RETR, bidirectional resume, CRC32C chunk verification, and control metadata commands.",
            "- Not beta/production: performance spread remains significant, 100G dedicated-line validation is not complete, and TLS/GSI/raw FTP stream/directory sync are out of scope.",
            "- Defaults remain POSIX backend, full final verify, every_n_chunks manifest flush, no commit fsync, no preallocate full, and no default io_uring.",
            "",
            "## Residual Process Check",
            "",
            f"- Local: `{residual.get('local', '') if isinstance(residual, dict) else ''}`",
            f"- Remote: `{residual.get('remote', '') if isinstance(residual, dict) else ''}`",
            "",
            "## Failures",
            "",
        ]
    )
    failures = report.get("failures", [])
    if isinstance(failures, list) and failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- None.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def relative_to_root(path: str, root: Path) -> str:
    if not path:
        return ""
    parsed = Path(path)
    if parsed.is_absolute():
        try:
            return parsed.resolve().relative_to(root).as_posix()
        except ValueError:
            return path
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GridFlux alpha release gate.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--build-dir", default="build")
    parser.add_argument("--io-uring-build-dir", default="build-io-uring-real")
    parser.add_argument("--remote")
    parser.add_argument("--remote-root", default="/root/projects/GridFlux")
    parser.add_argument("--server-host")
    parser.add_argument("--results-dir", default="tools/perf/results")
    args = parser.parse_args()

    if args.full and (not args.remote or not args.server_host):
        raise SystemExit("--full requires --remote and --server-host")

    root = repo_root()
    results_dir = root / args.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = compact_timestamp()
    log_dir = results_dir / f"{timestamp}_alpha-release-gate"
    log_dir.mkdir(parents=True, exist_ok=True)
    report_path = root / "docs" / "release" / "ALPHA_RELEASE_GATE.md"
    json_path = results_dir / f"{timestamp}_alpha-release-gate.json"

    steps: list[StepResult] = []
    matrix_raw = ""
    matrix_summary = ""
    private_matrix: dict[str, object] = {}

    command_specs = [
        ("build_debug", ["cmake", "--build", args.build_dir]),
        ("ctest_debug", ["ctest", "--test-dir", args.build_dir, "--output-on-failure"]),
        ("ctest_iouring", ["ctest", "--test-dir", args.io_uring_build_dir, "--output-on-failure"]),
        (
            "ctest_iouring_smoke",
            [
                "ctest",
                "--test-dir",
                args.io_uring_build_dir,
                "-R",
                "FileIoTest.IoUringContextReadWriteSmokeWhenAvailable",
                "--output-on-failure",
            ],
        ),
        (
            "public_export_hygiene",
            [
                sys.executable,
                "tools/release/export_public_repo.py",
                "--output",
                f"/tmp/gridflux-public-alpha-{timestamp}",
                "--force",
            ],
        ),
        ("stor_smoke", [sys.executable, "tools/test/run_gridftp_control_stor_smoke.py", "--build-dir", args.build_dir]),
        ("retr_smoke", [sys.executable, "tools/test/run_gridftp_control_retr_smoke.py", "--build-dir", args.build_dir]),
        ("stor_resume_smoke", [sys.executable, "tools/test/run_gridftp_control_resume_smoke.py", "--build-dir", args.build_dir]),
        ("retr_resume_smoke", [sys.executable, "tools/test/run_gridftp_control_retr_resume_smoke.py", "--build-dir", args.build_dir]),
        ("metadata_smoke", [sys.executable, "tools/test/run_gridftp_control_metadata_smoke.py", "--build-dir", args.build_dir]),
        ("list_smoke", [sys.executable, "tools/test/run_gridftp_control_list_smoke.py", "--build-dir", args.build_dir]),
    ]
    for name, command in command_specs:
        step = run_step(name, command, log_dir, cwd=root)
        steps.append(step)

    if args.full:
        before = set(results_dir.glob("*_gridftp-private-matrix-*.csv"))
        matrix_command = [
            sys.executable,
            "tools/perf/run_gridftp_private_matrix.py",
            "--smoke",
            "--directions",
            "stor,retr",
            "--bytes",
            "1073741824",
            "--connections",
            "8",
            "--chunk-sizes",
            "4194304",
            "--buffer-sizes",
            "262144",
            "--checksums",
            "crc32c,none",
            "--checksum-backend",
            "auto",
            "--file-io-backends",
            "posix",
            "--file-io-buffer-sizes",
            "0",
            "--posix-write-strategies",
            "auto",
            "--file-io-advices",
            "off",
            "--preallocates",
            "off",
            "--manifest-flush-policies",
            "every_n_chunks",
            "--manifest-flush-interval-chunks-list",
            "16",
            "--commit-sync-policies",
            "none",
            "--final-verify-policies",
            "full,verified_chunks",
            "--repeat",
            "3",
            "--remote",
            args.remote,
            "--server-host",
            args.server_host,
            "--local-build-dir",
            str((root / args.io_uring_build_dir).resolve()),
            "--remote-build-dir",
            f"{args.remote_root.rstrip('/')}/{args.io_uring_build_dir}",
            "--output-dir",
            args.results_dir,
            "--case-timeout",
            "900",
        ]
        matrix_step = run_step("private_baseline_matrix", matrix_command, log_dir, cwd=root)
        steps.append(matrix_step)
        matrix_raw, matrix_summary = find_latest_matrix_csvs(results_dir, before)
        private_matrix = parse_matrix_summary(Path(matrix_summary))
        private_matrix["raw_csv"] = relative_to_root(matrix_raw, root)
        private_matrix["summary_csv"] = relative_to_root(matrix_summary, root)

    residual = run_remote_process_check(args.remote)

    artifact_paths = [
        "INDEX.md",
        "docs/ROADMAP.md",
        "docs/PROJECT_STATE.md",
        "docs/release/ALPHA_RELEASE_GATE.md",
        "docs/release/ALPHA_READINESS.md",
        relative_to_root(str(json_path), root),
    ]
    if matrix_raw:
        artifact_paths.extend(csv_referenced_artifacts(relative_to_root(matrix_raw, root), root))
    if matrix_summary:
        artifact_paths.extend(csv_referenced_artifacts(relative_to_root(matrix_summary, root), root))
    artifact_paths = sorted({path for path in artifact_paths if path})

    report: dict[str, object] = {
        "timestamp": timestamp_utc(),
        "mode": "full" if args.full else "quick",
        "source_tree_hash": source_tree_hash(root),
        "git": git_status(root),
        "steps": [asdict(step) for step in steps],
        "ctest": {
            step.name: ctest_counts(Path(step.log))
            for step in steps
            if step.name.startswith("ctest_")
        },
        "private_matrix": private_matrix,
        "hygiene": next((asdict(step) for step in steps if step.name == "public_export_hygiene"), {}),
        "artifact_sync": {},
        "residual_process_check": residual,
        "failures": [],
        "passed": False,
    }
    write_markdown_report(report_path, report)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.remote:
        sync_step = sync_artifacts(args.remote, args.remote_root, root, artifact_paths)
        steps.append(sync_step)
        sync_json = log_dir / "remote-artifact-sync.json"
        sync_command = [
            sys.executable,
            "tools/release/check_remote_artifact_sync.py",
            "--remote",
            args.remote,
            "--local-root",
            str(root),
            "--remote-root",
            args.remote_root,
            "--json-output",
            str(sync_json),
        ]
        for path in artifact_paths:
            sync_command.extend(["--path", path])
        if matrix_raw:
            sync_command.extend(["--csv", relative_to_root(matrix_raw, root)])
        if matrix_summary:
            sync_command.extend(["--csv", relative_to_root(matrix_summary, root)])
        sync_check = run_step("remote_artifact_sync_check", sync_command, log_dir, cwd=root)
        steps.append(sync_check)
        report["artifact_sync"] = {
            "rsync": asdict(sync_step),
            "check": asdict(sync_check),
            "json": str(sync_json),
        }

    failures = [step.name for step in steps if step.status != "pass"]
    if residual.get("local") or residual.get("remote"):
        failures.append("residual_process_check")
    if private_matrix and private_matrix.get("status") == "fail":
        failures.append("private_matrix")
    report["steps"] = [asdict(step) for step in steps]
    report["failures"] = failures
    report["passed"] = not failures
    write_markdown_report(report_path, report)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"alpha_release_gate_report={report_path}")
    print(f"alpha_release_gate_json={json_path}")
    print(f"result={'pass' if report['passed'] else 'fail'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
