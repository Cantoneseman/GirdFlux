#!/usr/bin/env python3
"""Run a layered cloud disk/writeback bottleneck proof on the private cloud pair.

This is a measurement wrapper only. It does not install packages, does not
change GridFlux defaults, and delegates transfer correctness to the existing
private GridFTP matrix runner.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import math
import os
import shlex
import socket
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "release"))
sys.path.insert(0, str(ROOT / "tools" / "perf"))
import remote_auth  # noqa: E402

storage_probe = importlib.import_module("run_beta1b_storage_system_probe")


TMP_PREFIX = "/tmp/gridflux-cloud-disk-proof"
DEFAULT_BYTES = [1024**3, 4 * 1024**3]
DEFAULT_DEFAULTS = {
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

NETWORK_FIELDS = [
    "timestamp",
    "direction",
    "parallelism",
    "duration_seconds",
    "throughput_gbps",
    "status",
    "server_log",
    "client_log",
    "error",
]

CHECKSUM_FIELDS = [
    "timestamp",
    "machine",
    "backend_requested",
    "backend_effective",
    "size_bytes",
    "iterations",
    "elapsed_seconds",
    "throughput_gbps",
    "status",
    "log",
    "error",
]

MEMORY_FIELDS = [
    "timestamp",
    "side",
    "category",
    "tool",
    "bytes",
    "elapsed_seconds",
    "throughput_gbps",
    "status",
    "log",
    "error",
]


@dataclass(frozen=True)
class MatrixStep:
    name: str
    command: list[str]


@dataclass
class RunState:
    timestamp: str
    output_dir: Path
    network_rows: list[dict[str, str]] = field(default_factory=list)
    checksum_rows: list[dict[str, str]] = field(default_factory=list)
    memory_rows: list[dict[str, str]] = field(default_factory=list)
    storage_raw_csv: str = ""
    storage_summary_csv: str = ""
    storage_counts: dict[str, int] = field(default_factory=dict)
    stor_raw_csvs: list[str] = field(default_factory=list)
    stor_summary_csvs: list[str] = field(default_factory=list)
    retr_raw_csvs: list[str] = field(default_factory=list)
    retr_summary_csvs: list[str] = field(default_factory=list)
    steps: list[dict[str, object]] = field(default_factory=list)
    cleanup: dict[str, str] = field(default_factory=dict)


def compact_timestamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def timestamp_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_private_env(path: Path = Path("/root/.xtransfer_env")) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            parsed = shlex.split(value, posix=True)
            value = parsed[0] if parsed else ""
        except ValueError:
            value = value.strip().strip("'\"")
        if key.strip():
            os.environ.setdefault(key.strip(), value)
    for candidate in ("GRIDFLUX_SSH_PASSWORD", "SSHPASS", "XTRANSFER_SSH_PASSWORD", "SSH_PASSWORD"):
        if os.environ.get(candidate):
            os.environ.setdefault("GRIDFLUX_SSH_PASSWORD", os.environ[candidate])
            os.environ.setdefault("SSHPASS", os.environ[candidate])
            break


def sanitize(text: str, max_len: int = 1200) -> str:
    cleaned = " ".join((text or "").replace("\x00", "").split())
    redacted = [
        "password",
        "passwd",
        "token",
        "private_key",
        "BEGIN PRIVATE KEY",
        "GRIDFLUX_SSH_PASSWORD",
        "SSHPASS",
        "XTRANSFER_SSH_PASSWORD",
    ]
    for marker in redacted:
        cleaned = cleaned.replace(marker, "<redacted>")
    return cleaned[:max_len]


def parse_size_token(token: str) -> int:
    value = token.strip().lower()
    for suffix, multiplier in [
        ("gib", 1024**3),
        ("gb", 1000**3),
        ("g", 1024**3),
        ("mib", 1024**2),
        ("mb", 1000**2),
        ("m", 1024**2),
        ("kib", 1024),
        ("kb", 1000),
        ("k", 1024),
    ]:
        if value.endswith(suffix):
            return int(value[: -len(suffix)]) * multiplier
    return int(value)


def parse_size_list(text: str) -> list[int]:
    return [parse_size_token(part) for part in text.split(",") if part.strip()]


def parse_int_list(text: str) -> list[int]:
    return [int(part.strip()) for part in text.split(",") if part.strip()]


def relative_to_root(path: str | Path) -> str:
    parsed = Path(path)
    if not parsed.is_absolute():
        parsed = ROOT / parsed
    try:
        return parsed.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(parsed.resolve())


def run_local(script: str, *, timeout: int = 120, check: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(sanitize(completed.stderr or completed.stdout))
    return completed


def run_remote(remote: str, script: str, *, timeout: int = 120, check: bool = False) -> subprocess.CompletedProcess[str]:
    command = remote_auth.ssh_prefix(remote, root=ROOT) + [f"bash -lc {shlex.quote(script)}"]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=remote_auth.command_env(remote, ROOT),
    )
    if check and completed.returncode != 0:
        raise RuntimeError(sanitize(completed.stderr or completed.stdout))
    return completed


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def read_csv(path_text: str) -> list[dict[str, str]]:
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def merge_csv_files(sources: list[str], destination: Path) -> str:
    rows: list[dict[str, str]] = []
    fields: list[str] = []
    for source in sources:
        path = Path(source)
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file():
            continue
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for field in reader.fieldnames or []:
                if field not in fields:
                    fields.append(field)
            rows.extend(reader)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    return relative_to_root(destination)


def key_value(stdout: str, key: str) -> str:
    prefix = key + "="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip()
    return ""


def command_exists_local(binary: str) -> bool:
    return run_local(f"command -v {shlex.quote(binary)} >/dev/null 2>&1").returncode == 0


def command_exists_remote(remote: str, binary: str) -> bool:
    return run_remote(remote, f"command -v {shlex.quote(binary)} >/dev/null 2>&1").returncode == 0


def find_bench_binary(build_dir: str, name: str) -> str:
    candidates = [Path(build_dir) / name, ROOT / "build" / name, ROOT / "build-io-uring-real" / name]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return str(Path(build_dir) / name)


def environment_script(server_host: str, client_host: str) -> str:
    project = "/root/projects/GridFlux"
    return f"""
set +e
echo "generated=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "hostname=$(hostname 2>/dev/null || true)"
if [ -r /etc/os-release ]; then . /etc/os-release; echo "os=${{PRETTY_NAME:-unknown}}"; fi
echo "kernel=$(uname -srmo 2>/dev/null || true)"
echo "cpu=$(LC_ALL=C lscpu 2>/dev/null | awk -F: '/Model name/ {{gsub(/^[ \\t]+/, "", $2); print $2; exit}}')"
echo "memory_kb=$(awk '/MemTotal:/ {{print $2; exit}}' /proc/meminfo 2>/dev/null)"
echo "project_exists=$([ -d {project} ] && echo yes || echo no)"
echo "build_exists=$([ -d {project}/build ] && echo yes || echo no)"
echo "build_server=$([ -x {project}/build/gridflux-gridftp-server ] && echo yes || echo no)"
echo "build_checksum=$([ -x {project}/build/gridflux-checksum-bench ] && echo yes || echo no)"
echo "build_storage=$([ -x {project}/build/gridflux-storage-bench ] && echo yes || echo no)"
route_line=$(ip route get {shlex.quote(server_host)} 2>/dev/null || ip route get {shlex.quote(client_host)} 2>/dev/null || true)
echo "route=$route_line"
iface=$(printf '%s\\n' "$route_line" | awk '{{for (i=1;i<=NF;i++) if ($i=="dev") {{print $(i+1); exit}}}}')
echo "iface=$iface"
if [ -n "$iface" ]; then
  echo "iface_link=$(ip -o link show "$iface" 2>/dev/null || true)"
  echo "iface_addr=$(ip -o addr show "$iface" 2>/dev/null || true)"
  echo "iface_driver=$(ethtool -i "$iface" 2>/dev/null | tr '\\n' ';' || true)"
  echo "iface_speed=$(ethtool "$iface" 2>/dev/null | awk -F: '/Speed:/ {{gsub(/^[ \\t]+/, "", $2); print $2; exit}}')"
fi
for bin in cmake ninja ctest g++-13 python3 iperf3 iostat fio findmnt lsblk gridflux-checksum-bench gridflux-storage-bench; do
  echo "binary=$bin path=$(command -v "$bin" 2>/dev/null || true)"
done
for path in /tmp {project} {project}/tools/perf/results; do
  echo "df=$path $(df -PT "$path" 2>/dev/null | tail -n 1)"
  if command -v findmnt >/dev/null 2>&1; then echo "findmnt=$path $(findmnt -T "$path" -n -o SOURCE,TARGET,FSTYPE,OPTIONS 2>/dev/null)"; fi
done
echo "section=lsblk"
if command -v lsblk >/dev/null 2>&1; then lsblk -b -f -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS,MODEL 2>&1 || true; else echo "lsblk=unavailable"; fi
"""


def collect_environment(args: argparse.Namespace, txt_path: Path, json_path: Path) -> dict[str, object]:
    local = run_local(environment_script(args.server_host, args.client_host), timeout=180)
    remote = run_remote(args.remote, environment_script(args.server_host, args.client_host), timeout=180)
    ping = run_remote(args.remote, f"ping -c 3 -W 2 {shlex.quote(args.server_host)}", timeout=30)
    ssh_ok = remote.returncode == 0
    text = "\n".join(
        [
            f"generated={timestamp_utc()}",
            "scope=machine_one_server",
            local.stdout.strip(),
            "",
            "scope=machine_two_client",
            remote.stdout.strip(),
            "",
            "scope=private_connectivity",
            sanitize(ping.stdout or ping.stderr, 4000),
            "",
        ]
    )
    write_text(txt_path, text)
    local_bins = {name: command_exists_local(name) for name in ["cmake", "ninja", "ctest", "g++-13", "python3", "iperf3", "iostat", "fio"]}
    remote_bins = {
        name: command_exists_remote(args.remote, name)
        for name in ["cmake", "ninja", "ctest", "g++-13", "python3", "iperf3", "iostat", "fio"]
    }
    health = {
        "timestamp": timestamp_utc(),
        "ssh_remote_ok": ssh_ok,
        "local_environment_returncode": local.returncode,
        "remote_environment_returncode": remote.returncode,
        "private_ping_returncode": ping.returncode,
        "local_binaries": local_bins,
        "remote_binaries": remote_bins,
        "fio_status": "available" if local_bins.get("fio") or remote_bins.get("fio") else "fio_unavailable",
    }
    write_text(json_path, json.dumps(health, indent=2, sort_keys=True) + "\n")
    return health


def wait_for_port(host: str, port: int, *, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            try:
                sock.connect((host, port))
                return True
            except OSError:
                time.sleep(0.2)
    return False


def parse_iperf_gbps(stdout: str) -> str:
    try:
        data = json.loads(stdout)
    except ValueError:
        return ""
    end = data.get("end", {})
    bps = (
        end.get("sum_received", {}).get("bits_per_second")
        or end.get("sum_sent", {}).get("bits_per_second")
        or end.get("sum", {}).get("bits_per_second")
    )
    return f"{float(bps) / 1_000_000_000:.3f}" if bps else ""


def run_network(args: argparse.Namespace, path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not command_exists_local("iperf3") or not command_exists_remote(args.remote, "iperf3"):
        rows.append(
            {
                "timestamp": timestamp_utc(),
                "direction": "preflight",
                "status": "fail",
                "error": "iperf3 unavailable on one or both hosts",
            }
        )
        write_csv(path, rows, NETWORK_FIELDS)
        return rows

    server_log = args.log_dir / f"{args.timestamp}_cloud-disk-proof-iperf3-server.log"
    proc: subprocess.Popen[str] | None = None
    try:
        with server_log.open("w", encoding="utf-8") as handle:
            proc = subprocess.Popen(
                ["iperf3", "-s", "-B", args.server_host, "-p", str(args.iperf_port)],
                cwd=ROOT,
                text=True,
                stdout=handle,
                stderr=subprocess.STDOUT,
            )
        time.sleep(1.0)
        for p in args.parallelism_values:
            result = run_remote(
                args.remote,
                f"iperf3 -J -c {shlex.quote(args.server_host)} -p {args.iperf_port} -P {p} -t {args.iperf_seconds}",
                timeout=args.iperf_seconds + 90,
            )
            rows.append(
                {
                    "timestamp": timestamp_utc(),
                    "direction": "client_to_server",
                    "parallelism": str(p),
                    "duration_seconds": str(args.iperf_seconds),
                    "throughput_gbps": parse_iperf_gbps(result.stdout),
                    "status": "pass" if result.returncode == 0 else "fail",
                    "server_log": relative_to_root(server_log),
                    "client_log": "",
                    "error": "" if result.returncode == 0 else sanitize(result.stderr or result.stdout),
                }
            )
            write_csv(path, rows, NETWORK_FIELDS)
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    remote_log = f"{TMP_PREFIX}-iperf3-client-server.log"
    start = run_remote(
        args.remote,
        f"rm -f {shlex.quote(remote_log)}; nohup iperf3 -s -B {shlex.quote(args.client_host)} -p {args.iperf_reverse_port} >{shlex.quote(remote_log)} 2>&1 & echo $!",
        timeout=30,
    )
    remote_pid = start.stdout.strip().splitlines()[-1] if start.stdout.strip() else ""
    time.sleep(1.0)
    fetched_remote_log = args.log_dir / f"{args.timestamp}_cloud-disk-proof-iperf3-client-server.log"
    try:
        for p in args.parallelism_values:
            result = run_local(
                f"iperf3 -J -c {shlex.quote(args.client_host)} -p {args.iperf_reverse_port} -P {p} -t {args.iperf_seconds}",
                timeout=args.iperf_seconds + 90,
            )
            rows.append(
                {
                    "timestamp": timestamp_utc(),
                    "direction": "server_to_client",
                    "parallelism": str(p),
                    "duration_seconds": str(args.iperf_seconds),
                    "throughput_gbps": parse_iperf_gbps(result.stdout),
                    "status": "pass" if result.returncode == 0 else "fail",
                    "server_log": "",
                    "client_log": relative_to_root(fetched_remote_log),
                    "error": "" if result.returncode == 0 else sanitize(result.stderr or result.stdout),
                }
            )
            write_csv(path, rows, NETWORK_FIELDS)
    finally:
        if remote_pid.isdigit():
            run_remote(args.remote, f"kill {remote_pid} >/dev/null 2>&1 || true", timeout=30)
        fetch_remote(args.remote, remote_log, fetched_remote_log)
    write_csv(path, rows, NETWORK_FIELDS)
    return rows


def fetch_remote(remote: str, remote_path: str, local_path: Path) -> bool:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    command = ["scp", "-o", "StrictHostKeyChecking=no", f"{remote}:{remote_path}", str(local_path)]
    command, env = remote_auth.wrap_with_sshpass(remote, command, root=ROOT)
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, env=env)
    if completed.returncode != 0:
        write_text(local_path, sanitize(completed.stderr or completed.stdout))
        return False
    return True


def run_checksum(args: argparse.Namespace, path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    local_bin = find_bench_binary(args.local_build_dir, "gridflux-checksum-bench")
    remote_bin = f"{args.remote_build_dir.rstrip('/')}/gridflux-checksum-bench"
    for machine, runner, bench in [
        ("server", lambda command, timeout: run_local(command, timeout=timeout), local_bin),
        ("client", lambda command, timeout: run_remote(args.remote, command, timeout=timeout), remote_bin),
    ]:
        for backend in ["hardware", "software", "auto"]:
            log = args.log_dir / f"{args.timestamp}_{machine}-checksum-{backend}.log"
            command = (
                f"{shlex.quote(bench)} --backend {backend} --bytes {args.checksum_bytes} "
                f"--iterations {args.checksum_iterations}"
            )
            result = runner(command, 1200)
            write_text(log, result.stdout + result.stderr)
            throughput = ""
            elapsed = ""
            effective = backend
            for line in (result.stdout + result.stderr).splitlines():
                if "throughput_gbps=" in line:
                    throughput = line.split("throughput_gbps=", 1)[1].split()[0]
                if line.startswith("elapsed_seconds="):
                    elapsed = line.split("=", 1)[1].strip()
                if "backend=" in line:
                    effective = line.split("backend=", 1)[1].split()[0]
            rows.append(
                {
                    "timestamp": timestamp_utc(),
                    "machine": machine,
                    "backend_requested": backend,
                    "backend_effective": effective,
                    "size_bytes": str(args.checksum_bytes),
                    "iterations": str(args.checksum_iterations),
                    "elapsed_seconds": elapsed,
                    "throughput_gbps": throughput,
                    "status": "pass" if result.returncode == 0 and throughput else "fail",
                    "log": relative_to_root(log),
                    "error": "" if result.returncode == 0 else sanitize(result.stderr or result.stdout),
                }
            )
            write_csv(path, rows, CHECKSUM_FIELDS)
    write_csv(path, rows, CHECKSUM_FIELDS)
    return rows


def run_memory_or_sink(args: argparse.Namespace, path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    script = ROOT / "tools" / "perf" / "run_private_host_baseline.py"
    if not script.is_file():
        rows.append(
            {
                "timestamp": timestamp_utc(),
                "side": "link",
                "category": "memory_or_sink",
                "tool": "unavailable",
                "bytes": str(args.memory_bytes),
                "status": "unavailable",
                "error": "run_private_host_baseline.py missing",
            }
        )
        write_csv(path, rows, MEMORY_FIELDS)
        return rows
    command = [
        sys.executable,
        str(script),
        "--remote",
        args.remote,
        "--server-host",
        args.server_host,
        "--local-build-dir",
        args.local_build_dir,
        "--remote-build-dir",
        args.remote_build_dir,
        "--bytes",
        str(args.memory_bytes),
        "--output-dir",
        args.output_dir,
        "--timeout",
        str(args.case_timeout),
    ]
    started = time.time()
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, timeout=args.case_timeout + 120)
    log = args.log_dir / f"{args.timestamp}_memory-or-sink.log"
    write_text(log, "$ " + " ".join(shlex.quote(part) for part in command) + "\n\n" + completed.stdout + completed.stderr)
    candidates = [
        candidate
        for candidate in (ROOT / args.output_dir).glob("*_host-baseline.csv")
        if candidate.stat().st_mtime >= started - 1
    ]
    source = max(candidates, key=lambda item: item.stat().st_mtime) if candidates else None
    if source:
        for row in read_csv(str(source)):
            rows.append(
                {
                    "timestamp": row.get("timestamp", timestamp_utc()),
                    "side": row.get("side", ""),
                    "category": row.get("category", ""),
                    "tool": row.get("tool", ""),
                    "bytes": row.get("bytes", ""),
                    "elapsed_seconds": row.get("elapsed_seconds", ""),
                    "throughput_gbps": row.get("throughput_gbps", ""),
                    "status": row.get("result", ""),
                    "log": row.get("log", ""),
                    "error": row.get("error", ""),
                }
            )
    else:
        rows.append(
            {
                "timestamp": timestamp_utc(),
                "side": "link",
                "category": "memory_or_sink",
                "tool": "unavailable",
                "bytes": str(args.memory_bytes),
                "status": "unavailable",
                "log": relative_to_root(log),
                "error": sanitize(completed.stderr or completed.stdout),
            }
        )
    write_csv(path, rows, MEMORY_FIELDS)
    return rows


def run_storage_probe(args: argparse.Namespace) -> tuple[str, str, dict[str, int]]:
    probe_args = argparse.Namespace(
        remote=args.remote,
        server_host=args.server_host,
        local_build_dir=args.local_build_dir,
        remote_build_dir=args.remote_build_dir,
        output_dir=args.output_dir,
        bytes=",".join(str(value) for value in args.bytes_values),
        bytes_list=",".join(str(value) for value in args.bytes_values),
        buffer_sizes=args.storage_buffer_sizes,
        repeat=args.repeat,
        case_timeout=args.case_timeout,
        probe_dirs=args.probe_dirs,
        skip_fio=args.skip_fio,
        skip_iouring_subset=True,
        skip_storage_probe=False,
        skip_stor_matrix=True,
    )
    return storage_probe.run_probe(probe_args, args.timestamp + "_cloud-disk-proof", args.log_dir)


def matrix_common(
    args: argparse.Namespace,
    *,
    direction: str,
    bytes_value: int,
    event_dir: Path,
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
        direction,
        "--bytes",
        str(bytes_value),
        "--connections",
        ",".join(str(value) for value in args.connections_values),
        "--chunk-sizes",
        "4194304",
        "--buffer-sizes",
        "262144",
        "--checksums",
        "crc32c,none",
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
        "off",
        "--data-tls-modes",
        "off",
        "--event-log-dir",
        str(event_dir),
        "--repeat",
        str(args.repeat),
        "--case-timeout",
        str(args.case_timeout),
        "--run-root-base",
        str(run_root_base),
    ]


def gridflux_step_specs(args: argparse.Namespace, event_dir: Path) -> list[MatrixStep]:
    specs: list[MatrixStep] = []
    run_root_base = Path(f"{TMP_PREFIX}-gridflux-runs")
    for direction in ["stor", "retr"]:
        for bytes_value in args.bytes_values:
            specs.append(
                MatrixStep(
                    name=f"gridflux_{direction}_{bytes_value}",
                    command=matrix_common(
                        args,
                        direction=direction,
                        bytes_value=bytes_value,
                        event_dir=event_dir / f"{direction}_{bytes_value}",
                        run_root_base=run_root_base,
                    ),
                )
            )
    return specs


def run_step(spec: MatrixStep, log_dir: Path) -> dict[str, object]:
    log_path = log_dir / f"{spec.name}.log"
    started = time.monotonic()
    completed = subprocess.run(
        spec.command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
        timeout=max(3600, 64 * 60),
    )
    elapsed = time.monotonic() - started
    write_text(log_path, "$ " + " ".join(shlex.quote(part) for part in spec.command) + "\n\n" + completed.stdout + completed.stderr)
    return {
        "name": spec.name,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "log": relative_to_root(log_path),
        "stdout": completed.stdout,
        "result": "pass" if completed.returncode == 0 else "fail",
    }


def split_key_value_stdout(stdout: str, key: str) -> str:
    prefix = key + "="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip()
    return ""


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


def run_gridflux_matrix(args: argparse.Namespace, state: RunState) -> None:
    event_dir = args.log_dir / "events"
    event_dir.mkdir(parents=True, exist_ok=True)
    for spec in gridflux_step_specs(args, event_dir):
        step = run_step(spec, args.log_dir)
        state.steps.append({key: value for key, value in step.items() if key != "stdout"})
        raw = split_key_value_stdout(str(step.get("stdout", "")), "csv") or split_key_value_stdout(
            str(step.get("stdout", "")), "raw_csv"
        )
        summary = split_key_value_stdout(str(step.get("stdout", "")), "summary_csv")
        if raw and "_stor_" in spec.name:
            state.stor_raw_csvs.append(raw)
        elif raw:
            state.retr_raw_csvs.append(raw)
        if summary and "_stor_" in spec.name:
            state.stor_summary_csvs.append(summary)
        elif summary:
            state.retr_summary_csvs.append(summary)


def run_analyzer(args: argparse.Namespace, paths: dict[str, str], state: RunState) -> tuple[str, str]:
    summary_csv = args.output_dir_path / f"{args.timestamp}_cloud-disk-proof-attribution-summary.csv"
    report = ROOT / "docs" / "perf" / "CLOUD_DISK_BOTTLENECK_PROOF.md"
    command = [
        sys.executable,
        "tools/perf/analyze_cloud_disk_bottleneck_proof.py",
        "--network-csv",
        paths["network_csv"],
        "--checksum-csv",
        paths["checksum_csv"],
        "--memory-csv",
        paths["memory_csv"],
        "--storage-raw-csv",
        state.storage_raw_csv,
        "--storage-summary-csv",
        state.storage_summary_csv,
        "--output",
        str(report),
        "--summary-output",
        str(summary_csv),
    ]
    for raw in state.stor_raw_csvs:
        command.extend(["--stor-raw-csv", raw])
    for summary in state.stor_summary_csvs:
        command.extend(["--stor-summary-csv", summary])
    for raw in state.retr_raw_csvs:
        command.extend(["--retr-raw-csv", raw])
    for summary in state.retr_summary_csvs:
        command.extend(["--retr-summary-csv", summary])
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    log = args.log_dir / "analyze_cloud_disk_bottleneck_proof.log"
    write_text(log, "$ " + " ".join(shlex.quote(part) for part in command) + "\n\n" + completed.stdout + completed.stderr)
    state.steps.append(
        {
            "name": "analyze_cloud_disk_bottleneck_proof",
            "returncode": completed.returncode,
            "elapsed_seconds": "",
            "log": relative_to_root(log),
            "result": "pass" if completed.returncode == 0 else "fail",
        }
    )
    return relative_to_root(report), relative_to_root(summary_csv)


def run_plotter(args: argparse.Namespace, summary_csv: str) -> list[str]:
    command = [
        sys.executable,
        "tools/perf/plot_cloud_disk_bottleneck_proof.py",
        "--summary-csv",
        summary_csv,
        "--output-dir",
        "docs/perf/figures",
        "--format",
        args.figure_format,
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    log = args.log_dir / "plot_cloud_disk_bottleneck_proof.log"
    write_text(log, "$ " + " ".join(shlex.quote(part) for part in command) + "\n\n" + completed.stdout + completed.stderr)
    outputs = []
    for line in completed.stdout.splitlines():
        if line.startswith("figure="):
            outputs.append(line.split("=", 1)[1].strip())
    return outputs


def cleanup(args: argparse.Namespace) -> dict[str, str]:
    process_check = (
        "ps -eo pid=,comm=,args= | awk '$2 ~ /^(globus-gridftp-server|globus-url-copy|"
        "gridflux-gridftp-server|gridflux-file-server|gridflux-file-client|gridflux-file-download-sender|"
        "gridflux-file-download-client|iperf3)$/ {print}'"
    )
    run_local(
        "ps -eo pid=,comm=,args= | awk '$2 ~ /^(iperf3|globus-gridftp-server|globus-url-copy|"
        "gridflux-gridftp-server|gridflux-file-server|gridflux-file-client|gridflux-file-download-sender|"
        "gridflux-file-download-client)$/ && ($0 ~ /gridflux-cloud-disk-proof/ || $0 ~ /gridflux_phase4a/) {print $1}' "
        "| xargs -r kill >/dev/null 2>&1 || true",
        timeout=30,
    )
    run_remote(
        args.remote,
        "ps -eo pid=,comm=,args= | awk '$2 ~ /^(iperf3|globus-gridftp-server|globus-url-copy|"
        "gridflux-gridftp-server|gridflux-file-server|gridflux-file-client|gridflux-file-download-sender|"
        "gridflux-file-download-client)$/ && ($0 ~ /gridflux-cloud-disk-proof/ || $0 ~ /gridflux_phase4a/) {print $1}' "
        "| xargs -r kill >/dev/null 2>&1 || true",
        timeout=30,
    )
    run_local(f"rm -rf {TMP_PREFIX}-* /tmp/gridflux_phase4a_*", timeout=300)
    run_remote(args.remote, f"rm -rf {TMP_PREFIX}-* /tmp/gridflux_phase4a_*", timeout=300)
    local_residual = run_local(process_check, timeout=30).stdout.strip()
    remote_residual = run_remote(args.remote, process_check, timeout=30).stdout.strip()
    return {
        "removed_temp_prefix": f"{TMP_PREFIX}-* and /tmp/gridflux_phase4a_*",
        "server_residual_processes": local_residual,
        "client_residual_processes": remote_residual,
    }


def write_wrapper(state: RunState, paths: dict[str, str]) -> Path:
    network_failures = sum(1 for row in state.network_rows if row.get("status") != "pass")
    checksum_failures = sum(1 for row in state.checksum_rows if row.get("status") != "pass")
    storage_failures = int(state.storage_counts.get("fail", 0))
    matrix_failures = summary_fail_count(state.stor_summary_csvs + state.retr_summary_csvs)
    mismatches = hash_mismatch_count(state.stor_raw_csvs + state.retr_raw_csvs)
    step_failures = sum(1 for step in state.steps if step.get("result") != "pass")
    status = (
        "pass"
        if network_failures == 0
        and checksum_failures == 0
        and storage_failures == 0
        and matrix_failures == 0
        and mismatches == 0
        and step_failures == 0
        else "fail"
    )
    wrapper = state.output_dir / f"{state.timestamp}_cloud-disk-proof.json"
    write_text(
        wrapper,
        json.dumps(
            {
                "timestamp": state.timestamp,
                "generated": timestamp_utc(),
                "status": status,
                "default_strategy": DEFAULT_DEFAULTS,
                "paths": paths,
                "storage_counts": state.storage_counts,
                "stor_raw_csvs": state.stor_raw_csvs,
                "stor_summary_csvs": state.stor_summary_csvs,
                "retr_raw_csvs": state.retr_raw_csvs,
                "retr_summary_csvs": state.retr_summary_csvs,
                "network_failures": network_failures,
                "checksum_failures": checksum_failures,
                "storage_failures": storage_failures,
                "matrix_grouped_failures": matrix_failures,
                "hash_mismatch_count": mismatches,
                "steps": state.steps,
                "cleanup": state.cleanup,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return wrapper


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default=os.environ.get("GRIDFLUX_REMOTE", "root@<redacted>"))
    parser.add_argument("--server-host", default=os.environ.get("GRIDFLUX_SERVER_HOST", "<redacted>"))
    parser.add_argument("--client-host", default=os.environ.get("GRIDFLUX_CLIENT_HOST", "<redacted>"))
    parser.add_argument("--local-build-dir", default="/root/projects/GridFlux/build")
    parser.add_argument("--remote-build-dir", default="/root/projects/GridFlux/build")
    parser.add_argument("--output-dir", default="tools/perf/results")
    parser.add_argument("--bytes-list", default=",".join(str(value) for value in DEFAULT_BYTES))
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--smoke-bytes", default=str(64 * 1024**2))
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--smoke-repeat", type=int, default=1)
    parser.add_argument("--connections", default="1,4,8")
    parser.add_argument("--smoke-connections", default="1,4")
    parser.add_argument("--parallelism-list", default="1,4,8,16")
    parser.add_argument("--smoke-parallelism-list", default="1,4")
    parser.add_argument("--storage-buffer-sizes", default="262144,1048576")
    parser.add_argument("--checksum-bytes", type=int, default=1024**3)
    parser.add_argument("--checksum-iterations", type=int, default=3)
    parser.add_argument("--memory-bytes", type=int, default=1024**3)
    parser.add_argument("--iperf-seconds", type=int, default=10)
    parser.add_argument("--iperf-port", type=int, default=5311)
    parser.add_argument("--iperf-reverse-port", type=int, default=5312)
    parser.add_argument("--case-timeout", type=int, default=3600)
    parser.add_argument("--probe-dirs", default="", help="comma list of label:path entries")
    parser.add_argument("--skip-network", action="store_true")
    parser.add_argument("--skip-checksum", action="store_true")
    parser.add_argument("--skip-memory", action="store_true")
    parser.add_argument("--skip-storage", action="store_true")
    parser.add_argument("--skip-gridflux", action="store_true")
    parser.add_argument("--skip-fio", action="store_true")
    parser.add_argument("--figure-format", choices=["png", "svg", "both"], default="both")
    return parser


def main() -> int:
    load_private_env()
    parser = build_parser()
    args = parser.parse_args()
    if args.repeat <= 0 or args.smoke_repeat <= 0:
        raise SystemExit("repeat values must be positive")
    args.timestamp = compact_timestamp()
    args.output_dir_path = ROOT / args.output_dir
    args.output_dir_path.mkdir(parents=True, exist_ok=True)
    args.log_dir = args.output_dir_path / f"{args.timestamp}_cloud-disk-proof"
    args.log_dir.mkdir(parents=True, exist_ok=True)
    args.bytes_values = parse_size_list(args.smoke_bytes if args.smoke else args.bytes_list)
    args.repeat = args.smoke_repeat if args.smoke else args.repeat
    args.connections_values = parse_int_list(args.smoke_connections if args.smoke else args.connections)
    args.parallelism_values = parse_int_list(args.smoke_parallelism_list if args.smoke else args.parallelism_list)
    args.checksum_bytes = min(args.checksum_bytes, max(args.bytes_values)) if args.smoke else args.checksum_bytes
    args.memory_bytes = min(args.memory_bytes, max(args.bytes_values)) if args.smoke else args.memory_bytes

    state = RunState(timestamp=args.timestamp, output_dir=args.output_dir_path)
    paths = {
        "environment_txt": relative_to_root(args.output_dir_path / f"{args.timestamp}_cloud-disk-proof-env.txt"),
        "environment_json": relative_to_root(args.output_dir_path / f"{args.timestamp}_cloud-disk-proof-env.json"),
        "network_csv": relative_to_root(args.output_dir_path / f"{args.timestamp}_cloud-disk-proof-network.csv"),
        "checksum_csv": relative_to_root(args.output_dir_path / f"{args.timestamp}_cloud-disk-proof-checksum.csv"),
        "memory_csv": relative_to_root(args.output_dir_path / f"{args.timestamp}_cloud-disk-proof-memory-or-sink.csv"),
        "storage_csv": relative_to_root(args.output_dir_path / f"{args.timestamp}_cloud-disk-proof-storage.csv"),
        "storage_summary_csv": relative_to_root(args.output_dir_path / f"{args.timestamp}_cloud-disk-proof-storage-summary.csv"),
        "stor_csv": relative_to_root(args.output_dir_path / f"{args.timestamp}_cloud-disk-proof-gridflux-stor.csv"),
        "stor_summary_csv": relative_to_root(args.output_dir_path / f"{args.timestamp}_cloud-disk-proof-gridflux-stor-summary.csv"),
        "retr_csv": relative_to_root(args.output_dir_path / f"{args.timestamp}_cloud-disk-proof-gridflux-retr.csv"),
        "retr_summary_csv": relative_to_root(args.output_dir_path / f"{args.timestamp}_cloud-disk-proof-gridflux-retr-summary.csv"),
        "attribution_summary": relative_to_root(args.output_dir_path / f"{args.timestamp}_cloud-disk-proof-attribution-summary.csv"),
        "report": "docs/perf/CLOUD_DISK_BOTTLENECK_PROOF.md",
    }
    try:
        collect_environment(args, ROOT / paths["environment_txt"], ROOT / paths["environment_json"])
        if not args.skip_network:
            state.network_rows = run_network(args, ROOT / paths["network_csv"])
        else:
            write_csv(ROOT / paths["network_csv"], [], NETWORK_FIELDS)
        if not args.skip_checksum:
            state.checksum_rows = run_checksum(args, ROOT / paths["checksum_csv"])
        else:
            write_csv(ROOT / paths["checksum_csv"], [], CHECKSUM_FIELDS)
        if not args.skip_memory:
            state.memory_rows = run_memory_or_sink(args, ROOT / paths["memory_csv"])
        else:
            write_csv(ROOT / paths["memory_csv"], [], MEMORY_FIELDS)
        if not args.skip_storage:
            generated_raw, generated_summary, state.storage_counts = run_storage_probe(args)
            state.storage_raw_csv = merge_csv_files([generated_raw], ROOT / paths["storage_csv"])
            state.storage_summary_csv = merge_csv_files([generated_summary], ROOT / paths["storage_summary_csv"])
            paths["storage_probe_raw_csv"] = relative_to_root(generated_raw)
            paths["storage_probe_summary_csv"] = relative_to_root(generated_summary)
        else:
            write_csv(ROOT / paths["storage_csv"], [], storage_probe.PROBE_RAW_FIELDS)
            write_csv(ROOT / paths["storage_summary_csv"], [], storage_probe.PROBE_SUMMARY_FIELDS)
            state.storage_raw_csv = paths["storage_csv"]
            state.storage_summary_csv = paths["storage_summary_csv"]
            state.storage_counts = {"rows": 0, "pass": 0, "fail": 0, "unavailable": 0}
        if not args.skip_gridflux:
            run_gridflux_matrix(args, state)
            if state.stor_raw_csvs:
                paths["stor_source_csvs"] = list(state.stor_raw_csvs)
                state.stor_raw_csvs = [merge_csv_files(state.stor_raw_csvs, ROOT / paths["stor_csv"])]
            if state.stor_summary_csvs:
                paths["stor_summary_source_csvs"] = list(state.stor_summary_csvs)
                state.stor_summary_csvs = [merge_csv_files(state.stor_summary_csvs, ROOT / paths["stor_summary_csv"])]
            if state.retr_raw_csvs:
                paths["retr_source_csvs"] = list(state.retr_raw_csvs)
                state.retr_raw_csvs = [merge_csv_files(state.retr_raw_csvs, ROOT / paths["retr_csv"])]
            if state.retr_summary_csvs:
                paths["retr_summary_source_csvs"] = list(state.retr_summary_csvs)
                state.retr_summary_csvs = [merge_csv_files(state.retr_summary_csvs, ROOT / paths["retr_summary_csv"])]
        report_path, attribution_summary = run_analyzer(args, paths, state)
        paths["report"] = report_path
        paths["attribution_summary"] = attribution_summary
        paths["figures"] = run_plotter(args, attribution_summary)
    finally:
        state.cleanup = cleanup(args)
        if state.stor_raw_csvs:
            paths["stor_csv"] = ";".join(state.stor_raw_csvs)
        if state.stor_summary_csvs:
            paths["stor_summary_csv"] = ";".join(state.stor_summary_csvs)
        if state.retr_raw_csvs:
            paths["retr_csv"] = ";".join(state.retr_raw_csvs)
        if state.retr_summary_csvs:
            paths["retr_summary_csv"] = ";".join(state.retr_summary_csvs)
        wrapper = write_wrapper(state, paths)

    print(f"wrapper={relative_to_root(wrapper)}")
    for key, value in paths.items():
        print(f"{key}={value}")
    print(f"result={json.loads(wrapper.read_text(encoding='utf-8')).get('status')}")
    return 0 if json.loads(wrapper.read_text(encoding="utf-8")).get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
