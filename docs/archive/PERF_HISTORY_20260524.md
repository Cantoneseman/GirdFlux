# Performance History Archive

Date: 2026-05-24

This file keeps the historical performance-test map that was removed from the
front of `docs/perf/README.md` during Lab Beta 2F slimming. The live README now
focuses on current lab profiles, defaults, and canonical result paths.

## Historical Tool Families

| Area | Tooling | Notes |
|---|---|---|
| Memory/TCP loopback | `run_loopback_matrix.py`, `run_private_once.sh` | Early memory-to-memory TCP sink baselines |
| File loopback/private | `run_file_loopback_matrix.py`, `run_file_private_once.sh` | Early file transfer baseline tooling |
| GridFTP-like private matrix | `run_gridftp_private_matrix.py` | Canonical STOR/RETR framed transfer matrix; still used by the lab wrapper |
| CRC32C backend checks | checksum `none` / `crc32c`, backend `auto` / `software` / `hardware` | Hardware backend selected on SSE4.2-capable x86 when available |
| io_uring experiments | Phase 4F/4G/4H helpers | Remain opt-in; POSIX is still the default backend |
| Storage/writeback attribution | `run_beta1b_storage_system_probe.py`, `run_cloud_disk_bottleneck_proof.py` | Used to attribute cloud/lab storage bottlenecks |
| Native FTP/GridFTP comparisons | baseline FTP/GridFTP and GridFTP-vs-GridFlux scripts | Historical comparison tools, not current release gates |
| Tree transfer performance | tree upload/download matrix helpers | Directory transfer still reuses single-file STOR/RETR semantics |
| Event logs | `--event-log <path>` JSONL | Used for case-level diagnostics; must not include secrets |

## Historical Guidance

- Cloud Beta results are environment-specific and must not be used as a 100G
  upper-bound claim.
- The current lab baseline showed network/RDMA/storage limits before GridFlux
  data-plane optimization; performance claims should cite that context.
- The full Beta 2B matrix is retained as evidence, but routine work should use
  the slim lab profiles unless a heavy gate is explicitly requested.
- Public reports must not contain private credentials, private keys, tokens, or
  private workspace files.

Canonical retained result paths are listed in
[`docs/perf/RESULTS_INDEX.md`](../perf/RESULTS_INDEX.md).
