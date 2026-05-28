# Lab GridFlux Performance Snapshot

- Timestamp: `20260522T180406Z`
- Output dir: `tools/perf/results/20260522T180406Z_lab-gridflux-performance`
- Main combined raw CSV: `tools/perf/results/20260522T180406Z_lab-gridflux-performance/main_matrix/gridflux-main-combined.csv`
- Main combined summary CSV: `tools/perf/results/20260522T180406Z_lab-gridflux-performance/main_matrix/gridflux-main-combined-summary.csv`
- Run root: `/mnt/aim_sdc/gridflux-test`; home control: `/home/Su/gridflux-test`; small temp/root side: `/tmp` on `/`.

## Baseline Context

- TCP baseline remains `36-41 Gbps`; RDMA single-direction remains about `59.8 Gbps`; main ConnectX-5 PCIe link is `x8 downgraded`; direct fio storage is below `1 GB/s`.
- This snapshot evaluates Beta behavior under the current lab constraints; it is not a 100G ceiling result.

## Main Matrix

- 10GiB rows: `72`, pass `72`, fail `0`, sha mismatch `0`.
- 20GiB rows: `25`, pass `24`, fail `1`, sha mismatch `0`; stopped after `stor_crc32c_c4_r0` failed with `recv: Resource temporarily unavailable`.

| Size | Direction | Checksum | Best median Gbps | Best Gbps | Best conn | p95 Gbps | Spread % |
|---:|---|---|---:|---:|---:|---:|---:|
| 10GiB | STOR | none | 7.281 | 7.390 | 1 | 7.390 | 4.0 |
| 10GiB | STOR | crc32c | 3.167 | 3.171 | 1 | 3.171 | 0.4 |
| 10GiB | RETR | none | 5.249 | 5.539 | 16 | 5.539 | 5.7 |
| 10GiB | RETR | crc32c | 3.613 | 3.649 | 16 | 3.649 | 9.6 |
| 20GiB | STOR | none | 4.689 | 4.735 | 1 | 4.735 | 1.9 |
| 20GiB | STOR | crc32c | 2.530 | 2.578 | 1 | 2.578 | 3.5 |
| 20GiB | RETR | none | n/a | n/a | n/a | n/a | n/a |
| 20GiB | RETR | crc32c | n/a | n/a | n/a | n/a | n/a |

## Checksum Cost

| Size | Direction | none median Gbps | crc32c median Gbps | Throughput drop |
|---:|---|---:|---:|---:|
| 10GiB | STOR | 7.281 | 3.167 | 56.5% |
| 10GiB | RETR | 5.249 | 3.613 | 31.2% |
| 20GiB | STOR | 4.689 | 2.530 | 46.1% |
| 20GiB | RETR | n/a | n/a | n/a |

## Stage Bottlenecks

| Case | Conn | Median Gbps | Key median stages seconds |
|---|---:|---:|---|
| 10GiB STOR none | 1 | 7.281 | data_receive 2.42; temp_write 2.49; checksum 0.01; manifest_flush 4.62; final_verify 0.00 |
| 10GiB STOR crc32c | 1 | 3.167 | data_receive 2.70; temp_write 2.29; checksum 7.42; manifest_flush 4.61; final_verify 8.52 |
| 10GiB RETR none | 16 | 5.249 | sender_source_read 2.85; sender_network_send 245.78; receiver_download_temp_write 128.33; sender_checksum 0.02; receiver_final_verify 0.00 |
| 10GiB RETR crc32c | 16 | 3.613 | sender_source_read 2.86; sender_network_send 228.16; receiver_download_temp_write 118.25; sender_checksum 23.55; receiver_final_verify 7.44 |

## Directory Control

- `/home/Su/gridflux-test` STOR crc32c c4: `2.459 Gbps`.
- `/home/Su/gridflux-test` RETR crc32c c4: `3.266 Gbps`.

## io_uring Subset

- Safe rerun status: posix pass `12/12`; io_uring pass `0/12`.
- io_uring result: unavailable, errors: `file IO backend unavailable: io_uring `. Do not enable by default.
- First combined attempt filled small `/tmp` after failed io_uring STOR rows; retained under `tools/perf/results/20260522T180406Z_lab-gridflux-performance/iouring` and excluded from conclusions. Safe results are under `tools/perf/results/20260522T180406Z_lab-gridflux-performance/iouring_safe`.

## TLS/Data TLS Subset

| Direction | Conn | off/off median Gbps | required/required median Gbps | Drop |
|---|---:|---:|---:|---:|
| STOR | 4 | 2.712 | 2.312 | 14.7% |
| STOR | 8 | 2.967 | 2.310 | 22.1% |
| RETR | 4 | 3.433 | 3.297 | 4.0% |
| RETR | 8 | 3.263 | 3.357 | -2.9% |

## Final Verify Subset

| Policy | Median Gbps | Best Gbps | Median final_verify seconds |
|---|---:|---:|---:|
| full | 3.527 | 3.571 | 7.66 |
| verified_chunks | 4.906 | 4.925 | 0.00 |

## Conclusions

- Current best 10GiB Beta numbers under this lab baseline: STOR none about `7.28 Gbps` median at conn=1; STOR crc32c about `3.16 Gbps` median at conn=1; RETR none about `5.25 Gbps` median at conn=16; RETR crc32c about `3.61 Gbps` median at conn=16.
- 20GiB STOR none drops to about `4.69 Gbps` median at conn=1; 20GiB crc32c was stopped after a c4 client-side `recv: Resource temporarily unavailable` failure, with c1 median about `2.53 Gbps` and c2 median about `2.12 Gbps` before the stop.
- Checksum/final verify cost is material. `verified_chunks` improved RETR c4 crc32c from about `3.53 Gbps` median to about `4.91 Gbps` median in the opt-in subset, but default remains `full`.
- io_uring is not available in this build/runtime path (`file IO backend unavailable: io_uring`), so it has no benefit and should not be default-enabled.
- TLS/data TLS passed. STOR saw about `15-22%` median drop; RETR saw small/no clear drop under the current bottlenecks.
- Do not enter 100GiB repeat yet: small root space is only about `65G`, network/RDMA/storage baselines are below 100G requirements, and 20GiB crc32c already exposed a client-side control receive failure.

## Cleanup

- Cleanup log: `tools/perf/results/20260522T180406Z_lab-gridflux-performance/cleanup_check.txt`
- Final cleanup removed run roots and `/tmp/gridflux_phase4a_*`; residual GridFlux/iperf/RDMA perftest processes were empty on both hosts.

## Additional CSVs

- `tools/perf/results/20260522T180406Z_lab-gridflux-performance/home_control/home_control-combined.csv`
- `tools/perf/results/20260522T180406Z_lab-gridflux-performance/home_control/home_control-combined-summary.csv`
- `tools/perf/results/20260522T180406Z_lab-gridflux-performance/iouring_safe/iouring_safe-combined.csv`
- `tools/perf/results/20260522T180406Z_lab-gridflux-performance/iouring_safe/iouring_safe-combined-summary.csv`
- `tools/perf/results/20260522T180406Z_lab-gridflux-performance/tls_safe/tls_safe-combined.csv`
- `tools/perf/results/20260522T180406Z_lab-gridflux-performance/tls_safe/tls_safe-combined-summary.csv`
- `tools/perf/results/20260522T180406Z_lab-gridflux-performance/final_verify/final_verify-combined.csv`
- `tools/perf/results/20260522T180406Z_lab-gridflux-performance/final_verify/final_verify-combined-summary.csv`
