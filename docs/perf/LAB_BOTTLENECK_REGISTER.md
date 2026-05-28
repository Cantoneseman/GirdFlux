# Lab Bottleneck Register

Date: 2026-05-28

This register separates lab-machine limits from GridFlux project limits before
the Beta closeout gates continue. It uses retained evidence only; no heavy or
100GiB run was started for this update.

## Current Decision

Do not claim 100G readiness yet, and do not start 100GiB repeat runs until the
machine baseline is lifted or clearly accepted as the test ceiling.

The 2026-05-28 recheck confirms the same direction: TCP, single-direction RDMA,
PCIe width, storage bandwidth, and small-side space are machine blockers before
any larger GridFlux readiness matrix. Manifest flush is no longer the primary
shortfall: Beta 2E promoted `manifest_flush_interval_chunks=256`, while `16`
remains an explicit A/B value.

## Machine Bottlenecks

| Area | Current Evidence | Impact | Next Action |
|---|---|---|---|
| TCP baseline | 2026-05-28 recheck: best `27.712 Gbps` main->small and `34.295 Gbps` small->main; retransmits were `0`, while CPU utilization was high. | TCP is below an `80Gbps+` readiness bar, so GridFlux file throughput cannot be interpreted as a tuned 100G ceiling. | Review RSS queue spread, IRQ affinity, socket buffers, NUMA binding, congestion control, and CPU copy overhead before larger GridFlux matrices. |
| RDMA baseline | 2026-05-28 recheck: single-direction read/write remains `57.470-59.820 Gbps`; bidirectional write aggregate is `111.960 Gbps`. | RoCE works, but single-direction bandwidth is capped well below line rate. | Treat hardware/PCIe as the first suspect before RDMA protocol or GridFlux work. |
| PCIe width | Main ConnectX-5: `LnkCap x16`, `LnkSta x8 (downgraded)`; small ConnectX-5: `x16 ok`. | Main NIC PCIe width can plausibly cap single-direction RDMA near the observed `60 Gbps`. | Move/reseat/check slot/BIOS bifurcation if hardware access is available; rerun RDMA and TCP after correction. |
| MTU / RDMA state | Both 100G interfaces are `100000Mb/s`, link detected, MTU `9000`, NUMA node `1`; RoCE target devices are `ACTIVE/LINK_UP`, active MTU `4096`. | Link setup is basically healthy; MTU mismatch is not the current blocker. | Keep as baseline guard; only change after recording before/after. |
| Storage bandwidth | 2026-05-28 recheck: main best direct I/O about `0.525 GB/s`; small best direct I/O about `0.848 GB/s` mixed rw, with read/write near `0.5-0.6 GB/s`. | Direct storage is far below the `~12.5 GB/s` needed to sustain 100G file-to-file transfers and below a conservative `2GB/s` expansion bar. | Identify whether faster local NVMe/RAID/pmem paths exist, or accept storage as the current file-transfer ceiling. |
| Disk space | Latest checks still show main data mounts with ample space, but small root/tmp remains the practical output side and is not safe for accumulated 100GiB repeat. | Small side is not safe for accumulated 100GiB repeat output; 20GiB must remain batched and cleaned if used at all. | Keep large run roots on main data mounts and continue per-case cleanup on small. |
| NUMA / IRQ | Target NICs are NUMA node `1`; prior TCP runs show high CPU utilization. Detailed IRQ/RSS tuning is not closed. | CPU placement and IRQ concentration may still limit TCP and GridFlux scaling. | Stage D should record IRQ queue distribution and test reversible affinity/socket-buffer changes. |

## Project Bottlenecks

| Area | Current Evidence | Status | Next Action |
|---|---|---|---|
| Manifest flush | Beta 2C/2D showed interval `256` cuts manifest flush cost by about `92-95%`; Beta 2E quick `4/4 pass`, `sha_mismatch=0`. | Closed for Beta default: `manifest_flush_interval_chunks=256`. | Keep `16` only for explicit A/B and regression checks. |
| Full final verify | Stage B live gate passed with `row_count=20`, `fail_count=0`, `sha_mismatch=0`; crc32c/full spent about `7.5-8.5s` in 10GiB final verify while `verified_chunks` removed that reread. | Known project cost, but default `final_verify_policy=full` remains the safety baseline. | Keep `full` default through Beta; consider `verified_chunks` only as an explicit opt-in after safety review. |
| `verified_chunks` policy | Stage B fallback safety passed: `checksum=none + verified_chunks` falls back to effective `full`; RC gate fallback safety also passed. | Safe opt-in evidence exists; not a default. | Keep opt-in; do not use it to mask machine/storage baseline issues. |
| Online CRC32C | Stage C preliminary review passed `6/6`; STOR crc32c/verified_chunks still trailed none/full by about `57.5%`, while RETR crc32c/verified_chunks was roughly tied with none/full in that sample. | Open performance cost; partly mixed with final verify and storage limits. | Consider a separate opt-in checksum pipeline prototype only after the machine baseline is fixed or accepted. |
| GridFlux data plane | Beta RC release profile `32/32 pass`, resume/fallback safety `4/4 pass`, `sha_mismatch=0`; no new GridFlux profile was run in the 100G recheck because machine blockers were decisive. | Correctness is clean, performance is constrained by both project costs and lab baseline. | Do not optimize core C++ data plane until machine baseline and final verify/checksum costs are separated. |
| io_uring | Lab snapshot marked io_uring unavailable for that run; earlier Phase 4G/4I proved correctness but no stable default benefit. | Opt-in prototype only. | Do not default-enable; revisit only with a stronger storage baseline. |
| TLS/data TLS | 10GiB subset passed; STOR saw about `15-22%` median drop, RETR had small/no clear drop under current bottlenecks. | Functional opt-in; not default. | Keep out of Beta closeout unless release security scope changes. |

## Evidence Paths

| Topic | Path |
|---|---|
| Lab baseline diagnosis | `tools/perf/results/20260522T150508Z_lab-baseline-diag/` |
| Lab GridFlux performance snapshot | `tools/perf/results/20260522T180406Z_lab-gridflux-performance/` |
| Beta 2B checksum/final verify | `tools/perf/results/20260523T065043Z_lab-beta2b-checksum-final-verify/` |
| Beta 2C manifest flush A/B | `tools/perf/results/20260524T075209Z_lab-gridflux-profile-manifest-flush/`, `tools/perf/results/20260524T082718Z_lab-gridflux-profile-manifest-flush-20gib/` |
| Beta 2D stability | `tools/perf/results/20260524T093758Z_lab-beta2d-manifest-flush-stability/` |
| Beta 2E default 256 quick | `tools/perf/results/20260524T144503Z_lab-gridflux-profile-quick/` |
| 2026-05-28 100G readiness recheck | `tools/perf/results/20260528T013912Z_lab-100g-readiness-recheck/` |

## Gate Order

1. Stage B: final verify safety/performance gate; keep default `full`.
2. Stage C: CRC32C cost review after final verify is separated.
3. Stage D: machine baseline lift; keep GridFlux conclusions distinct from NIC/storage tuning.
4. Stage E/F: Beta RC/freeze is green for Beta scope, but 100G readiness stays blocked until Stage D improves.

## Light Check From 2026-05-27

- Main target NIC `enp177s0np0`: UP, `192.168.100.2/30`, MTU `9000`, NUMA node `1`, `100000Mb/s`, link detected.
- Small target NIC `enp130s0np0`: UP, `192.168.100.1/30`, MTU `9000`, NUMA node `1`, `100000Mb/s`, link detected.
- Main PCIe check still reports `LnkSta Width x8 (downgraded)` for the target ConnectX-5.
- Small PCIe check reports `LnkSta Width x16 (ok)`.
- No residual `gridflux-gridftp-server`, `gridflux-file-*`, `iperf3`, `ib_write_bw`, or `ib_read_bw` processes were found on either host.
