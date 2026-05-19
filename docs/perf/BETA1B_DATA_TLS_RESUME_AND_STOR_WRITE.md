# Beta 1B Data TLS Resume Fix And STOR Write Diagnosis

Generated: 2026-05-19

## Summary

Beta 1B-0/1B-1 fixed the correctness blocker found during Beta 1A-1:
`STOR resume + tls=required + data_tls=required` could close the control
connection after an intentional partial upload instead of returning the expected
`550` and allowing `REST GFID` resume. Defaults remain unchanged:
anonymous auth, TLS off, data TLS off, POSIX backend, full final verify,
every-n-chunks manifest flush, preallocate off, and POSIX write strategy auto.

The fix is intentionally narrow. STOR/RETR frames, checksum, manifest, resume,
and final verify semantics are unchanged. LIST/NLST listing data remains
plaintext by Phase 6D design and is not part of data TLS.

## Historical Blocker

Historical evidence:

- `tools/perf/results/20260519T080840Z_gridftp-private-matrix-full.csv`
- failing surface: `direction=stor-resume`, `tls_mode=required`,
  `data_tls_mode=required`
- symptom: client saw `control connection closed` instead of a recoverable
  transfer failure reply.

Root cause: the data TLS path could receive `SIGPIPE` from OpenSSL writes or
shutdown handling after the client intentionally closed a TLS data connection
for `--max-chunks` resume injection. Raw socket paths already avoid SIGPIPE via
`MSG_NOSIGNAL`; the TLS path needed the same process-level protection. When
SIGPIPE terminated the server process, the control session could not convert
the incomplete data-channel transfer into a normal `550` reply.

Fix: `src/core/io/tls_socket.cpp` now ignores `SIGPIPE` during OpenSSL
initialization. TLS data-channel failures are then handled as ordinary transfer
failures and the control session remains alive for `REST GFID` resume.

## Focused Validation

Focused smoke:

```bash
python3 tools/test/run_gridftp_data_tls_resume_smoke.py --build-dir build-io-uring-real --file-io-backends posix,io_uring
```

Result: passed. The smoke covers ordinary STOR/RETR over data TLS, STOR resume
over control TLS + data TLS, RETR resume over control TLS + data TLS, checksum
`crc32c|none`, backend `posix|io_uring`, and LIST/NLST compatibility with the
existing plaintext listing data channel.

Focused private matrix:

- raw CSV: `tools/perf/results/20260519T101941Z_gridftp-private-matrix-smoke.csv`
- summary CSV: `tools/perf/results/20260519T101941Z_gridftp-private-matrix-smoke-summary.csv`
- cases: 96
- failures: 0
- hash mismatches: 0

Coverage:

- directions: `stor-resume`, `retr-resume`
- TLS/data TLS: `off/off`, `required/off`, `required/required`
- checksum: `crc32c`, `none`
- backend: `posix`, `io_uring`
- connections: `1,2,4,8`
- bytes: 1 GiB

Median throughput from the focused matrix:

| direction | TLS | data TLS | cases | median Gbps | min Gbps | max Gbps |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| STOR resume | off | off | 16 | 1.303 | 0.471 | 1.503 |
| STOR resume | required | off | 16 | 1.376 | 0.959 | 1.472 |
| STOR resume | required | required | 16 | 1.367 | 1.052 | 1.505 |
| RETR resume | off | off | 16 | 1.047 | 0.984 | 2.409 |
| RETR resume | required | off | 16 | 1.041 | 0.966 | 1.175 |
| RETR resume | required | required | 16 | 1.045 | 0.985 | 2.430 |

This matrix is a correctness gate, not a new default-policy performance claim.
The single-run spread reinforces the Beta 1A/Beta 4L conclusion that this
environment needs repeat medians before default tuning decisions.

## STOR Write / Writeback Diagnosis

No new C++ diagnostic fields were required in Beta 1B. Existing logs and CSV
already expose the receiver write path:

- `stage_recv_seconds` / `data_receive_seconds`
- `stage_write_seconds` / `temp_write_seconds`
- `stage_manifest_flush_seconds`
- `stage_final_verify_seconds`
- `stage_rename_commit_seconds`
- `write_syscall_count`
- `write_avg_bytes_per_syscall`
- `file_io_wait_seconds`
- per-case environment sidecars for Dirty/Writeback/Cached, `df`, and optional
  `iostat`

In the focused matrix, STOR resume median receiver temp write time was about
5.05s while receiver data receive time was about 0.096s. Manifest flush median
was about 0.56s, final verify median about 0.11s, and rename/commit median about
0.016s. That keeps the Beta 1A diagnosis intact: the immediate STOR bottleneck
is receiver temp write/writeback, not CRC32C hardware or control/data TLS
handshake correctness.

For RETR resume, receiver download temp write and sender network send remain
coupled. Median receiver write and sender send stage sums can exceed wall clock
because they are accumulated across connections; use them as stage pressure
signals, not as wall-clock percentages.

## Gate Decision

- The data TLS resume correctness blocker is fixed.
- Focused STOR/RETR resume matrix passed without hash mismatch.
- Do not run 4 GiB repeat=3 full heavy until the next optimization question is
  scoped.
- Beta 1B should continue with STOR receiver write/writeback diagnosis and
  storage-path experiments, using existing write syscall and environment
  sidecar fields.
- Defaults remain unchanged; `io_uring`, data TLS, preallocate full,
  `verified_chunks`, final-only manifest flush, commit fsync, and coalesced
  write remain opt-in.
