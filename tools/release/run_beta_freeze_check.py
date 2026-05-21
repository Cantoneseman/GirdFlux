#!/usr/bin/env python3
"""Check that the current GridFlux beta RC is ready to freeze before 100G migration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import run_alpha_release_gate as alpha
import run_beta_release_gate as beta_gate


REQUIRED_DOCS = [
    "docs/release/BETA_RELEASE_GATE.md",
    "docs/release/BETA_RELEASE_CANDIDATE.md",
    "docs/release/BETA_LIMITATIONS.md",
    "docs/perf/BETA_PERFORMANCE_SUMMARY.md",
    "docs/perf/100G_MIGRATION_CHECKLIST.md",
    "docs/perf/BETA1B_STORAGE_SYSTEM_ATTRIBUTION.md",
    "docs/perf/BETA1C_RETR_STABILITY.md",
    "docs/PROJECT_STATE.md",
    "docs/ROADMAP.md",
    "INDEX.md",
]

DEFAULT_STRATEGY = beta_gate.default_strategy_summary()


def read_json(path: Path | str | None) -> dict[str, object]:
    if not path:
        return {}
    parsed = Path(path)
    if not parsed.is_file():
        return {}
    try:
        data = json.loads(parsed.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def latest_result(root: Path, pattern: str) -> Path | None:
    return beta_gate.latest_by_mtime(sorted((root / "tools" / "perf" / "results").glob(pattern)))


def status_is_pass(payload: dict[str, object]) -> bool:
    if not payload:
        return False
    if payload.get("passed") is True:
        return True
    if str(payload.get("status", "")).lower() == "pass":
        return True
    if str(payload.get("result", "")).lower() == "pass":
        return True
    return False


def artifact_verify_pass(payload: dict[str, object]) -> bool:
    if not status_is_pass(payload):
        return False
    for key in ["missing", "mismatch", "failures"]:
        value = payload.get(key, 0)
        try:
            if int(value) != 0:
                return False
        except (TypeError, ValueError):
            return False
    return True


def latest_artifact_verify(root: Path, rc_payload: dict[str, object]) -> tuple[Path | None, dict[str, object]]:
    final_verify = latest_result(root, "*_beta-release-candidate-final-verify.json")
    if final_verify:
        return final_verify, read_json(final_verify)
    embedded = rc_payload.get("artifact_verify_summary", {})
    return None, embedded if isinstance(embedded, dict) else {}


def required_docs_status(root: Path, freeze_doc: Path) -> dict[str, object]:
    paths = list(REQUIRED_DOCS)
    paths.append(freeze_doc.relative_to(root).as_posix())
    items = []
    missing = []
    for relative in paths:
        exists = (root / relative).is_file() or relative == freeze_doc.relative_to(root).as_posix()
        items.append({"path": relative, "exists": exists})
        if not exists:
            missing.append(relative)
    return {"items": items, "missing": missing, "passed": not missing}


def default_strategy_status(root: Path, freeze_doc: Path) -> dict[str, object]:
    script_defaults = beta_gate.default_strategy_summary()
    script_passed = script_defaults == DEFAULT_STRATEGY
    docs = [
        root / "docs" / "release" / "BETA_RELEASE_CANDIDATE.md",
        root / "docs" / "release" / "BETA_LIMITATIONS.md",
        root / "docs" / "perf" / "100G_MIGRATION_CHECKLIST.md",
        freeze_doc,
    ]
    tokens = [
        (key, value, [f"{key}={value}", f"`{key}`: `{value}`", f"`{key}={value}`"])
        for key, value in DEFAULT_STRATEGY.items()
    ]
    doc_results = []
    for doc in docs:
        if not doc.is_file():
            doc_results.append({"path": doc.relative_to(root).as_posix(), "passed": doc == freeze_doc, "missing": tokens})
            continue
        text = doc.read_text(encoding="utf-8", errors="replace")
        missing = [f"{key}={value}" for key, value, forms in tokens if not any(form in text for form in forms)]
        doc_results.append(
            {
                "path": doc.relative_to(root).as_posix(),
                "passed": not missing,
                "missing": missing,
            }
        )
    return {
        "script_defaults": script_defaults,
        "expected_defaults": DEFAULT_STRATEGY,
        "script_passed": script_passed,
        "docs": doc_results,
        "passed": script_passed and all(bool(item.get("passed")) for item in doc_results),
    }


def summarize_gate(path: Path | None, payload: dict[str, object]) -> dict[str, object]:
    hygiene = payload.get("hygiene", {})
    freshness = payload.get("artifact_manifest_freshness", {})
    sync = payload.get("artifact_sync_summary", {})
    verify = payload.get("artifact_verify_summary", {})
    return {
        "path": str(path) if path else "",
        "passed": bool(payload.get("passed", False)),
        "failed_steps": payload.get("failed_steps", 0),
        "public_hygiene_passed": isinstance(hygiene, dict) and hygiene.get("status") == "pass",
        "artifact_freshness": freshness if isinstance(freshness, dict) else {},
        "artifact_sync_summary": sync if isinstance(sync, dict) else {},
        "artifact_verify_summary": verify if isinstance(verify, dict) else {},
    }


def write_markdown(path: Path, report: dict[str, object]) -> None:
    gate = report.get("beta_gate", {})
    rc = report.get("beta_release_candidate", {})
    verify = report.get("artifact_final_verify", {})
    docs = report.get("required_docs", {})
    defaults = report.get("default_strategy_check", {})
    residual = report.get("residual_process_check", {})
    lines = [
        "# GridFlux Beta Freeze",
        "",
        f"- Timestamp: `{report.get('timestamp', '')}`",
        f"- Result: `{'pass' if report.get('passed') else 'fail'}`",
        "- Scope: current two-cloud-server Beta RC freeze before any 100G migration.",
        "- 100G status: not certified and not tested in this freeze.",
        "",
        "## Default Strategy",
        "",
    ]
    for key, value in DEFAULT_STRATEGY.items():
        lines.append(f"- `{key}={value}`")
    lines.extend(
        [
            "",
            "## Freeze Checks",
            "",
            f"- Latest Beta Gate: `{gate.get('path', '') if isinstance(gate, dict) else ''}` pass=`{gate.get('passed', '') if isinstance(gate, dict) else ''}`",
            f"- Latest Beta RC: `{rc.get('path', '') if isinstance(rc, dict) else ''}` pass=`{rc.get('passed', '') if isinstance(rc, dict) else ''}`",
            f"- Artifact final verify: `{verify.get('path', '') if isinstance(verify, dict) else ''}` pass=`{verify.get('passed', '') if isinstance(verify, dict) else ''}`",
            f"- Public hygiene from latest Beta Gate: `{gate.get('public_hygiene_passed', '') if isinstance(gate, dict) else ''}`",
            f"- Required docs present: `{docs.get('passed', '') if isinstance(docs, dict) else ''}`",
            f"- Default strategy check: `{defaults.get('passed', '') if isinstance(defaults, dict) else ''}`",
            f"- Residual process check local: `{residual.get('local', '') if isinstance(residual, dict) else ''}`",
            f"- Residual process check remote: `{residual.get('remote', '') if isinstance(residual, dict) else ''}`",
            "",
            "## Migration Guardrails",
            "",
            "- Current Beta is a cloud-server candidate, not a 100G-certified build.",
            "- Before moving to 100G, run `iperf3`, `gridflux-storage-bench`, memory sink, and CRC32C benchmark baselines.",
            "- On 100G, run 10GiB smoke first, then 100GiB repeat after network/storage baselines are clean.",
            "- Keep conservative defaults until 100G data proves a stable opt-in should graduate.",
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


def build_report(args: argparse.Namespace, *, root: Path, json_path: Path, markdown_path: Path) -> dict[str, object]:
    gate_path = latest_result(root, "*_beta-release-gate.json")
    gate_payload = read_json(gate_path)
    rc_path = latest_result(root, "*_beta-release-candidate.json")
    rc_payload = read_json(rc_path)
    verify_path, verify_payload = latest_artifact_verify(root, rc_payload)
    docs = required_docs_status(root, markdown_path)
    defaults = default_strategy_status(root, markdown_path)
    residual = alpha.run_remote_process_check(args.remote)
    gate_summary = summarize_gate(gate_path, gate_payload)
    rc_summary = {
        "path": str(rc_path) if rc_path else "",
        "passed": bool(rc_payload.get("passed", False)),
        "failures": rc_payload.get("failures", []),
    }
    final_verify = {
        "path": str(verify_path) if verify_path else "",
        "passed": artifact_verify_pass(verify_payload),
        "summary": verify_payload,
    }
    failures: list[str] = []
    if not gate_summary["passed"]:
        failures.append("beta_gate")
    if not rc_summary["passed"]:
        failures.append("beta_release_candidate")
    if not final_verify["passed"]:
        failures.append("artifact_final_verify")
    if not gate_summary["public_hygiene_passed"]:
        failures.append("public_hygiene")
    if not docs["passed"]:
        failures.append("required_docs")
    if not defaults["passed"]:
        failures.append("default_strategy")
    if residual.get("local") or residual.get("remote"):
        failures.append("residual_process_check")
    report = {
        "timestamp": alpha.timestamp_utc(),
        "json": str(json_path),
        "markdown": str(markdown_path),
        "source_tree_hash": alpha.source_tree_hash(root),
        "git": alpha.git_status(root),
        "remote": args.remote,
        "default_strategy": DEFAULT_STRATEGY,
        "beta_gate": gate_summary,
        "beta_release_candidate": rc_summary,
        "artifact_final_verify": final_verify,
        "required_docs": docs,
        "default_strategy_check": defaults,
        "residual_process_check": residual,
        "failures": failures,
        "passed": not failures,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check GridFlux beta freeze readiness.")
    parser.add_argument("--remote", default="root@<redacted>")
    parser.add_argument("--results-dir", default="tools/perf/results")
    args = parser.parse_args()

    root = alpha.repo_root()
    results_dir = root / args.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = alpha.compact_timestamp()
    json_path = results_dir / f"{timestamp}_beta-freeze-check.json"
    markdown_path = root / "docs" / "release" / "BETA_FREEZE.md"
    report = build_report(args, root=root, json_path=json_path, markdown_path=markdown_path)
    write_markdown(markdown_path, report)
    # Re-check docs/default strategy after the markdown has been generated.
    report = build_report(args, root=root, json_path=json_path, markdown_path=markdown_path)
    write_markdown(markdown_path, report)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"beta_freeze_report={markdown_path}")
    print(f"beta_freeze_json={json_path}")
    print(f"result={'pass' if report['passed'] else 'fail'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
