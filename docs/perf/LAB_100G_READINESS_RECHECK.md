# Lab 100G Readiness Recheck

Date: 2026-05-28

## Decision

GridFlux remains Beta-ready under the conservative default path, but the lab
environment is not 100G-ready.

- 20GiB repeat expansion: not recommended for 100G readiness work yet.
- 100GiB repeat: no.
- 100G-ready claim: no.
- Default GridFlux strategy: unchanged.
- `verified_chunks`: still opt-in only.

The blockers are machine/baseline blockers first: TCP below the 80Gbps bar,
single-direction RDMA below the 80Gbps bar, direct storage below even 2GB/s,
main NIC PCIe width downgraded, and small-side space still unsuitable for
accumulated 100GiB output.

## Evidence Paths

| Artifact | Path |
|---|---|
| Recheck result directory | `tools/perf/results/20260528T013912Z_lab-100g-readiness-recheck/` |
| Redacted inventory | `tools/perf/results/20260528T013912Z_lab-100g-readiness-recheck/inventory/` |
| TCP summary | `tools/perf/results/20260528T013912Z_lab-100g-readiness-recheck/tcp_iperf_summary.csv` |
| RDMA summary | `tools/perf/results/20260528T013912Z_lab-100g-readiness-recheck/rdma_perftest_summary.csv` |
| Storage summary | `tools/perf/results/20260528T013912Z_lab-100g-readiness-recheck/storage_fio_summary.csv` |
| Decision JSON | `tools/perf/results/20260528T013912Z_lab-100g-readiness-recheck/readiness_summary.json` |
| Final cleanup | `tools/perf/results/20260528T013912Z_lab-100g-readiness-recheck/final_cleanup_check.txt` |

## Hardware / System Recheck

| Area | main | small | Readiness interpretation |
|---|---|---|---|
| Kernel | `6.8.0-111-generic` | `5.15.0-179-generic` | Mixed kernels are acceptable for testing but should be noted before tuning. |
| 100G link | `100000Mb/s`, link detected | `100000Mb/s`, link detected | Physical link is up. |
| Driver | `mlx5_core`, firmware `16.35.8002` | `mlx5_core`, firmware `16.35.8002` | Driver/firmware family matches. |
| MTU | `9000` | `9000` | MTU mismatch is not the blocker. |
| NIC NUMA node | `1` | `1` | NUMA placement still matters for CPU/IRQ tuning. |
| PCIe link | max x16, current x8 downgraded | max x16, current x16 ok | main PCIe width remains a likely RDMA/TCP ceiling. |
| RDMA port | active, active MTU `4096` | active, active MTU `4096` | RoCE verbs are usable. |

The raw inventory files redact address-like fields and do not include
credentials.

## Network Baseline

`iperf3`, 30 seconds per case, parallel `1/4/8/16`:

| Direction | P1 | P4 | P8 | P16 | Best | Readiness |
|---|---:|---:|---:|---:|---:|---|
| main -> small | 27.712 | 23.433 | 23.413 | 22.584 | 27.712 Gbps | fail |
| small -> main | 32.407 | 34.295 | 34.110 | 24.434 | 34.295 Gbps | fail |

Observations:

- TCP is below the `80Gbps+` readiness bar in both directions.
- Retransmits were `0` in the retained summary, so this run points more toward
  CPU copy/stack/queue/NUMA/socket tuning than packet loss.
- CPU utilization is high in the iperf summaries, especially on the receiving
  side in several cases.

## RDMA Baseline

Perftest used 1MiB messages, QP=1, 10 second duration, RoCE GID index `3`:

| Test | Direction | Mode | Gbps | Readiness |
|---|---|---|---:|---|
| `ib_write_bw` | small -> main | single direction | 59.820 | fail |
| `ib_write_bw` | main -> small | single direction | 57.470 | fail |
| `ib_read_bw` | small -> main | single direction | 57.620 | fail |
| `ib_read_bw` | main -> small | single direction | 59.810 | fail |
| `ib_write_bw` | small -> main | bidirectional aggregate | 111.960 | diagnostic only |

Single-direction RDMA remains around `57-60Gbps`, consistent with the prior
diagnosis. Bidirectional aggregate is healthy enough to show that RoCE works,
but it does not remove the single-direction readiness blocker.

## Storage Baseline

`fio`, direct I/O, `ioengine=libaio`, `iodepth=32`, `numjobs=1`, 4GiB per case,
block sizes `1MiB` and `4MiB`:

| Role | Path | Best write | Best read | Best mixed rw | Readiness |
|---|---|---:|---:|---:|---|
| main | `/mnt/aim_sdc/gridflux-test` | 0.497 GB/s | 0.525 GB/s | 0.510 GB/s | fail |
| main | `/mnt/aim_sdd/gridflux-test` | 0.497 GB/s | 0.524 GB/s | 0.507 GB/s | fail |
| small | `/home/Su/gridflux-test` | 0.564 GB/s | 0.574 GB/s | 0.848 GB/s | fail |
| small | `/tmp/gridflux-test` | 0.474 GB/s | 0.489 GB/s | 0.836 GB/s | fail |

The 100G file-transfer target needs roughly `12.5GB/s` of sustained storage
bandwidth. This recheck is not close, and it is also below a conservative
`2GB/s` threshold for expanding 100G-readiness validation. A pmem-like mount was
present but not writable by the test user, so it was skipped without sudo
writes.

## GridFlux Default-Path Sanity

No new GridFlux quick/focused run was started in this recheck because the
baseline blockers were already decisive. The current correctness evidence is
the Beta RC gate:

| Evidence | Result | Path |
|---|---|---|
| Beta RC release profile | `32/32 pass`, `sha_mismatch=0` | `tools/perf/results/20260527T174327Z_lab-gridflux-profile-release/` |
| Beta RC resume/fallback safety | `4/4 pass`, fallback effective policy `full` | `tools/perf/results/20260527T183315Z_lab-beta-rc-gate/` |

This keeps the distinction clean: GridFlux default correctness is green, but
the lab machine/storage baseline does not justify larger 100G-readiness
matrices.

## Expansion Decision

| Question | Answer | Reason |
|---|---|---|
| Enter 20GiB repeat for 100G readiness? | No | TCP/RDMA/storage are below expansion bars. |
| Enter 100GiB repeat? | No | Storage throughput and small-side free space are not safe for accumulated 100GiB output. |
| Claim 100G-ready? | No | Network, RDMA, PCIe, and storage evidence do not support it. |
| Optimize GridFlux data path next? | Not yet | Fix or explicitly accept the machine baseline before attributing more performance to GridFlux. |

## Next Actions

1. Hardware/ops: fix or explain main NIC PCIe x8 downgrade, then rerun RDMA
   single-direction and TCP.
2. Network: inspect RSS queue spread, IRQ affinity, NUMA binding, socket
   buffers, congestion control, and CPU copy overhead with before/after logs.
3. Storage: identify a real local NVMe/RAID/pmem target that can approach at
   least `8-12GB/s`, or document storage as the accepted file-transfer ceiling.
4. GridFlux: keep Beta defaults unchanged. Revisit GridFlux performance only
   after the machine baseline is lifted or explicitly accepted.
