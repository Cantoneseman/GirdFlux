#!/usr/bin/env python3
"""Generate the GridFlux beta release-candidate closeout package."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

import run_alpha_release_gate as alpha
import run_beta_release_gate as beta_gate
import sync_remote_artifacts


def read_json(path_text: str | Path) -> dict[str, object]:
    if not path_text:
        return {}
    path = Path(path_text)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_gate_paths_from_log(text: str) -> dict[str, str]:
    keys = ["beta_release_gate_report", "beta_release_gate_json", "beta_artifact_manifest"]
    return beta_gate.parse_output_paths(text, keys)


def summarize_steps(steps: list[alpha.StepResult]) -> dict[str, object]:
    failures = [step for step in steps if step.status != "pass"]
    return {
        "total_steps": len(steps),
        "passed_steps": sum(1 for step in steps if step.status == "pass"),
        "failed_steps": len(failures),
        "first_failed_step": asdict(failures[0]) if failures else {},
        "passed": not failures,
    }


def csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def latest_result(root: Path, pattern: str) -> Path | None:
    return beta_gate.latest_by_mtime(sorted((root / "tools" / "perf" / "results").glob(pattern)))


def latest_beta_long_soak(root: Path) -> Path | None:
    results = root / "tools" / "perf" / "results"
    return beta_gate.latest_by_mtime(
        sorted(results.glob("*_beta-long-soak*.json"))
        + sorted(results.glob("*_beta-release-gate/beta-long-soak-short.json"))
    )


def summarize_beta_long_soak(path_text: str | Path | None) -> dict[str, object]:
    if not path_text:
        return {"path": "", "present": False, "passed": False}
    path = Path(path_text)
    payload = read_json(path)
    if not payload:
        return {"path": str(path), "present": False, "passed": False}
    fail_count = int(payload.get("fail_count", 0) or 0)
    return {
        "path": str(path),
        "present": True,
        "passed": str(payload.get("result", "")).lower() == "pass" and fail_count == 0,
        "profile": payload.get("profile", ""),
        "iterations": payload.get("iterations", 0),
        "pass_count": payload.get("pass_count", 0),
        "fail_count": fail_count,
        "elapsed_seconds": payload.get("elapsed_seconds", 0.0),
    }


def as_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def best_summary_value(rows: list[dict[str, str]], *, protocol: str, direction: str, size: str) -> dict[str, object]:
    candidates = [
        row
        for row in rows
        if row.get("protocol") == protocol
        and row.get("direction") == direction
        and row.get("size_bytes") == size
        and int(float(row.get("sha256_mismatch_count", "0") or "0")) == 0
        and int(float(row.get("fail_count", "0") or "0")) == 0
    ]
    if not candidates:
        return {}
    best = max(candidates, key=lambda row: as_float(row.get("best_Gbps", "0")))
    return {
        "protocol": protocol,
        "direction": direction,
        "size_bytes": size,
        "best_Gbps": as_float(best.get("best_Gbps", "0")),
        "median_Gbps": as_float(best.get("median_Gbps", "0")),
        "parallelism": best.get("parallelism") or best.get("connections") or "",
        "checksum": best.get("checksum", ""),
    }


def extract_three_way_performance(root: Path) -> dict[str, object]:
    summary_path = latest_result(root, "*_ftp-gridftp-gridflux-summary.csv")
    host_path = latest_result(root, "*_three-way-host-baseline.csv")
    summary_rows = csv_rows(summary_path) if summary_path else []
    host_rows = csv_rows(host_path) if host_path else []
    size_1g = "1073741824"
    performance = {
        "summary_csv": alpha.relative_to_root(str(summary_path), root) if summary_path else "",
        "host_baseline_csv": alpha.relative_to_root(str(host_path), root) if host_path else "",
        "plain_ftp_1g_upload_best": best_summary_value(summary_rows, protocol="plain_ftp", direction="upload", size=size_1g),
        "plain_ftp_1g_download_best": best_summary_value(summary_rows, protocol="plain_ftp", direction="download", size=size_1g),
        "native_gridftp_1g_upload_best": best_summary_value(summary_rows, protocol="native_gridftp", direction="upload", size=size_1g),
        "native_gridftp_1g_download_best": best_summary_value(summary_rows, protocol="native_gridftp", direction="download", size=size_1g),
        "gridflux_1g_stor_best": best_summary_value(summary_rows, protocol="gridflux", direction="stor", size=size_1g),
        "gridflux_1g_retr_best": best_summary_value(summary_rows, protocol="gridflux", direction="retr", size=size_1g),
        "iperf3_gbps": [
            {"parallelism": row.get("parallelism", ""), "Gbps": as_float(row.get("Gbps", "0"))}
            for row in host_rows
            if row.get("kind") == "iperf3"
        ],
        "storage_write_gbps": [
            {"machine": row.get("machine", ""), "Gbps": as_float(row.get("Gbps", "0"))}
            for row in host_rows
            if row.get("kind") == "storage" and row.get("operation") == "write_1GiB_tmp"
        ],
    }
    return performance


def extract_beta_report_numbers(root: Path) -> dict[str, object]:
    numbers: dict[str, object] = {}
    for key, relative in [
        ("stor_storage_system_report", "docs/perf/BETA1B_STORAGE_SYSTEM_ATTRIBUTION.md"),
        ("retr_stability_report", "docs/perf/BETA1C_RETR_STABILITY.md"),
    ]:
        path = root / relative
        numbers[key] = relative if path.is_file() else ""
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        match = re.search(r"GridFlux STOR e2e median/best: `([^`]+)`", text)
        if match:
            numbers["stor_e2e_median_best"] = match.group(1)
        match = re.search(r"RETR summary median/best throughput: `([^`]+)`", text)
        if match:
            numbers["retr_median_best"] = match.group(1)
    return numbers


def known_bottlenecks() -> list[str]:
    return [
        "Current cloud-server environment is not a 100G validation target.",
        "STOR remains constrained by receiver temp write/writeback and cloud storage/filesystem behavior.",
        "RETR correctness/stability is green, but throughput spread remains high in full-size focused data.",
        "TLS/data TLS, verified_chunks, io_uring, bounded/dirty_poll, and preallocate full remain opt-in.",
        "Full GSI/DCAU/PROT/AUTH TLS and raw FTP STOR/RETR are not implemented.",
    ]


def write_candidate_markdown(path: Path, report: dict[str, object]) -> None:
    gate = report.get("beta_release_gate", {})
    artifact = report.get("artifact_manifest", {})
    freshness = report.get("artifact_manifest_freshness", {})
    sync = report.get("artifact_sync_summary", {})
    verify = report.get("artifact_verify_summary", {})
    perf = report.get("key_performance_numbers", {})
    soak = report.get("beta_long_soak", {})
    lines = [
        "# GridFlux Beta Release Candidate",
        "",
        f"- Timestamp: `{report.get('timestamp', '')}`",
        f"- Result: `{'pass' if report.get('passed') else 'fail'}`",
        f"- Source tree hash: `{report.get('source_tree_hash', '')}`",
        "",
        "## Default Strategy",
        "",
    ]
    for key, value in beta_gate.default_strategy_summary().items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Beta Gate", ""])
    if isinstance(gate, dict):
        lines.extend(
            [
                f"- Gate JSON: `{gate.get('json', '')}`",
                f"- Gate report: `{gate.get('report', '')}`",
                f"- Gate passed: `{gate.get('passed', '')}`",
                f"- Gate failed steps: `{gate.get('failed_steps', '')}`",
            ]
        )
    lines.extend(["", "## Key Performance Numbers", ""])
    if isinstance(perf, dict):
        for key, value in perf.items():
            lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Known Bottlenecks", ""])
    for item in known_bottlenecks():
        lines.append(f"- {item}")
    lines.extend(["", "## Beta 1E Long Soak", ""])
    if isinstance(soak, dict) and soak:
        lines.extend(
            [
                f"- Path: `{soak.get('path', '')}`",
                f"- Present: `{soak.get('present', '')}`",
                f"- Passed: `{soak.get('passed', '')}`",
                f"- Profile: `{soak.get('profile', '')}`",
                f"- Iterations: `{soak.get('iterations', '')}`",
                f"- Fail count: `{soak.get('fail_count', '')}`",
            ]
        )
    else:
        lines.append("- No long soak JSON recorded.")
    lines.extend(["", "## Artifact Closure", ""])
    if isinstance(artifact, dict):
        lines.extend(
            [
                f"- Manifest: `{artifact.get('path', '')}`",
                f"- Artifact count: `{artifact.get('artifact_count', '')}`",
            ]
        )
    if isinstance(freshness, dict):
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
    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    if isinstance(failures, list) and failures:
        lines.extend(f"- `{failure}`" for failure in failures)
    else:
        lines.append("- None.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def candidate_artifact_paths(
    *,
    root: Path,
    candidate_json: Path,
    candidate_markdown: Path,
    gate_json: Path,
    soak_json: Path | None = None,
) -> list[str]:
    paths = set(
        beta_gate.collect_beta_artifact_paths(
            root=root,
            gate_json=gate_json,
            gate_markdown=root / "docs" / "release" / "BETA_RELEASE_GATE.md",
        )
    )
    paths.add(alpha.relative_to_root(str(candidate_json), root))
    paths.add(alpha.relative_to_root(str(candidate_markdown), root))
    if soak_json and soak_json.is_file():
        paths.add(alpha.relative_to_root(str(soak_json), root))
        payload = read_json(soak_json)
        for field in ["event_log_paths", "case_log_paths", "server_log_paths", "client_log_paths"]:
            values = payload.get(field, [])
            if isinstance(values, list):
                for value in values:
                    normalized = alpha.normalize_artifact_path(str(value), root)
                    if normalized:
                        paths.add(normalized)
    for path in [
        root / "tools" / "release" / "run_beta_release_candidate.py",
        root / "docs" / "release" / "BETA_RELEASE_CANDIDATE.md",
    ]:
        if path.is_file():
            paths.add(alpha.relative_to_root(str(path), root))
    result: list[str] = []
    for item in sorted(paths):
        try:
            normalized = sync_remote_artifacts.validate_artifact_path(item)
        except ValueError:
            continue
        if (root / normalized).is_file():
            result.append(normalized)
    return result


def finalize_report(
    *,
    report: dict[str, object],
    steps: list[alpha.StepResult],
    require_remote_artifacts: bool,
    require_soak: bool = False,
) -> dict[str, object]:
    failures = [step.name for step in steps if step.status != "pass"]
    gate = report.get("beta_release_gate", {})
    if isinstance(gate, dict) and not gate.get("passed", False):
        failures.append("beta_release_gate")
    freshness = report.get("artifact_manifest_freshness", {})
    if isinstance(freshness, dict) and freshness and freshness.get("status") != "pass":
        failures.append("artifact_manifest_freshness")
    if require_remote_artifacts:
        for key in ["artifact_sync_summary", "artifact_verify_summary"]:
            value = report.get(key, {})
            if isinstance(value, dict) and value and value.get("status") != "pass":
                failures.append(key)
    if require_soak:
        soak = report.get("beta_long_soak", {})
        if not isinstance(soak, dict) or not soak.get("passed", False):
            failures.append("beta_long_soak")
    report["steps"] = [asdict(step) for step in steps]
    report.update(summarize_steps(steps))
    report["failures"] = failures
    report["passed"] = not failures
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run or package the GridFlux beta release candidate.")
    parser.add_argument("--gate-json", default="")
    parser.add_argument("--build-dir", default="build")
    parser.add_argument("--io-uring-build-dir", default="build-io-uring-real")
    parser.add_argument("--remote", default="root@<redacted>")
    parser.add_argument("--remote-root", default="/root/projects/GridFlux")
    parser.add_argument("--server-host", default="<redacted>")
    parser.add_argument("--results-dir", default="tools/perf/results")
    parser.add_argument("--soak-json", default="")
    parser.add_argument("--require-soak", action="store_true")
    args = parser.parse_args()

    root = alpha.repo_root()
    results_dir = root / args.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = alpha.compact_timestamp()
    log_dir = results_dir / f"{timestamp}_beta-release-candidate"
    log_dir.mkdir(parents=True, exist_ok=True)
    json_path = results_dir / f"{timestamp}_beta-release-candidate.json"
    markdown_path = root / "docs" / "release" / "BETA_RELEASE_CANDIDATE.md"
    manifest_path = results_dir / f"{timestamp}_beta-release-candidate-artifacts.json"
    steps: list[alpha.StepResult] = []

    gate_json = args.gate_json
    gate_paths: dict[str, str] = {}
    if not gate_json:
        gate_step = alpha.run_step(
            "beta_release_gate",
            [
                sys.executable,
                "tools/release/run_beta_release_gate.py",
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
        steps.append(gate_step)
        gate_paths = parse_gate_paths_from_log(Path(gate_step.log).read_text(encoding="utf-8", errors="replace"))
        gate_json = gate_paths.get("beta_release_gate_json", "")
    gate_payload = read_json(gate_json)
    gate_report = {
        "json": alpha.relative_to_root(gate_json, root),
        "report": gate_paths.get("beta_release_gate_report", "docs/release/BETA_RELEASE_GATE.md"),
        "artifact_manifest": gate_paths.get("beta_artifact_manifest", str(gate_payload.get("artifact_manifest", {}).get("path", "")) if isinstance(gate_payload.get("artifact_manifest", {}), dict) else ""),
        "passed": bool(gate_payload.get("passed", False)),
        "total_steps": gate_payload.get("total_steps", 0),
        "failed_steps": gate_payload.get("failed_steps", 0),
    }
    source_hash = alpha.source_tree_hash(root)
    key_numbers = {
        **extract_three_way_performance(root),
        **extract_beta_report_numbers(root),
    }
    soak_path = Path(args.soak_json) if args.soak_json else latest_beta_long_soak(root)
    soak_summary = summarize_beta_long_soak(soak_path)
    if soak_summary.get("path"):
        soak_summary["path"] = alpha.relative_to_root(str(soak_summary["path"]), root)
    report: dict[str, object] = {
        "timestamp": alpha.timestamp_utc(),
        "source_tree_hash": source_hash,
        "default_strategy": beta_gate.default_strategy_summary(),
        "beta_release_gate": gate_report,
        "gate_summary": {
            "ctest": gate_payload.get("ctest", {}),
            "io_uring_smoke": gate_payload.get("io_uring_smoke", {}),
            "quick_alpha_gate": gate_payload.get("quick_alpha_gate", {}),
            "full_alpha_gate": gate_payload.get("full_alpha_gate", {}),
            "alpha_release_candidate": gate_payload.get("alpha_release_candidate", {}),
            "public_hygiene": gate_payload.get("hygiene", {}),
            "residual_process_check": gate_payload.get("residual_process_check", {}),
        },
        "key_performance_numbers": key_numbers,
        "beta_long_soak": soak_summary,
        "known_bottlenecks": known_bottlenecks(),
        "artifact_manifest": {},
        "artifact_manifest_freshness": {},
        "artifact_sync_summary": {},
        "artifact_verify_summary": {},
        "public_hygiene_result": gate_payload.get("hygiene", {}),
        "artifact_sync_result": gate_payload.get("artifact_sync_summary", {}),
        "residual_process_status": gate_payload.get("residual_process_check", {}),
        "steps": [],
        "failures": [],
        "passed": False,
    }
    report = finalize_report(report=report, steps=steps, require_remote_artifacts=False, require_soak=args.require_soak)
    write_candidate_markdown(markdown_path, report)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact_paths = candidate_artifact_paths(
        root=root,
        candidate_json=json_path,
        candidate_markdown=markdown_path,
        gate_json=Path(gate_json),
        soak_json=Path(soak_path) if soak_path else None,
    )
    alpha.write_alpha_artifact_manifest(
        path=manifest_path,
        root=root,
        source_hash=source_hash,
        remote_required=bool(args.remote),
        artifact_paths=artifact_paths,
    )
    report["artifact_manifest"] = {
        "path": alpha.relative_to_root(str(manifest_path), root),
        "artifact_count": len(artifact_paths),
        "remote_required": bool(args.remote),
    }
    report["artifact_manifest_freshness"] = alpha.check_alpha_artifact_manifest_freshness(manifest_path, root)
    report = finalize_report(report=report, steps=steps, require_remote_artifacts=False, require_soak=args.require_soak)
    write_candidate_markdown(markdown_path, report)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact_paths = candidate_artifact_paths(
        root=root,
        candidate_json=json_path,
        candidate_markdown=markdown_path,
        gate_json=Path(gate_json),
        soak_json=Path(soak_path) if soak_path else None,
    )
    alpha.write_alpha_artifact_manifest(
        path=manifest_path,
        root=root,
        source_hash=source_hash,
        remote_required=bool(args.remote),
        artifact_paths=artifact_paths,
    )
    report["artifact_manifest"] = {
        "path": alpha.relative_to_root(str(manifest_path), root),
        "artifact_count": len(artifact_paths),
        "remote_required": bool(args.remote),
    }
    report["artifact_manifest_freshness"] = alpha.check_alpha_artifact_manifest_freshness(manifest_path, root)

    if args.remote:
        sync_json = log_dir / "remote-beta-rc-artifact-sync.json"
        sync_step = alpha.run_step(
            "remote_beta_rc_artifact_sync",
            [
                sys.executable,
                "tools/release/sync_remote_artifacts.py",
                "--manifest",
                alpha.relative_to_root(str(manifest_path), root),
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
        verify_json = log_dir / "remote-beta-rc-artifact-verify.json"
        verify_step = alpha.run_step(
            "remote_beta_rc_artifact_verify",
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
                alpha.relative_to_root(str(manifest_path), root),
                "--json-output",
                str(verify_json),
            ],
            log_dir,
            cwd=root,
        )
        steps.append(verify_step)
        report["artifact_sync_summary"] = read_json(sync_json)
        report["artifact_verify_summary"] = read_json(verify_json)

    report = finalize_report(
        report=report,
        steps=steps,
        require_remote_artifacts=bool(args.remote),
        require_soak=args.require_soak,
    )
    write_candidate_markdown(markdown_path, report)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact_paths = candidate_artifact_paths(
        root=root,
        candidate_json=json_path,
        candidate_markdown=markdown_path,
        gate_json=Path(gate_json),
        soak_json=Path(soak_path) if soak_path else None,
    )
    alpha.write_alpha_artifact_manifest(
        path=manifest_path,
        root=root,
        source_hash=source_hash,
        remote_required=bool(args.remote),
        artifact_paths=artifact_paths,
    )
    report["artifact_manifest"] = {
        "path": alpha.relative_to_root(str(manifest_path), root),
        "artifact_count": len(artifact_paths),
        "remote_required": bool(args.remote),
    }
    report["artifact_manifest_freshness"] = alpha.check_alpha_artifact_manifest_freshness(manifest_path, root)
    if args.remote:
        post_sync_json = log_dir / "remote-beta-rc-artifact-post-report-sync.json"
        post_sync = alpha.run_step(
            "remote_beta_rc_artifact_post_report_sync",
            [
                sys.executable,
                "tools/release/sync_remote_artifacts.py",
                "--manifest",
                alpha.relative_to_root(str(manifest_path), root),
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
        post_verify_json = log_dir / "remote-beta-rc-artifact-post-report-verify.json"
        post_verify = alpha.run_step(
            "remote_beta_rc_artifact_post_report_verify",
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
                alpha.relative_to_root(str(manifest_path), root),
                "--json-output",
                str(post_verify_json),
            ],
            log_dir,
            cwd=root,
        )
        if post_sync.status != "pass" or post_verify.status != "pass":
            steps.extend([post_sync, post_verify])
            report["artifact_sync_summary"] = read_json(post_sync_json)
            report["artifact_verify_summary"] = read_json(post_verify_json)
    report = finalize_report(
        report=report,
        steps=steps,
        require_remote_artifacts=bool(args.remote),
        require_soak=args.require_soak,
    )
    write_candidate_markdown(markdown_path, report)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"beta_release_candidate_report={markdown_path}")
    print(f"beta_release_candidate_json={json_path}")
    print(f"beta_release_candidate_artifact_manifest={manifest_path}")
    print(f"result={'pass' if report['passed'] else 'fail'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
