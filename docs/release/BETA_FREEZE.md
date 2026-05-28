# GridFlux Beta Freeze

- Timestamp: `2026-05-27T18:38:05Z`
- Result: `pass`
- Scope: Lab Beta RC freeze for the current conservative GridFlux Beta
  defaults.
- Beta-ready: `yes`, for the documented Beta feature/default set.
- 100G-ready: `no`; the lab machine baseline is still below a tuned 100G
  ceiling.
- Freeze closeout: complete. No protocol/default changes are required for this
  Beta scope.

## Default Strategy

- `auth-mode=anonymous`
- `tls-mode=off`
- `data-tls-mode=off`
- `file_io_backend=posix`
- `final_verify_policy=full`
- `manifest_flush_policy=every_n_chunks`
- `manifest_flush_interval_chunks=256`
- `preallocate=off`
- `posix_write_strategy=auto`
- `receiver_write_profile=default`
- `receiver_write_yield_policy=none`

The following remain opt-in only:

- `final_verify_policy=verified_chunks`
- `file_io_backend=io_uring`
- TLS/data TLS
- heavy profiles and 100GiB repeat

## Freeze Checks

| Check | Result | Evidence |
|---|---|---|
| main Debug build | pass | local `build/` |
| small Debug build | pass | `gridflux-lab-small:/home/Su/projects/GridFlux/build/` |
| main focused CTest | `62/62` pass | terminal output from RC gate |
| small focused CTest | `62/62` pass | terminal output from RC gate |
| release-style profile | `32/32` pass, `sha_mismatch=0` | `tools/perf/results/20260527T174327Z_lab-gridflux-profile-release/` |
| resume safety | STOR/RETR resume `2/2` pass | `tools/perf/results/20260527T183315Z_lab-beta-rc-gate/safety_resume_full/` |
| fallback safety | `checksum=none + verified_chunks` fell back to effective `full`, `2/2` pass | `tools/perf/results/20260527T183315Z_lab-beta-rc-gate/safety_none_verified_chunks_fallback/` |
| combined RC analysis | `row_count=36`, `fail_count=0`, `sha_mismatch=0`, `gate_pass=true` | `tools/perf/results/20260527T183315Z_lab-beta-rc-gate/20260527T183315Z_lab-beta-rc-gate-all.json` |
| final verify gate | live gate `20` combined rows, `fail_count=0`, `sha_mismatch=0`, fallback safety passed | `tools/perf/results/20260527T150541Z_lab-final-verify-gate/` |
| CRC32C cost review | preliminary `6/6` pass; no checksum default change | `tools/perf/results/20260528T165246Z_lab-checksum-cost-review/` |
| manifest flush stability | interval `256` promoted to default after stability evidence; `16` remains explicit A/B | `tools/perf/results/20260524T093758Z_lab-beta2d-manifest-flush-stability/` |
| 100G readiness recheck | not 100G-ready; TCP/RDMA/storage/PCIe remain blockers | `tools/perf/results/20260528T013912Z_lab-100g-readiness-recheck/` |
| cleanup | run-root removed; no main/small residual transfer, iperf, or RDMA test processes | `tools/perf/results/20260527T183315Z_lab-beta-rc-gate/final_cleanup_check.txt` |

## Guardrails

- This freeze does not certify 100G readiness.
- The current lab baseline remains constrained by TCP/RDMA/storage and the main
  NIC PCIe x8 downgrade; see
  [LAB_BOTTLENECK_REGISTER.md](../perf/LAB_BOTTLENECK_REGISTER.md).
- Manifest flush is closed for Beta; it is not the next primary bottleneck.
- Full final verify stays default because it is the conservative safety path.
- `verified_chunks` is retained only as an opt-in comparison path.
- CRC32C, especially STOR-side checksum work after final verify is separated,
  is only a future opt-in prototype candidate.
- No manifest v3, binary manifest, framed protocol rewrite, checksum pipeline,
  raw FTP, RDMA data plane, QUIC, or FEC work is part of this freeze.

## Decision

The current Lab Beta can enter Beta freeze under the documented constraints.
The next work should be chosen explicitly between:

- A. `100G readiness / baseline lift`: fix or explain PCIe x8, lift TCP/RDMA,
  find real high-throughput storage, and retest before any 20GiB/100GiB
  readiness expansion.
- B. `CRC32C opt-in prototype`: prototype threaded/pipelined checksum work as
  opt-in only, without changing default `full` final verify or default
  checksum behavior.

A 100G-ready claim requires new machine baseline evidence first.
