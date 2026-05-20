#!/usr/bin/env python3
"""Run Beta 1B-5 storage/system writeback attribution probes."""

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

PROBE_GROUP_FIELDS = [
    "dir_label",
    "method",
    "operation",
    "bytes",
    "buffer_size",
    "preallocate",
    "file_io_backend",
    "file_io_buffer_size",
    "posix_write_strategy",
]

PROBE_RAW_FIELDS = [
    "timestamp",
    "run_id",
    "case_name",
    *PROBE_GROUP_FIELDS,
    "repeat",
    "iteration",
    "aggregate",
    "elapsed_seconds",
    "throughput_gbps",
    "read_call_count",
    "write_call_count",
    "write_syscall_count",
    "write_total_bytes",
    "avg_read_bytes_per_call",
    "avg_write_bytes_per_call",
    "write_avg_bytes_per_syscall",
    "file_io_wait_seconds",
    "io_uring_submit_count",
    "io_uring_wait_count",
    "io_uring_completion_count",
    "path",
    "fs_type",
    "free_bytes",
    "mount_source",
    "mount_target",
    "mount_fstype",
    "mount_options",
    "dirty_kb_before",
    "writeback_kb_before",
    "cached_kb_before",
    "dirty_kb_after",
    "writeback_kb_after",
    "cached_kb_after",
    "sidecar_before_log",
    "sidecar_after_log",
    "df_log",
    "mount_log",
    "lsblk_log",
    "iostat_log",
    "tool_raw_csv",
    "tool_summary_csv",
    "log",
    "result",
    "error",
]

PROBE_SUMMARY_FIELDS = [
    *PROBE_GROUP_FIELDS,
    "case_count",
    "pass_count",
    "fail_count",
    "unavailable_count",
    "throughput_gbps_min",
    "throughput_gbps_median",
    "throughput_gbps_max",
    "throughput_gbps_p95",
    "throughput_gbps_spread_pct",
    "elapsed_median",
    "file_io_wait_seconds_median",
    "write_syscall_count_median",
    "write_avg_bytes_per_syscall_median",
    "dirty_writeback_kb_before_median",
    "dirty_writeback_kb_after_median",
    "mount_source",
    "mount_target",
    "mount_fstype",
    "example_sidecar",
    "example_iostat",
]


@dataclass(frozen=True)
class ProbeDir:
    label: str
    path: Path


@dataclass(frozen=True)
class StorageCase:
    dir_label: str
    directory: Path
    method: str
    operation: str
    bytes_count: int
    buffer_size: int
    preallocate: str
    file_io_backend: str
    file_io_buffer_size: int
    posix_write_strategy: str


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


def safe_token(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")[:80] or "case"


def run_env(remote: str) -> dict[str, str]:
    env = os.environ.copy()
    auth = remote_auth.resolve_auth(remote, ROOT)
    if auth:
        env["GRIDFLUX_SSH_PASSWORD"] = auth.password
        env["SSHPASS"] = auth.password
    return env


def command_exists(name: str) -> bool:
    return subprocess.run(
        ["bash", "-lc", f"command -v {shlex.quote(name)} >/dev/null 2>&1"],
        text=True,
        capture_output=True,
        check=False,
    ).returncode == 0


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


def number(row: dict[str, str], field: str) -> float:
    try:
        value = float(row.get(field, "") or "0")
        return 0.0 if math.isnan(value) or math.isinf(value) else value
    except ValueError:
        return 0.0


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) * 95 + 99) / 100) - 1))
    return ordered[index]


def spread_pct(values: list[float]) -> float:
    if not values:
        return 0.0
    center = statistics.median(values)
    if center == 0.0:
        return 0.0 if min(values) == max(values) else 0.0
    return ((max(values) - min(values)) / abs(center)) * 100.0


def meminfo_from_text(text: str) -> dict[str, str]:
    result = {"dirty_kb": "", "writeback_kb": "", "cached_kb": ""}
    mapping = {"Dirty": "dirty_kb", "Writeback": "writeback_kb", "Cached": "cached_kb"}
    for line in text.splitlines():
        match = re.match(r"^(Dirty|Writeback|Cached):\s+(\d+)\s+kB\b", line)
        if match:
            result[mapping[match.group(1)]] = match.group(2)
    return result


def df_snapshot(path: Path) -> tuple[str, str]:
    completed = subprocess.run(["df", "-PT", str(path)], text=True, capture_output=True, check=False)
    lines = completed.stdout.strip().splitlines()
    if len(lines) < 2:
        return "", ""
    parts = lines[1].split()
    free = str(int(parts[4]) * 1024) if len(parts) > 4 and parts[4].isdigit() else ""
    return parts[1] if len(parts) > 1 else "", free


def findmnt_snapshot(path: Path) -> dict[str, str]:
    if not command_exists("findmnt"):
        return {"mount_source": "unavailable", "mount_target": "", "mount_fstype": "", "mount_options": ""}
    completed = subprocess.run(
        ["findmnt", "-T", str(path), "-n", "-o", "SOURCE,TARGET,FSTYPE,OPTIONS"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return {"mount_source": "", "mount_target": "", "mount_fstype": "", "mount_options": ""}
    parts = completed.stdout.strip().split(maxsplit=3)
    return {
        "mount_source": parts[0] if len(parts) > 0 else "",
        "mount_target": parts[1] if len(parts) > 1 else "",
        "mount_fstype": parts[2] if len(parts) > 2 else "",
        "mount_options": parts[3] if len(parts) > 3 else "",
    }


def sidecar_text(path: Path) -> str:
    command = f"""
set +e
echo "timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "hostname=$(hostname)"
echo "path={shlex.quote(str(path))}"
echo "section=meminfo"
grep -E '^(Dirty|Writeback|Cached):' /proc/meminfo 2>&1 || true
echo "section=df_pt"
df -PT {shlex.quote(str(path))} 2>&1 || true
echo "section=findmnt"
if command -v findmnt >/dev/null 2>&1; then
  findmnt -T {shlex.quote(str(path))} -o SOURCE,TARGET,FSTYPE,OPTIONS 2>&1 || true
else
  echo "findmnt=unavailable"
fi
echo "section=mount"
mount 2>&1 || echo "mount=unavailable"
echo "section=lsblk"
if command -v lsblk >/dev/null 2>&1; then
  lsblk -b -f -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS,MODEL 2>&1 || true
else
  echo "lsblk=unavailable"
fi
echo "section=iostat"
if command -v iostat >/dev/null 2>&1; then
  iostat -xz 1 1 2>&1 || true
else
  echo "iostat=unavailable"
fi
"""
    completed = subprocess.run(["bash", "-lc", command], text=True, capture_output=True, check=False)
    return completed.stdout + completed.stderr


def capture_sidecar(path: Path, sidecar: Path) -> dict[str, str]:
    text = sidecar_text(path)
    write_text(sidecar, text)
    return meminfo_from_text(text)


def default_probe_dirs(args: argparse.Namespace) -> list[ProbeDir]:
    project_temp = ROOT / args.output_dir
    return [
        ProbeDir("project_temp", project_temp),
        ProbeDir("tmp", Path("/tmp")),
        ProbeDir("target_root", ROOT),
    ]


def parse_probe_dirs(args: argparse.Namespace) -> list[ProbeDir]:
    if not args.probe_dirs:
        return default_probe_dirs(args)
    result: list[ProbeDir] = []
    for index, item in enumerate(part.strip() for part in args.probe_dirs.split(",") if part.strip()):
        if ":" in item:
            label, path = item.split(":", 1)
        else:
            label, path = f"dir{index}", item
        result.append(ProbeDir(safe_token(label), Path(path)))
    return result


def storage_system_probe_cases(args: argparse.Namespace) -> list[StorageCase]:
    dirs = parse_probe_dirs(args)
    bytes_values = parse_int_list(args.bytes_list or args.bytes)
    buffer_sizes = parse_int_list(args.buffer_sizes)
    cases: list[StorageCase] = []
    for probe_dir in dirs:
        for bytes_count in bytes_values:
            for operation in ["write", "read"]:
                for buffer_size in buffer_sizes:
                    for preallocate in ["off", "full"]:
                        cases.append(
                            StorageCase(
                                probe_dir.label,
                                probe_dir.path,
                                "gridflux_storage_bench",
                                operation,
                                bytes_count,
                                buffer_size,
                                preallocate,
                                "posix",
                                0,
                                "auto",
                            )
                        )
                    if not args.skip_iouring_subset:
                        cases.append(
                            StorageCase(
                                probe_dir.label,
                                probe_dir.path,
                                "gridflux_storage_bench",
                                operation,
                                bytes_count,
                                buffer_size,
                                "off",
                                "io_uring",
                                0,
                                "auto",
                            )
                        )
                    if not args.skip_fio:
                        for preallocate in ["off", "full"]:
                            cases.append(
                                StorageCase(
                                    probe_dir.label,
                                    probe_dir.path,
                                    "fio",
                                    operation,
                                    bytes_count,
                                    buffer_size,
                                    preallocate,
                                    "external",
                                    0,
                                    "n/a",
                                )
                            )
    return cases


def base_probe_row(
    *,
    run_id: str,
    case: StorageCase,
    case_name: str,
    path: Path,
    repeat: int,
    before: dict[str, str],
    after: dict[str, str],
    before_log: Path,
    after_log: Path,
) -> dict[str, str]:
    fs_type, free_bytes = df_snapshot(case.directory)
    mount = findmnt_snapshot(case.directory)
    row = {field: "" for field in PROBE_RAW_FIELDS}
    row.update(
        {
            "timestamp": timestamp_utc(),
            "run_id": run_id,
            "case_name": case_name,
            "dir_label": case.dir_label,
            "method": case.method,
            "operation": case.operation,
            "bytes": str(case.bytes_count),
            "buffer_size": str(case.buffer_size),
            "preallocate": case.preallocate,
            "file_io_backend": case.file_io_backend,
            "file_io_buffer_size": str(case.file_io_buffer_size),
            "posix_write_strategy": case.posix_write_strategy,
            "repeat": str(repeat),
            "path": str(path),
            "fs_type": fs_type,
            "free_bytes": free_bytes,
            "sidecar_before_log": str(before_log),
            "sidecar_after_log": str(after_log),
            "df_log": str(before_log),
            "mount_log": str(before_log),
            "lsblk_log": str(before_log),
            "iostat_log": str(after_log),
            "result": "fail",
        }
    )
    row.update(mount)
    for label, values in [("before", before), ("after", after)]:
        row[f"dirty_kb_{label}"] = values.get("dirty_kb", "")
        row[f"writeback_kb_{label}"] = values.get("writeback_kb", "")
        row[f"cached_kb_{label}"] = values.get("cached_kb", "")
    return row


def run_storage_bench_case(
    args: argparse.Namespace,
    *,
    run_id: str,
    case: StorageCase,
    output_dir: Path,
    sidecar_dir: Path,
) -> list[dict[str, str]]:
    case_name = safe_token(
        f"{case.dir_label}_{case.method}_{case.operation}_b{case.bytes_count}_buf{case.buffer_size}_"
        f"pre{case.preallocate}_{case.file_io_backend}"
    )
    case.directory.mkdir(parents=True, exist_ok=True)
    bench_path = case.directory / f"gridflux-beta1b5-{os.getpid()}-{case_name}.bin"
    before_log = sidecar_dir / f"{case_name}_before.log"
    after_log = sidecar_dir / f"{case_name}_after.log"
    before = capture_sidecar(case.directory, before_log)
    bench_modes = "write,read" if case.operation == "read" else case.operation
    command = [
        sys.executable,
        "tools/benchmark/run_storage_bench.py",
        "--side",
        "local",
        "--build-dir",
        args.local_build_dir,
        "--output-dir",
        args.output_dir,
        "--path",
        str(bench_path),
        "--bytes",
        str(case.bytes_count),
        "--modes",
        bench_modes,
        "--buffer-sizes",
        str(case.buffer_size),
        "--preallocates",
        case.preallocate,
        "--file-io-backends",
        case.file_io_backend,
        "--file-io-buffer-sizes",
        str(case.file_io_buffer_size),
        "--file-io-queue-depths",
        "1",
        "--file-io-batch-sizes",
        "1",
        "--file-io-advices",
        "off",
        "--posix-write-strategies",
        case.posix_write_strategy,
        "--iterations",
        str(args.repeat),
        "--timeout",
        str(args.case_timeout),
    ]
    if case.operation == "read":
        command.append("--keep-file")
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    log = output_dir / f"{case_name}_storage_bench.log"
    write_text(log, "$ " + " ".join(command) + "\n\n" + completed.stdout + completed.stderr)
    after = capture_sidecar(case.directory, after_log)
    raw_csv = split_key_value_stdout(completed.stdout, "csv")
    summary_csv = split_key_value_stdout(completed.stdout, "summary_csv")
    rows = [row for row in read_csv(raw_csv) if row.get("operation") == case.operation]
    if case.operation == "read":
        bench_path.unlink(missing_ok=True)
    if not rows:
        row = base_probe_row(
            run_id=run_id,
            case=case,
            case_name=case_name,
            path=bench_path,
            repeat=args.repeat,
            before=before,
            after=after,
            before_log=before_log,
            after_log=after_log,
        )
        row["tool_raw_csv"] = raw_csv
        row["tool_summary_csv"] = summary_csv
        row["log"] = str(log)
        row["error"] = (completed.stdout + completed.stderr).replace("\n", " ")[:1000]
        return [row]
    output: list[dict[str, str]] = []
    for source in rows:
        row = base_probe_row(
            run_id=run_id,
            case=case,
            case_name=case_name,
            path=bench_path,
            repeat=args.repeat,
            before=before,
            after=after,
            before_log=before_log,
            after_log=after_log,
        )
        for field in [
            "iteration",
            "aggregate",
            "elapsed_seconds",
            "throughput_gbps",
            "read_call_count",
            "write_call_count",
            "write_syscall_count",
            "write_total_bytes",
            "avg_read_bytes_per_call",
            "avg_write_bytes_per_call",
            "write_avg_bytes_per_syscall",
            "file_io_wait_seconds",
            "io_uring_submit_count",
            "io_uring_wait_count",
            "io_uring_completion_count",
        ]:
            row[field] = source.get(field, "")
        row["tool_raw_csv"] = raw_csv
        row["tool_summary_csv"] = summary_csv
        row["log"] = str(log)
        row["result"] = source.get("result", "fail")
        row["error"] = source.get("error", "")
        if completed.returncode != 0 and row["result"] == "pass":
            row["result"] = "fail"
            row["error"] = (completed.stdout + completed.stderr).replace("\n", " ")[:1000]
        output.append(row)
    return output


def fio_throughput_from_json(text: str, operation: str, bytes_count: int) -> tuple[str, str, str]:
    json_start = text.find("{")
    if json_start < 0:
        return "", "", "fio output did not contain JSON"
    try:
        data = json.loads(text[json_start:])
        section = data["jobs"][0][operation]
        elapsed = float(section.get("runtime", 0.0)) / 1000.0
        io_bytes = float(section.get("io_bytes", bytes_count))
        bw_bytes = float(section.get("bw_bytes", 0.0))
        if bw_bytes <= 0.0 and elapsed > 0.0:
            bw_bytes = io_bytes / elapsed
        throughput = (bw_bytes * 8.0) / 1_000_000_000.0 if bw_bytes > 0.0 else 0.0
        return f"{elapsed:.6f}", f"{throughput:.6f}", ""
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        return "", "", str(error)


def run_fio_case(
    args: argparse.Namespace,
    *,
    run_id: str,
    case: StorageCase,
    output_dir: Path,
    sidecar_dir: Path,
) -> list[dict[str, str]]:
    case_name = safe_token(
        f"{case.dir_label}_{case.method}_{case.operation}_b{case.bytes_count}_buf{case.buffer_size}_pre{case.preallocate}"
    )
    case.directory.mkdir(parents=True, exist_ok=True)
    fio_path = case.directory / f"gridflux-beta1b5-fio-{os.getpid()}-{case_name}.bin"
    before_log = sidecar_dir / f"{case_name}_before.log"
    after_log = sidecar_dir / f"{case_name}_after.log"
    before = capture_sidecar(case.directory, before_log)
    rows: list[dict[str, str]] = []
    if not command_exists("fio"):
        after = capture_sidecar(case.directory, after_log)
        row = base_probe_row(
            run_id=run_id,
            case=case,
            case_name=case_name,
            path=fio_path,
            repeat=args.repeat,
            before=before,
            after=after,
            before_log=before_log,
            after_log=after_log,
        )
        row["result"] = "unavailable"
        row["error"] = "fio=unavailable"
        row["log"] = str(output_dir / f"{case_name}_fio-unavailable.log")
        write_text(Path(row["log"]), "fio=unavailable\n")
        return [row]

    fallocate = "none" if case.preallocate == "off" else "posix"
    for iteration in range(1, args.repeat + 1):
        prep_text = ""
        if case.operation == "read":
            prep = [
                "fio",
                "--name=gridflux-beta1b5-prep",
                f"--filename={fio_path}",
                "--rw=write",
                f"--bs={case.buffer_size}",
                f"--size={case.bytes_count}",
                "--ioengine=sync",
                "--direct=0",
                "--numjobs=1",
                f"--fallocate={fallocate}",
                "--output-format=json",
            ]
            prep_completed = subprocess.run(prep, text=True, capture_output=True, check=False, timeout=args.case_timeout)
            prep_text = "$ " + " ".join(prep) + "\n" + prep_completed.stdout + prep_completed.stderr + "\n"
        command = [
            "fio",
            "--name=gridflux-beta1b5",
            f"--filename={fio_path}",
            f"--rw={case.operation}",
            f"--bs={case.buffer_size}",
            f"--size={case.bytes_count}",
            "--ioengine=sync",
            "--direct=0",
            "--numjobs=1",
            f"--fallocate={fallocate}",
            "--output-format=json",
        ]
        completed = subprocess.run(command, text=True, capture_output=True, check=False, timeout=args.case_timeout)
        log = output_dir / f"{case_name}_fio_iter{iteration}.log"
        write_text(log, prep_text + "$ " + " ".join(command) + "\n" + completed.stdout + completed.stderr)
        elapsed, throughput, error = fio_throughput_from_json(completed.stdout + completed.stderr, case.operation, case.bytes_count)
        row = base_probe_row(
            run_id=run_id,
            case=case,
            case_name=case_name,
            path=fio_path,
            repeat=args.repeat,
            before=before,
            after=before,
            before_log=before_log,
            after_log=after_log,
        )
        row["iteration"] = str(iteration)
        row["aggregate"] = "false"
        row["elapsed_seconds"] = elapsed
        row["throughput_gbps"] = throughput
        row["log"] = str(log)
        row["result"] = "pass" if completed.returncode == 0 and throughput else "unavailable"
        row["error"] = error if row["result"] != "pass" else ""
        rows.append(row)
    fio_path.unlink(missing_ok=True)
    after = capture_sidecar(case.directory, after_log)
    for row in rows:
        row["dirty_kb_after"] = after.get("dirty_kb", "")
        row["writeback_kb_after"] = after.get("writeback_kb", "")
        row["cached_kb_after"] = after.get("cached_kb", "")
    return rows


def summarize_probe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in rows:
        if row.get("aggregate") == "true":
            continue
        key = tuple(row.get(field, "") for field in PROBE_GROUP_FIELDS)
        grouped.setdefault(key, []).append(row)
    output: list[dict[str, str]] = []
    for key, group in sorted(grouped.items()):
        throughputs = [number(row, "throughput_gbps") for row in group if row.get("result") == "pass"]
        elapsed = [number(row, "elapsed_seconds") for row in group if row.get("result") == "pass"]
        waits = [number(row, "file_io_wait_seconds") for row in group if row.get("result") == "pass"]
        syscalls = [number(row, "write_syscall_count") for row in group if row.get("result") == "pass"]
        avg_syscalls = [number(row, "write_avg_bytes_per_syscall") for row in group if row.get("result") == "pass"]
        dirty_before = [
            number(row, "dirty_kb_before") + number(row, "writeback_kb_before")
            for row in group
            if row.get("result") == "pass"
        ]
        dirty_after = [
            number(row, "dirty_kb_after") + number(row, "writeback_kb_after")
            for row in group
            if row.get("result") == "pass"
        ]
        first = group[0]
        summary = dict(zip(PROBE_GROUP_FIELDS, key, strict=True))
        summary.update(
            {
                "case_count": str(len(group)),
                "pass_count": str(sum(1 for row in group if row.get("result") == "pass")),
                "fail_count": str(sum(1 for row in group if row.get("result") == "fail")),
                "unavailable_count": str(sum(1 for row in group if row.get("result") == "unavailable")),
                "throughput_gbps_min": f"{min(throughputs):.6f}" if throughputs else "",
                "throughput_gbps_median": f"{median(throughputs):.6f}" if throughputs else "",
                "throughput_gbps_max": f"{max(throughputs):.6f}" if throughputs else "",
                "throughput_gbps_p95": f"{p95(throughputs):.6f}" if throughputs else "",
                "throughput_gbps_spread_pct": f"{spread_pct(throughputs):.6f}" if throughputs else "",
                "elapsed_median": f"{median(elapsed):.6f}" if elapsed else "",
                "file_io_wait_seconds_median": f"{median(waits):.6f}" if waits else "",
                "write_syscall_count_median": f"{median(syscalls):.6f}" if syscalls else "",
                "write_avg_bytes_per_syscall_median": f"{median(avg_syscalls):.6f}" if avg_syscalls else "",
                "dirty_writeback_kb_before_median": f"{median(dirty_before):.6f}" if dirty_before else "",
                "dirty_writeback_kb_after_median": f"{median(dirty_after):.6f}" if dirty_after else "",
                "mount_source": first.get("mount_source", ""),
                "mount_target": first.get("mount_target", ""),
                "mount_fstype": first.get("mount_fstype", ""),
                "example_sidecar": first.get("sidecar_after_log", ""),
                "example_iostat": first.get("iostat_log", ""),
            }
        )
        output.append(summary)
    return output


def write_probe_csvs(raw_csv: Path, summary_csv: Path, rows: list[dict[str, str]]) -> None:
    with raw_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROBE_RAW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with summary_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROBE_SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summarize_probe_rows(rows))


def run_probe(args: argparse.Namespace, run_id: str, log_dir: Path) -> tuple[str, str, dict[str, int]]:
    raw_csv = ROOT / args.output_dir / f"{run_id}_storage-system-probe.csv"
    summary_csv = ROOT / args.output_dir / f"{run_id}_storage-system-probe-summary.csv"
    sidecar_dir = log_dir / "storage-sidecars"
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for index, case in enumerate(storage_system_probe_cases(args), start=1):
        print(
            f"[storage {index}] dir={case.dir_label} method={case.method} op={case.operation} "
            f"bytes={case.bytes_count} buffer={case.buffer_size} pre={case.preallocate} backend={case.file_io_backend}",
            flush=True,
        )
        if case.method == "fio":
            case_rows = run_fio_case(args, run_id=run_id, case=case, output_dir=log_dir, sidecar_dir=sidecar_dir)
        else:
            case_rows = run_storage_bench_case(
                args, run_id=run_id, case=case, output_dir=log_dir, sidecar_dir=sidecar_dir
            )
        rows.extend(case_rows)
        write_probe_csvs(raw_csv, summary_csv, rows)
    counts = {
        "rows": len(rows),
        "pass": sum(1 for row in rows if row.get("result") == "pass"),
        "fail": sum(1 for row in rows if row.get("result") == "fail"),
        "unavailable": sum(1 for row in rows if row.get("result") == "unavailable"),
    }
    return str(raw_csv), str(summary_csv), counts


def matrix_common(
    args: argparse.Namespace,
    *,
    bytes_value: str,
    repeat: int,
    event_dir: Path,
    storage_csv: str,
    tls_mode: str,
    data_tls_mode: str,
    run_root_base: Path,
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
        "--manifest-flush-policies",
        "every_n_chunks",
        "--manifest-flush-interval-chunks-list",
        "16",
        "--commit-sync-policies",
        "none",
        "--final-verify-policies",
        "full",
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
    if storage_csv:
        command.extend(["--storage-bench-csv", storage_csv])
    return command


def aligned_stor_step_specs(
    args: argparse.Namespace,
    *,
    bytes_values: list[int],
    repeat: int,
    event_dir: Path,
    storage_csv: str,
) -> list[StepSpec]:
    run_root_base = ROOT / args.output_dir / "beta1b5-stor-runroots"
    specs: list[StepSpec] = []
    for bytes_value in bytes_values:
        common_off = matrix_common(
            args,
            bytes_value=str(bytes_value),
            repeat=repeat,
            event_dir=event_dir,
            storage_csv=storage_csv,
            tls_mode="off",
            data_tls_mode="off",
            run_root_base=run_root_base,
        )
        specs.append(
            StepSpec(
                f"stor_storage_system_posix_off_{bytes_value}",
                [
                    *common_off,
                    "--connections",
                    "1,4,8",
                    "--checksums",
                    "crc32c,none",
                ],
            )
        )
        common_tls = matrix_common(
            args,
            bytes_value=str(bytes_value),
            repeat=repeat,
            event_dir=event_dir,
            storage_csv=storage_csv,
            tls_mode="required",
            data_tls_mode="required",
            run_root_base=run_root_base,
        )
        specs.append(
            StepSpec(
                f"stor_storage_system_posix_tls_{bytes_value}",
                [
                    *common_tls,
                    "--connections",
                    "4",
                    "--checksums",
                    "crc32c",
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
    write_text(log_path, "$ " + " ".join(spec.command) + "\n\n" + completed.stdout + completed.stderr)
    return {
        "name": spec.name,
        "command": spec.command,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "log": str(log_path),
        "stdout": completed.stdout,
        "result": "pass" if completed.returncode == 0 else "fail",
    }


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


def analyzer_step(
    *,
    probe_raw: str,
    probe_summary: str,
    stor_raws: list[str],
    stor_summaries: list[str],
    report_path: Path,
) -> StepSpec:
    command = [
        sys.executable,
        "tools/perf/analyze_beta1b_storage_system.py",
        "--output",
        str(report_path),
        "--probe-raw-csv",
        probe_raw,
        "--probe-summary-csv",
        probe_summary,
    ]
    for raw in stor_raws:
        command.extend(["--matrix-raw-csv", raw])
    for summary in stor_summaries:
        command.extend(["--matrix-summary-csv", summary])
    return StepSpec("analyze_beta1b_storage_system", command)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Beta 1B-5 storage/system attribution probes.")
    parser.add_argument("--remote", default="root@<redacted>")
    parser.add_argument("--server-host", default="<redacted>")
    parser.add_argument("--local-build-dir", default="/root/projects/GridFlux/build-io-uring-real")
    parser.add_argument("--remote-build-dir", default="/root/projects/GridFlux/build-io-uring-real")
    parser.add_argument("--output-dir", default="tools/perf/results")
    parser.add_argument("--bytes", default="1073741824")
    parser.add_argument("--bytes-list", default="")
    parser.add_argument("--buffer-sizes", default="262144,1048576")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--case-timeout", type=int, default=1800)
    parser.add_argument("--probe-dirs", default="", help="comma list of label:path entries")
    parser.add_argument("--skip-fio", action="store_true")
    parser.add_argument("--skip-iouring-subset", action="store_true")
    parser.add_argument("--skip-storage-probe", action="store_true")
    parser.add_argument("--skip-stor-matrix", action="store_true")
    args = parser.parse_args()

    if args.repeat <= 0:
        raise SystemExit("--repeat must be greater than zero")
    if args.bytes_list and args.bytes:
        bytes_values = parse_int_list(args.bytes_list)
    else:
        bytes_values = parse_int_list(args.bytes_list or args.bytes)
    if not bytes_values:
        raise SystemExit("at least one byte size is required")

    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = compact_timestamp()
    run_slug = "beta1b-storage-system-attribution"
    log_dir = output_dir / f"{run_id}_{run_slug}"
    log_dir.mkdir(parents=True, exist_ok=True)
    event_dir = log_dir / "events"
    event_dir.mkdir(parents=True, exist_ok=True)
    report_path = ROOT / "docs" / "perf" / "BETA1B_STORAGE_SYSTEM_ATTRIBUTION.md"
    summary_json = output_dir / f"{run_id}_{run_slug}.json"

    env = run_env(args.remote)
    steps: list[dict[str, object]] = []
    probe_raw = ""
    probe_summary = ""
    probe_counts = {"rows": 0, "pass": 0, "fail": 0, "unavailable": 0}
    if not args.skip_storage_probe:
        probe_raw, probe_summary, probe_counts = run_probe(args, run_id, log_dir)

    stor_raws: list[str] = []
    stor_summaries: list[str] = []
    if not args.skip_stor_matrix:
        for spec in aligned_stor_step_specs(
            args,
            bytes_values=bytes_values,
            repeat=args.repeat,
            event_dir=event_dir,
            storage_csv=probe_raw,
        ):
            step = run_step(spec, log_dir, env=env)
            steps.append(step)
            raw = split_key_value_stdout(str(step.get("stdout", "")), "csv")
            summary = split_key_value_stdout(str(step.get("stdout", "")), "summary_csv")
            if raw:
                stor_raws.append(raw)
            if summary:
                stor_summaries.append(summary)

    analyze = run_step(
        analyzer_step(
            probe_raw=probe_raw,
            probe_summary=probe_summary,
            stor_raws=stor_raws,
            stor_summaries=stor_summaries,
            report_path=report_path,
        ),
        log_dir,
        env=env,
    )
    steps.append(analyze)

    stor_cases = 0
    stor_failures = 0
    for step in steps:
        if str(step["name"]).startswith("stor_"):
            cases, failures = parse_cases(str(step.get("stdout", "")))
            stor_cases += cases
            stor_failures += failures
    grouped_failures = summary_fail_count(stor_summaries)
    mismatches = hash_mismatch_count(stor_raws)
    step_failures = [step for step in steps if step["result"] != "pass"]
    result = "pass" if not step_failures and probe_counts["fail"] == 0 and grouped_failures == 0 and mismatches == 0 else "fail"

    summary = {
        "timestamp": timestamp_utc(),
        "result": result,
        "bytes_list": [str(value) for value in bytes_values],
        "repeat": args.repeat,
        "probe_raw_csv": probe_raw,
        "probe_summary_csv": probe_summary,
        "probe_counts": probe_counts,
        "stor_raw_csvs": stor_raws,
        "stor_summary_csvs": stor_summaries,
        "stor_transfer_cases": stor_cases,
        "stor_transfer_failures": stor_failures,
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
    print(f"probe_raw_csv={probe_raw}")
    print(f"probe_summary_csv={probe_summary}")
    for raw in stor_raws:
        print(f"stor_raw_csv={raw}")
    for summary_path in stor_summaries:
        print(f"stor_summary_csv={summary_path}")
    print(
        f"probe_rows={probe_counts['rows']} probe_pass={probe_counts['pass']} "
        f"probe_fail={probe_counts['fail']} probe_unavailable={probe_counts['unavailable']}"
    )
    print(f"stor_transfer_cases={stor_cases} stor_transfer_failures={stor_failures}")
    print(f"grouped_fail_count={grouped_failures}")
    print(f"hash_mismatch_count={mismatches}")
    print(f"result={result}")
    return 0 if result == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
