#!/usr/bin/env python3
"""Run ordinary FTP and Globus GridFTP baseline smoke tests.

The script keeps credentials out of logs. Remote SSH authentication is delegated
to tools/release/remote_auth.py, which may read the private AGENTS.md file.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "release"))
import remote_auth  # noqa: E402


RESULT_FIELDS = [
    "protocol",
    "direction",
    "bytes",
    "elapsed_seconds",
    "mib_per_second",
    "gbps",
    "tool",
    "parallelism",
    "sha256_match",
    "status",
    "notes",
]

BASELINE_PREFIX = "/tmp/gridflux-baseline"


@dataclass
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass
class BaselineSummary:
    timestamp: str
    ftp_status: str = "not_run"
    gridftp_status: str = "not_run"
    ftp_csv: str = ""
    gridftp_csv: str = ""
    gridftp_status_file: str = ""
    env_file: str = ""
    report_file: str = "docs/perf/BASELINE_FTP_GRIDFTP_SMOKE.md"
    cleanup: dict[str, str] = field(default_factory=dict)
    rows: list[dict[str, str]] = field(default_factory=list)
    gridftp_rows: list[dict[str, str]] = field(default_factory=list)


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


def parse_size_list(text: str, *, include_4gib: bool = False) -> list[int]:
    values = [parse_size_token(part) for part in text.split(",") if part.strip()]
    if include_4gib and 4 * 1024**3 not in values:
        values.append(4 * 1024**3)
    return values


def mib_per_second(bytes_count: int, elapsed: float) -> float:
    if elapsed <= 0:
        return 0.0
    return bytes_count / (1024**2) / elapsed


def gbps(bytes_count: int, elapsed: float) -> float:
    if elapsed <= 0:
        return 0.0
    return bytes_count * 8 / elapsed / 1_000_000_000


def sanitize_note(text: str, max_len: int = 220) -> str:
    cleaned = " ".join((text or "").replace("\x00", "").split())
    for key in ("password", "token", "private_key", "GRIDFLUX_SSH_PASSWORD", "SSHPASS"):
        cleaned = cleaned.replace(key, "<redacted-key>")
    return cleaned[:max_len]


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
        raise RuntimeError(sanitize_note(result.stderr or result.stdout))
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
        raise RuntimeError(sanitize_note(result.stderr or result.stdout))
    return result


def agents_topology_defaults() -> tuple[str, str]:
    agents = ROOT / "AGENTS.md"
    if not agents.is_file():
        return "", ""
    try:
        text = agents.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "", ""
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        cells = remote_auth.markdown_cells(line)
        if len(cells) < 5:
            continue
        header = "".join(cells[:5]).lower()
        if "password" in header or "密码" in header or ("<redacted>" in header and "用户" in header):
            continue
        _machine, _public_ip, private_ip, user, _password = cells[:5]
        if private_ip and user:
            rows.append((user, private_ip, _public_ip))
    if len(rows) < 2:
        return "", ""
    server_host = rows[0][1]
    remote = f"{rows[1][0]}@{rows[1][1]}"
    return remote, server_host


def package_status_script() -> str:
    packages = [
        "ftp",
        "lftp",
        "vsftpd",
        "globus-gridftp-server",
        "globus-url-copy",
        "uberftp",
        "globus",
    ]
    package_list = " ".join(shlex.quote(pkg) for pkg in packages)
    return f"""
set +e
echo "hostname=$(hostname 2>/dev/null || true)"
echo "kernel=$(uname -srmo 2>/dev/null || true)"
if [ -r /etc/os-release ]; then . /etc/os-release; echo "os=${{PRETTY_NAME:-unknown}}"; else echo "os=unknown"; fi
echo "cpu=$(LC_ALL=C lscpu 2>/dev/null | awk -F: '/Model name/ {{gsub(/^[ \\t]+/, "", $2); print $2; exit}}')"
if command -v apt-get >/dev/null 2>&1; then pm=apt; elif command -v dnf >/dev/null 2>&1; then pm=dnf; elif command -v yum >/dev/null 2>&1; then pm=yum; else pm=unknown; fi
echo "package_manager=$pm"
for pkg in {package_list}; do
  bin="$pkg"
  case "$pkg" in
    globus-url-copy) bin=globus-url-copy ;;
    globus-gridftp-server) bin=globus-gridftp-server ;;
  esac
  installed=no
  installable=unknown
  version=""
  if command -v "$bin" >/dev/null 2>&1; then installed=yes; version=$(command -v "$bin"); fi
  if [ "$pm" = apt ]; then
    candidate=$(apt-cache policy "$pkg" 2>/dev/null | awk '/Candidate:/ {{print $2; exit}}')
    [ -n "$candidate" ] && [ "$candidate" != "(none)" ] && installable=yes || installable=no
  elif [ "$pm" = dnf ] || [ "$pm" = yum ]; then
    if rpm -q "$pkg" >/dev/null 2>&1; then installed=yes; fi
    if "$pm" -q list available "$pkg" >/dev/null 2>&1; then installable=yes; else installable=no; fi
  fi
  echo "package=$pkg installed=$installed installable=$installable version=$version"
done
"""


def command_available(script_runner, binary: str) -> bool:
    result = script_runner(f"command -v {shlex.quote(binary)} >/dev/null 2>&1")
    return result.returncode == 0


def detect_pm(script_runner) -> str:
    result = script_runner(
        "if command -v apt-get >/dev/null 2>&1; then echo apt; "
        "elif command -v dnf >/dev/null 2>&1; then echo dnf; "
        "elif command -v yum >/dev/null 2>&1; then echo yum; else echo unknown; fi"
    )
    return result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "unknown"


def installable(script_runner, package: str) -> bool:
    quoted = shlex.quote(package)
    result = script_runner(
        f"""
pm=unknown
if command -v apt-get >/dev/null 2>&1; then pm=apt; elif command -v dnf >/dev/null 2>&1; then pm=dnf; elif command -v yum >/dev/null 2>&1; then pm=yum; fi
if [ "$pm" = apt ]; then
  candidate=$(apt-cache policy {quoted} 2>/dev/null | awk '/Candidate:/ {{print $2; exit}}')
  [ -n "$candidate" ] && [ "$candidate" != "(none)" ]
elif [ "$pm" = dnf ] || [ "$pm" = yum ]; then
  "$pm" -q list available {quoted} >/dev/null 2>&1 || rpm -q {quoted} >/dev/null 2>&1
else
  exit 1
fi
""",
        timeout=120,
    )
    return result.returncode == 0


def ensure_package(script_runner, package: str, binary: str, *, timeout: int = 600) -> str:
    if command_available(script_runner, binary):
        return "already_installed"
    if not installable(script_runner, package):
        return "unavailable_package"
    pm = detect_pm(script_runner)
    if pm == "apt":
        command = (
            "export DEBIAN_FRONTEND=noninteractive; "
            "if [ \"$(id -u)\" = 0 ]; then prefix=''; else prefix='sudo -n'; fi; "
            f"$prefix apt-get update -y >/dev/null 2>&1 && $prefix apt-get install -y {shlex.quote(package)} >/dev/null 2>&1"
        )
    elif pm in {"dnf", "yum"}:
        command = (
            "if [ \"$(id -u)\" = 0 ]; then prefix=''; else prefix='sudo -n'; fi; "
            f"$prefix {pm} install -y {shlex.quote(package)} >/dev/null 2>&1"
        )
    else:
        return "unavailable_package_manager"
    result = script_runner(command, timeout=timeout)
    if result.returncode != 0:
        return "install_failed:" + sanitize_note(result.stderr or result.stdout, 120)
    return "installed" if command_available(script_runner, binary) else "install_failed:binary_missing"


def local_runner(script: str, timeout: int = 120) -> CommandResult:
    return run_local(script, timeout=timeout)


def remote_runner(remote: str):
    def _run(script: str, timeout: int = 120) -> CommandResult:
        return run_remote(remote, script, timeout=timeout)

    return _run


def preexisting_processes(script_runner, pattern: str) -> str:
    result = script_runner(f"pgrep -af {shlex.quote(pattern)} || true")
    return result.stdout.strip()


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in RESULT_FIELDS})


def relative_to_root(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def parse_kv(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


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


def make_local_zero_file(path: str, bytes_count: int) -> str:
    mib = bytes_count // (1024**2)
    result = run_local(
        f"mkdir -p {shlex.quote(str(Path(path).parent))} && "
        f"dd if=/dev/zero of={shlex.quote(path)} bs=1M count={mib} conv=fsync status=none && "
        f"sha256sum {shlex.quote(path)} | awk '{{print $1}}'",
        timeout=900,
        check=True,
    )
    return result.stdout.strip().splitlines()[-1]


def make_remote_zero_file(remote: str, path: str, bytes_count: int) -> str:
    mib = bytes_count // (1024**2)
    result = run_remote(
        remote,
        f"mkdir -p {shlex.quote(str(Path(path).parent))} && "
        f"dd if=/dev/zero of={shlex.quote(path)} bs=1M count={mib} conv=fsync status=none && "
        f"sha256sum {shlex.quote(path)} | awk '{{print $1}}'",
        timeout=900,
        check=True,
    )
    return result.stdout.strip().splitlines()[-1]


def remote_lftp(remote: str, lftp_command: str, log_name: str, *, timeout: int = 900) -> CommandResult:
    log_path = f"{BASELINE_PREFIX}-ftp-client/{log_name}"
    script = f"""
set +e
start=$(python3 -c 'import time; print(time.monotonic())')
lftp -e {shlex.quote(lftp_command)} >{shlex.quote(log_path)} 2>&1
rc=$?
end=$(python3 -c 'import time; print(time.monotonic())')
if [ "$rc" = 0 ]; then echo "status=pass"; else echo "status=fail"; fi
echo "returncode=$rc"
python3 - <<PY
print("elapsed_seconds=%.6f" % (float("$end") - float("$start")))
PY
if [ "$rc" != 0 ]; then tail -n 5 {shlex.quote(log_path)} 2>/dev/null | sed 's/^/log_tail=/' ; fi
exit "$rc"
"""
    return run_remote(remote, script, timeout=timeout)


def ftp_put(remote: str, host: str, port: int, source: str, *, timeout: int = 900) -> tuple[bool, float, str]:
    command = (
        "set net:max-retries 1; set net:timeout 60; set ftp:passive-mode yes; "
        f"open -u anonymous, ftp://{host}:{port}; "
        f"put -O /incoming {source}; bye"
    )
    result = remote_lftp(remote, command, f"lftp_put_{Path(source).name}.log", timeout=timeout)
    kv = parse_kv(result.stdout)
    elapsed = float(kv.get("elapsed_seconds", "0") or "0")
    note = sanitize_note(result.stderr or result.stdout)
    return result.returncode == 0, elapsed, note


def ftp_get(remote: str, host: str, port: int, remote_file: str, dest: str, *, timeout: int = 900) -> tuple[bool, float, str]:
    command = (
        "set net:max-retries 1; set net:timeout 60; set ftp:passive-mode yes; "
        f"open -u anonymous, ftp://{host}:{port}; "
        f"get /incoming/{remote_file} -o {dest}; bye"
    )
    result = remote_lftp(remote, command, f"lftp_get_{remote_file}.log", timeout=timeout)
    kv = parse_kv(result.stdout)
    elapsed = float(kv.get("elapsed_seconds", "0") or "0")
    note = sanitize_note(result.stderr or result.stdout)
    return result.returncode == 0, elapsed, note


def sha_local(path: str) -> str:
    result = run_local(f"sha256sum {shlex.quote(path)} | awk '{{print $1}}'", timeout=120)
    return result.stdout.strip().splitlines()[-1] if result.returncode == 0 and result.stdout.strip() else ""


def sha_remote(remote: str, path: str) -> str:
    result = run_remote(remote, f"sha256sum {shlex.quote(path)} | awk '{{print $1}}'", timeout=120)
    return result.stdout.strip().splitlines()[-1] if result.returncode == 0 and result.stdout.strip() else ""


def setup_vsftpd_root(server_root: str, sizes: list[int]) -> dict[int, str]:
    run_local(
        f"rm -rf {shlex.quote(server_root)} && "
        f"mkdir -p {shlex.quote(server_root + '/incoming')} && "
        f"chmod 755 {shlex.quote(server_root)} && chmod 777 {shlex.quote(server_root + '/incoming')}",
        timeout=120,
        check=True,
    )
    hashes: dict[int, str] = {}
    for bytes_count in sizes:
        hashes[bytes_count] = make_local_zero_file(f"{server_root}/incoming/baseline_{bytes_count}.bin", bytes_count)
        run_local(f"chmod 666 {shlex.quote(server_root + f'/incoming/baseline_{bytes_count}.bin')}", timeout=120)
    return hashes


def start_vsftpd(args: argparse.Namespace, server_root: str, log_path: Path) -> subprocess.Popen[str]:
    config = Path(f"{BASELINE_PREFIX}-vsftpd.conf")
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
                f"anon_root={server_root}",
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
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        ["vsftpd", str(config)],
        cwd=ROOT,
        text=True,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    if not wait_for_port("127.0.0.1", args.ftp_port, timeout=10):
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        raise RuntimeError("vsftpd did not open the baseline FTP port")
    return process


def stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_ftp_baseline(args: argparse.Namespace, timestamp: str, sizes: list[int], summary: BaselineSummary) -> list[dict[str, str]]:
    local_preexisting = preexisting_processes(local_runner, "[v]sftpd")
    if local_preexisting:
        summary.ftp_status = "skipped_preexisting_vsftpd"
        return []

    vsftpd_status = ensure_package(local_runner, "vsftpd", "vsftpd")
    lftp_status = ensure_package(remote_runner(args.remote), "lftp", "lftp")
    if vsftpd_status.startswith("unavailable") or vsftpd_status.startswith("install_failed"):
        summary.ftp_status = f"unavailable_server_{vsftpd_status}"
        return []
    if lftp_status.startswith("unavailable") or lftp_status.startswith("install_failed"):
        summary.ftp_status = f"unavailable_client_{lftp_status}"
        return []

    run_local("if command -v systemctl >/dev/null 2>&1; then systemctl stop vsftpd >/dev/null 2>&1 || true; fi", timeout=120)
    server_root = f"{BASELINE_PREFIX}-ftp-root"
    client_root = f"{BASELINE_PREFIX}-ftp-client"
    run_remote(args.remote, f"rm -rf {shlex.quote(client_root)} && mkdir -p {shlex.quote(client_root)}", timeout=120, check=True)
    setup_vsftpd_root(server_root, sizes)

    process: subprocess.Popen[str] | None = None
    rows: list[dict[str, str]] = []
    try:
        process = start_vsftpd(args, server_root, Path(args.output_dir) / f"{timestamp}_vsftpd.log")
        for bytes_count in sizes:
            filename = f"baseline_{bytes_count}.bin"
            client_file = f"{client_root}/{filename}"
            client_download = f"{client_root}/download_{filename}"
            source_sha = make_remote_zero_file(args.remote, client_file, bytes_count)

            ok, elapsed, note = ftp_put(args.remote, args.server_host, args.ftp_port, client_file)
            server_sha = sha_local(f"{server_root}/incoming/{filename}")
            upload_match = bool(source_sha and server_sha and source_sha == server_sha)
            rows.append(
                {
                    "protocol": "ftp",
                    "direction": "upload",
                    "bytes": str(bytes_count),
                    "elapsed_seconds": f"{elapsed:.6f}",
                    "mib_per_second": f"{mib_per_second(bytes_count, elapsed):.3f}",
                    "gbps": f"{gbps(bytes_count, elapsed):.3f}",
                    "tool": "lftp/vsftpd",
                    "parallelism": "1",
                    "sha256_match": "yes" if upload_match else "no",
                    "status": "pass" if ok and upload_match else "fail",
                    "notes": "" if ok and upload_match else note,
                }
            )

            ok, elapsed, note = ftp_get(args.remote, args.server_host, args.ftp_port, filename, client_download)
            download_sha = sha_remote(args.remote, client_download)
            expected_sha = sha_local(f"{server_root}/incoming/{filename}")
            download_match = bool(download_sha and expected_sha and download_sha == expected_sha)
            rows.append(
                {
                    "protocol": "ftp",
                    "direction": "download",
                    "bytes": str(bytes_count),
                    "elapsed_seconds": f"{elapsed:.6f}",
                    "mib_per_second": f"{mib_per_second(bytes_count, elapsed):.3f}",
                    "gbps": f"{gbps(bytes_count, elapsed):.3f}",
                    "tool": "lftp/vsftpd",
                    "parallelism": "1",
                    "sha256_match": "yes" if download_match else "no",
                    "status": "pass" if ok and download_match else "fail",
                    "notes": "" if ok and download_match else note,
                }
            )
        summary.ftp_status = "pass" if rows and all(row["status"] == "pass" for row in rows) else "fail"
        return rows
    finally:
        stop_process(process)
        run_local("if command -v systemctl >/dev/null 2>&1; then systemctl stop vsftpd >/dev/null 2>&1 || true; fi", timeout=120)


def start_gridftp(args: argparse.Namespace, server_root: str, log_path: Path) -> subprocess.Popen[str]:
    log_handle = log_path.open("w", encoding="utf-8")
    command = [
        "globus-gridftp-server",
        "-aa",
        "-p",
        str(args.gridftp_port),
        "-root",
        server_root,
        "-d",
        "ERROR",
    ]
    process = subprocess.Popen(command, cwd=ROOT, text=True, stdout=log_handle, stderr=subprocess.STDOUT)
    if not wait_for_port("127.0.0.1", args.gridftp_port, timeout=10):
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        raise RuntimeError("globus-gridftp-server did not open the baseline GridFTP port")
    return process


def remote_globus_url_copy(
    remote: str,
    command: str,
    *,
    timeout: int = 900,
) -> tuple[bool, float, str]:
    script = f"""
set +e
start=$(python3 -c 'import time; print(time.monotonic())')
{command} >/tmp/gridflux-baseline-gridftp-client/globus-url-copy.log 2>&1
rc=$?
end=$(python3 -c 'import time; print(time.monotonic())')
echo "returncode=$rc"
python3 - <<PY
print("elapsed_seconds=%.6f" % (float("$end") - float("$start")))
PY
if [ "$rc" != 0 ]; then tail -n 8 /tmp/gridflux-baseline-gridftp-client/globus-url-copy.log 2>/dev/null | sed 's/^/log_tail=/' ; fi
exit "$rc"
"""
    result = run_remote(remote, script, timeout=timeout)
    kv = parse_kv(result.stdout)
    elapsed = float(kv.get("elapsed_seconds", "0") or "0")
    return result.returncode == 0, elapsed, sanitize_note(result.stderr or result.stdout)


def run_gridftp_baseline(args: argparse.Namespace, timestamp: str, sizes: list[int], summary: BaselineSummary) -> list[dict[str, str]]:
    local_preexisting = preexisting_processes(local_runner, "[g]lobus-gridftp-server")
    if local_preexisting:
        summary.gridftp_status = "skipped_preexisting_gridftp"
        return []

    server_pkg = ensure_package(local_runner, "globus-gridftp-server", "globus-gridftp-server")
    client_pkg = ensure_package(remote_runner(args.remote), "globus-url-copy", "globus-url-copy")
    if server_pkg.startswith("unavailable") or client_pkg.startswith("unavailable"):
        summary.gridftp_status = "unavailable_package"
        return []
    if server_pkg.startswith("install_failed") or client_pkg.startswith("install_failed"):
        summary.gridftp_status = "unavailable_package_install_failed"
        return []

    server_root = f"{BASELINE_PREFIX}-gridftp-root"
    client_root = f"{BASELINE_PREFIX}-gridftp-client"
    run_local(f"rm -rf {shlex.quote(server_root)} && mkdir -p {shlex.quote(server_root + '/incoming')}", timeout=120, check=True)
    run_remote(args.remote, f"rm -rf {shlex.quote(client_root)} && mkdir -p {shlex.quote(client_root)}", timeout=120, check=True)
    for bytes_count in sizes:
        make_local_zero_file(f"{server_root}/incoming/baseline_{bytes_count}.bin", bytes_count)

    process: subprocess.Popen[str] | None = None
    rows: list[dict[str, str]] = []
    try:
        try:
            process = start_gridftp(args, server_root, Path(args.output_dir) / f"{timestamp}_globus-gridftp-server.log")
        except RuntimeError as exc:
            summary.gridftp_status = "unavailable_requires_gsi_or_server_start_failed:" + sanitize_note(str(exc), 120)
            return rows

        for bytes_count in sizes:
            filename = f"baseline_{bytes_count}.bin"
            client_file = f"{client_root}/{filename}"
            client_download = f"{client_root}/download_{filename}"
            source_sha = make_remote_zero_file(args.remote, client_file, bytes_count)
            for parallelism in [1, 4, 8]:
                upload_command = (
                    f"globus-url-copy -vb -p {parallelism} "
                    f"file://{client_file} "
                    f"gsiftp://{args.server_host}:{args.gridftp_port}/incoming/{filename}"
                )
                ok, elapsed, note = remote_globus_url_copy(args.remote, upload_command)
                server_sha = sha_local(f"{server_root}/incoming/{filename}")
                match = bool(source_sha and server_sha and source_sha == server_sha)
                rows.append(
                    {
                        "protocol": "gridftp",
                        "direction": "upload",
                        "bytes": str(bytes_count),
                        "elapsed_seconds": f"{elapsed:.6f}",
                        "mib_per_second": f"{mib_per_second(bytes_count, elapsed):.3f}",
                        "gbps": f"{gbps(bytes_count, elapsed):.3f}",
                        "tool": "globus-url-copy/globus-gridftp-server",
                        "parallelism": str(parallelism),
                        "sha256_match": "yes" if match else "no",
                        "status": "pass" if ok and match else "fail",
                        "notes": "" if ok and match else note,
                    }
                )

                download_command = (
                    f"globus-url-copy -vb -p {parallelism} "
                    f"gsiftp://{args.server_host}:{args.gridftp_port}/incoming/{filename} "
                    f"file://{client_download}"
                )
                ok, elapsed, note = remote_globus_url_copy(args.remote, download_command)
                download_sha = sha_remote(args.remote, client_download)
                expected_sha = sha_local(f"{server_root}/incoming/{filename}")
                match = bool(download_sha and expected_sha and download_sha == expected_sha)
                rows.append(
                    {
                        "protocol": "gridftp",
                        "direction": "download",
                        "bytes": str(bytes_count),
                        "elapsed_seconds": f"{elapsed:.6f}",
                        "mib_per_second": f"{mib_per_second(bytes_count, elapsed):.3f}",
                        "gbps": f"{gbps(bytes_count, elapsed):.3f}",
                        "tool": "globus-url-copy/globus-gridftp-server",
                        "parallelism": str(parallelism),
                        "sha256_match": "yes" if match else "no",
                        "status": "pass" if ok and match else "fail",
                        "notes": "" if ok and match else note,
                    }
                )
        summary.gridftp_status = "pass" if rows and all(row["status"] == "pass" for row in rows) else "fail"
        return rows
    finally:
        stop_process(process)


def collect_environment(args: argparse.Namespace, path: Path) -> None:
    local = run_local(package_status_script(), timeout=180)
    remote = run_remote(args.remote, package_status_script(), timeout=180)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"generated={timestamp_utc()}",
                "scope=server_machine_one",
                local.stdout.strip(),
                "",
                "scope=client_machine_two",
                remote.stdout.strip(),
                "",
            ]
        ),
        encoding="utf-8",
    )


def cleanup(args: argparse.Namespace) -> dict[str, str]:
    cleanup_info: dict[str, str] = {}
    local_cleanup = run_local(
        f"""
set +e
if command -v systemctl >/dev/null 2>&1; then systemctl stop vsftpd >/dev/null 2>&1 || true; fi
rm -rf /tmp/gridflux-baseline-* /tmp/gridflux-baseline-vsftpd.conf
ps -eo pid=,comm=,args= | awk '$2 ~ /^(vsftpd|globus-gridftp-server|globus-url-copy|lftp|ftp)$/ {print}'
exit 0
""",
        timeout=120,
    )
    remote_cleanup = run_remote(
        args.remote,
        f"""
set +e
rm -rf /tmp/gridflux-baseline-*
ps -eo pid=,comm=,args= | awk '$2 ~ /^(vsftpd|globus-gridftp-server|globus-url-copy|lftp|ftp)$/ {print}'
exit 0
""",
        timeout=120,
    )
    cleanup_info["server_residual_processes"] = local_cleanup.stdout.strip()
    cleanup_info["client_residual_processes"] = remote_cleanup.stdout.strip()
    cleanup_info["server_cleanup_status"] = "pass" if local_cleanup.returncode == 0 else "fail"
    cleanup_info["client_cleanup_status"] = "pass" if remote_cleanup.returncode == 0 else "fail"
    cleanup_info["removed_dirs"] = "/tmp/gridflux-baseline-*"
    return cleanup_info


def write_gridftp_status(path: Path, summary: BaselineSummary) -> None:
    path.write_text(
        "\n".join(
            [
                f"generated={timestamp_utc()}",
                f"gridftp_baseline_status={summary.gridftp_status}",
                "note=system packages only; no source build and no GSI/certificate setup attempted",
                "",
            ]
        ),
        encoding="utf-8",
    )


def rows_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "_No passing rows._"
    lines = [
        "| protocol | direction | bytes | MiB/s | Gbps | status | sha256 | notes |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in rows:
        notes = row.get("notes", "")
        lines.append(
            "| {protocol} | {direction} | {bytes} | {mib_per_second} | {gbps} | {status} | {sha256_match} | {notes} |".format(
                **{**row, "notes": notes.replace("|", "/")}
            )
        )
    return "\n".join(lines)


def near_80mbps(rows: list[dict[str, str]]) -> str:
    passing = [float(row["mib_per_second"]) for row in rows if row.get("status") == "pass" and row.get("mib_per_second")]
    if not passing:
        return "no passing rows"
    median = sorted(passing)[len(passing) // 2]
    if 60 <= median <= 100:
        return f"yes, median {median:.1f} MiB/s is near 80 MB/s"
    return f"no, median {median:.1f} MiB/s is not near 80 MB/s"


def write_report(summary: BaselineSummary) -> None:
    report = ROOT / summary.report_file
    lines = [
        "# Baseline FTP / GridFTP Smoke",
        "",
        f"Generated: {timestamp_utc()}",
        "",
        "## Executive Summary",
        "",
        "This is a lightweight comparison baseline on the existing two cloud servers. It is not a GridFlux release gate, and it does not change GridFlux defaults or C++ transfer code.",
        "",
        f"- FTP baseline status: `{summary.ftp_status}`.",
        f"- GridFTP baseline status: `{summary.gridftp_status}`.",
        f"- FTP 80 MB/s comparison: {near_80mbps(summary.rows)}.",
        f"- GridFTP 80 MB/s comparison: {near_80mbps(summary.gridftp_rows)}.",
        "",
        "## Artifacts",
        "",
        f"- Environment: `{summary.env_file}`",
        f"- FTP CSV: `{summary.ftp_csv}`",
    ]
    if summary.gridftp_csv:
        lines.append(f"- GridFTP CSV: `{summary.gridftp_csv}`")
    if summary.gridftp_status_file:
        lines.append(f"- GridFTP status: `{summary.gridftp_status_file}`")
    lines.extend(
        [
            "",
            "## FTP Results",
            "",
            rows_table(summary.rows),
            "",
            "## GridFTP Results",
            "",
            rows_table(summary.gridftp_rows),
            "",
            "## Current GridFlux Context",
            "",
            "Beta 1C RETR focused matrix reported median/best RETR throughput of `3.457 / 4.675 Gbps`; Beta 1B-5 attributed STOR write bottlenecks mostly to cloud storage, filesystem, page cache, and OS writeback behavior. This baseline smoke is only a comparison point for ordinary FTP/GridFTP in the same environment.",
            "",
            "## Cleanup",
            "",
            f"- Removed directories: `{summary.cleanup.get('removed_dirs', '')}`",
            f"- Server cleanup status: `{summary.cleanup.get('server_cleanup_status', '')}`",
            f"- Client cleanup status: `{summary.cleanup.get('client_cleanup_status', '')}`",
            f"- Server residual processes: `{summary.cleanup.get('server_residual_processes', '') or 'none'}`",
            f"- Client residual processes: `{summary.cleanup.get('client_residual_processes', '') or 'none'}`",
            "",
            "## Limits",
            "",
            "- Only `256MiB` and `1GiB` are tested by default.",
            "- GridFTP uses system packages only. If packages or anonymous/no-GSI operation are unavailable, the result is recorded as unavailable rather than compiled from source.",
            "- No server passwords, tokens, or private keys are written to this report.",
            "",
        ]
    )
    report.write_text("\n".join(lines), encoding="utf-8")


def write_wrapper(summary: BaselineSummary, path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "timestamp": summary.timestamp,
                "ftp_status": summary.ftp_status,
                "gridftp_status": summary.gridftp_status,
                "ftp_csv": summary.ftp_csv,
                "gridftp_csv": summary.gridftp_csv,
                "gridftp_status_file": summary.gridftp_status_file,
                "env_file": summary.env_file,
                "report_file": summary.report_file,
                "cleanup": summary.cleanup,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    default_remote, default_server_host = agents_topology_defaults()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default=os.environ.get("GRIDFLUX_REMOTE", default_remote or "root@<redacted>"))
    parser.add_argument("--server-host", default=os.environ.get("GRIDFLUX_SERVER_HOST", default_server_host or "<redacted>"))
    parser.add_argument("--output-dir", default="tools/perf/results")
    parser.add_argument("--bytes-list", default="268435456,1073741824")
    parser.add_argument("--include-4gib", action="store_true")
    parser.add_argument("--ftp-port", type=int, default=2121)
    parser.add_argument("--ftp-pasv-min-port", type=int, default=32100)
    parser.add_argument("--ftp-pasv-max-port", type=int, default=32119)
    parser.add_argument("--gridftp-port", type=int, default=2811)
    parser.add_argument("--skip-ftp", action="store_true")
    parser.add_argument("--skip-gridftp", action="store_true")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    timestamp = compact_timestamp()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sizes = parse_size_list(args.bytes_list, include_4gib=args.include_4gib)

    summary = BaselineSummary(timestamp=timestamp)
    env_path = output_dir / f"{timestamp}_baseline_env.txt"
    wrapper_path = output_dir / f"{timestamp}_baseline-ftp-gridftp-smoke.json"
    ftp_csv = output_dir / f"{timestamp}_ftp-baseline.csv"
    gridftp_csv = output_dir / f"{timestamp}_gridftp-baseline.csv"
    gridftp_status = output_dir / f"{timestamp}_gridftp-baseline-status.txt"
    summary.env_file = relative_to_root(env_path)
    summary.ftp_csv = relative_to_root(ftp_csv)

    try:
        collect_environment(args, env_path)
        if args.skip_ftp:
            summary.ftp_status = "skipped"
        else:
            summary.rows = run_ftp_baseline(args, timestamp, sizes, summary)
        write_csv(ftp_csv, summary.rows)

        if args.skip_gridftp:
            summary.gridftp_status = "skipped"
        else:
            summary.gridftp_rows = run_gridftp_baseline(args, timestamp, sizes, summary)
        if summary.gridftp_rows:
            summary.gridftp_csv = relative_to_root(gridftp_csv)
            write_csv(gridftp_csv, summary.gridftp_rows)
        else:
            summary.gridftp_status_file = relative_to_root(gridftp_status)
            write_gridftp_status(gridftp_status, summary)
    finally:
        summary.cleanup = cleanup(args)
        write_report(summary)
        write_wrapper(summary, wrapper_path)

    print(f"baseline_wrapper={relative_to_root(wrapper_path)}")
    print(f"baseline_env={summary.env_file}")
    print(f"ftp_csv={summary.ftp_csv}")
    if summary.gridftp_csv:
        print(f"gridftp_csv={summary.gridftp_csv}")
    if summary.gridftp_status_file:
        print(f"gridftp_status={summary.gridftp_status_file}")
    print(f"report={summary.report_file}")
    print(f"ftp_status={summary.ftp_status}")
    print(f"gridftp_status={summary.gridftp_status}")
    print(f"server_residual_processes={summary.cleanup.get('server_residual_processes', '') or 'none'}")
    print(f"client_residual_processes={summary.cleanup.get('client_residual_processes', '') or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
