#!/usr/bin/env python3
"""Focused loopback smoke for STOR/RETR resume over control TLS + data TLS."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def make_file(path: Path, total_bytes: int) -> None:
    block = bytes((index * 29) % 251 for index in range(1024 * 1024))
    remaining = total_bytes
    with path.open("wb") as handle:
        while remaining:
            size = min(remaining, len(block))
            handle.write(block[:size])
            remaining -= size


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def generate_cert(cert: Path, key: Path) -> bool:
    openssl = shutil.which("openssl")
    if not openssl:
        return False
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-sha256",
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=localhost",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    key.chmod(0o600)
    return True


def read_line(sock: socket.socket | ssl.SSLSocket, buffer: bytearray) -> str:
    while b"\n" not in buffer:
        chunk = sock.recv(4096)
        if not chunk:
            raise RuntimeError("control connection closed")
        buffer.extend(chunk)
    index = buffer.index(ord("\n"))
    line = bytes(buffer[: index + 1]).decode("utf-8", errors="replace").rstrip("\r\n")
    del buffer[: index + 1]
    return line


def read_reply(sock: socket.socket | ssl.SSLSocket, buffer: bytearray) -> list[str]:
    first = read_line(sock, buffer)
    lines = [first]
    if len(first) >= 4 and first[:3].isdigit() and first[3] == "-":
        expected = first[:3] + " "
        while True:
            line = read_line(sock, buffer)
            lines.append(line)
            if line.startswith(expected):
                break
    return lines


def reply_code(lines: list[str]) -> int:
    return int(lines[0][:3]) if lines and len(lines[0]) >= 3 and lines[0][:3].isdigit() else 0


def send_command(sock: socket.socket | ssl.SSLSocket, buffer: bytearray, command: str) -> list[str]:
    sock.sendall((command + "\r\n").encode("utf-8"))
    return read_reply(sock, buffer)


def parse_epsv_port(lines: list[str]) -> int:
    match = re.search(r"\(\|\|\|(\d+)\|\)", "\n".join(lines))
    if not match:
        raise RuntimeError(f"failed to parse EPSV port from {lines!r}")
    return int(match.group(1))


def parse_transfer_id(lines: list[str]) -> str:
    match = re.search(r"transfer_id=GFID:([A-Za-z0-9._-]+)", "\n".join(lines))
    if not match:
        raise RuntimeError(f"failed to parse transfer id from {lines!r}")
    return match.group(1)


def tls_connect(port: int, cafile: Path) -> tuple[ssl.SSLSocket, bytearray, list[str]]:
    raw = socket.create_connection(("127.0.0.1", port), timeout=5.0)
    context = ssl.create_default_context(cafile=str(cafile))
    context.check_hostname = False
    sock = context.wrap_socket(raw, server_hostname="localhost")
    buffer = bytearray()
    greeting = read_reply(sock, buffer)
    return sock, buffer, greeting


def wait_tls_server(port: int, cafile: Path) -> None:
    deadline = time.monotonic() + 10.0
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            sock, _, greeting = tls_connect(port, cafile)
            with sock:
                if reply_code(greeting) == 220:
                    return
        except (OSError, ssl.SSLError, RuntimeError) as error:
            last_error = error
            time.sleep(0.05)
    raise RuntimeError(f"TLS server did not become ready: {last_error}")


def login(control_port: int, cert: Path) -> tuple[ssl.SSLSocket, bytearray]:
    sock, buffer, greeting = tls_connect(control_port, cert)
    assert reply_code(greeting) == 220, greeting
    assert reply_code(send_command(sock, buffer, "USER gridflux")) == 331
    assert reply_code(send_command(sock, buffer, "PASS gridflux")) == 230
    assert reply_code(send_command(sock, buffer, "TYPE I")) == 200
    return sock, buffer


def open_epsv(sock: ssl.SSLSocket, buffer: bytearray) -> int:
    epsv = send_command(sock, buffer, "EPSV")
    assert reply_code(epsv) == 229, epsv
    return parse_epsv_port(epsv)


def read_data(host: str, port: int) -> str:
    with socket.create_connection((host, port), timeout=5.0) as sock:
        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def run_client(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False, timeout=60)


def upload_cmd(
    upload_bin: Path,
    source: Path,
    port: int,
    transfer_id: str,
    args: argparse.Namespace,
    checksum: str,
    backend: str,
    *,
    resume: bool = False,
    max_chunks: int | None = None,
) -> list[str]:
    command = [
        str(upload_bin),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--input",
        str(source),
        "--connections",
        str(args.connections),
        "--chunk-size",
        str(args.chunk_size),
        "--buffer-size",
        str(args.buffer_size),
        "--checksum",
        checksum,
        "--checksum-backend",
        args.checksum_backend,
        "--transfer-id",
        transfer_id,
        "--file-io-backend",
        backend,
        "--data-tls-mode",
        "required",
        "--tls-ca-file",
        str(args._cert),
    ]
    if resume:
        command.append("--resume")
    if max_chunks is not None:
        command.extend(["--max-chunks", str(max_chunks)])
    return command


def download_cmd(
    download_bin: Path,
    output: Path,
    port: int,
    transfer_id: str,
    args: argparse.Namespace,
    checksum: str,
    backend: str,
    *,
    resume: bool = False,
    max_chunks: int | None = None,
) -> list[str]:
    command = [
        str(download_bin),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--output",
        str(output),
        "--connections",
        str(args.connections),
        "--buffer-size",
        str(args.buffer_size),
        "--checksum",
        checksum,
        "--checksum-backend",
        args.checksum_backend,
        "--transfer-id",
        transfer_id,
        "--file-io-backend",
        backend,
        "--data-tls-mode",
        "required",
        "--tls-ca-file",
        str(args._cert),
    ]
    if resume:
        command.append("--resume")
    if max_chunks is not None:
        command.extend(["--max-chunks", str(max_chunks)])
    return command


def run_stor_resume(
    control_port: int,
    upload_bin: Path,
    source: Path,
    root: Path,
    args: argparse.Namespace,
    checksum: str,
    backend: str,
    name: str,
) -> None:
    expected_sha = sha256_file(source)
    sock, buffer = login(control_port, args._cert)
    with sock:
        data_port = open_epsv(sock, buffer)
        stor = send_command(sock, buffer, f"STOR {name}")
        assert reply_code(stor) == 150, stor
        transfer_id = parse_transfer_id(stor)
        partial = run_client(
            upload_cmd(upload_bin, source, data_port, transfer_id, args, checksum, backend,
                       max_chunks=args.max_chunks)
        )
        if partial.returncode == 0:
            raise RuntimeError("partial STOR unexpectedly succeeded")
        failed = read_reply(sock, buffer)
        assert reply_code(failed) == 550, failed

    dest = root / name
    assert not dest.exists()
    assert (root / f"{name}.gridflux.manifest").exists()
    assert (root / f"{name}.part.{transfer_id}").exists()

    sock, buffer = login(control_port, args._cert)
    with sock:
        rest = send_command(sock, buffer, f"REST GFID:{transfer_id}")
        assert reply_code(rest) == 350, rest
        data_port = open_epsv(sock, buffer)
        stor = send_command(sock, buffer, f"STOR {name}")
        assert reply_code(stor) == 150, stor
        assert parse_transfer_id(stor) == transfer_id
        resumed = run_client(
            upload_cmd(upload_bin, source, data_port, transfer_id, args, checksum, backend,
                       resume=True)
        )
        if resumed.returncode != 0:
            raise RuntimeError(resumed.stdout + resumed.stderr)
        complete = read_reply(sock, buffer)
        assert reply_code(complete) == 226, complete
        assert reply_code(send_command(sock, buffer, "QUIT")) == 221
    if sha256_file(dest) != expected_sha:
        raise RuntimeError(f"STOR resume hash mismatch for {name}")


def run_retr_resume(
    control_port: int,
    download_bin: Path,
    source_name: str,
    output: Path,
    source_sha: str,
    args: argparse.Namespace,
    checksum: str,
    backend: str,
) -> None:
    sock, buffer = login(control_port, args._cert)
    with sock:
        data_port = open_epsv(sock, buffer)
        retr = send_command(sock, buffer, f"RETR {source_name}")
        assert reply_code(retr) == 150, retr
        transfer_id = parse_transfer_id(retr)
        partial = run_client(
            download_cmd(download_bin, output, data_port, transfer_id, args, checksum, backend,
                         max_chunks=args.max_chunks)
        )
        if partial.returncode == 0:
            raise RuntimeError("partial RETR unexpectedly succeeded")
        failed = read_reply(sock, buffer)
        assert reply_code(failed) == 550, failed

    assert not output.exists()
    assert Path(str(output) + f".part.{transfer_id}").exists()
    assert Path(str(output) + ".gridflux.download.manifest").exists()

    sock, buffer = login(control_port, args._cert)
    with sock:
        rest = send_command(sock, buffer, f"REST GFID:{transfer_id}")
        assert reply_code(rest) == 350, rest
        data_port = open_epsv(sock, buffer)
        retr = send_command(sock, buffer, f"RETR {source_name}")
        assert reply_code(retr) == 150, retr
        assert parse_transfer_id(retr) == transfer_id
        resumed = run_client(
            download_cmd(download_bin, output, data_port, transfer_id, args, checksum, backend,
                         resume=True)
        )
        if resumed.returncode != 0:
            raise RuntimeError(resumed.stdout + resumed.stderr)
        complete = read_reply(sock, buffer)
        assert reply_code(complete) == 226, complete
        assert reply_code(send_command(sock, buffer, "QUIT")) == 221
    if sha256_file(output) != source_sha:
        raise RuntimeError(f"RETR resume hash mismatch for {source_name}")


def run_normal_stor_retr(
    control_port: int,
    upload_bin: Path,
    download_bin: Path,
    source: Path,
    output: Path,
    args: argparse.Namespace,
    checksum: str,
    backend: str,
    name: str,
) -> None:
    expected_sha = sha256_file(source)
    sock, buffer = login(control_port, args._cert)
    with sock:
        data_port = open_epsv(sock, buffer)
        stor = send_command(sock, buffer, f"STOR {name}")
        assert reply_code(stor) == 150, stor
        transfer_id = parse_transfer_id(stor)
        upload = run_client(upload_cmd(upload_bin, source, data_port, transfer_id, args, checksum,
                                       backend))
        if upload.returncode != 0:
            raise RuntimeError(upload.stdout + upload.stderr)
        assert reply_code(read_reply(sock, buffer)) == 226

        data_port = open_epsv(sock, buffer)
        retr = send_command(sock, buffer, f"RETR {name}")
        assert reply_code(retr) == 150, retr
        transfer_id = parse_transfer_id(retr)
        download = run_client(
            download_cmd(download_bin, output, data_port, transfer_id, args, checksum, backend)
        )
        if download.returncode != 0:
            raise RuntimeError(download.stdout + download.stderr)
        assert reply_code(read_reply(sock, buffer)) == 226
        assert reply_code(send_command(sock, buffer, "QUIT")) == 221
    if sha256_file(output) != expected_sha:
        raise RuntimeError(f"normal STOR/RETR hash mismatch for {name}")


def verify_plain_listing(control_port: int, cert: Path, expected_name: str) -> None:
    sock, buffer = login(control_port, cert)
    with sock:
        data_port = open_epsv(sock, buffer)
        listing = send_command(sock, buffer, "NLST")
        assert reply_code(listing) == 150, listing
        data = read_data("127.0.0.1", data_port)
        complete = read_reply(sock, buffer)
        assert reply_code(complete) == 226, complete
        if expected_name not in data:
            raise RuntimeError(f"NLST plaintext listing missed {expected_name!r}: {data!r}")
        assert reply_code(send_command(sock, buffer, "QUIT")) == 221


def run_case(args: argparse.Namespace, checksum: str, backend: str) -> None:
    build_dir = Path(args.build_dir)
    server_bin = build_dir / "gridflux-gridftp-server"
    upload_bin = build_dir / "gridflux-file-client"
    download_bin = build_dir / "gridflux-file-download-client"
    for binary in (server_bin, upload_bin, download_bin):
        if not binary.exists():
            raise FileNotFoundError(f"missing GridFlux binary: {binary}")

    with tempfile.TemporaryDirectory(prefix="gridflux-gridftp-data-tls-resume.") as temp_text:
        temp_dir = Path(temp_text)
        cert = temp_dir / "cert.pem"
        key = temp_dir / "key.pem"
        if not generate_cert(cert, key):
            print("openssl CLI unavailable; data TLS resume smoke skipped")
            return
        args._cert = cert

        root = temp_dir / "root"
        root.mkdir()
        source = temp_dir / "source.bin"
        make_file(source, args.bytes)
        retr_source = root / f"retr-source-{checksum}-{backend}.bin"
        shutil.copy2(source, retr_source)
        server_log = temp_dir / "gridftp-data-tls-resume.log"
        event_log = temp_dir / "gridftp-data-tls-resume-events.jsonl"
        control_port = free_port()
        data_port_base = free_port()
        server_cmd = [
            str(server_bin),
            "--host",
            "127.0.0.1",
            "--port",
            str(control_port),
            "--root",
            str(root),
            "--data-port-base",
            str(data_port_base),
            "--connections",
            str(args.connections),
            "--chunk-size",
            str(args.chunk_size),
            "--buffer-size",
            str(args.buffer_size),
            "--checksum",
            checksum,
            "--checksum-backend",
            args.checksum_backend,
            "--file-io-backend",
            backend,
            "--tls-mode",
            "required",
            "--tls-cert-file",
            str(cert),
            "--tls-key-file",
            str(key),
            "--data-tls-mode",
            "required",
            "--event-log",
            str(event_log),
        ]
        with server_log.open("w", encoding="utf-8") as log_handle:
            server = subprocess.Popen(server_cmd, stdout=log_handle, stderr=subprocess.STDOUT)
        try:
            wait_tls_server(control_port, cert)
            normal_output = temp_dir / f"normal-{checksum}-{backend}.bin"
            run_normal_stor_retr(
                control_port,
                upload_bin,
                download_bin,
                source,
                normal_output,
                args,
                checksum,
                backend,
                f"normal-{checksum}-{backend}.bin",
            )
            run_stor_resume(
                control_port,
                upload_bin,
                source,
                root,
                args,
                checksum,
                backend,
                f"stor-resume-{checksum}-{backend}.bin",
            )
            retr_output = temp_dir / f"retr-resume-{checksum}-{backend}.bin"
            run_retr_resume(
                control_port,
                download_bin,
                retr_source.name,
                retr_output,
                sha256_file(retr_source),
                args,
                checksum,
                backend,
            )
            verify_plain_listing(control_port, cert, f"stor-resume-{checksum}-{backend}.bin")
            text = server_log.read_text(encoding="utf-8", errors="replace")
            events = event_log.read_text(encoding="utf-8", errors="replace")
            for forbidden in ("PRIVATE KEY", "BEGIN PRIVATE KEY"):
                if forbidden in text or forbidden in events:
                    raise RuntimeError("data TLS resume smoke leaked private key material")
            parsed_events = [json.loads(line) for line in events.splitlines() if line.strip()]
            if not any(event.get("event") == "stor_failed" for event in parsed_events):
                raise RuntimeError(f"missing partial STOR failure event: {events}")
        except BaseException:
            if server_log.exists():
                print(server_log.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
            if event_log.exists():
                print(event_log.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
            raise
        finally:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


def comma_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run GridFlux data TLS STOR/RETR resume smoke."
    )
    parser.add_argument("--build-dir", default="build")
    parser.add_argument("--bytes", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--connections", type=int, default=1)
    parser.add_argument("--chunk-size", type=int, default=1024 * 1024)
    parser.add_argument("--buffer-size", type=int, default=65536)
    parser.add_argument("--checksums", default="crc32c,none")
    parser.add_argument("--checksum-backend", choices=["auto", "software", "hardware"], default="auto")
    parser.add_argument("--file-io-backends", default="posix")
    parser.add_argument("--max-chunks", type=int, default=1)
    args = parser.parse_args()
    for checksum in comma_list(args.checksums):
        if checksum not in {"crc32c", "none"}:
            raise ValueError(f"unsupported checksum {checksum!r}")
        for backend in comma_list(args.file_io_backends):
            if backend not in {"posix", "io_uring"}:
                raise ValueError(f"unsupported file IO backend {backend!r}")
            run_case(args, checksum, backend)
    print("gridftp data TLS resume smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
