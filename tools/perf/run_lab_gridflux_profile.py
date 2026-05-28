#!/usr/bin/env python3
"""Run slimmed lab GridFlux performance profiles.

This wrapper delegates actual transfers to run_gridftp_private_matrix.py. It
keeps the lab profile definitions small and explicit so daily checks do not
accidentally expand back into the full Beta 2B matrix.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "tools" / "perf" / "run_gridftp_private_matrix.py"


@dataclass(frozen=True)
class ProfileCase:
    direction: str
    checksum: str
    final_verify_policy: str
    connections: int
    manifest_flush_interval_chunks: int = 256

    @property
    def token(self) -> str:
        return (
            f"{self.direction}_{self.checksum}_fv{self.final_verify_policy}"
            f"_c{self.connections}_mfi{self.manifest_flush_interval_chunks}"
        )


@dataclass(frozen=True)
class StepSpec:
    case: ProfileCase
    command: list[str]
    output_dir: Path


def compact_timestamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def timestamp_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_matrix_module():
    spec = importlib.util.spec_from_file_location("run_gridftp_private_matrix", MATRIX_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {MATRIX_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def shell_join(command: list[str]) -> str:
    import shlex

    return " ".join(shlex.quote(part) for part in command)


def profile_defaults(profile: str) -> tuple[str, int]:
    if profile == "quick":
        return "1GiB", 1
    if profile == "focused":
        return "10GiB", 1
    if profile == "release":
        return "10GiB", 2
    if profile == "heavy":
        return "20GiB", 3
    if profile == "final-verify":
        return "10GiB", 1
    if profile == "manifest-flush":
        return "10GiB", 1
    if profile == "manifest-flush-20gib":
        return "20GiB", 1
    raise ValueError(f"unknown profile: {profile}")


def default_manifest_flush_intervals(profile: str) -> list[int]:
    if profile in ("manifest-flush", "manifest-flush-20gib"):
        return [16, 256]
    return [256]


def parse_int_list(text: str) -> list[int]:
    values: list[int] = []
    for item in text.split(","):
        value = item.strip()
        if not value:
            continue
        values.append(int(value, 10))
    return values


def profile_base_cases(profile: str) -> list[ProfileCase]:
    if profile == "quick":
        return [
            ProfileCase("stor", "none", "full", 1),
            ProfileCase("stor", "crc32c", "full", 4),
            ProfileCase("retr", "none", "full", 4),
            ProfileCase("retr", "crc32c", "full", 4),
        ]
    if profile == "focused":
        return [
            ProfileCase("stor", "none", "full", 1),
            ProfileCase("stor", "crc32c", "full", 4),
            ProfileCase("stor", "crc32c", "verified_chunks", 4),
            ProfileCase("retr", "none", "full", 4),
            ProfileCase("retr", "crc32c", "full", 4),
            ProfileCase("retr", "crc32c", "verified_chunks", 4),
        ]
    if profile == "release":
        cases: list[ProfileCase] = []
        for direction in ("stor", "retr"):
            for connection in (1, 4, 16):
                cases.append(ProfileCase(direction, "none", "full", connection))
                cases.append(ProfileCase(direction, "crc32c", "full", connection))
            for connection in (4, 16):
                cases.append(ProfileCase(direction, "crc32c", "verified_chunks", connection))
        return cases
    if profile == "final-verify":
        return [
            ProfileCase("stor", "crc32c", "full", 1),
            ProfileCase("stor", "crc32c", "verified_chunks", 1),
            ProfileCase("stor", "crc32c", "full", 4),
            ProfileCase("stor", "crc32c", "verified_chunks", 4),
            ProfileCase("retr", "crc32c", "full", 4),
            ProfileCase("retr", "crc32c", "verified_chunks", 4),
            ProfileCase("retr", "crc32c", "full", 16),
            ProfileCase("retr", "crc32c", "verified_chunks", 16),
        ]
    if profile == "heavy":
        cases = []
        for direction in ("stor", "retr"):
            for connection in (1, 4, 8, 16, 32):
                cases.append(ProfileCase(direction, "none", "full", connection))
                cases.append(ProfileCase(direction, "crc32c", "full", connection))
                cases.append(ProfileCase(direction, "crc32c", "verified_chunks", connection))
        return cases
    if profile == "manifest-flush":
        return [
            ProfileCase("stor", "none", "full", 1),
            ProfileCase("stor", "crc32c", "full", 1),
            ProfileCase("stor", "crc32c", "full", 4),
            ProfileCase("stor", "crc32c", "verified_chunks", 1),
            ProfileCase("stor", "crc32c", "verified_chunks", 4),
            ProfileCase("retr", "none", "full", 4),
            ProfileCase("retr", "none", "full", 16),
            ProfileCase("retr", "crc32c", "full", 4),
            ProfileCase("retr", "crc32c", "full", 16),
            ProfileCase("retr", "crc32c", "verified_chunks", 4),
            ProfileCase("retr", "crc32c", "verified_chunks", 16),
        ]
    if profile == "manifest-flush-20gib":
        return [
            ProfileCase("stor", "crc32c", "full", 1),
            ProfileCase("stor", "crc32c", "verified_chunks", 1),
            ProfileCase("retr", "crc32c", "full", 16),
            ProfileCase("retr", "crc32c", "verified_chunks", 16),
        ]
    raise ValueError(f"unknown profile: {profile}")


def profile_cases(profile: str, intervals: list[int] | None = None) -> list[ProfileCase]:
    if profile in ("manifest-flush", "manifest-flush-20gib"):
        selected_intervals = intervals if intervals is not None else default_manifest_flush_intervals(profile)
    else:
        selected_intervals = default_manifest_flush_intervals(profile)
    cases: list[ProfileCase] = []
    for case in profile_base_cases(profile):
        for interval in selected_intervals:
            cases.append(
                ProfileCase(
                    case.direction,
                    case.checksum,
                    case.final_verify_policy,
                    case.connections,
                    interval,
                )
            )
    return cases


def expanded_row_count(profile: str, repeat: int, intervals: list[int] | None = None) -> int:
    return len(profile_cases(profile, intervals)) * repeat


def build_step_specs(args: argparse.Namespace, run_id: str, wrapper_dir: Path) -> list[StepSpec]:
    run_root_base = Path(args.run_root_base) if args.run_root_base else Path(
        f"/mnt/aim_sdc/gridflux-test/lab-profile-{run_id}"
    )
    intervals = getattr(args, "manifest_flush_intervals", None)
    steps_dir = wrapper_dir / "steps"
    specs: list[StepSpec] = []
    for index, case in enumerate(profile_cases(args.profile, intervals)):
        step_output_dir = steps_dir / f"{index:03d}_{case.token}"
        command = [
            sys.executable,
            "tools/perf/run_gridftp_private_matrix.py",
            "--full",
            "--remote",
            args.remote,
            "--server-host",
            args.server_host,
            "--local-build-dir",
            args.local_build_dir,
            "--remote-build-dir",
            args.remote_build_dir,
            "--output-dir",
            str(step_output_dir),
            "--directions",
            case.direction,
            "--bytes",
            args.size,
            "--connections",
            str(case.connections),
            "--chunk-sizes",
            "1MiB",
            "--buffer-sizes",
            "64KiB",
            "--checksums",
            case.checksum,
            "--checksum-backend",
            "auto",
            "--tls-modes",
            "off",
            "--data-tls-modes",
            "off",
            "--file-io-backends",
            "posix",
            "--preallocates",
            "off",
            "--manifest-flush-policies",
            "every_n_chunks",
            "--commit-sync-policies",
            "none",
            "--final-verify-policies",
            case.final_verify_policy,
            "--posix-write-strategies",
            "auto",
            "--receiver-write-profiles",
            "default",
            "--receiver-max-pending-bytes-list",
            "0",
            "--receiver-write-yield-policies",
            "none",
            "--repeat",
            str(args.repeat),
            "--run-root-base",
            str(run_root_base),
            "--case-timeout",
            str(args.case_timeout),
        ]
        if args.profile in ("manifest-flush", "manifest-flush-20gib"):
            command.extend(
                [
                    "--manifest-flush-interval-chunks-list",
                    str(case.manifest_flush_interval_chunks),
                ]
            )
        if args.skip_cleanup:
            command.append("--keep-files")
        specs.append(StepSpec(case=case, command=command, output_dir=step_output_dir))
    return specs


def extract_stdout_path(stdout: str, key: str) -> str:
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


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def hash_mismatch_count(rows: list[dict[str, str]]) -> int:
    mismatches = 0
    for row in rows:
        source = row.get("source_sha256", "")
        dest = row.get("dest_sha256", "")
        if source and dest and source != dest:
            mismatches += 1
    return mismatches


def filter_process_output(output: str) -> str:
    process_tokens = (
        "gridflux-gridftp-server",
        "gridflux-file-",
        "iperf3",
        "ib_write_bw",
        "ib_read_bw",
    )
    return "\n".join(
        line
        for line in output.splitlines()
        if any(token in line for token in process_tokens)
    )


def process_check(remote: str) -> tuple[str, str]:
    pattern = (
        "'[g]ridflux-gridftp-server|[g]ridflux-file-|[i]perf3|"
        "[i]b_write_bw|[i]b_read_bw'"
    )
    local = subprocess.run(
        ["bash", "-lc", f"pgrep -af {pattern} || true"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    ).stdout
    remote_output = subprocess.run(
        ["ssh", remote, f"pgrep -af {pattern} || true"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    ).stdout
    return filter_process_output(local), filter_process_output(remote_output)


def cleanup_run_root(run_root_base: Path, *, skip_cleanup: bool) -> str:
    if skip_cleanup:
        return "skipped"
    shutil.rmtree(run_root_base, ignore_errors=True)
    return "removed" if not run_root_base.exists() else "remaining"


def write_cleanup_check(path: Path, remote: str, run_root_base: Path, skip_cleanup: bool) -> dict[str, str]:
    run_root_status = cleanup_run_root(run_root_base, skip_cleanup=skip_cleanup)
    local_processes, remote_processes = process_check(remote)
    result = {
        "timestamp": timestamp_utc(),
        "run_root_base": str(run_root_base),
        "run_root_status": run_root_status,
        "local_processes": local_processes,
        "remote_processes": remote_processes,
    }
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in result.items()) + "\n",
        encoding="utf-8",
    )
    return result


def run_step(spec: StepSpec, log_dir: Path) -> dict[str, object]:
    log_dir.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    completed = subprocess.run(
        spec.command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed = time.monotonic() - start
    stdout_log = log_dir / f"{spec.output_dir.name}.stdout.log"
    stderr_log = log_dir / f"{spec.output_dir.name}.stderr.log"
    stdout_log.write_text(completed.stdout, encoding="utf-8")
    stderr_log.write_text(completed.stderr, encoding="utf-8")
    csv_path = extract_stdout_path(completed.stdout, "csv")
    summary_path = extract_stdout_path(completed.stdout, "summary_csv")
    rows = read_csv(csv_path)
    return {
        "name": spec.output_dir.name,
        "case": spec.case.__dict__,
        "command": spec.command,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "stdout_log": str(stdout_log),
        "stderr_log": str(stderr_log),
        "raw_csv": csv_path,
        "summary_csv": summary_path,
        "rows": len(rows),
        "fail_count": sum(1 for row in rows if row.get("result") != "pass"),
        "sha_mismatch": hash_mismatch_count(rows),
    }


def dry_run(args: argparse.Namespace) -> int:
    run_id = "DRYRUN"
    wrapper_dir = Path(args.output_dir) / f"{run_id}_lab-gridflux-profile-{args.profile}"
    specs = build_step_specs(args, run_id, wrapper_dir)
    print(f"profile={args.profile}")
    print(f"size={args.size}")
    print(f"repeat={args.repeat}")
    print(f"base_case_count={len(specs)}")
    print(f"case_count={expanded_row_count(args.profile, args.repeat, args.manifest_flush_intervals)}")
    for index, spec in enumerate(specs):
        print(
            f"case[{index}] direction={spec.case.direction} checksum={spec.case.checksum} "
            f"final_verify={spec.case.final_verify_policy} "
            f"connections={spec.case.connections} "
            f"manifest_flush_interval={spec.case.manifest_flush_interval_chunks} "
            f"repeat={args.repeat}"
        )
    print("commands:")
    for spec in specs:
        print(shell_join(spec.command))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run slimmed lab GridFlux profiles.")
    parser.add_argument(
        "--profile",
        choices=[
            "quick",
            "focused",
            "release",
            "heavy",
            "manifest-flush",
            "manifest-flush-20gib",
            "final-verify",
        ],
        required=True,
    )
    parser.add_argument("--size", default="")
    parser.add_argument("--repeat", type=int, default=0)
    parser.add_argument("--output-dir", default="tools/perf/results")
    parser.add_argument("--remote", default="gridflux-lab-small")
    parser.add_argument("--server-host", default="192.168.100.2")
    parser.add_argument("--local-build-dir", default="/home/Su/projects/GridFlux/build")
    parser.add_argument("--remote-build-dir", default="/home/Su/projects/GridFlux/build")
    parser.add_argument("--run-root-base", default="")
    parser.add_argument("--case-timeout", type=int, default=1800)
    parser.add_argument("--manifest-flush-intervals", default="")
    parser.add_argument("--skip-cleanup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    default_size, default_repeat = profile_defaults(args.profile)
    if not args.size:
        args.size = default_size
    if args.repeat == 0:
        args.repeat = default_repeat
    if args.repeat <= 0:
        raise SystemExit("--repeat must be greater than zero")
    if args.profile in ("manifest-flush", "manifest-flush-20gib"):
        args.manifest_flush_intervals = (
            parse_int_list(args.manifest_flush_intervals)
            if args.manifest_flush_intervals
            else default_manifest_flush_intervals(args.profile)
        )
    else:
        args.manifest_flush_intervals = default_manifest_flush_intervals(args.profile)
    if any(value <= 0 or value > 65536 for value in args.manifest_flush_intervals):
        raise SystemExit("--manifest-flush-intervals values must be in range 1..65536")

    if args.dry_run:
        return dry_run(args)

    run_id = compact_timestamp()
    output_dir = Path(args.output_dir)
    wrapper_dir = output_dir / f"{run_id}_lab-gridflux-profile-{args.profile}"
    wrapper_dir.mkdir(parents=True, exist_ok=True)
    log_dir = wrapper_dir / "logs"
    run_root_base = Path(args.run_root_base) if args.run_root_base else Path(
        f"/mnt/aim_sdc/gridflux-test/lab-profile-{run_id}"
    )
    specs = build_step_specs(args, run_id, wrapper_dir)
    matrix = load_matrix_module()

    all_rows: list[dict[str, str]] = []
    steps: list[dict[str, object]] = []
    for spec in specs:
        print(
            f"[{len(steps) + 1}/{len(specs)}] {spec.case.token} "
            f"size={args.size} repeat={args.repeat}",
            flush=True,
        )
        step = run_step(spec, log_dir)
        steps.append(step)
        rows = read_csv(str(step.get("raw_csv", "")))
        for row in rows:
            row["lab_profile"] = args.profile
            row["lab_profile_case"] = spec.case.token
            row["lab_profile_step"] = spec.output_dir.name
            row["lab_profile_raw_csv"] = str(step.get("raw_csv", ""))
        all_rows.extend(rows)
        print(
            f"  returncode={step['returncode']} rows={step['rows']} "
            f"failures={step['fail_count']} sha_mismatch={step['sha_mismatch']}",
            flush=True,
        )

    raw_fields = [
        *matrix.CSV_FIELDS,
        "lab_profile",
        "lab_profile_case",
        "lab_profile_step",
        "lab_profile_raw_csv",
    ]
    combined_csv = wrapper_dir / f"{run_id}_lab-gridflux-profile-{args.profile}.csv"
    combined_summary = wrapper_dir / f"{run_id}_lab-gridflux-profile-{args.profile}-summary.csv"
    write_csv(combined_csv, all_rows, raw_fields)
    write_csv(combined_summary, matrix.summarize_rows(all_rows), matrix.SUMMARY_FIELDS)

    cleanup = write_cleanup_check(
        wrapper_dir / "cleanup_check.txt",
        args.remote,
        run_root_base,
        args.skip_cleanup,
    )
    fail_count = sum(1 for row in all_rows if row.get("result") != "pass")
    sha_mismatch = hash_mismatch_count(all_rows)
    step_failures = sum(1 for step in steps if int(step.get("returncode", 1)) != 0)
    wrapper_json = wrapper_dir / f"{run_id}_lab-gridflux-profile-{args.profile}.json"
    summary = {
        "timestamp": run_id,
        "profile": args.profile,
        "size": args.size,
        "repeat": args.repeat,
        "base_case_count": len(specs),
        "case_count": len(all_rows),
        "expected_case_count": expanded_row_count(
            args.profile, args.repeat, args.manifest_flush_intervals
        ),
        "fail_count": fail_count,
        "sha_mismatch": sha_mismatch,
        "step_failures": step_failures,
        "combined_csv": str(combined_csv),
        "combined_summary_csv": str(combined_summary),
        "cleanup_check": str(wrapper_dir / "cleanup_check.txt"),
        "cleanup": cleanup,
        "steps": steps,
    }
    wrapper_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"wrapper_json={wrapper_json}")
    print(f"csv={combined_csv}")
    print(f"summary_csv={combined_summary}")
    print(f"cleanup_check={wrapper_dir / 'cleanup_check.txt'}")
    print(f"cases={len(all_rows)} failures={fail_count} sha_mismatch={sha_mismatch}")
    if step_failures or fail_count or sha_mismatch:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
