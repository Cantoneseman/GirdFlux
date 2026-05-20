#!/usr/bin/env python3
"""Compare plain FTP, native GridFTP, and GridFlux throughput on two hosts."""

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


TMP_PREFIX = "/tmp/gridflux-three-way"
XTRANSFER_PREFIX = "/tmp/xtransfer-baseline"
RESULT_FIELDS = [
    "protocol",
    "direction",
    "size_bytes",
    "parallelism",
    "connections",
    "checksum",
    "repeat",
    "elapsed_seconds",
    "throughput_MBps",
    "throughput_Gbps",
    "source_sha256",
    "dest_sha256",
    "sha256_match",
    "transfer_id",
    "skipped_bytes",
    "resent_bytes",
    "verified_bytes",
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
    "median_MBps",
    "median_Gbps",
    "best_MBps",
    "best_Gbps",
    "sample_count",
    "sha256_mismatch_count",
    "fail_count",
]


@dataclass
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass
class RunState:
    timestamp: str
    output_dir: Path
    started_pids: list[int] = field(default_factory=list)
    gridftp_user_created: bool = False
    ftp_rows: list[dict[str, str]] = field(default_factory=list)
    gridftp_rows: list[dict[str, str]] = field(default_factory=list)
    gridflux_rows: list[dict[str, str]] = field(default_factory=list)
    gridflux_raw_csv: str = ""
    gridflux_summary_csv: str = ""
    cleanup: dict[str, str] = field(default_factory=dict)


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
        key = key.strip()
        if not key:
            continue
        try:
            parsed = shlex.split(value, posix=True)
            value = parsed[0] if parsed else ""
        except ValueError:
            value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)
    for candidate in ("XTRANSFER_SSH_PASSWORD", "SSH_PASSWORD", "SERVER_PASSWORD"):
        if os.environ.get(candidate):
            os.environ.setdefault("GRIDFLUX_SSH_PASSWORD", os.environ[candidate])
            os.environ.setdefault("SSHPASS", os.environ[candidate])
            break
    if os.environ.get("GRIDFLUX_SSH_PASSWORD"):
        os.environ.setdefault("SSHPASS", os.environ["GRIDFLUX_SSH_PASSWORD"])
    if os.environ.get("SSHPASS"):
        os.environ.setdefault("GRIDFLUX_SSH_PASSWORD", os.environ["SSHPASS"])


def compact_timestamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def timestamp_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def parse_size_list(text: str, *, include_4gib: bool = False) -> list[int]:
    values = [parse_size_token(part) for part in text.split(",") if part.strip()]
    if include_4gib and 4 * 1024**3 not in values:
        values.append(4 * 1024**3)
    return values


def mbps_from_elapsed(bytes_count: int, elapsed: float) -> float:
    return 0.0 if elapsed <= 0 else bytes_count / 1_000_000 / elapsed


def gbps_from_elapsed(bytes_count: int, elapsed: float) -> float:
    return 0.0 if elapsed <= 0 else bytes_count * 8 / 1_000_000_000 / elapsed


def sanitize(text: str, max_len: int = 240) -> str:
    cleaned = " ".join((text or "").replace("\x00", "").split())
    for key in (
        "password",
        "passwd",
        "token",
        "private_key",
        "GRIDFLUX_SSH_PASSWORD",
        "SSHPASS",
        "XTRANSFER_SSH_PASSWORD",
    ):
        cleaned = cleaned.replace(key, "<redacted-key>")
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
        raise RuntimeError(sanitize(result.stderr or result.stdout))
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
        raise RuntimeError(sanitize(result.stderr or result.stdout))
    return result


def fetch_remote(remote: str, remote_path: str, local_path: Path) -> bool:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
        remote + ":" + remote_path,
        str(local_path),
    ]
    command, env = remote_auth.wrap_with_sshpass(remote, command, root=ROOT)
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, env=env)
    if completed.returncode != 0:
        local_path.write_text(sanitize(completed.stderr or completed.stdout), encoding="utf-8")
        return False
    return True


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def read_csv(path: Path | str) -> list[dict[str, str]]:
    parsed = Path(path)
    if not parsed.is_absolute():
        parsed = ROOT / parsed
    if not parsed.is_file():
        return []
    with parsed.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def package_status_script() -> str:
    packages = [
        "vsftpd",
        "lftp",
        "iperf3",
        "globus-gridftp-server-progs",
        "globus-gass-copy-progs",
        "globus-proxy-utils",
        "globus-gsi-cert-utils-progs",
        "globus-simple-ca",
        "libglobus-xio0",
        "libglobus-xio-dev",
        "libglobus-xio-gsi-driver",
        "libglobus-xio-gridftp-driver",
        "libglobus-gridftp-server6",
        "libglobus-gridftp-server-dev",
    ]
    package_list = " ".join(shlex.quote(pkg) for pkg in packages)
    return f"""
set +e
echo "hostname=$(hostname 2>/dev/null || true)"
echo "kernel=$(uname -srmo 2>/dev/null || true)"
if [ -r /etc/os-release ]; then . /etc/os-release; echo "os=${{PRETTY_NAME:-unknown}}"; else echo "os=unknown"; fi
echo "cpu=$(LC_ALL=C lscpu 2>/dev/null | awk -F: '/Model name/ {{gsub(/^[ \\t]+/, "", $2); print $2; exit}}')"
echo "memory_kb=$(awk '/MemTotal:/ {{print $2; exit}}' /proc/meminfo 2>/dev/null)"
echo "disk_tmp=$(df -h /tmp 2>/dev/null | tail -1)"
echo "gridflux_build=$([ -x /root/projects/GridFlux/build/gridflux-gridftp-server ] && echo present || echo missing)"
if command -v apt-get >/dev/null 2>&1; then pm=apt; elif command -v dnf >/dev/null 2>&1; then pm=dnf; elif command -v yum >/dev/null 2>&1; then pm=yum; else pm=unknown; fi
echo "package_manager=$pm"
for bin in vsftpd lftp iperf3 globus-gridftp-server globus-url-copy; do
  echo "binary=$bin path=$(command -v "$bin" 2>/dev/null || true)"
done
for pkg in {package_list}; do
  installed=no
  installable=unknown
  if [ "$pm" = apt ]; then
    dpkg -s "$pkg" >/dev/null 2>&1 && installed=yes
    candidate=$(apt-cache policy "$pkg" 2>/dev/null | awk '/Candidate:/ {{print $2; exit}}')
    [ -n "$candidate" ] && [ "$candidate" != "(none)" ] && installable=yes || installable=no
  fi
  echo "package=$pkg installed=$installed installable=$installable"
done
"""


def collect_environment(args: argparse.Namespace, path: Path) -> None:
    local = run_local(package_status_script(), timeout=180)
    remote = run_remote(args.remote, package_status_script(), timeout=180)
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
                sanitize(ping.stdout or ping.stderr, 2000),
                "",
            ]
        ),
        encoding="utf-8",
    )


def command_available_local(binary: str) -> bool:
    return run_local(f"command -v {shlex.quote(binary)} >/dev/null 2>&1").returncode == 0


def command_available_remote(remote: str, binary: str) -> bool:
    return run_remote(remote, f"command -v {shlex.quote(binary)} >/dev/null 2>&1").returncode == 0


def apt_install_local(packages: list[str]) -> None:
    quoted = " ".join(shlex.quote(pkg) for pkg in packages)
    run_local(
        "export DEBIAN_FRONTEND=noninteractive; "
        "apt-get update -y >/dev/null 2>&1 || true; "
        f"apt-get install -y {quoted} >/dev/null 2>&1 || true",
        timeout=1200,
    )


def apt_install_remote(remote: str, packages: list[str]) -> None:
    quoted = " ".join(shlex.quote(pkg) for pkg in packages)
    run_remote(
        remote,
        "export DEBIAN_FRONTEND=noninteractive; "
        "apt-get update -y >/dev/null 2>&1 || true; "
        f"apt-get install -y {quoted} >/dev/null 2>&1 || true",
        timeout=1200,
    )


def ensure_packages(args: argparse.Namespace) -> None:
    packages = [
        "vsftpd",
        "lftp",
        "iperf3",
        "globus-gridftp-server-progs",
        "globus-gass-copy-progs",
        "globus-proxy-utils",
        "globus-gsi-cert-utils-progs",
        "globus-simple-ca",
        "libglobus-xio0",
        "libglobus-xio-dev",
        "libglobus-xio-gsi-driver",
        "libglobus-xio-gridftp-driver",
        "libglobus-gridftp-server6",
        "libglobus-gridftp-server-dev",
    ]
    apt_install_local(packages)
    apt_install_remote(args.remote, packages)


def timed_remote(remote: str, command: str, log_path: str, *, timeout: int = 1200) -> tuple[bool, float, str]:
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
if [ "$rc" != 0 ]; then tail -n 12 {shlex.quote(log_path)} 2>/dev/null | sed 's/^/log_tail=/' ; fi
exit "$rc"
"""
    result = run_remote(remote, script, timeout=timeout)
    elapsed = 0.0
    for line in result.stdout.splitlines():
        if line.startswith("elapsed_seconds="):
            elapsed = float(line.split("=", 1)[1])
            break
    return result.returncode == 0, elapsed, sanitize(result.stderr or result.stdout)


def sha_local(path: str) -> str:
    result = run_local(f"sha256sum {shlex.quote(path)} | awk '{{print $1}}'", timeout=180)
    return result.stdout.strip().splitlines()[-1] if result.returncode == 0 and result.stdout.strip() else ""


def sha_remote(remote: str, path: str) -> str:
    result = run_remote(remote, f"sha256sum {shlex.quote(path)} | awk '{{print $1}}'", timeout=180)
    return result.stdout.strip().splitlines()[-1] if result.returncode == 0 and result.stdout.strip() else ""


def make_local_file(path: str, bytes_count: int) -> str:
    mib = bytes_count // (1024**2)
    result = run_local(
        f"mkdir -p {shlex.quote(str(Path(path).parent))}; "
        f"dd if=/dev/zero of={shlex.quote(path)} bs=1M count={mib} conv=fsync status=none; "
        f"sha256sum {shlex.quote(path)} | awk '{{print $1}}'",
        timeout=1200,
        check=True,
    )
    return result.stdout.strip().splitlines()[-1]


def make_remote_file(remote: str, path: str, bytes_count: int) -> str:
    mib = bytes_count // (1024**2)
    result = run_remote(
        remote,
        f"mkdir -p {shlex.quote(str(Path(path).parent))}; "
        f"dd if=/dev/zero of={shlex.quote(path)} bs=1M count={mib} conv=fsync status=none; "
        f"sha256sum {shlex.quote(path)} | awk '{{print $1}}'",
        timeout=1200,
        check=True,
    )
    return result.stdout.strip().splitlines()[-1]


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


def prepare_input_data(args: argparse.Namespace, sizes: list[int], path: Path) -> dict[int, str]:
    hashes: dict[int, str] = {}
    lines = [f"generated={timestamp_utc()}"]
    for bytes_count in sizes:
        remote_path = f"{TMP_PREFIX}-client-data/input_{bytes_count}.bin"
        digest = make_remote_file(args.remote, remote_path, bytes_count)
        hashes[bytes_count] = digest
        lines.append(f"{bytes_count} {digest} {remote_path}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return hashes


def run_host_baseline(args: argparse.Namespace, path: Path) -> None:
    rows: list[dict[str, str]] = []
    iperf_proc: subprocess.Popen[str] | None = None
    iperf_log = args.output_dir_path / f"{args.timestamp}_iperf3-server.log"
    try:
        if command_available_local("iperf3") and command_available_remote(args.remote, "iperf3"):
            iperf_proc = subprocess.Popen(
                ["iperf3", "-s", "-B", args.server_host, "-p", str(args.iperf_port)],
                cwd=ROOT,
                text=True,
                stdout=iperf_log.open("w", encoding="utf-8"),
                stderr=subprocess.STDOUT,
            )
            time.sleep(1.0)
            for parallelism in [1, 4, 8]:
                result = run_remote(
                    args.remote,
                    f"iperf3 -J -c {shlex.quote(args.server_host)} -p {args.iperf_port} -P {parallelism} -t {args.iperf_seconds}",
                    timeout=args.iperf_seconds + 60,
                )
                gbps = ""
                if result.returncode == 0:
                    try:
                        data = json.loads(result.stdout)
                        bps = data.get("end", {}).get("sum_received", {}).get("bits_per_second") or data.get(
                            "end", {}
                        ).get("sum_sent", {}).get("bits_per_second")
                        gbps = f"{float(bps) / 1_000_000_000:.3f}" if bps else ""
                    except (ValueError, TypeError):
                        gbps = ""
                rows.append(
                    {
                        "kind": "iperf3",
                        "machine": "client_to_server",
                        "operation": "network",
                        "parallelism": str(parallelism),
                        "bytes": "",
                        "elapsed_seconds": str(args.iperf_seconds),
                        "MBps": "",
                        "Gbps": gbps,
                        "status": "pass" if result.returncode == 0 else "fail",
                        "log_path": relative_to_root(iperf_log),
                        "notes": "" if result.returncode == 0 else sanitize(result.stderr or result.stdout),
                    }
                )
        else:
            rows.append(
                {
                    "kind": "iperf3",
                    "machine": "client_to_server",
                    "operation": "network",
                    "parallelism": "",
                    "bytes": "",
                    "elapsed_seconds": "",
                    "MBps": "",
                    "Gbps": "",
                    "status": "unavailable",
                    "log_path": "",
                    "notes": "iperf3 missing",
                }
            )
    finally:
        if iperf_proc and iperf_proc.poll() is None:
            iperf_proc.terminate()
            try:
                iperf_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                iperf_proc.kill()

    for machine, runner in [
        ("server", lambda script: run_local(script, timeout=900)),
        ("client", lambda script: run_remote(args.remote, script, timeout=900)),
    ]:
        script = f"""
set +e
mkdir -p {TMP_PREFIX}-storage
start=$(python3 -c 'import time; print(time.monotonic())')
dd if=/dev/zero of={TMP_PREFIX}-storage/write_1g.bin bs=1M count=1024 conv=fsync status=none
rc=$?
end=$(python3 -c 'import time; print(time.monotonic())')
rm -f {TMP_PREFIX}-storage/write_1g.bin
echo "returncode=$rc"
python3 - <<PY
print("elapsed_seconds=%.6f" % (float("$end") - float("$start")))
PY
exit "$rc"
"""
        result = runner(script)
        elapsed = 0.0
        for line in result.stdout.splitlines():
            if line.startswith("elapsed_seconds="):
                elapsed = float(line.split("=", 1)[1])
        rows.append(
            {
                "kind": "storage",
                "machine": machine,
                "operation": "write_1GiB_tmp",
                "parallelism": "1",
                "bytes": str(1024**3),
                "elapsed_seconds": f"{elapsed:.6f}",
                "MBps": f"{mbps_from_elapsed(1024**3, elapsed):.3f}",
                "Gbps": f"{gbps_from_elapsed(1024**3, elapsed):.3f}",
                "status": "pass" if result.returncode == 0 else "fail",
                "log_path": "",
                "notes": "" if result.returncode == 0 else sanitize(result.stderr or result.stdout),
            }
        )
    write_csv(path, rows, ["kind", "machine", "operation", "parallelism", "bytes", "elapsed_seconds", "MBps", "Gbps", "status", "log_path", "notes"])


def start_vsftpd(args: argparse.Namespace, root: str) -> subprocess.Popen[str]:
    config = Path(f"{TMP_PREFIX}-vsftpd.conf")
    config.write_text(
        "\n".join(
            [
                "listen=YES",
                "listen_ipv6=NO",
                "listen_address=0.0.0.0",
                f"listen_port={args.ftp_port}",
                "anonymous_enable=YES",
                "no_anon_password=YES",
                "local_enable=NO",
                "write_enable=YES",
                "anon_upload_enable=YES",
                "anon_mkdir_write_enable=YES",
                "anon_other_write_enable=YES",
                "anon_umask=000",
                f"anon_root={root}",
                "pasv_enable=YES",
                f"pasv_min_port={args.ftp_pasv_min_port}",
                f"pasv_max_port={args.ftp_pasv_max_port}",
                f"pasv_address={args.server_host}",
                "connect_from_port_20=NO",
                "seccomp_sandbox=NO",
                "background=NO",
                "xferlog_enable=NO",
                "dual_log_enable=NO",
                "syslog_enable=NO",
                "allow_writeable_chroot=YES",
                "secure_chroot_dir=/var/run/vsftpd/empty",
                "",
            ]
        ),
        encoding="utf-8",
    )
    run_local("mkdir -p /var/run/vsftpd/empty", timeout=120)
    log_path = args.output_dir_path / f"{args.timestamp}_plain-ftp-server.log"
    process = subprocess.Popen(["vsftpd", str(config)], cwd=ROOT, text=True, stdout=log_path.open("w", encoding="utf-8"), stderr=subprocess.STDOUT)
    if not wait_for_port("127.0.0.1", args.ftp_port, timeout=10):
        process.terminate()
        raise RuntimeError("vsftpd did not open test port")
    return process


def stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def result_row(
    *,
    protocol: str,
    direction: str,
    size_bytes: int,
    parallelism: str = "",
    connections: str = "",
    checksum: str = "",
    repeat: int,
    elapsed: float,
    source_sha: str,
    dest_sha: str,
    status: str,
    command_summary: str,
    server_log: str = "",
    client_log: str = "",
    event_log: str = "",
    transfer_id: str = "",
    skipped: str = "",
    resent: str = "",
    verified: str = "",
    notes: str = "",
) -> dict[str, str]:
    match = bool(source_sha and dest_sha and source_sha == dest_sha)
    final_status = status if status != "pass" or match else "fail"
    return {
        "protocol": protocol,
        "direction": direction,
        "size_bytes": str(size_bytes),
        "parallelism": parallelism,
        "connections": connections,
        "checksum": checksum,
        "repeat": str(repeat),
        "elapsed_seconds": f"{elapsed:.6f}",
        "throughput_MBps": f"{mbps_from_elapsed(size_bytes, elapsed):.3f}",
        "throughput_Gbps": f"{gbps_from_elapsed(size_bytes, elapsed):.3f}",
        "source_sha256": source_sha,
        "dest_sha256": dest_sha,
        "sha256_match": "yes" if match else "no",
        "transfer_id": transfer_id,
        "skipped_bytes": skipped,
        "resent_bytes": resent,
        "verified_bytes": verified,
        "event_log_path": event_log,
        "server_log_path": server_log,
        "client_log_path": client_log,
        "command_summary": command_summary,
        "status": final_status,
        "notes": notes if final_status == "pass" else sanitize(notes),
    }


def run_plain_ftp(args: argparse.Namespace, sizes: list[int], input_hashes: dict[int, str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if run_local("ps -eo comm= | grep -qx vsftpd").returncode == 0:
        return [
            result_row(
                protocol="plain_ftp",
                direction="setup",
                size_bytes=0,
                repeat=0,
                elapsed=0,
                source_sha="",
                dest_sha="",
                status="fail",
                command_summary="preflight",
                notes="preexisting vsftpd process detected",
            )
        ]
    root = f"{TMP_PREFIX}-ftp-root"
    run_local(f"rm -rf {shlex.quote(root)}; mkdir -p {shlex.quote(root + '/incoming')}; chmod 755 {shlex.quote(root)}; chmod 777 {shlex.quote(root + '/incoming')}", timeout=120, check=True)
    for size in sizes:
        make_local_file(f"{root}/incoming/download_{size}.bin", size)
        run_local(f"chmod 666 {shlex.quote(root + f'/incoming/download_{size}.bin')}", timeout=120)
    process: subprocess.Popen[str] | None = None
    try:
        process = start_vsftpd(args, root)
        for size in sizes:
            client_file = f"{TMP_PREFIX}-client-data/input_{size}.bin"
            for repeat in range(1, args.repeat + 1):
                upload_name = f"input_{size}.bin"
                run_local(f"rm -f {shlex.quote(root + '/incoming/' + upload_name)}", timeout=120)
                remote_log = f"{TMP_PREFIX}-client-data/plain_ftp_upload_{size}_r{repeat}.log"
                local_log = args.output_dir_path / f"{args.timestamp}_plain_ftp_upload_{size}_r{repeat}_client.log"
                command = (
                    "lftp -e "
                    + shlex.quote(
                        f"set net:max-retries 1; set net:timeout 60; set ftp:passive-mode yes; "
                        f"open -u anonymous, ftp://{args.server_host}:{args.ftp_port}; put -O /incoming {client_file}; bye"
                    )
                )
                ok, elapsed, note = timed_remote(args.remote, command, remote_log, timeout=args.case_timeout)
                fetch_remote(args.remote, remote_log, local_log)
                dest_sha = sha_local(f"{root}/incoming/{upload_name}")
                rows.append(
                    result_row(
                        protocol="plain_ftp",
                        direction="upload",
                        size_bytes=size,
                        parallelism="1",
                        repeat=repeat,
                        elapsed=elapsed,
                        source_sha=input_hashes[size],
                        dest_sha=dest_sha,
                        status="pass" if ok else "fail",
                        command_summary="lftp put",
                        server_log=relative_to_root(args.output_dir_path / f"{args.timestamp}_plain-ftp-server.log"),
                        client_log=relative_to_root(local_log),
                        notes="" if ok else note,
                    )
                )

                dest_path = f"{TMP_PREFIX}-client-data/plain_ftp_download_{size}_r{repeat}.bin"
                run_remote(args.remote, f"rm -f {shlex.quote(dest_path)}", timeout=120)
                remote_log = f"{TMP_PREFIX}-client-data/plain_ftp_download_{size}_r{repeat}.log"
                local_log = args.output_dir_path / f"{args.timestamp}_plain_ftp_download_{size}_r{repeat}_client.log"
                command = (
                    "lftp -e "
                    + shlex.quote(
                        f"set net:max-retries 1; set net:timeout 60; set ftp:passive-mode yes; "
                        f"open -u anonymous, ftp://{args.server_host}:{args.ftp_port}; "
                        f"get /incoming/download_{size}.bin -o {dest_path}; bye"
                    )
                )
                ok, elapsed, note = timed_remote(args.remote, command, remote_log, timeout=args.case_timeout)
                fetch_remote(args.remote, remote_log, local_log)
                source_sha = sha_local(f"{root}/incoming/download_{size}.bin")
                dest_sha = sha_remote(args.remote, dest_path)
                rows.append(
                    result_row(
                        protocol="plain_ftp",
                        direction="download",
                        size_bytes=size,
                        parallelism="1",
                        repeat=repeat,
                        elapsed=elapsed,
                        source_sha=source_sha,
                        dest_sha=dest_sha,
                        status="pass" if ok else "fail",
                        command_summary="lftp get",
                        server_log=relative_to_root(args.output_dir_path / f"{args.timestamp}_plain-ftp-server.log"),
                        client_log=relative_to_root(local_log),
                        notes="" if ok else note,
                    )
                )
    finally:
        stop_process(process)
    return rows


def setup_gridftp_user(root: str) -> bool:
    created = False
    if run_local("id gridflux3way >/dev/null 2>&1").returncode != 0:
        run_local("groupadd --system gridflux3way >/dev/null 2>&1 || true", timeout=120)
        run_local(f"useradd --system --home-dir {shlex.quote(root)} --shell /usr/sbin/nologin --gid gridflux3way gridflux3way", timeout=120, check=True)
        created = True
    run_local(f"mkdir -p {shlex.quote(root + '/incoming')}; chown -R gridflux3way:gridflux3way {shlex.quote(root)}; chmod -R u+rwX,g+rwX,o-rwx {shlex.quote(root)}", timeout=120, check=True)
    return created


def start_gridftp(args: argparse.Namespace, root: str) -> bool:
    pidfile = f"{TMP_PREFIX}-gridftp.pid"
    log = args.output_dir_path / f"{args.timestamp}_native-gridftp-server.log"
    run_local(f"rm -f {shlex.quote(pidfile)}", timeout=120)
    command = [
        "globus-gridftp-server",
        "-aa",
        "-anonymous-user",
        "gridflux3way",
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
            run_local(f"kill {pid} >/dev/null 2>&1 || true", timeout=30)
            time.sleep(1)
            run_local(f"kill -9 {pid} >/dev/null 2>&1 || true", timeout=30)
    run_local(
        "ps -eo pid=,comm=,args= | awk '$2 == \"globus-gridftp-server\" && $0 ~ /gridflux-three-way/ {print $1}' | xargs -r kill >/dev/null 2>&1 || true",
        timeout=30,
    )


def run_native_gridftp(args: argparse.Namespace, sizes: list[int], input_hashes: dict[int, str], state: RunState) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not command_available_local("globus-gridftp-server") or not command_available_remote(args.remote, "globus-url-copy"):
        return [
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
        ]
    root = f"{TMP_PREFIX}-gridftp-root"
    state.gridftp_user_created = setup_gridftp_user(root)
    for size in sizes:
        path = f"{root}/incoming/download_{size}.bin"
        make_local_file(path, size)
        run_local(f"chown gridflux3way:gridflux3way {shlex.quote(path)}", timeout=120)
    if not start_gridftp(args, root):
        return [
            result_row(
                protocol="native_gridftp",
                direction="setup",
                size_bytes=0,
                repeat=0,
                elapsed=0,
                source_sha="",
                dest_sha="",
                status="fail",
                command_summary="globus-gridftp-server -aa",
                server_log=relative_to_root(args.output_dir_path / f"{args.timestamp}_native-gridftp-server.log"),
                notes="native GridFTP server did not start in anonymous/no-GSI mode",
            )
        ]
    for size in sizes:
        client_file = f"{TMP_PREFIX}-client-data/input_{size}.bin"
        for parallelism in [1, 4, 8]:
            for repeat in range(1, args.repeat + 1):
                upload_name = f"native_upload_{size}_p{parallelism}_r{repeat}.bin"
                run_local(f"rm -f {shlex.quote(root + '/incoming/' + upload_name)}", timeout=120)
                remote_log = f"{TMP_PREFIX}-client-data/native_gridftp_upload_{size}_p{parallelism}_r{repeat}.log"
                local_log = args.output_dir_path / f"{args.timestamp}_native_gridftp_upload_{size}_p{parallelism}_r{repeat}_client.log"
                command = (
                    f"globus-url-copy -vb -nodcau -rp -p {parallelism} "
                    f"file://{client_file} "
                    f"ftp://anonymous@{args.server_host}:{args.gridftp_port}/incoming/{upload_name}"
                )
                ok, elapsed, note = timed_remote(args.remote, command, remote_log, timeout=args.case_timeout)
                fetch_remote(args.remote, remote_log, local_log)
                dest_sha = sha_local(f"{root}/incoming/{upload_name}")
                rows.append(
                    result_row(
                        protocol="native_gridftp",
                        direction="upload",
                        size_bytes=size,
                        parallelism=str(parallelism),
                        repeat=repeat,
                        elapsed=elapsed,
                        source_sha=input_hashes[size],
                        dest_sha=dest_sha,
                        status="pass" if ok else "fail",
                        command_summary=f"globus-url-copy -nodcau -rp -p {parallelism} file://... ftp://...",
                        server_log=relative_to_root(args.output_dir_path / f"{args.timestamp}_native-gridftp-server.log"),
                        client_log=relative_to_root(local_log),
                        notes="" if ok else note,
                    )
                )

                dest_path = f"{TMP_PREFIX}-client-data/native_gridftp_download_{size}_p{parallelism}_r{repeat}.bin"
                run_remote(args.remote, f"rm -f {shlex.quote(dest_path)}", timeout=120)
                remote_log = f"{TMP_PREFIX}-client-data/native_gridftp_download_{size}_p{parallelism}_r{repeat}.log"
                local_log = args.output_dir_path / f"{args.timestamp}_native_gridftp_download_{size}_p{parallelism}_r{repeat}_client.log"
                command = (
                    f"globus-url-copy -vb -nodcau -rp -p {parallelism} "
                    f"ftp://anonymous@{args.server_host}:{args.gridftp_port}/incoming/download_{size}.bin "
                    f"file://{dest_path}"
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
                        parallelism=str(parallelism),
                        repeat=repeat,
                        elapsed=elapsed,
                        source_sha=source_sha,
                        dest_sha=dest_sha,
                        status="pass" if ok else "fail",
                        command_summary=f"globus-url-copy -nodcau -rp -p {parallelism} ftp://... file://...",
                        server_log=relative_to_root(args.output_dir_path / f"{args.timestamp}_native-gridftp-server.log"),
                        client_log=relative_to_root(local_log),
                        notes="" if ok else note,
                    )
                )
    return rows


def ensure_gridflux_build(args: argparse.Namespace) -> None:
    build_cmd = "cmake --build build"
    if not (ROOT / "build" / "gridflux-gridftp-server").exists():
        run_local("cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_COMPILER=g++-13", timeout=1200, check=True)
    run_local(build_cmd, timeout=1200, check=True)
    remote_script = """
cd /root/projects/GridFlux
if [ ! -x build/gridflux-gridftp-server ]; then
  cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_COMPILER=g++-13
fi
cmake --build build
"""
    run_remote(args.remote, remote_script, timeout=1800, check=True)


def parse_key_stdout(stdout: str, key: str) -> str:
    prefix = key + "="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip()
    return ""


def run_gridflux(args: argparse.Namespace, sizes: list[int], state: RunState) -> list[dict[str, str]]:
    ensure_gridflux_build(args)
    event_dir = args.output_dir_path / f"{args.timestamp}_gridflux-three-way-events"
    event_dir.mkdir(parents=True, exist_ok=True)
    start_time = time.time()
    command = [
        sys.executable,
        "tools/perf/run_gridftp_private_matrix.py",
        "--smoke",
        "--remote",
        args.remote,
        "--server-host",
        args.server_host,
        "--local-build-dir",
        "/root/projects/GridFlux/build",
        "--remote-build-dir",
        "/root/projects/GridFlux/build",
        "--output-dir",
        args.output_dir,
        "--directions",
        "stor,retr",
        "--bytes",
        ",".join(str(size) for size in sizes),
        "--connections",
        "1,4,8",
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
        "--repeat",
        str(args.repeat),
        "--event-log-dir",
        str(event_dir),
        "--case-timeout",
        str(args.case_timeout),
        "--run-root-base",
        f"{TMP_PREFIX}-gridflux-runs",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
        timeout=max(args.case_timeout * 64, 3600),
    )
    matrix_log = args.output_dir_path / f"{args.timestamp}_gridflux_matrix_runner.log"
    matrix_log.write_text(
        "$ " + " ".join(shlex.quote(part) for part in command) + "\n\n" + completed.stdout + completed.stderr,
        encoding="utf-8",
    )
    raw_csv = parse_key_stdout(completed.stdout, "raw_csv")
    summary_csv = parse_key_stdout(completed.stdout, "summary_csv")
    if not raw_csv:
        candidates = [
            path
            for path in args.output_dir_path.glob("*_gridftp-private-matrix-smoke.csv")
            if path.stat().st_mtime >= start_time - 1
        ]
        if candidates:
            raw_csv = relative_to_root(max(candidates, key=lambda path: path.stat().st_mtime))
    if not summary_csv:
        candidates = [
            path
            for path in args.output_dir_path.glob("*_gridftp-private-matrix-smoke-summary.csv")
            if path.stat().st_mtime >= start_time - 1
        ]
        if candidates:
            summary_csv = relative_to_root(max(candidates, key=lambda path: path.stat().st_mtime))
    state.gridflux_raw_csv = raw_csv
    state.gridflux_summary_csv = summary_csv
    rows: list[dict[str, str]] = []
    for row in read_csv(raw_csv):
        size = int(row.get("bytes") or "0")
        elapsed = float(row.get("elapsed") or "0")
        source_sha = row.get("source_sha256", "")
        dest_sha = row.get("dest_sha256", "")
        status = "pass" if row.get("result") == "pass" else "fail"
        rows.append(
            result_row(
                protocol="gridflux",
                direction=row.get("direction", ""),
                size_bytes=size,
                connections=row.get("connections", ""),
                checksum=row.get("checksum_algorithm", ""),
                repeat=int(row.get("repeat_index") or "0"),
                elapsed=elapsed,
                source_sha=source_sha,
                dest_sha=dest_sha,
                status=status,
                command_summary="run_gridftp_private_matrix.py stor,retr",
                server_log=row.get("server_log", ""),
                client_log=row.get("client_log", ""),
                event_log=row.get("event_log", ""),
                transfer_id=row.get("transfer_id", ""),
                skipped=row.get("skipped_bytes", ""),
                resent=row.get("resent_bytes", ""),
                verified=row.get("verified_bytes", ""),
                notes="" if status == "pass" else row.get("error", ""),
            )
        )
    if completed.returncode != 0 and not rows:
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
                command_summary="run_gridftp_private_matrix.py stor,retr",
                client_log=relative_to_root(matrix_log),
                notes=sanitize(completed.stderr or completed.stdout),
            )
        )
    return rows


def summary_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: dict[tuple[str, str, str, str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        key = (
            row.get("protocol", ""),
            row.get("direction", ""),
            row.get("size_bytes", ""),
            row.get("parallelism", ""),
            row.get("connections", ""),
            row.get("checksum", ""),
        )
        groups.setdefault(key, []).append(row)
    result: list[dict[str, str]] = []
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
        fail_count = sum(1 for row in items if row.get("status") != "pass")
        mismatch_count = sum(1 for row in items if row.get("sha256_match") == "no")
        result.append(
            {
                "protocol": key[0],
                "direction": key[1],
                "size_bytes": key[2],
                "parallelism": key[3],
                "connections": key[4],
                "checksum": key[5],
                "median_MBps": f"{statistics.median(valid_mbps):.3f}" if valid_mbps else "",
                "median_Gbps": f"{statistics.median(valid):.3f}" if valid else "",
                "best_MBps": f"{max(valid_mbps):.3f}" if valid_mbps else "",
                "best_Gbps": f"{max(valid):.3f}" if valid else "",
                "sample_count": str(len(valid)),
                "sha256_mismatch_count": str(mismatch_count),
                "fail_count": str(fail_count),
            }
        )
    return result


def best_by_direction(summary: list[dict[str, str]], directions: set[str]) -> dict[str, str] | None:
    candidates = [
        row
        for row in summary
        if row.get("direction") in directions and row.get("best_Gbps") and int(row.get("sample_count") or "0") > 0
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: float(row["best_Gbps"]))


def seconds_for_size(bytes_count: int, gbps_value: str) -> float:
    gbps = float(gbps_value)
    return bytes_count * 8 / (gbps * 1_000_000_000)


def markdown_summary_table(rows: list[dict[str, str]], limit: int = 40) -> str:
    if not rows:
        return "_No rows._"
    lines = [
        "| protocol | direction | size | p/conn | checksum | median Gbps | best Gbps | samples | fail | mismatch |",
        "| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows[:limit]:
        pc = row.get("parallelism") or row.get("connections")
        lines.append(
            f"| {row.get('protocol','')} | {row.get('direction','')} | {row.get('size_bytes','')} | {pc} | {row.get('checksum','')} | {row.get('median_Gbps','')} | {row.get('best_Gbps','')} | {row.get('sample_count','')} | {row.get('fail_count','')} | {row.get('sha256_mismatch_count','')} |"
        )
    return "\n".join(lines)


def markdown_host_baseline_table(path: str) -> str:
    rows = read_csv(path)
    if not rows:
        return "_No host baseline rows._"
    lines = [
        "| kind | machine | operation | parallelism | MBps | Gbps | status |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('kind','')} | {row.get('machine','')} | {row.get('operation','')} | {row.get('parallelism','')} | {row.get('MBps','')} | {row.get('Gbps','')} | {row.get('status','')} |"
        )
    return "\n".join(lines)


def write_report(args: argparse.Namespace, state: RunState, paths: dict[str, str]) -> None:
    summary = summary_rows(state.ftp_rows + state.gridftp_rows + state.gridflux_rows)
    best_upload = best_by_direction(summary, {"upload", "stor"})
    best_download = best_by_direction(summary, {"download", "retr"})
    one_gib_rows = [row for row in summary if row.get("size_bytes") == str(1024**3)]
    best_upload_1gib = best_by_direction(one_gib_rows, {"upload", "stor"})
    best_download_1gib = best_by_direction(one_gib_rows, {"download", "retr"})
    native_best_upload = best_by_direction([r for r in summary if r["protocol"] == "native_gridftp"], {"upload"})
    gridflux_best_upload = best_by_direction([r for r in summary if r["protocol"] == "gridflux"], {"stor"})
    native_best_download = best_by_direction([r for r in summary if r["protocol"] == "native_gridftp"], {"download"})
    gridflux_best_download = best_by_direction([r for r in summary if r["protocol"] == "gridflux"], {"retr"})

    def compare(gridflux_row: dict[str, str] | None, native_row: dict[str, str] | None) -> str:
        if not gridflux_row or not native_row:
            return "not comparable because one side has no passing hash-valid row"
        delta = (float(gridflux_row["best_Gbps"]) / float(native_row["best_Gbps"]) - 1.0) * 100
        return f"{delta:+.1f}% by best Gbps"

    lines = [
        "# FTP / GridFTP / GridFlux Three-Way Comparison",
        "",
        f"Generated: {timestamp_utc()}",
        "",
        "## Executive Summary",
        "",
        "This report compares plain FTP, native Globus GridFTP, and the current GridFlux prototype between the two Alibaba Cloud servers over the private network. It is a measurement report only: no GridFlux C++ code or default policy was changed.",
        "",
        f"- Plain FTP rows: `{len(state.ftp_rows)}`.",
        f"- Native GridFTP rows: `{len(state.gridftp_rows)}`.",
        f"- GridFlux rows: `{len(state.gridflux_rows)}`.",
        f"- GridFlux vs native GridFTP upload/STOR: {compare(gridflux_best_upload, native_best_upload)}.",
        f"- GridFlux vs native GridFTP download/RETR: {compare(gridflux_best_download, native_best_download)}.",
        "",
        "## Artifacts",
        "",
    ]
    for label, path in paths.items():
        lines.append(f"- {label}: `{path}`")
    if state.gridflux_raw_csv:
        lines.append(f"- GridFlux raw matrix: `{state.gridflux_raw_csv}`")
    if state.gridflux_summary_csv:
        lines.append(f"- GridFlux matrix summary: `{state.gridflux_summary_csv}`")
    lines.extend(["", "## Network And Storage Baseline", "", markdown_host_baseline_table(paths["host_baseline"])])
    lines.extend(["", "## Summary Table", "", markdown_summary_table(summary)])
    lines.extend(["", "## Best Results", ""])
    for label, row in [("best upload/STOR", best_upload), ("best download/RETR", best_download)]:
        if row:
            one_gib = seconds_for_size(1024**3, row["best_Gbps"])
            ten_gb = seconds_for_size(10_000_000_000, row["best_Gbps"])
            lines.append(
                f"- {label}: `{row['protocol']}` `{row['direction']}` size `{row['size_bytes']}` best `{row['best_Gbps']} Gbps`; 1GiB estimate `{one_gib:.2f}s`, 10GB estimate `{ten_gb:.2f}s`."
            )
        else:
            lines.append(f"- {label}: no passing hash-valid row.")
    lines.extend(["", "## Best 1GiB Results", ""])
    for label, row in [("best 1GiB upload/STOR", best_upload_1gib), ("best 1GiB download/RETR", best_download_1gib)]:
        if row:
            one_gib = seconds_for_size(1024**3, row["best_Gbps"])
            ten_gb = seconds_for_size(10_000_000_000, row["best_Gbps"])
            lines.append(
                f"- {label}: `{row['protocol']}` `{row['direction']}` best `{row['best_Gbps']} Gbps`; 1GiB measured-size estimate `{one_gib:.2f}s`, 10GB estimate `{ten_gb:.2f}s`."
            )
        else:
            lines.append(f"- {label}: no passing hash-valid row.")
    lines.extend(
        [
            "",
            "## Fair Conclusion",
            "",
            "- Plain FTP is a low-friction single-stream baseline.",
            "- Native GridFTP is the mature high-performance baseline when anonymous/no-GSI operation succeeds in this temporary setup.",
            "- GridFlux is the current prototype; any advantage is based only on hash-valid CSV rows in this report.",
            "- If GridFlux is not faster in every scenario, its current differentiators remain reliable resume semantics, manifest/checksum verification, event logs, directory transfer, and room for targeted optimization.",
            "",
            "## Cleanup",
            "",
            f"- Removed paths: `{state.cleanup.get('removed_paths','')}`",
            f"- Server residual processes: `{state.cleanup.get('server_residual_processes','') or 'none'}`",
            f"- Client residual processes: `{state.cleanup.get('client_residual_processes','') or 'none'}`",
            f"- Temporary GridFTP user removed: `{state.cleanup.get('gridftp_user_removed','')}`",
            "",
        ]
    )
    (ROOT / "docs" / "perf" / "FTP_GRIDFTP_GRIDFLUX_COMPARISON.md").write_text("\n".join(lines), encoding="utf-8")


def cleanup(args: argparse.Namespace, state: RunState) -> dict[str, str]:
    stop_gridftp()
    run_local(
        "ps -eo pid=,comm=,args= | awk '$2 == \"vsftpd\" && $0 ~ /gridflux-three-way-vsftpd.conf/ {print $1}' | xargs -r kill >/dev/null 2>&1 || true",
        timeout=30,
    )
    run_local(
        "ps -eo pid=,comm=,args= | awk '$2 == \"iperf3\" && $0 ~ / -s / && $0 ~ /5201/ {print $1}' | xargs -r kill >/dev/null 2>&1 || true",
        timeout=30,
    )
    run_remote(
        args.remote,
        "ps -eo pid=,comm=,args= | awk '$0 ~ /gridflux-three-way/ && $2 ~ /^(globus-url-copy|lftp|iperf3)$/ {print $1}' | xargs -r kill >/dev/null 2>&1 || true",
        timeout=30,
    )
    run_local(f"rm -rf {TMP_PREFIX}-* {XTRANSFER_PREFIX}-*", timeout=120)
    run_remote(args.remote, f"rm -rf {TMP_PREFIX}-* {XTRANSFER_PREFIX}-*", timeout=120)
    user_removed = "not_created"
    if state.gridftp_user_created:
        run_local("userdel -r gridflux3way >/dev/null 2>&1 || userdel gridflux3way >/dev/null 2>&1 || true", timeout=120)
        run_local("groupdel gridflux3way >/dev/null 2>&1 || true", timeout=120)
        user_removed = "yes"
    process_check = "ps -eo pid=,comm=,args= | awk '$2 ~ /^(vsftpd|lftp|ftp|globus-gridftp-server|globus-url-copy|gridflux-gridftp-server|gridflux-file-server|gridflux-file-client|gridflux-file-download-sender|gridflux-file-download-client|iperf3)$/ {print}'"
    local = run_local(process_check, timeout=30).stdout.strip()
    remote = run_remote(args.remote, process_check, timeout=30).stdout.strip()
    return {
        "removed_paths": f"{TMP_PREFIX}-* {XTRANSFER_PREFIX}-*",
        "server_residual_processes": local,
        "client_residual_processes": remote,
        "gridftp_user_removed": user_removed,
    }


def write_wrapper(state: RunState, paths: dict[str, str]) -> Path:
    path = state.output_dir / f"{state.timestamp}_three-way-wrapper.json"
    path.write_text(
        json.dumps(
            {
                "timestamp": state.timestamp,
                "paths": paths,
                "gridflux_raw_csv": state.gridflux_raw_csv,
                "gridflux_summary_csv": state.gridflux_summary_csv,
                "cleanup": state.cleanup,
                "ftp_rows": len(state.ftp_rows),
                "native_gridftp_rows": len(state.gridftp_rows),
                "gridflux_rows": len(state.gridflux_rows),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default=os.environ.get("GRIDFLUX_REMOTE", "root@<redacted>"))
    parser.add_argument("--server-host", default=os.environ.get("GRIDFLUX_SERVER_HOST", "<redacted>"))
    parser.add_argument("--output-dir", default="tools/perf/results")
    parser.add_argument("--bytes-list", default="268435456,1073741824")
    parser.add_argument("--include-4gib", action="store_true")
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--case-timeout", type=int, default=1800)
    parser.add_argument("--iperf-seconds", type=int, default=10)
    parser.add_argument("--iperf-port", type=int, default=5201)
    parser.add_argument("--ftp-port", type=int, default=2121)
    parser.add_argument("--ftp-pasv-min-port", type=int, default=32100)
    parser.add_argument("--ftp-pasv-max-port", type=int, default=32179)
    parser.add_argument("--gridftp-port", type=int, default=2811)
    parser.add_argument("--gridftp-port-range-start", type=int, default=32200)
    parser.add_argument("--gridftp-port-range-end", type=int, default=32279)
    return parser


def main() -> int:
    load_private_env()
    parser = build_parser()
    args = parser.parse_args()
    args.timestamp = compact_timestamp()
    args.output_dir_path = Path(args.output_dir)
    args.output_dir_path.mkdir(parents=True, exist_ok=True)
    sizes = parse_size_list(args.bytes_list, include_4gib=args.include_4gib)
    state = RunState(timestamp=args.timestamp, output_dir=args.output_dir_path)

    paths = {
        "environment": relative_to_root(args.output_dir_path / f"{args.timestamp}_three-way-env.txt"),
        "host_baseline": relative_to_root(args.output_dir_path / f"{args.timestamp}_three-way-host-baseline.csv"),
        "input_sha256": relative_to_root(args.output_dir_path / f"{args.timestamp}_three-way-input-sha256.txt"),
        "plain_ftp": relative_to_root(args.output_dir_path / f"{args.timestamp}_plain-ftp-three-way.csv"),
        "native_gridftp": relative_to_root(args.output_dir_path / f"{args.timestamp}_native-gridftp-three-way.csv"),
        "gridflux": relative_to_root(args.output_dir_path / f"{args.timestamp}_gridflux-three-way.csv"),
        "summary": relative_to_root(args.output_dir_path / f"{args.timestamp}_ftp-gridftp-gridflux-summary.csv"),
        "report": "docs/perf/FTP_GRIDFTP_GRIDFLUX_COMPARISON.md",
    }

    try:
        ensure_packages(args)
        collect_environment(args, ROOT / paths["environment"])
        run_host_baseline(args, ROOT / paths["host_baseline"])
        input_hashes = prepare_input_data(args, sizes, ROOT / paths["input_sha256"])
        state.ftp_rows = run_plain_ftp(args, sizes, input_hashes)
        write_csv(ROOT / paths["plain_ftp"], state.ftp_rows, RESULT_FIELDS)
        state.gridftp_rows = run_native_gridftp(args, sizes, input_hashes, state)
        write_csv(ROOT / paths["native_gridftp"], state.gridftp_rows, RESULT_FIELDS)
        state.gridflux_rows = run_gridflux(args, sizes, state)
        write_csv(ROOT / paths["gridflux"], state.gridflux_rows, RESULT_FIELDS)
        write_csv(ROOT / paths["summary"], summary_rows(state.ftp_rows + state.gridftp_rows + state.gridflux_rows), SUMMARY_FIELDS)
    finally:
        state.cleanup = cleanup(args, state)
        write_csv(ROOT / paths["summary"], summary_rows(state.ftp_rows + state.gridftp_rows + state.gridflux_rows), SUMMARY_FIELDS)
        write_report(args, state, paths)
        wrapper = write_wrapper(state, paths)

    print(f"wrapper={relative_to_root(wrapper)}")
    for key, value in paths.items():
        print(f"{key}={value}")
    if state.gridflux_raw_csv:
        print(f"gridflux_raw_csv={state.gridflux_raw_csv}")
    if state.gridflux_summary_csv:
        print(f"gridflux_summary_csv={state.gridflux_summary_csv}")
    print(f"server_residual_processes={state.cleanup.get('server_residual_processes','') or 'none'}")
    print(f"client_residual_processes={state.cleanup.get('client_residual_processes','') or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
