# Lab Beta RC Gate

Date: 2026-05-27

## Decision

Lab Beta RC gate passed for the current conservative lab Beta scope.

- Beta-ready: yes, for the documented GridFlux Beta feature/default set.
- 100G-ready: no. The lab machine baseline remains below a tuned 100G ceiling.
- Default policy is unchanged.
- `verified_chunks` remains opt-in only.
- Heavy and 100GiB repeat were not run for this gate.

## Default Strategy Under Test

| Setting | Value |
|---|---|
| auth mode | anonymous |
| control TLS | off |
| data TLS | off |
| file I/O backend | posix |
| final verify policy | full |
| manifest flush policy | every_n_chunks |
| manifest flush interval | 256 chunks |
| preallocate | off |
| POSIX write strategy | auto |
| receiver write profile | default |
| receiver write yield | none |
| `verified_chunks` | opt-in only |

## Evidence

| Item | Result | Path |
|---|---|---|
| Release profile dry-run | `release`, 10GiB, repeat=2, 32 rows; no explicit manifest interval flag in runner commands | command output retained in terminal session |
| main build | Debug build passed | local `build/` |
| small build | Debug build passed | `gridflux-lab-small:/home/Su/projects/GridFlux/build/` |
| main focused CTest | `62/62` passed | local CTest output |
| small focused CTest | `62/62` passed | remote CTest output |
| Release-style profile | `32/32` passed, `sha_mismatch=0` | `tools/perf/results/20260527T174327Z_lab-gridflux-profile-release/` |
| Resume safety | 1GiB STOR/RETR resume `2/2` passed | `tools/perf/results/20260527T183315Z_lab-beta-rc-gate/safety_resume_full/` |
| Fallback safety | `checksum=none + verified_chunks` STOR/RETR `2/2` passed; effective policy fell back to `full` | `tools/perf/results/20260527T183315Z_lab-beta-rc-gate/safety_none_verified_chunks_fallback/` |
| Combined RC analysis | `row_count=36`, `fail_count=0`, `sha_mismatch=0`, `fallback_row_count=2`, `gate_pass=true` | `tools/perf/results/20260527T183315Z_lab-beta-rc-gate/20260527T183315Z_lab-beta-rc-gate-all.json` |
| Cleanup | run-root removed; no main/small residual transfer, iperf, or RDMA test processes | `tools/perf/results/20260527T183315Z_lab-beta-rc-gate/final_cleanup_check.txt` |

## Release Profile Key Data

10GiB, repeat=2, median throughput:

| Direction | Checksum | Final verify | Connections | Median Gbps | Median final verify s | Median manifest flush s |
|---|---|---|---:|---:|---:|---:|
| STOR | none | full | 1 | 14.003 | 0.000 | 0.117 |
| STOR | crc32c | full | 1 | 3.676 | 8.547 | 0.118 |
| STOR | none | full | 4 | 12.008 | 0.000 | 0.195 |
| STOR | crc32c | full | 4 | 3.576 | 8.506 | 0.213 |
| STOR | none | full | 16 | 10.493 | 0.000 | 0.206 |
| STOR | crc32c | full | 16 | 3.739 | 8.487 | 0.191 |
| STOR | crc32c | verified_chunks | 4 | 5.128 | 0.000 | 0.222 |
| STOR | crc32c | verified_chunks | 16 | 5.402 | 0.000 | 0.199 |
| RETR | none | full | 1 | 7.484 | 0.000 | 0.241 |
| RETR | crc32c | full | 1 | 3.390 | 7.896 | 0.268 |
| RETR | none | full | 4 | 10.893 | 0.000 | 0.344 |
| RETR | crc32c | full | 4 | 5.523 | 7.885 | 0.350 |
| RETR | none | full | 16 | 11.352 | 0.000 | 0.317 |
| RETR | crc32c | full | 16 | 5.754 | 7.532 | 0.277 |
| RETR | crc32c | verified_chunks | 4 | 11.470 | 0.000 | 0.359 |
| RETR | crc32c | verified_chunks | 16 | 11.475 | 0.000 | 0.417 |

## Interpretation

- The conservative default path is stable for the release-style gate:
  default `full` final verify passed across STOR/RETR, checksum `none/crc32c`,
  and connections `1/4/16`.
- `verified_chunks` remains a correct opt-in comparison path for crc32c rows.
  It was not promoted to default.
- `checksum=none + verified_chunks` safely falls back to effective `full`.
- Full final verify remains the main default-path performance cost for crc32c
  transfers: 10GiB crc32c/full rows spend about `7.5-8.5s` in final verify.
- Manifest flush is no longer the dominant cost in this gate; median values are
  about `0.12-0.42s` with the default interval `256`.
- These results do not certify 100G readiness. TCP/RDMA/storage bottlenecks are
  separately tracked in [LAB_BOTTLENECK_REGISTER.md](LAB_BOTTLENECK_REGISTER.md).

## What Was Not Run

- No heavy profile.
- No 100GiB repeat.
- No raw FTP, RDMA data plane, QUIC, FEC, manifest v3, binary manifest, or
  protocol rewrite work.
- No default `verified_chunks`, no default `io_uring`, and no checksum pipeline
  change.

## Next Step

Proceed to Beta freeze documentation using this RC evidence. After freeze,
separate follow-up work should focus on either an opt-in CRC32C pipeline
prototype or a reversible lab machine baseline lift. 100G readiness needs
machine baseline evidence first.
