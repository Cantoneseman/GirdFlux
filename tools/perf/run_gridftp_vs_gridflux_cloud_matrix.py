#!/usr/bin/env python3
"""Run a native GridFTP vs GridFlux comparison on the current cloud pair.

This is a measurement wrapper only. It keeps GridFlux defaults conservative and
delegates GridFlux transfers to run_gridftp_private_matrix.py.
"""

from __future__ import annotations

import argparse
import csv
import json
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
import remote_auth  # noqa: E402


TMP_PREFIX = "/tmp/gridftp-vs-gridflux-cloud"
DEFAULT_BYTES = [256 * 1024**2, 1024**3, 4 * 1024**3, 10 * 1024**3]
DEFAULT_PARALLELISM = [1, 4, 8, 16]
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

TRANSFER_FIELDS = [
    "protocol",
    "direction",
    "size_bytes",
    "parallelism",
    "connections",
    "checksum",
    "file_io_backend",
    "tls_mode",
    "data_tls_mode",
    "repeat",
    "elapsed_seconds",
    "throughput_MBps",
    "throughput_Gbps",
    "source_sha256",
    "dest_sha256",
    "sha256_match",
    "event_log_path",
    "server_log_path",
    "client_log_path",
    "command_summary",
    "status",
    "notes",
]

SUMMARY_FIELDS = [
    "protocol",
    "direction",
    "size_bytes",
    "parallelism",
    "connections",
    "checksum",
    "file_io_backend",
    "tls_mode",
    "data_tls_mode",
    "median_MBps",
    "median_Gbps",
    "best_MBps",
    "best_Gbps",
    "p95_Gbps",
    "spread_pct",
    "sample_count",
    "sha256_mismatch_count",
    "fail_count",
]

HOST_BASELINE_FIELDS = [
    "kind",
    "machine",
    "operation",
    "parallelism",
    "size_bytes",
    "elapsed_seconds",
    "MBps",
    "Gbps",
    "status",
    "log_path",
    "notes",
]

CHECKSUM_FIELDS = [
    "machine",
    "backend",
    "size_bytes",
    "iterations",
    "elapsed_seconds",
    "throughput_Gbps",
    "status",
    "log_path",
    "notes",
]


@dataclass
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class GridFluxStep:
    name: str
    command: list[str]


@dataclass
class RunState:
    timestamp: str
    output_dir: Path
    native_rows: list[dict[str, str]] = field(default_factory=list)
    gridflux_rows: list[dict[str, str]] = field(default_factory=list)
    gridflux_raw_csvs: list[str] = field(default_factory=list)
    gridflux_summary_csvs: list[str] = field(default_factory=list)
    gridftp_user_created: bool = False
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


def repeat_for_size(size: int, args: argparse.Namespace) -> int:
    if args.smoke:
        return 1
    if size == 1024**3:
        return args.repeat_1gib
    if size == 4 * 1024**3:
        return args.repeat_4gib
    if size == 10 * 1024**3:
        return args.repeat_10gib
    return args.repeat_short


def sanitize(text: str, max_len: int = 240) -> str:
    cleaned = " ".join((text or "").replace("\x00", "").split())
    for marker in (
        "password",
        "passwd",
        "token",
        "private_key",
        "GRIDFLUX_SSH_PASSWORD",
        "SSHPASS",
        "XTRANSFER_SSH_PASSWORD",
    ):
        cleaned = cleaned.replace(marker, "<redacted-key>")
    return cleaned[:max_len]


def relative_to_root(path: Path | str) -> str:
    parsed = Path(path)
    if not parsed.is_absolute():
        parsed = ROOT / parsed
    try:
        return parsed.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(parsed.resolve())


def run_local(script: str, *, timeout: int = 120, check: bool = False) -> CommandResult:
    completed = subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    result = CommandResult(completed.returncode, completed.stdout, completed.stderr)
    if check and result.returncode != 0:
        raise RuntimeError(sanitize(result.stderr or result.stdout, 1000))
    return result


def run_remote(remote: str, script: str, *, timeout: int = 120, check: bool = False) -> CommandResult:
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
    result = CommandResult(completed.returncode, completed.stdout, completed.stderr)
    if check and result.returncode != 0:
        raise RuntimeError(sanitize(result.stderr or result.stdout, 1000))
    return result


def fetch_remote(remote: str, remote_path: str, local_path: Path) -> bool:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    command = ["scp", "-o", "StrictHostKeyChecking=no", remote + ":" + remote_path, str(local_path)]
    command, env = remote_auth.wrap_with_sshpass(remote, command, root=ROOT)
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, env=env)
    if completed.returncode != 0:
        local_path.write_text(sanitize(completed.stderr or completed.stdout, 1000), encoding="utf-8")
        return False
    return True


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


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


def mbps_from_elapsed(bytes_count: int, elapsed: float) -> float:
    return 0.0 if elapsed <= 0.0 else bytes_count / 1_000_000 / elapsed


def gbps_from_elapsed(bytes_count: int, elapsed: float) -> float:
    return 0.0 if elapsed <= 0.0 else bytes_count * 8 / 1_000_000_000 / elapsed


def command_available_local(binary: str) -> bool:
    return run_local(f"command -v {shlex.quote(binary)} >/dev/null 2>&1").returncode == 0


def command_available_remote(remote: str, binary: str) -> bool:
    return run_remote(remote, f"command -v {shlex.quote(binary)} >/dev/null 2>&1").returncode == 0


def apt_install_local(packages: list[str]) -> None:
    quoted = " ".join(shlex.quote(package) for package in packages)
    run_local(
        "export DEBIAN_FRONTEND=noninteractive; apt-get update -y >/dev/null 2>&1 || true; "
        f"apt-get install -y {quoted} >/dev/null 2>&1 || true",
        timeout=1200,
    )


def apt_install_remote(remote: str, packages: list[str]) -> None:
    quoted = " ".join(shlex.quote(package) for package in packages)
    run_remote(
        remote,
        "export DEBIAN_FRONTEND=noninteractive; apt-get update -y >/dev/null 2>&1 || true; "
        f"apt-get install -y {quoted} >/dev/null 2>&1 || true",
        timeout=1200,
    )


def ensure_packages(args: argparse.Namespace) -> None:
    if not args.install_missing:
        return
    packages = [
        "iperf3",
        "globus-gridftp-server-progs",
        "globus-gass-copy-progs",
        "globus-proxy-utils",
        "globus-gsi-cert-utils-progs",
        "globus-simple-ca",
        "libglobus-gridftp-server6",
    ]
    apt_install_local(packages)
    apt_install_remote(args.remote, packages)


def environment_script(server_host: str, client_host: str) -> str:
    return f"""
set +e
echo "generated={timestamp_utc()}"
echo "hostname=$(hostname 2>/dev/null || true)"
echo "kernel=$(uname -srmo 2>/dev/null || true)"
if [ -r /etc/os-release ]; then . /etc/os-release; echo "os=${{PRETTY_NAME:-unknown}}"; fi
echo "cpu=$(LC_ALL=C lscpu 2>/dev/null | awk -F: '/Model name/ {{gsub(/^[ \\t]+/, "", $2); print $2; exit}}')"
echo "memory_kb=$(awk '/MemTotal:/ {{print $2; exit}}' /proc/meminfo 2>/dev/null)"
echo "df_tmp=$(df -h /tmp 2>/dev/null | tail -1)"
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
if command -v apt-get >/dev/null 2>&1; then pm=apt; elif command -v dnf >/dev/null 2>&1; then pm=dnf; elif command -v yum >/dev/null 2>&1; then pm=yum; else pm=unknown; fi
echo "package_manager=$pm"
for bin in iperf3 globus-gridftp-server globus-url-copy gridflux-gridftp-server gridflux-checksum-bench gridflux-storage-bench; do
  echo "binary=$bin path=$(command -v "$bin" 2>/dev/null || true)"
done
echo "gridflux_build=$([ -x /root/projects/GridFlux/build/gridflux-gridftp-server ] && echo present || echo missing)"
echo "gridflux_iouring_build=$([ -x /root/projects/GridFlux/build-io-uring-real/gridflux-gridftp-server ] && echo present || echo missing)"
"""


def collect_environment(args: argparse.Namespace, path: Path) -> None:
    local = run_local(environment_script(args.server_host, args.client_host), timeout=180)
    remote = run_remote(args.remote, environment_script(args.server_host, args.client_host), timeout=180)
    ping = run_remote(args.remote, f"ping -c 3 -W 2 {shlex.quote(args.server_host)}", timeout=30)
    path.write_text(
        "\n".join(
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
        ),
        encoding="utf-8",
    )


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


def run_iperf_baseline(args: argparse.Namespace, rows: list[dict[str, str]]) -> None:
    if not command_available_local("iperf3") or not command_available_remote(args.remote, "iperf3"):
        rows.append(
            {
                "kind": "iperf3",
                "machine": "private_link",
                "operation": "tcp",
                "status": "unavailable",
                "notes": "iperf3 missing on one or both hosts",
            }
        )
        return

    server_log = args.output_dir_path / f"{args.timestamp}_cloud-iperf3-server.log"
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            ["iperf3", "-s", "-B", args.server_host, "-p", str(args.iperf_port)],
            cwd=ROOT,
            text=True,
            stdout=server_log.open("w", encoding="utf-8"),
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
                    "kind": "iperf3",
                    "machine": "client_to_server",
                    "operation": "tcp",
                    "parallelism": str(p),
                    "elapsed_seconds": str(args.iperf_seconds),
                    "Gbps": parse_iperf_gbps(result.stdout),
                    "status": "pass" if result.returncode == 0 else "fail",
                    "log_path": relative_to_root(server_log),
                    "notes": "" if result.returncode == 0 else sanitize(result.stderr or result.stdout),
                }
            )
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
    try:
        for p in args.parallelism_values:
            result = run_local(
                f"iperf3 -J -c {shlex.quote(args.client_host)} -p {args.iperf_reverse_port} -P {p} -t {args.iperf_seconds}",
                timeout=args.iperf_seconds + 90,
            )
            rows.append(
                {
                    "kind": "iperf3",
                    "machine": "server_to_client",
                    "operation": "tcp",
                    "parallelism": str(p),
                    "elapsed_seconds": str(args.iperf_seconds),
                    "Gbps": parse_iperf_gbps(result.stdout),
                    "status": "pass" if result.returncode == 0 else "fail",
                    "log_path": remote_log,
                    "notes": "" if result.returncode == 0 else sanitize(result.stderr or result.stdout),
                }
            )
    finally:
        if remote_pid.isdigit():
            run_remote(args.remote, f"kill {remote_pid} >/dev/null 2>&1 || true", timeout=30)


def storage_script(size: int, path: str) -> str:
    mib = max(1, size // (1024**2))
    return f"""
set +e
mkdir -p {shlex.quote(str(Path(path).parent))}
before=$(awk '/^(Dirty|Writeback|Cached):/ {{print $1 $2}}' /proc/meminfo 2>/dev/null | tr '\\n' ';')
start=$(python3 -c 'import time; print(time.monotonic())')
dd if=/dev/zero of={shlex.quote(path)} bs=1M count={mib} conv=fsync status=none
rc_write=$?
mid=$(python3 -c 'import time; print(time.monotonic())')
dd if={shlex.quote(path)} of=/dev/null bs=1M status=none
rc_read=$?
end=$(python3 -c 'import time; print(time.monotonic())')
after=$(awk '/^(Dirty|Writeback|Cached):/ {{print $1 $2}}' /proc/meminfo 2>/dev/null | tr '\\n' ';')
rm -f {shlex.quote(path)}
echo "write_rc=$rc_write"
echo "read_rc=$rc_read"
python3 - <<PY
start=float("$start"); mid=float("$mid"); end=float("$end")
print("write_elapsed=%.6f" % (mid - start))
print("read_elapsed=%.6f" % (end - mid))
PY
echo "meminfo_before=$before"
echo "meminfo_after=$after"
"""


def key_value(stdout: str, key: str) -> str:
    prefix = key + "="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip()
    return ""


def run_storage_baseline(args: argparse.Namespace, rows: list[dict[str, str]]) -> None:
    for machine, runner, path in [
        ("server", lambda script: run_local(script, timeout=args.case_timeout), f"{TMP_PREFIX}-storage/server.bin"),
        ("client", lambda script: run_remote(args.remote, script, timeout=args.case_timeout), f"{TMP_PREFIX}-storage/client.bin"),
    ]:
        for size in args.storage_bytes_values:
            result = runner(storage_script(size, path))
            write_elapsed = float(key_value(result.stdout, "write_elapsed") or "0")
            read_elapsed = float(key_value(result.stdout, "read_elapsed") or "0")
            for operation, elapsed, rc_key in [
                ("write", write_elapsed, "write_rc"),
                ("read", read_elapsed, "read_rc"),
            ]:
                rc = key_value(result.stdout, rc_key)
                rows.append(
                    {
                        "kind": "storage",
                        "machine": machine,
                        "operation": operation,
                        "parallelism": "1",
                        "size_bytes": str(size),
                        "elapsed_seconds": f"{elapsed:.6f}",
                        "MBps": f"{mbps_from_elapsed(size, elapsed):.3f}",
                        "Gbps": f"{gbps_from_elapsed(size, elapsed):.3f}",
                        "status": "pass" if result.returncode == 0 and rc == "0" else "fail",
                        "log_path": "",
                        "notes": sanitize(
                            f"before={key_value(result.stdout, 'meminfo_before')} after={key_value(result.stdout, 'meminfo_after')}"
                            if result.returncode == 0
                            else result.stderr or result.stdout
                        ),
                    }
                )


def run_host_baseline(args: argparse.Namespace, path: Path) -> None:
    rows: list[dict[str, str]] = []
    run_iperf_baseline(args, rows)
    run_storage_baseline(args, rows)
    write_csv(path, rows, HOST_BASELINE_FIELDS)


def find_bench_binary(build_dir: str, name: str) -> str:
    candidates = [Path(build_dir) / name, ROOT / "build-io-uring-real" / name, ROOT / "build" / name]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return str(Path(build_dir) / name)


def run_checksum_bench(args: argparse.Namespace, path: Path) -> None:
    rows: list[dict[str, str]] = []
    local_bin = find_bench_binary(args.local_build_dir, "gridflux-checksum-bench")
    remote_bin = f"{args.remote_build_dir.rstrip('/')}/gridflux-checksum-bench"
    for machine, command_runner, bench in [
        ("server", lambda command: run_local(command, timeout=900), local_bin),
        ("client", lambda command: run_remote(args.remote, command, timeout=900), remote_bin),
    ]:
        for backend in ["auto", "hardware", "software"]:
            log = args.output_dir_path / f"{args.timestamp}_{machine}-checksum-{backend}.log"
            command = f"{shlex.quote(bench)} --backend {backend} --bytes {args.checksum_bytes} --iterations {args.checksum_iterations}"
            result = command_runner(command)
            if machine == "client":
                remote_log = f"{TMP_PREFIX}-checksum-{backend}.log"
                run_remote(args.remote, f"{command} >{shlex.quote(remote_log)} 2>&1", timeout=900)
                fetch_remote(args.remote, remote_log, log)
            else:
                log.write_text(result.stdout + result.stderr, encoding="utf-8")
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
                    "machine": machine,
                    "backend": effective,
                    "size_bytes": str(args.checksum_bytes),
                    "iterations": str(args.checksum_iterations),
                    "elapsed_seconds": elapsed,
                    "throughput_Gbps": throughput,
                    "status": "pass" if result.returncode == 0 else "fail",
                    "log_path": relative_to_root(log),
                    "notes": "" if result.returncode == 0 else sanitize(result.stderr or result.stdout),
                }
            )
    write_csv(path, rows, CHECKSUM_FIELDS)


def sha_local(path: str) -> str:
    result = run_local(f"sha256sum {shlex.quote(path)} | awk '{{print $1}}'", timeout=600)
    return result.stdout.strip().splitlines()[-1] if result.returncode == 0 and result.stdout.strip() else ""


def sha_remote(remote: str, path: str) -> str:
    result = run_remote(remote, f"sha256sum {shlex.quote(path)} | awk '{{print $1}}'", timeout=600)
    return result.stdout.strip().splitlines()[-1] if result.returncode == 0 and result.stdout.strip() else ""


def make_local_file(path: str, bytes_count: int) -> str:
    mib = max(1, bytes_count // (1024**2))
    result = run_local(
        f"mkdir -p {shlex.quote(str(Path(path).parent))}; "
        f"dd if=/dev/zero of={shlex.quote(path)} bs=1M count={mib} conv=fsync status=none; "
        f"sha256sum {shlex.quote(path)} | awk '{{print $1}}'",
        timeout=max(1200, bytes_count // (1024**2) * 4),
        check=True,
    )
    return result.stdout.strip().splitlines()[-1]


def make_remote_file(remote: str, path: str, bytes_count: int) -> str:
    mib = max(1, bytes_count // (1024**2))
    result = run_remote(
        remote,
        f"mkdir -p {shlex.quote(str(Path(path).parent))}; "
        f"dd if=/dev/zero of={shlex.quote(path)} bs=1M count={mib} conv=fsync status=none; "
        f"sha256sum {shlex.quote(path)} | awk '{{print $1}}'",
        timeout=max(1200, bytes_count // (1024**2) * 4),
        check=True,
    )
    return result.stdout.strip().splitlines()[-1]


def prepare_native_inputs(args: argparse.Namespace, sizes: list[int], path: Path) -> dict[int, str]:
    hashes: dict[int, str] = {}
    lines = [f"generated={timestamp_utc()}"]
    for size in sizes:
        remote_path = f"{TMP_PREFIX}-client-data/input_{size}.bin"
        digest = make_remote_file(args.remote, remote_path, size)
        hashes[size] = digest
        lines.append(f"{size} {digest} {remote_path}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return hashes


def result_row(
    *,
    protocol: str,
    direction: str,
    size_bytes: int,
    repeat: int,
    elapsed: float,
    source_sha: str,
    dest_sha: str,
    status: str,
    parallelism: str = "",
    connections: str = "",
    checksum: str = "",
    file_io_backend: str = "",
    tls_mode: str = "off",
    data_tls_mode: str = "off",
    event_log: str = "",
    server_log: str = "",
    client_log: str = "",
    command_summary: str = "",
    notes: str = "",
) -> dict[str, str]:
    hashes_present = bool(source_sha and dest_sha)
    match = hashes_present and source_sha == dest_sha
    hash_status = "yes" if match else ("no" if hashes_present else "")
    final_status = status if status != "pass" or match else "fail"
    return {
        "protocol": protocol,
        "direction": direction,
        "size_bytes": str(size_bytes),
        "parallelism": parallelism,
        "connections": connections,
        "checksum": checksum,
        "file_io_backend": file_io_backend,
        "tls_mode": tls_mode,
        "data_tls_mode": data_tls_mode,
        "repeat": str(repeat),
        "elapsed_seconds": f"{elapsed:.6f}",
        "throughput_MBps": f"{mbps_from_elapsed(size_bytes, elapsed):.3f}",
        "throughput_Gbps": f"{gbps_from_elapsed(size_bytes, elapsed):.3f}",
        "source_sha256": source_sha,
        "dest_sha256": dest_sha,
        "sha256_match": hash_status,
        "event_log_path": event_log,
        "server_log_path": server_log,
        "client_log_path": client_log,
        "command_summary": command_summary,
        "status": final_status,
        "notes": notes if final_status == "pass" else sanitize(notes),
    }


def setup_gridftp_user(root: str) -> bool:
    created = False
    if run_local("id gridfluxcloud >/dev/null 2>&1").returncode != 0:
        run_local("groupadd --system gridfluxcloud >/dev/null 2>&1 || true", timeout=120)
        run_local(
            f"useradd --system --home-dir {shlex.quote(root)} --shell /usr/sbin/nologin --gid gridfluxcloud gridfluxcloud",
            timeout=120,
            check=True,
        )
        created = True
    run_local(
        f"mkdir -p {shlex.quote(root + '/incoming')}; "
        f"chown -R gridfluxcloud:gridfluxcloud {shlex.quote(root)}; "
        f"chmod -R u+rwX,g+rwX,o-rwx {shlex.quote(root)}",
        timeout=120,
        check=True,
    )
    return created


def start_gridftp(args: argparse.Namespace, root: str) -> bool:
    pidfile = f"{TMP_PREFIX}-gridftp.pid"
    log = args.output_dir_path / f"{args.timestamp}_native-gridftp-server.log"
    run_local(f"rm -f {shlex.quote(pidfile)}", timeout=120)
    command = [
        "globus-gridftp-server",
        "-aa",
        "-anonymous-user",
        "gridfluxcloud",
        "-anonymous-names-allowed",
        "*",
        "-home-dir",
        root,
        "-rp",
        root,
        "-p",
        str(args.gridftp_port),
        "-control-interface",
        args.server_host,
        "-data-interface",
        args.server_host,
        "-port-range",
        f"{args.gridftp_port_range_start},{args.gridftp_port_range_end}",
        "-l",
        str(log),
        "-pidfile",
        pidfile,
        "-S",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        log.write_text(sanitize(completed.stdout + completed.stderr, 4000), encoding="utf-8")
        return False
    return wait_for_port(args.server_host, args.gridftp_port, timeout=10)


def stop_gridftp() -> None:
    pidfile = Path(f"{TMP_PREFIX}-gridftp.pid")
    if pidfile.is_file():
        pid = pidfile.read_text(encoding="utf-8", errors="ignore").strip()
        if pid.isdigit():
            run_local(f"kill {pid} >/dev/null 2>&1 || true; sleep 1; kill -9 {pid} >/dev/null 2>&1 || true", timeout=30)
    run_local(
        "ps -eo pid=,comm=,args= | awk '$2 == \"globus-gridftp-server\" && $0 ~ /gridftp-vs-gridflux-cloud/ {print $1}' | xargs -r kill >/dev/null 2>&1 || true",
        timeout=30,
    )


def timed_remote(remote: str, command: str, log_path: str, *, timeout: int) -> tuple[bool, float, str]:
    script = f"""
set +e
mkdir -p {shlex.quote(str(Path(log_path).parent))}
start=$(python3 -c 'import time; print(time.monotonic())')
{command} >{shlex.quote(log_path)} 2>&1
rc=$?
end=$(python3 -c 'import time; print(time.monotonic())')
echo "returncode=$rc"
python3 - <<PY
print("elapsed_seconds=%.6f" % (float("$end") - float("$start")))
PY
if [ "$rc" != 0 ]; then tail -n 20 {shlex.quote(log_path)} 2>/dev/null | sed 's/^/log_tail=/' ; fi
exit "$rc"
"""
    result = run_remote(remote, script, timeout=timeout)
    elapsed = float(key_value(result.stdout, "elapsed_seconds") or "0")
    return result.returncode == 0, elapsed, sanitize(result.stderr or result.stdout, 1000)


def run_native_gridftp(args: argparse.Namespace, sizes: list[int], input_hashes: dict[int, str], state: RunState) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not command_available_local("globus-gridftp-server") or not command_available_remote(args.remote, "globus-url-copy"):
        rows.append(
            result_row(
                protocol="native_gridftp",
                direction="setup",
                size_bytes=0,
                repeat=0,
                elapsed=0,
                source_sha="",
                dest_sha="",
                status="fail",
                command_summary="preflight",
                notes="globus-gridftp-server or globus-url-copy unavailable",
            )
        )
        return rows
    root = f"{TMP_PREFIX}-gridftp-root"
    state.gridftp_user_created = setup_gridftp_user(root)
    for size in sizes:
        source = f"{root}/incoming/download_{size}.bin"
        make_local_file(source, size)
        run_local(f"chown gridfluxcloud:gridfluxcloud {shlex.quote(source)}", timeout=120)
    if not start_gridftp(args, root):
        rows.append(
            result_row(
                protocol="native_gridftp",
                direction="setup",
                size_bytes=0,
                repeat=0,
                elapsed=0,
                source_sha="",
                dest_sha="",
                status="fail",
                server_log=relative_to_root(args.output_dir_path / f"{args.timestamp}_native-gridftp-server.log"),
                command_summary="globus-gridftp-server -aa",
                notes="native GridFTP server did not start in anonymous/no-GSI mode",
            )
        )
        return rows
    for size in sizes:
        for p in args.parallelism_values:
            for repeat in range(1, repeat_for_size(size, args) + 1):
                client_file = f"{TMP_PREFIX}-client-data/input_{size}.bin"
                upload_name = f"native_upload_{size}_p{p}_r{repeat}.bin"
                run_local(f"rm -f {shlex.quote(root + '/incoming/' + upload_name)}", timeout=120)
                remote_log = f"{TMP_PREFIX}-client-data/native_upload_{size}_p{p}_r{repeat}.log"
                local_log = args.output_dir_path / f"{args.timestamp}_native_upload_{size}_p{p}_r{repeat}.log"
                command = (
                    f"globus-url-copy -vb -nodcau -rp -p {p} "
                    f"file://{client_file} ftp://anonymous@{args.server_host}:{args.gridftp_port}/incoming/{upload_name}"
                )
                ok, elapsed, note = timed_remote(args.remote, command, remote_log, timeout=args.case_timeout)
                fetch_remote(args.remote, remote_log, local_log)
                dest_sha = sha_local(f"{root}/incoming/{upload_name}")
                rows.append(
                    result_row(
                        protocol="native_gridftp",
                        direction="upload",
                        size_bytes=size,
                        parallelism=str(p),
                        repeat=repeat,
                        elapsed=elapsed,
                        source_sha=input_hashes[size],
                        dest_sha=dest_sha,
                        status="pass" if ok else "fail",
                        server_log=relative_to_root(args.output_dir_path / f"{args.timestamp}_native-gridftp-server.log"),
                        client_log=relative_to_root(local_log),
                        command_summary=f"globus-url-copy -nodcau -rp -p {p} file://... ftp://...",
                        notes="" if ok else note,
                    )
                )

                dest_path = f"{TMP_PREFIX}-client-data/native_download_{size}_p{p}_r{repeat}.bin"
                run_remote(args.remote, f"rm -f {shlex.quote(dest_path)}", timeout=120)
                remote_log = f"{TMP_PREFIX}-client-data/native_download_{size}_p{p}_r{repeat}.log"
                local_log = args.output_dir_path / f"{args.timestamp}_native_download_{size}_p{p}_r{repeat}.log"
                command = (
                    f"globus-url-copy -vb -nodcau -rp -p {p} "
                    f"ftp://anonymous@{args.server_host}:{args.gridftp_port}/incoming/download_{size}.bin file://{dest_path}"
                )
                ok, elapsed, note = timed_remote(args.remote, command, remote_log, timeout=args.case_timeout)
                fetch_remote(args.remote, remote_log, local_log)
                source_sha = sha_local(f"{root}/incoming/download_{size}.bin")
                dest_sha = sha_remote(args.remote, dest_path)
                rows.append(
                    result_row(
                        protocol="native_gridftp",
                        direction="download",
                        size_bytes=size,
                        parallelism=str(p),
                        repeat=repeat,
                        elapsed=elapsed,
                        source_sha=source_sha,
                        dest_sha=dest_sha,
                        status="pass" if ok else "fail",
                        server_log=relative_to_root(args.output_dir_path / f"{args.timestamp}_native-gridftp-server.log"),
                        client_log=relative_to_root(local_log),
                        command_summary=f"globus-url-copy -nodcau -rp -p {p} ftp://... file://...",
                        notes="" if ok else note,
                    )
                )
    return rows


def split_key_value_stdout(stdout: str, key: str) -> str:
    prefix = key + "="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip()
    return ""


def gridflux_common_command(
    args: argparse.Namespace,
    *,
    event_dir: Path,
    run_root_base: Path,
    local_build_dir: str | None = None,
    remote_build_dir: str | None = None,
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
        local_build_dir or args.local_build_dir,
        "--remote-build-dir",
        remote_build_dir or args.remote_build_dir,
        "--output-dir",
        args.output_dir,
        "--directions",
        "stor,retr",
        "--chunk-sizes",
        "4194304",
        "--buffer-sizes",
        "262144",
        "--checksum-backend",
        "auto",
        "--preallocates",
        "off",
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
        "--event-log-dir",
        str(event_dir),
        "--case-timeout",
        str(args.case_timeout),
        "--run-root-base",
        str(run_root_base),
    ]


def gridflux_step_specs(args: argparse.Namespace, sizes: list[int], event_dir: Path) -> list[GridFluxStep]:
    specs: list[GridFluxStep] = []
    for size in sizes:
        common = gridflux_common_command(
            args,
            event_dir=event_dir / f"main_{size}",
            run_root_base=Path(f"{TMP_PREFIX}-gridflux-runs"),
        )
        specs.append(
            GridFluxStep(
                name=f"gridflux_posix_off_{size}",
                command=[
                    *common,
                    "--bytes",
                    str(size),
                    "--connections",
                    ",".join(str(value) for value in args.parallelism_values),
                    "--checksums",
                    "crc32c,none",
                    "--file-io-backends",
                    "posix",
                    "--tls-modes",
                    "off",
                    "--data-tls-modes",
                    "off",
                    "--repeat",
                    str(repeat_for_size(size, args)),
                ],
            )
        )
    if not args.skip_iouring_subset and 1024**3 in sizes:
        common = gridflux_common_command(
            args,
            event_dir=event_dir / "iouring_1g",
            run_root_base=Path(f"{TMP_PREFIX}-gridflux-runs"),
            local_build_dir=args.iouring_local_build_dir,
            remote_build_dir=args.iouring_remote_build_dir,
        )
        specs.append(
            GridFluxStep(
                name="gridflux_iouring_off_1073741824",
                command=[
                    *common,
                    "--bytes",
                    str(1024**3),
                    "--connections",
                    "8",
                    "--checksums",
                    "crc32c",
                    "--file-io-backends",
                    "io_uring",
                    "--tls-modes",
                    "off",
                    "--data-tls-modes",
                    "off",
                    "--repeat",
                    "1",
                ],
            )
        )
    if not args.skip_tls_subset and 1024**3 in sizes:
        common = gridflux_common_command(
            args,
            event_dir=event_dir / "tls_1g",
            run_root_base=Path(f"{TMP_PREFIX}-gridflux-runs"),
        )
        specs.append(
            GridFluxStep(
                name="gridflux_posix_tls_1073741824",
                command=[
                    *common,
                    "--bytes",
                    str(1024**3),
                    "--connections",
                    "8",
                    "--checksums",
                    "crc32c",
                    "--file-io-backends",
                    "posix",
                    "--tls-modes",
                    "required",
                    "--data-tls-modes",
                    "required",
                    "--repeat",
                    "1",
                ],
            )
        )
    return specs


def gridflux_rows_from_raw(raw_csv: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in read_csv(raw_csv):
        size = int(row.get("bytes") or "0")
        elapsed = float(row.get("elapsed") or "0")
        status = "pass" if row.get("result") == "pass" else "fail"
        rows.append(
            result_row(
                protocol="gridflux",
                direction=row.get("direction", ""),
                size_bytes=size,
                connections=row.get("connections", ""),
                checksum=row.get("checksum_algorithm", ""),
                file_io_backend=row.get("file_io_backend", ""),
                tls_mode=row.get("tls_mode", "off"),
                data_tls_mode=row.get("data_tls_mode", "off"),
                repeat=int(row.get("repeat_index") or "0") + 1,
                elapsed=elapsed,
                source_sha=row.get("source_sha256", ""),
                dest_sha=row.get("dest_sha256", ""),
                status=status,
                event_log=row.get("event_log", ""),
                server_log=row.get("server_log", ""),
                client_log=row.get("client_log", ""),
                command_summary="run_gridftp_private_matrix.py stor,retr",
                notes="" if status == "pass" else row.get("error", ""),
            )
        )
    return rows


def ensure_gridflux_build(args: argparse.Namespace) -> None:
    if args.skip_build:
        return
    if not (ROOT / args.local_build_dir / "gridflux-gridftp-server").exists() and Path(args.local_build_dir).is_absolute():
        local_build_dir = Path(args.local_build_dir)
    else:
        local_build_dir = ROOT / args.local_build_dir if not Path(args.local_build_dir).is_absolute() else Path(args.local_build_dir)
    if not (local_build_dir / "gridflux-gridftp-server").is_file():
        run_local(
            f"cmake -S . -B {shlex.quote(str(local_build_dir))} -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_COMPILER=g++-13",
            timeout=1200,
            check=True,
        )
    run_local(f"cmake --build {shlex.quote(str(local_build_dir))}", timeout=1800, check=True)
    remote_script = f"""
cd /root/projects/GridFlux
if [ ! -x {shlex.quote(args.remote_build_dir.rstrip('/') + '/gridflux-gridftp-server')} ]; then
  cmake -S . -B {shlex.quote(args.remote_build_dir)} -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_COMPILER=g++-13
fi
cmake --build {shlex.quote(args.remote_build_dir)}
"""
    run_remote(args.remote, remote_script, timeout=2400, check=True)
    if not args.skip_iouring_subset:
        local_iouring = Path(args.iouring_local_build_dir)
        if not (local_iouring / "gridflux-gridftp-server").is_file():
            run_local(
                f"cmake -S . -B {shlex.quote(str(local_iouring))} -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++-13",
                timeout=1200,
                check=True,
            )
        run_local(f"cmake --build {shlex.quote(str(local_iouring))}", timeout=1800, check=True)
        remote_iouring_script = f"""
cd /root/projects/GridFlux
if [ ! -x {shlex.quote(args.iouring_remote_build_dir.rstrip('/') + '/gridflux-gridftp-server')} ]; then
  cmake -S . -B {shlex.quote(args.iouring_remote_build_dir)} -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++-13
fi
cmake --build {shlex.quote(args.iouring_remote_build_dir)}
"""
        run_remote(args.remote, remote_iouring_script, timeout=2400, check=True)


def run_gridflux(args: argparse.Namespace, sizes: list[int], state: RunState) -> list[dict[str, str]]:
    ensure_gridflux_build(args)
    rows: list[dict[str, str]] = []
    event_dir = args.output_dir_path / f"{args.timestamp}_gridftp-vs-gridflux-events"
    event_dir.mkdir(parents=True, exist_ok=True)
    for spec in gridflux_step_specs(args, sizes, event_dir):
        started = time.time()
        completed = subprocess.run(
            spec.command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=os.environ.copy(),
            timeout=max(args.case_timeout * 64, 3600),
        )
        log = args.output_dir_path / f"{args.timestamp}_{spec.name}.log"
        log.write_text(
            "$ " + " ".join(shlex.quote(part) for part in spec.command) + "\n\n" + completed.stdout + completed.stderr,
            encoding="utf-8",
        )
        raw_csv = split_key_value_stdout(completed.stdout, "csv") or split_key_value_stdout(completed.stdout, "raw_csv")
        summary_csv = split_key_value_stdout(completed.stdout, "summary_csv")
        if not raw_csv:
            candidates = [
                path
                for path in args.output_dir_path.glob("*_gridftp-private-matrix-smoke.csv")
                if path.stat().st_mtime >= started - 1
            ]
            if candidates:
                raw_csv = relative_to_root(max(candidates, key=lambda item: item.stat().st_mtime))
        if not summary_csv:
            candidates = [
                path
                for path in args.output_dir_path.glob("*_gridftp-private-matrix-smoke-summary.csv")
                if path.stat().st_mtime >= started - 1
            ]
            if candidates:
                summary_csv = relative_to_root(max(candidates, key=lambda item: item.stat().st_mtime))
        if raw_csv:
            state.gridflux_raw_csvs.append(raw_csv)
            rows.extend(gridflux_rows_from_raw(raw_csv))
        if summary_csv:
            state.gridflux_summary_csvs.append(summary_csv)
        if completed.returncode != 0 and not raw_csv:
            rows.append(
                result_row(
                    protocol="gridflux",
                    direction="setup",
                    size_bytes=0,
                    repeat=0,
                    elapsed=0,
                    source_sha="",
                    dest_sha="",
                    status="fail",
                    client_log=relative_to_root(log),
                    command_summary=spec.name,
                    notes=sanitize(completed.stderr or completed.stdout),
                )
            )
    return rows


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, max(0, int(round((len(sorted_values) - 1) * q))))
    return sorted_values[index]


def summary_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in rows:
        key = (
            row.get("protocol", ""),
            row.get("direction", ""),
            row.get("size_bytes", ""),
            row.get("parallelism", ""),
            row.get("connections", ""),
            row.get("checksum", ""),
            row.get("file_io_backend", ""),
            row.get("tls_mode", ""),
            row.get("data_tls_mode", ""),
        )
        groups.setdefault(key, []).append(row)
    summaries: list[dict[str, str]] = []
    for key, items in sorted(groups.items()):
        valid = [
            float(row.get("throughput_Gbps") or "0")
            for row in items
            if row.get("status") == "pass" and row.get("sha256_match") == "yes"
        ]
        valid_mbps = [
            float(row.get("throughput_MBps") or "0")
            for row in items
            if row.get("status") == "pass" and row.get("sha256_match") == "yes"
        ]
        spread = ((max(valid) - min(valid)) / statistics.median(valid) * 100.0) if len(valid) > 1 and statistics.median(valid) > 0 else 0.0
        summaries.append(
            {
                "protocol": key[0],
                "direction": key[1],
                "size_bytes": key[2],
                "parallelism": key[3],
                "connections": key[4],
                "checksum": key[5],
                "file_io_backend": key[6],
                "tls_mode": key[7],
                "data_tls_mode": key[8],
                "median_MBps": f"{statistics.median(valid_mbps):.3f}" if valid_mbps else "",
                "median_Gbps": f"{statistics.median(valid):.3f}" if valid else "",
                "best_MBps": f"{max(valid_mbps):.3f}" if valid_mbps else "",
                "best_Gbps": f"{max(valid):.3f}" if valid else "",
                "p95_Gbps": f"{percentile(valid, 0.95):.3f}" if valid else "",
                "spread_pct": f"{spread:.3f}" if valid else "",
                "sample_count": str(len(valid)),
                "sha256_mismatch_count": str(sum(1 for row in items if row.get("sha256_match") == "no")),
                "fail_count": str(sum(1 for row in items if row.get("status") != "pass")),
            }
        )
    return summaries


def cleanup(args: argparse.Namespace, state: RunState) -> dict[str, str]:
    stop_gridftp()
    run_local(
        "ps -eo pid=,comm=,args= | awk '$2 ~ /^(iperf3|globus-url-copy|gridflux-gridftp-server|gridflux-file-server|gridflux-file-client|gridflux-file-download-sender|gridflux-file-download-client)$/ && $0 ~ /gridftp-vs-gridflux-cloud/ {print $1}' | xargs -r kill >/dev/null 2>&1 || true",
        timeout=30,
    )
    run_remote(
        args.remote,
        "ps -eo pid=,comm=,args= | awk '$2 ~ /^(iperf3|globus-url-copy|gridflux-gridftp-server|gridflux-file-server|gridflux-file-client|gridflux-file-download-sender|gridflux-file-download-client)$/ && $0 ~ /gridftp-vs-gridflux-cloud/ {print $1}' | xargs -r kill >/dev/null 2>&1 || true",
        timeout=30,
    )
    run_local(f"rm -rf {TMP_PREFIX}-*", timeout=300)
    run_remote(args.remote, f"rm -rf {TMP_PREFIX}-*", timeout=300)
    user_removed = "not_created"
    if state.gridftp_user_created:
        run_local("userdel -r gridfluxcloud >/dev/null 2>&1 || userdel gridfluxcloud >/dev/null 2>&1 || true", timeout=120)
        run_local("groupdel gridfluxcloud >/dev/null 2>&1 || true", timeout=120)
        user_removed = "yes"
    process_check = (
        "ps -eo pid=,comm=,args= | "
        "awk '$2 ~ /^(globus-gridftp-server|globus-url-copy|gridflux-gridftp-server|"
        "gridflux-file-server|gridflux-file-client|gridflux-file-download-sender|"
        "gridflux-file-download-client|iperf3)$/ {print}'"
    )
    local = run_local(process_check, timeout=30).stdout.strip()
    remote = run_remote(args.remote, process_check, timeout=30).stdout.strip()
    return {
        "removed_paths": f"{TMP_PREFIX}-*",
        "gridftp_user_removed": user_removed,
        "server_residual_processes": local,
        "client_residual_processes": remote,
    }


def write_wrapper(state: RunState, paths: dict[str, str]) -> Path:
    summary = summary_rows(state.native_rows + state.gridflux_rows)
    mismatch_count = sum(int(row.get("sha256_mismatch_count") or "0") for row in summary)
    fail_count = sum(int(row.get("fail_count") or "0") for row in summary)
    wrapper = state.output_dir / f"{state.timestamp}_gridftp-vs-gridflux-cloud.json"
    wrapper.write_text(
        json.dumps(
            {
                "timestamp": state.timestamp,
                "generated": timestamp_utc(),
                "status": "pass" if mismatch_count == 0 and fail_count == 0 else "fail",
                "default_strategy": DEFAULT_STRATEGY,
                "paths": paths,
                "gridflux_raw_csvs": state.gridflux_raw_csvs,
                "gridflux_summary_csvs": state.gridflux_summary_csvs,
                "native_gridftp_rows": len(state.native_rows),
                "gridflux_rows": len(state.gridflux_rows),
                "hash_mismatch_count": mismatch_count,
                "fail_count": fail_count,
                "cleanup": state.cleanup,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return wrapper


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default=os.environ.get("GRIDFLUX_REMOTE", "root@<redacted>"))
    parser.add_argument("--server-host", default=os.environ.get("GRIDFLUX_SERVER_HOST", "<redacted>"))
    parser.add_argument("--client-host", default=os.environ.get("GRIDFLUX_CLIENT_HOST", "<redacted>"))
    parser.add_argument("--local-build-dir", default="/root/projects/GridFlux/build")
    parser.add_argument("--remote-build-dir", default="/root/projects/GridFlux/build")
    parser.add_argument("--iouring-local-build-dir", default="/root/projects/GridFlux/build-io-uring-real")
    parser.add_argument("--iouring-remote-build-dir", default="/root/projects/GridFlux/build-io-uring-real")
    parser.add_argument("--output-dir", default="tools/perf/results")
    parser.add_argument("--bytes-list", default=",".join(str(value) for value in DEFAULT_BYTES))
    parser.add_argument("--parallelism-list", default="1,4,8,16")
    parser.add_argument("--smoke", action="store_true", help="override to 256MiB/1GiB, p1/p4, repeat=1")
    parser.add_argument("--repeat-short", type=int, default=1)
    parser.add_argument("--repeat-1gib", type=int, default=3)
    parser.add_argument("--repeat-4gib", type=int, default=1)
    parser.add_argument("--repeat-10gib", type=int, default=1)
    parser.add_argument("--storage-bytes-list", default="1073741824,4294967296")
    parser.add_argument("--checksum-bytes", type=int, default=1073741824)
    parser.add_argument("--checksum-iterations", type=int, default=3)
    parser.add_argument("--case-timeout", type=int, default=3600)
    parser.add_argument("--iperf-seconds", type=int, default=10)
    parser.add_argument("--iperf-port", type=int, default=5201)
    parser.add_argument("--iperf-reverse-port", type=int, default=5202)
    parser.add_argument("--gridftp-port", type=int, default=2811)
    parser.add_argument("--gridftp-port-range-start", type=int, default=32200)
    parser.add_argument("--gridftp-port-range-end", type=int, default=32399)
    parser.add_argument("--install-missing", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--skip-native-gridftp", action="store_true")
    parser.add_argument("--skip-gridflux", action="store_true")
    parser.add_argument("--skip-iouring-subset", action="store_true")
    parser.add_argument("--skip-tls-subset", action="store_true")
    return parser


def main() -> int:
    load_private_env()
    parser = build_parser()
    args = parser.parse_args()
    args.timestamp = compact_timestamp()
    args.output_dir_path = Path(args.output_dir)
    args.output_dir_path.mkdir(parents=True, exist_ok=True)
    args.parallelism_values = [1, 4] if args.smoke else parse_int_list(args.parallelism_list)
    sizes = [256 * 1024**2, 1024**3] if args.smoke else parse_size_list(args.bytes_list)
    args.storage_bytes_values = [1024**3] if args.smoke else parse_size_list(args.storage_bytes_list)

    state = RunState(timestamp=args.timestamp, output_dir=args.output_dir_path)
    paths = {
        "environment": relative_to_root(args.output_dir_path / f"{args.timestamp}_gridftp-vs-gridflux-env.txt"),
        "host_baseline": relative_to_root(args.output_dir_path / f"{args.timestamp}_gridftp-vs-gridflux-host-baseline.csv"),
        "storage_baseline": relative_to_root(args.output_dir_path / f"{args.timestamp}_gridftp-vs-gridflux-storage-baseline.csv"),
        "checksum_baseline": relative_to_root(args.output_dir_path / f"{args.timestamp}_gridftp-vs-gridflux-checksum-baseline.csv"),
        "input_sha256": relative_to_root(args.output_dir_path / f"{args.timestamp}_gridftp-vs-gridflux-input-sha256.txt"),
        "native_gridftp": relative_to_root(args.output_dir_path / f"{args.timestamp}_native-gridftp-cloud.csv"),
        "gridflux": relative_to_root(args.output_dir_path / f"{args.timestamp}_gridflux-cloud.csv"),
        "summary": relative_to_root(args.output_dir_path / f"{args.timestamp}_gridftp-vs-gridflux-cloud-summary.csv"),
        "report": "docs/perf/GRIDFTP_VS_GRIDFLUX_CLOUD_COMPARISON.md",
    }

    try:
        ensure_packages(args)
        collect_environment(args, ROOT / paths["environment"])
        if not args.skip_baseline:
            run_host_baseline(args, ROOT / paths["host_baseline"])
            storage_rows = [row for row in read_csv(paths["host_baseline"]) if row.get("kind") == "storage"]
            write_csv(ROOT / paths["storage_baseline"], storage_rows, HOST_BASELINE_FIELDS)
            run_checksum_bench(args, ROOT / paths["checksum_baseline"])
        input_hashes = prepare_native_inputs(args, sizes, ROOT / paths["input_sha256"])
        if not args.skip_native_gridftp:
            state.native_rows = run_native_gridftp(args, sizes, input_hashes, state)
            write_csv(ROOT / paths["native_gridftp"], state.native_rows, TRANSFER_FIELDS)
        if not args.skip_gridflux:
            state.gridflux_rows = run_gridflux(args, sizes, state)
            write_csv(ROOT / paths["gridflux"], state.gridflux_rows, TRANSFER_FIELDS)
    finally:
        state.cleanup = cleanup(args, state)
        write_csv(ROOT / paths["native_gridftp"], state.native_rows, TRANSFER_FIELDS)
        write_csv(ROOT / paths["gridflux"], state.gridflux_rows, TRANSFER_FIELDS)
        write_csv(ROOT / paths["summary"], summary_rows(state.native_rows + state.gridflux_rows), SUMMARY_FIELDS)
        wrapper = write_wrapper(state, paths)

    print(f"wrapper={relative_to_root(wrapper)}")
    for key, value in paths.items():
        print(f"{key}={value}")
    for raw in state.gridflux_raw_csvs:
        print(f"gridflux_raw_csv={raw}")
    for summary in state.gridflux_summary_csvs:
        print(f"gridflux_summary_csv={summary}")
    print(f"server_residual_processes={state.cleanup.get('server_residual_processes','') or 'none'}")
    print(f"client_residual_processes={state.cleanup.get('client_residual_processes','') or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
