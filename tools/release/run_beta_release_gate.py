#!/usr/bin/env python3
"""Run the GridFlux beta release gate closeout package."""

from __future__ import annotations

import argparse
import csv
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import remote_auth
import run_alpha_release_gate as alpha
import sync_remote_artifacts


DEFAULT_STRATEGY = {
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
}

BETA_DOCS = [
    "docs/release/BETA_RELEASE_GATE.md",
    "docs/release/BETA_RELEASE_CANDIDATE.md",
    "docs/release/BETA_LIMITATIONS.md",
    "docs/perf/BETA_PERFORMANCE_SUMMARY.md",
    "docs/perf/100G_MIGRATION_CHECKLIST.md",
    "docs/perf/BETA1A_100G_READINESS.md",
    "docs/perf/BETA1B_DATA_TLS_RESUME_AND_STOR_WRITE.md",
    "docs/perf/BETA1B_STOR_WRITEBACK_DIAGNOSIS.md",
    "docs/perf/BETA1B_RECEIVER_WRITEBACK_OPTIN.md",
    "docs/perf/BETA1B_RECEIVER_WRITEBACK_STABILITY.md",
    "docs/perf/BETA1B_STORAGE_SYSTEM_ATTRIBUTION.md",
    "docs/perf/BETA1C_RETR_STABILITY.md",
    "docs/perf/BASELINE_FTP_GRIDFTP_SMOKE.md",
    "docs/perf/FTP_GRIDFTP_GRIDFLUX_COMPARISON.md",
]

BETA_TOOLS = [
    "tools/release/run_beta_release_gate.py",
    "tools/release/run_beta_release_candidate.py",
    "tools/release/test_beta_release_helpers.py",
    "tools/perf/run_beta1b_storage_system_probe.py",
    "tools/perf/analyze_beta1b_storage_system.py",
    "tools/perf/run_beta1c_retr_stability.py",
    "tools/perf/analyze_beta1c_retr_stability.py",
    "tools/perf/run_baseline_ftp_gridftp_smoke.py",
    "tools/perf/run_three_way_ftp_gridftp_gridflux.py",
    "tools/perf/plot_three_way_comparison.py",
]

RESIDUAL_PATTERN = "'[g]ridflux-gridftp-server|[g]ridflux-file-'"


def default_strategy_summary() -> dict[str, str]:
    return dict(DEFAULT_STRATEGY)


def acquire_beta_lock(results_dir: Path):
    lock_path = results_dir / ".beta-release-gate.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise SystemExit(f"another beta release gate is already running: {lock_path}") from exc
    handle.write(f"pid={os.getpid()} timestamp={alpha.timestamp_utc()}\n")
    handle.flush()
    return handle


def read_json_if_exists(path: Path | str) -> dict[str, object]:
    parsed = Path(path)
    if not parsed.exists():
        return {}
    try:
        data = json.loads(parsed.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def latest_by_mtime(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def parse_output_paths(log_text: str, keys: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in keys:
        match = re.search(rf"^{re.escape(key)}=(.+)$", log_text, flags=re.MULTILINE)
        if match:
            result[key] = match.group(1).strip()
    return result


def parse_iouring_smoke_passed(log_text: str) -> bool:
    pattern = "FileIoTest.IoUringContextReadWriteSmokeWhenAvailable"
    lines = [line for line in log_text.splitlines() if pattern in line]
    if not lines:
        return False
    return any("Passed" in line and "Skipped" not in line for line in lines)


def run_remote_shell_step(
    name: str,
    shell_command: str,
    log_dir: Path,
    *,
    remote: str,
    root: Path,
) -> alpha.StepResult:
    command = remote_auth.ssh_prefix(remote, root=root) + [shell_command]
    log_path = log_dir / f"{name}.log"
    start = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        env=remote_auth.command_env(remote, root),
    )
    elapsed = time.monotonic() - start
    log_path.write_text(
        "$ " + " ".join(command) + "\n\n" + completed.stdout + completed.stderr,
        encoding="utf-8",
    )
    return alpha.StepResult(
        name=name,
        status="pass" if completed.returncode == 0 else "fail",
        returncode=completed.returncode,
        log=str(log_path),
        elapsed_seconds=elapsed,
        error_code="ok" if completed.returncode == 0 else alpha.classify_error_text(completed.stdout + completed.stderr),
    )


def internal_step(name: str, log_dir: Path, *, passed: bool, text: str, error_code: str = "ok") -> alpha.StepResult:
    log_path = log_dir / f"{name}.log"
    log_path.write_text(text, encoding="utf-8")
    return alpha.StepResult(
        name=name,
        status="pass" if passed else "fail",
        returncode=0 if passed else 1,
        log=str(log_path),
        elapsed_seconds=0.0,
        error_code=error_code if not passed else "ok",
    )


def step_log_text(step: alpha.StepResult) -> str:
    return Path(step.log).read_text(encoding="utf-8", errors="replace") if step.log else ""


def step_summary(steps: list[alpha.StepResult]) -> dict[str, object]:
    failures = [step for step in steps if step.status != "pass"]
    return {
        "total_steps": len(steps),
        "passed_steps": sum(1 for step in steps if step.status == "pass"),
        "failed_steps": len(failures),
        "first_failed_step": asdict(failures[0]) if failures else {},
        "passed": not failures,
    }


def beta1b_storage_freshness(root: Path, log_dir: Path) -> alpha.StepResult:
    report = root / "docs" / "perf" / "BETA1B_STORAGE_SYSTEM_ATTRIBUTION.md"
    latest = latest_by_mtime(list((root / "tools" / "perf" / "results").glob("*_beta1b-storage-system-attribution.json")))
    reasons: list[str] = []
    if not report.is_file():
        reasons.append("missing report docs/perf/BETA1B_STORAGE_SYSTEM_ATTRIBUTION.md")
    if latest is None:
        reasons.append("missing *_beta1b-storage-system-attribution.json")
    payload = read_json_if_exists(latest) if latest else {}
    if latest and not payload:
        reasons.append(f"unreadable wrapper JSON {latest}")
    text = [
        f"report={alpha.relative_to_root(str(report), root)} exists={report.is_file()}",
        f"latest_wrapper={alpha.relative_to_root(str(latest), root) if latest else ''}",
        f"wrapper_readable={bool(payload) if latest else False}",
    ]
    if reasons:
        text.extend(f"reason={reason}" for reason in reasons)
    return internal_step(
        "beta1b_storage_system_freshness",
        log_dir,
        passed=not reasons,
        text="\n".join(text) + "\n",
        error_code="missing_artifact",
    )


def read_csv_rows(path_text: str, root: Path) -> list[dict[str, str]]:
    if not path_text:
        return []
    path = Path(path_text)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def summarize_beta1c_smoke(wrapper: dict[str, object]) -> dict[str, object]:
    raw_rows = int(wrapper.get("retr_transfer_cases", wrapper.get("retr_raw_rows", 0)) or 0)
    raw_fail = int(wrapper.get("retr_transfer_failures", wrapper.get("retr_raw_fail", 0)) or 0)
    raw_pass = raw_rows - raw_fail if raw_rows >= raw_fail else 0
    grouped_fail = int(wrapper.get("retr_summary_fail_count", 0) or 0)
    mismatch = int(wrapper.get("hash_mismatch_count", 0) or 0)
    return {
        "raw_rows": raw_rows,
        "raw_pass": raw_pass,
        "raw_fail": raw_fail,
        "grouped_fail": grouped_fail,
        "hash_mismatch_count": mismatch,
        "passed": raw_rows > 0 and raw_fail == 0 and grouped_fail == 0 and mismatch == 0,
    }


def collect_result_artifacts(root: Path, patterns: list[str], *, latest_only: bool = True) -> set[str]:
    results_dir = root / "tools" / "perf" / "results"
    result: set[str] = set()
    for pattern in patterns:
        paths = sorted(results_dir.glob(pattern))
        selected = [latest_by_mtime(paths)] if latest_only else paths
        for path in selected:
            if path is None or not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if path.suffix == ".csv":
                result.update(alpha.csv_referenced_artifacts(relative, root))
            else:
                result.add(relative)
    return result


def collect_beta_artifact_paths(
    *,
    root: Path,
    gate_json: Path,
    gate_markdown: Path,
    beta_manifest: Path | None = None,
    beta1c_raws: list[str] | None = None,
    beta1c_summaries: list[str] | None = None,
) -> list[str]:
    paths = set(
        alpha.collect_alpha_artifact_paths(
            root=root,
            gate_json=gate_json,
            matrix_raw="",
            matrix_summary="",
        )
    )
    paths.add(alpha.relative_to_root(str(gate_json), root))
    paths.add(alpha.relative_to_root(str(gate_markdown), root))
    # Do not include the manifest itself. Its hash changes when it is written,
    # which would make a freshness check fail by construction.
    del beta_manifest
    paths.update(path for path in BETA_DOCS if (root / path).is_file())
    paths.update(path for path in BETA_TOOLS if (root / path).is_file())
    for figure in (root / "docs" / "perf" / "figures").glob("three_way_*.*"):
        if figure.is_file():
            paths.add(figure.relative_to(root).as_posix())
    for figure in (root / "docs" / "perf" / "figures").glob("gridflux_short_vs_1g.*"):
        if figure.is_file():
            paths.add(figure.relative_to(root).as_posix())
    paths.update(
        collect_result_artifacts(
            root,
            [
                "*_beta1a*.json",
                "*_beta1b-storage-system-attribution.json",
                "*_beta1c-retr-stability.json",
                "*_baseline-ftp-gridftp-smoke.json",
                "*_three-way-wrapper.json",
                "*_ftp-gridftp-gridflux-summary.csv",
                "*_three-way-host-baseline.csv",
                "*_plain-ftp-three-way.csv",
                "*_native-gridftp-three-way.csv",
                "*_gridflux-three-way.csv",
            ],
            latest_only=True,
        )
    )
    for csv_path in list(beta1c_raws or []) + list(beta1c_summaries or []):
        paths.update(alpha.csv_referenced_artifacts(alpha.relative_to_root(csv_path, root), root))
    result: list[str] = []
    for path in sorted(paths):
        try:
            normalized = sync_remote_artifacts.validate_artifact_path(path)
        except ValueError:
            continue
        if (root / normalized).is_file():
            result.append(normalized)
    return result


def write_beta_gate_markdown(path: Path, report: dict[str, object]) -> None:
    steps = report.get("steps", [])
    artifact = report.get("artifact_manifest", {})
    freshness = report.get("artifact_manifest_freshness", {})
    sync = report.get("artifact_sync_summary", {})
    verify = report.get("artifact_verify_summary", {})
    residual = report.get("residual_process_check", {})
    beta1c = report.get("beta1c_retr_smoke", {})
    lines = [
        "# GridFlux Beta Release Gate",
        "",
        f"- Timestamp: `{report.get('timestamp', '')}`",
        f"- Result: `{'pass' if report.get('passed') else 'fail'}`",
        f"- Source tree hash: `{report.get('source_tree_hash', '')}`",
        f"- Remote: `{report.get('remote', '')}`",
        f"- Server host: `{report.get('server_host', '')}`",
        "",
        "## Default Strategy",
        "",
    ]
    for key, value in default_strategy_summary().items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Step Results",
            "",
            "| Step | Status | Error Code | Seconds | Log |",
            "|------|--------|------------|---------|-----|",
        ]
    )
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict):
                lines.append(
                    f"| `{step.get('name', '')}` | `{step.get('status', '')}` | "
                    f"`{step.get('error_code', '')}` | `{float(step.get('elapsed_seconds', 0.0)):.2f}` | "
                    f"`{step.get('log', '')}` |"
                )
    lines.extend(["", "## Beta Smoke Summary", ""])
    if isinstance(beta1c, dict) and beta1c:
        lines.extend(
            [
                f"- Beta 1C RETR smoke raw rows: `{beta1c.get('raw_rows', '')}`",
                f"- Beta 1C RETR smoke pass/fail: `{beta1c.get('raw_pass', '')}` / `{beta1c.get('raw_fail', '')}`",
                f"- Beta 1C grouped fail: `{beta1c.get('grouped_fail', '')}`",
                f"- Beta 1C hash mismatch: `{beta1c.get('hash_mismatch_count', '')}`",
            ]
        )
    storage = report.get("beta1b_storage_system_check", {})
    if isinstance(storage, dict) and storage:
        lines.append(f"- Beta 1B storage/system check: `{storage.get('status', '')}`")
    lines.extend(["", "## Nested Alpha Gates", ""])
    for name in ["quick_alpha_gate", "full_alpha_gate", "alpha_release_candidate"]:
        nested = report.get(name, {})
        if isinstance(nested, dict) and nested:
            lines.extend(
                [
                    f"- {name}: status=`{nested.get('status', '')}` json=`{nested.get('json', '')}`",
                ]
            )
    lines.extend(["", "## Artifact Closure", ""])
    if isinstance(artifact, dict) and artifact:
        lines.extend(
            [
                f"- Manifest: `{artifact.get('path', '')}`",
                f"- Artifact count: `{artifact.get('artifact_count', '')}`",
            ]
        )
    if isinstance(freshness, dict) and freshness:
        lines.append(
            "- Freshness: "
            f"checked=`{freshness.get('checked', '')}` "
            f"stale=`{freshness.get('stale_count', '')}` "
            f"status=`{freshness.get('status', '')}`"
        )
    if isinstance(sync, dict) and sync:
        lines.append(
            "- Sync: "
            f"checked=`{sync.get('checked', '')}` "
            f"missing=`{sync.get('missing', '')}` "
            f"mismatch=`{sync.get('mismatch', '')}` "
            f"status=`{sync.get('status', '')}`"
        )
    if isinstance(verify, dict) and verify:
        lines.append(
            "- Verify: "
            f"checked=`{verify.get('checked', verify.get('total', ''))}` "
            f"missing=`{verify.get('missing', '')}` "
            f"mismatch=`{verify.get('mismatch', '')}` "
            f"status=`{verify.get('status', '')}`"
        )
    lines.extend(
        [
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
        lines.extend(f"- `{failure}`" for failure in failures)
    else:
        lines.append("- None.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def finalized_report(
    *,
    report: dict[str, object],
    steps: list[alpha.StepResult],
    residual: dict[str, str],
    require_remote_artifacts: bool,
) -> dict[str, object]:
    failures = [step.name for step in steps if step.status != "pass"]
    if residual.get("local") or residual.get("remote"):
        failures.append("residual_process_check")
    if not report.get("io_uring_smoke", {}).get("local_passed", False):  # type: ignore[union-attr]
        failures.append("local_iouring_smoke_not_passed")
    if not report.get("io_uring_smoke", {}).get("remote_passed", False):  # type: ignore[union-attr]
        failures.append("remote_iouring_smoke_not_passed")
    beta1c = report.get("beta1c_retr_smoke", {})
    if isinstance(beta1c, dict) and not beta1c.get("passed", False):
        failures.append("beta1c_retr_smoke")
    freshness = report.get("artifact_manifest_freshness", {})
    if isinstance(freshness, dict) and freshness and freshness.get("status") != "pass":
        failures.append("artifact_manifest_freshness")
    if require_remote_artifacts:
        for name in ["artifact_sync_summary", "artifact_verify_summary"]:
            summary = report.get(name, {})
            if isinstance(summary, dict) and summary and summary.get("status") != "pass":
                failures.append(name)
    summary = step_summary(steps)
    report["steps"] = [asdict(step) for step in steps]
    report.update(summary)
    report["failures"] = failures
    report["failed_steps"] = sum(1 for step in steps if step.status != "pass")
    failed_steps = [asdict(step) for step in steps if step.status != "pass"]
    report["first_failed_step"] = failed_steps[0] if failed_steps else {}
    report["passed"] = not failures
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GridFlux beta release gate.")
    parser.add_argument("--build-dir", default="build")
    parser.add_argument("--io-uring-build-dir", default="build-io-uring-real")
    parser.add_argument("--remote", default="root@<redacted>")
    parser.add_argument("--remote-root", default="/root/projects/GridFlux")
    parser.add_argument("--server-host", default="<redacted>")
    parser.add_argument("--results-dir", default="tools/perf/results")
    parser.add_argument("--run-storage-smoke", action="store_true")
    args = parser.parse_args()

    if not args.remote or not args.server_host:
        raise SystemExit("beta release gate requires --remote and --server-host")

    root = alpha.repo_root()
    results_dir = root / args.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)
    lock = acquire_beta_lock(results_dir)
    timestamp = alpha.compact_timestamp()
    log_dir = results_dir / f"{timestamp}_beta-release-gate"
    log_dir.mkdir(parents=True, exist_ok=True)
    json_path = results_dir / f"{timestamp}_beta-release-gate.json"
    markdown_path = root / "docs" / "release" / "BETA_RELEASE_GATE.md"
    artifact_manifest_path = results_dir / f"{timestamp}_beta-artifacts.json"

    steps: list[alpha.StepResult] = []
    beta1c_raws: list[str] = []
    beta1c_summaries: list[str] = []
    quick_alpha: dict[str, object] = {}
    full_alpha: dict[str, object] = {}
    alpha_rc: dict[str, object] = {}

    try:
        for name, command in [
            ("local_build_debug", ["cmake", "--build", args.build_dir]),
            ("local_ctest_debug", ["ctest", "--test-dir", args.build_dir, "--output-on-failure"]),
            ("local_build_iouring_release", ["cmake", "--build", args.io_uring_build_dir]),
            ("local_ctest_iouring_release", ["ctest", "--test-dir", args.io_uring_build_dir, "--output-on-failure"]),
            (
                "local_ctest_iouring_smoke",
                [
                    "ctest",
                    "--test-dir",
                    args.io_uring_build_dir,
                    "-R",
                    "FileIoTest.IoUringContextReadWriteSmokeWhenAvailable",
                    "--output-on-failure",
                ],
            ),
        ]:
            steps.append(alpha.run_step(name, command, log_dir, cwd=root))

        remote_commands = [
            ("remote_build_debug", f"cd {shlex.quote(args.remote_root)} && cmake --build {shlex.quote(args.build_dir)}"),
            ("remote_ctest_debug", f"cd {shlex.quote(args.remote_root)} && ctest --test-dir {shlex.quote(args.build_dir)} --output-on-failure"),
            ("remote_build_iouring_release", f"cd {shlex.quote(args.remote_root)} && cmake --build {shlex.quote(args.io_uring_build_dir)}"),
            ("remote_ctest_iouring_release", f"cd {shlex.quote(args.remote_root)} && ctest --test-dir {shlex.quote(args.io_uring_build_dir)} --output-on-failure"),
            (
                "remote_ctest_iouring_smoke",
                f"cd {shlex.quote(args.remote_root)} && ctest --test-dir {shlex.quote(args.io_uring_build_dir)} "
                "-R FileIoTest.IoUringContextReadWriteSmokeWhenAvailable --output-on-failure",
            ),
        ]
        for name, command in remote_commands:
            steps.append(run_remote_shell_step(name, command, log_dir, remote=args.remote, root=root))

        quick_step = alpha.run_step(
            "quick_alpha_gate",
            [
                sys.executable,
                "tools/release/run_alpha_release_gate.py",
                "--quick",
                "--build-dir",
                args.build_dir,
                "--io-uring-build-dir",
                args.io_uring_build_dir,
                "--remote",
                args.remote,
                "--remote-root",
                args.remote_root,
                "--results-dir",
                args.results_dir,
            ],
            log_dir,
            cwd=root,
        )
        steps.append(quick_step)
        quick_paths = parse_output_paths(step_log_text(quick_step), ["alpha_release_gate_json", "alpha_artifact_manifest"])
        quick_alpha = {"status": quick_step.status, "json": quick_paths.get("alpha_release_gate_json", "")}

        full_step = alpha.run_step(
            "full_alpha_gate",
            [
                sys.executable,
                "tools/release/run_alpha_release_gate.py",
                "--full",
                "--build-dir",
                args.build_dir,
                "--io-uring-build-dir",
                args.io_uring_build_dir,
                "--remote",
                args.remote,
                "--remote-root",
                args.remote_root,
                "--server-host",
                args.server_host,
                "--results-dir",
                args.results_dir,
            ],
            log_dir,
            cwd=root,
        )
        steps.append(full_step)
        full_paths = parse_output_paths(step_log_text(full_step), ["alpha_release_gate_json", "alpha_artifact_manifest"])
        full_alpha = {
            "status": full_step.status,
            "json": full_paths.get("alpha_release_gate_json", ""),
            "artifact_manifest": full_paths.get("alpha_artifact_manifest", ""),
        }

        rc_step = alpha.run_step(
            "alpha_release_candidate",
            [
                sys.executable,
                "tools/release/run_alpha_release_candidate.py",
                "--build-dir",
                args.build_dir,
                "--io-uring-build-dir",
                args.io_uring_build_dir,
                "--remote",
                args.remote,
                "--remote-root",
                args.remote_root,
                "--server-host",
                args.server_host,
                "--results-dir",
                args.results_dir,
            ],
            log_dir,
            cwd=root,
        )
        steps.append(rc_step)
        rc_paths = parse_output_paths(
            step_log_text(rc_step),
            ["alpha_release_candidate_json", "alpha_release_candidate_artifact_manifest"],
        )
        alpha_rc = {
            "status": rc_step.status,
            "json": rc_paths.get("alpha_release_candidate_json", ""),
            "artifact_manifest": rc_paths.get("alpha_release_candidate_artifact_manifest", ""),
        }

        beta1c_step = alpha.run_step(
            "beta1c_retr_smoke",
            [
                sys.executable,
                "tools/perf/run_beta1c_retr_stability.py",
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
                "--bytes-list",
                "67108864",
                "--repeat",
                "1",
                "--case-timeout",
                "900",
            ],
            log_dir,
            cwd=root,
        )
        steps.append(beta1c_step)
        beta1c_paths = parse_output_paths(step_log_text(beta1c_step), ["json"])
        beta1c_wrapper = read_json_if_exists(beta1c_paths.get("json", ""))
        for path in beta1c_wrapper.get("retr_raw_csvs", []) if isinstance(beta1c_wrapper, dict) else []:
            beta1c_raws.append(str(path))
        for path in beta1c_wrapper.get("retr_summary_csvs", []) if isinstance(beta1c_wrapper, dict) else []:
            beta1c_summaries.append(str(path))

        if args.run_storage_smoke:
            storage_step = alpha.run_step(
                "beta1b_storage_system_smoke",
                [
                    sys.executable,
                    "tools/perf/run_beta1b_storage_system_probe.py",
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
                    "--bytes-list",
                    "67108864",
                    "--repeat",
                    "1",
                    "--skip-fio",
                    "--case-timeout",
                    "900",
                ],
                log_dir,
                cwd=root,
            )
        else:
            storage_step = beta1b_storage_freshness(root, log_dir)
        steps.append(storage_step)

        hygiene_step = alpha.run_step(
            "public_export_strict_hygiene",
            [
                sys.executable,
                "tools/release/export_public_repo.py",
                "--output",
                f"/tmp/gridflux-public-beta-gate-{timestamp}",
                "--force",
            ],
            log_dir,
            cwd=root,
        )
        steps.append(hygiene_step)

        residual = alpha.run_remote_process_check(args.remote)
        source_hash = alpha.source_tree_hash(root)
        local_iouring = parse_iouring_smoke_passed(step_log_text(next(step for step in steps if step.name == "local_ctest_iouring_smoke")))
        remote_iouring = parse_iouring_smoke_passed(step_log_text(next(step for step in steps if step.name == "remote_ctest_iouring_smoke")))

        report: dict[str, object] = {
            "timestamp": alpha.timestamp_utc(),
            "source_tree_hash": source_hash,
            "git": alpha.git_status(root),
            "remote": args.remote,
            "remote_root": args.remote_root,
            "server_host": args.server_host,
            "default_strategy": default_strategy_summary(),
            "ctest": {
                step.name: alpha.ctest_counts(Path(step.log))
                for step in steps
                if "ctest" in step.name
            },
            "io_uring_smoke": {
                "local_passed": local_iouring,
                "remote_passed": remote_iouring,
            },
            "quick_alpha_gate": quick_alpha,
            "full_alpha_gate": full_alpha,
            "alpha_release_candidate": alpha_rc,
            "beta1c_retr_smoke": summarize_beta1c_smoke(beta1c_wrapper),
            "beta1b_storage_system_check": asdict(storage_step),
            "hygiene": asdict(hygiene_step),
            "artifact_manifest": {},
            "artifact_manifest_freshness": {},
            "artifact_sync_summary": {},
            "artifact_verify_summary": {},
            "residual_process_check": residual,
            "steps": [],
            "failures": [],
            "passed": False,
        }
        report = finalized_report(
            report=report,
            steps=steps,
            residual=residual,
            require_remote_artifacts=False,
        )
        write_beta_gate_markdown(markdown_path, report)
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        artifact_paths = collect_beta_artifact_paths(
            root=root,
            gate_json=json_path,
            gate_markdown=markdown_path,
            beta_manifest=artifact_manifest_path,
            beta1c_raws=beta1c_raws,
            beta1c_summaries=beta1c_summaries,
        )
        manifest_data = alpha.write_alpha_artifact_manifest(
            path=artifact_manifest_path,
            root=root,
            source_hash=source_hash,
            remote_required=True,
            artifact_paths=artifact_paths,
        )
        report["artifact_manifest"] = {
            "path": alpha.relative_to_root(str(artifact_manifest_path), root),
            "artifact_count": len(manifest_data.get("artifacts", [])),
            "remote_required": True,
        }
        report["artifact_manifest_freshness"] = alpha.check_alpha_artifact_manifest_freshness(
            artifact_manifest_path, root
        )
        report = finalized_report(
            report=report,
            steps=steps,
            residual=residual,
            require_remote_artifacts=False,
        )
        write_beta_gate_markdown(markdown_path, report)
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        artifact_paths = collect_beta_artifact_paths(
            root=root,
            gate_json=json_path,
            gate_markdown=markdown_path,
            beta_manifest=artifact_manifest_path,
            beta1c_raws=beta1c_raws,
            beta1c_summaries=beta1c_summaries,
        )
        alpha.write_alpha_artifact_manifest(
            path=artifact_manifest_path,
            root=root,
            source_hash=source_hash,
            remote_required=True,
            artifact_paths=artifact_paths,
        )
        report["artifact_manifest"] = {
            "path": alpha.relative_to_root(str(artifact_manifest_path), root),
            "artifact_count": len(artifact_paths),
            "remote_required": True,
        }
        report["artifact_manifest_freshness"] = alpha.check_alpha_artifact_manifest_freshness(
            artifact_manifest_path, root
        )

        sync_json = log_dir / "remote-beta-artifact-sync.json"
        sync_step = alpha.run_step(
            "remote_beta_artifact_sync",
            [
                sys.executable,
                "tools/release/sync_remote_artifacts.py",
                "--manifest",
                alpha.relative_to_root(str(artifact_manifest_path), root),
                "--remote",
                args.remote,
                "--local-root",
                str(root),
                "--remote-root",
                args.remote_root,
                "--sync",
                "--json-output",
                str(sync_json),
            ],
            log_dir,
            cwd=root,
        )
        steps.append(sync_step)
        verify_json = log_dir / "remote-beta-artifact-verify.json"
        verify_step = alpha.run_step(
            "remote_beta_artifact_verify",
            [
                sys.executable,
                "tools/release/check_remote_artifact_sync.py",
                "--remote",
                args.remote,
                "--local-root",
                str(root),
                "--remote-root",
                args.remote_root,
                "--manifest",
                alpha.relative_to_root(str(artifact_manifest_path), root),
                "--json-output",
                str(verify_json),
            ],
            log_dir,
            cwd=root,
        )
        steps.append(verify_step)
        report["artifact_sync_summary"] = read_json_if_exists(sync_json)
        report["artifact_verify_summary"] = read_json_if_exists(verify_json)
        report = finalized_report(
            report=report,
            steps=steps,
            residual=residual,
            require_remote_artifacts=True,
        )
        write_beta_gate_markdown(markdown_path, report)
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        artifact_paths = collect_beta_artifact_paths(
            root=root,
            gate_json=json_path,
            gate_markdown=markdown_path,
            beta_manifest=artifact_manifest_path,
            beta1c_raws=beta1c_raws,
            beta1c_summaries=beta1c_summaries,
        )
        alpha.write_alpha_artifact_manifest(
            path=artifact_manifest_path,
            root=root,
            source_hash=source_hash,
            remote_required=True,
            artifact_paths=artifact_paths,
        )
        report["artifact_manifest"] = {
            "path": alpha.relative_to_root(str(artifact_manifest_path), root),
            "artifact_count": len(artifact_paths),
            "remote_required": True,
        }
        report["artifact_manifest_freshness"] = alpha.check_alpha_artifact_manifest_freshness(
            artifact_manifest_path, root
        )
        if report["artifact_manifest_freshness"].get("status") != "pass":
            report = finalized_report(
                report=report,
                steps=steps,
                residual=residual,
                require_remote_artifacts=True,
            )
            write_beta_gate_markdown(markdown_path, report)
            json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"beta_release_gate_report={markdown_path}")
            print(f"beta_release_gate_json={json_path}")
            print(f"beta_artifact_manifest={artifact_manifest_path}")
            print("result=fail")
            return 1

        post_sync_json = log_dir / "remote-beta-artifact-post-report-sync.json"
        post_sync = alpha.run_step(
            "remote_beta_artifact_post_report_sync",
            [
                sys.executable,
                "tools/release/sync_remote_artifacts.py",
                "--manifest",
                alpha.relative_to_root(str(artifact_manifest_path), root),
                "--remote",
                args.remote,
                "--local-root",
                str(root),
                "--remote-root",
                args.remote_root,
                "--sync",
                "--json-output",
                str(post_sync_json),
            ],
            log_dir,
            cwd=root,
        )
        post_verify_json = log_dir / "remote-beta-artifact-post-report-verify.json"
        post_verify = alpha.run_step(
            "remote_beta_artifact_post_report_verify",
            [
                sys.executable,
                "tools/release/check_remote_artifact_sync.py",
                "--remote",
                args.remote,
                "--local-root",
                str(root),
                "--remote-root",
                args.remote_root,
                "--manifest",
                alpha.relative_to_root(str(artifact_manifest_path), root),
                "--json-output",
                str(post_verify_json),
            ],
            log_dir,
            cwd=root,
        )
        if post_sync.status != "pass" or post_verify.status != "pass":
            steps.extend([post_sync, post_verify])
            report["artifact_sync_summary"] = read_json_if_exists(post_sync_json)
            report["artifact_verify_summary"] = read_json_if_exists(post_verify_json)
        report = finalized_report(
            report=report,
            steps=steps,
            residual=residual,
            require_remote_artifacts=True,
        )
        write_beta_gate_markdown(markdown_path, report)
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        print(f"beta_release_gate_report={markdown_path}")
        print(f"beta_release_gate_json={json_path}")
        print(f"beta_artifact_manifest={artifact_manifest_path}")
        print(f"result={'pass' if report['passed'] else 'fail'}")
        return 0 if report["passed"] else 1
    finally:
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
