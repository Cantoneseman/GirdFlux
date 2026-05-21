# Beta 1B Storage/System Writeback Attribution

Generated: 2026-05-20T09:04:15Z

## Executive Summary

Beta 1B-5 attributes the STOR receiver write/writeback bottleneck against native GridFlux storage bench, optional fio, mount metadata, Linux Dirty/Writeback/Cached samples, and an aligned STOR matrix. Defaults remain unchanged and receiver writeback bounded/dirty_poll stays opt-in only.

- Native storage write median/best: `26.035 / 29.912 Gbps`.
- Native storage read median/best: `74.059 / 77.879 Gbps`.
- GridFlux STOR e2e median/best: `9.921 / 17.128 Gbps`.
- GridFlux STOR temp-write median: `20.940 Gbps`; temp-write wall share median `51.7%`.
- Dirty/Writeback correlation: Pearson r `0.471` across `31` paired rows.

Beta 1C follow-up: RETR stability is now reviewed with a focused `1GiB repeat=3` matrix on the same two cloud servers. The next report is `docs/perf/BETA1C_RETR_STABILITY.md`; no default policy or receiver writeback behavior changes are implied by this STOR attribution result.

## Inputs

- `/root/projects/GridFlux/tools/perf/results/20260520T090359Z_storage-system-probe.csv`
- `/root/projects/GridFlux/tools/perf/results/20260520T090359Z_storage-system-probe-summary.csv`
- `tools/perf/results/20260520T090401Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T090412Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T090401Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260520T090412Z_gridftp-private-matrix-smoke-summary.csv`

## Result Counts

- Probe raw rows: `24`; pass `24`, fail `0`, unavailable `0`.
- Probe summary rows: `12`.
- STOR raw rows: `7`; pass `7`, fail `0`.
- STOR summary rows: `7`; grouped failures `0`.

## Native Storage vs GridFlux STOR

| metric | value | note |
| --- | --- | --- |
| native storage write median | 26.035 | gridflux-storage-bench POSIX write |
| native storage write best | 29.912 | best POSIX write summary row |
| native storage read median | 74.059 | gridflux-storage-bench POSIX read |
| native storage read best | 77.879 | best POSIX read summary row |
| GridFlux STOR e2e median | 9.921 | aligned STOR summary rows |
| GridFlux STOR e2e best | 17.128 | aligned STOR summary rows |
| GridFlux STOR temp-write median | 20.940 | bytes / receiver temp-write seconds |
| Temp-write wall share median | 51.7% | receiver temp-write / elapsed |
| temp-write vs native write | -19.6% | positive can reflect cache/writeback timing |
| STOR e2e vs temp-write | -52.6% | negative is non-write-path overhead plus overlap effects |


## Mount And Directory Attribution

| dir | source | target | fstype | sidecar |
| --- | --- | --- | --- | --- |
| project_temp | /dev/nvme0n1p3 | / | ext4 | /root/projects/GridFlux/tools/perf/results/20260520T090359Z_beta1b-storage-system-attribution/storage-sidecars/project_temp_gridflux_storage_bench_read_b67108864_buf262144_prefull_posix_after.log |
| target_root | /dev/nvme0n1p3 | / | ext4 | /root/projects/GridFlux/tools/perf/results/20260520T090359Z_beta1b-storage-system-attribution/storage-sidecars/target_root_gridflux_storage_bench_read_b67108864_buf262144_prefull_posix_after.log |
| tmp | /dev/nvme0n1p3 | / | ext4 | /root/projects/GridFlux/tools/perf/results/20260520T090359Z_beta1b-storage-system-attribution/storage-sidecars/tmp_gridflux_storage_bench_read_b67108864_buf262144_prefull_posix_after.log |
| /tmp vs target_root same mount? | yes |  |  |  |
| project_temp vs target_root same mount? | yes |  |  |  |


## Storage Knob Stability

| dimension | matched rows | >=5% wins | <=-5% regressions | median delta |
| --- | --- | --- | --- | --- |
| preallocate full | 3 | 3 | 0 | +23.7% |
| io_uring | 0 | 0 | 0 |  |


## STOR Stage Attribution

| case | e2e Gbps | temp-write Gbps | temp share | data recv | manifest | final verify | rename | spread % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bytes=67108864 tls=off/off conn=1 checksum=crc32c | 9.921 | 23.082 | 43.0% | 11.6% | 1.3% | 28.4% | 0.8% | 0.0 |
| bytes=67108864 tls=off/off conn=1 checksum=none | 17.128 | 22.721 | 75.4% | 22.8% | 1.9% | 0.0% | 0.1% | 0.0 |
| bytes=67108864 tls=off/off conn=4 checksum=crc32c | 9.186 | 17.784 | 51.7% | 9.6% | 1.2% | 24.0% | 0.7% | 0.0 |
| bytes=67108864 tls=off/off conn=4 checksum=none | 16.364 | 22.135 | 73.9% | 23.8% | 1.9% | 0.0% | 0.1% | 0.0 |
| bytes=67108864 tls=off/off conn=8 checksum=crc32c | 9.581 | 20.382 | 47.0% | 11.0% | 1.2% | 25.6% | 0.8% | 0.0 |
| bytes=67108864 tls=off/off conn=8 checksum=none | 15.520 | 19.372 | 80.1% | 18.8% | 1.8% | 0.0% | 0.1% | 0.0 |
| bytes=67108864 tls=required/required conn=4 checksum=crc32c | 7.043 | 20.940 | 33.6% | 80.9% | 0.9% | 19.0% | 0.5% | 0.0 |


## Required Answers

- Native storage write/read upper bound: see the native rows in the comparison table.
- GridFlux temp-write vs native: see `temp-write vs native write`; positive values can occur when page cache timing makes native write and STOR temp-write windows differ.
- STOR end-to-end vs temp-write: see `STOR e2e vs temp-write`; the stage table keeps final verify, manifest, and rename shares visible.
- Dirty/Writeback explanation: use the correlation line plus per-case sidecars in the probe and matrix CSVs.
- `/tmp` versus target root: see the mount table and same-mount rows.
- Preallocate and POSIX/io_uring value: see the storage knob stability table.
- Hardware/cloud ceiling: treat as likely only when native write/read and STOR temp-write converge and Dirty/Writeback remains strongly coupled to throughput.
- User-space queue: not recommended unless GridFlux temp-write remains well below native storage after storage/system limits are ruled out.

## Recommendation

- Native POSIX write median/best: `26.035 / 29.912 Gbps`.
- GridFlux STOR e2e median: `9.921 Gbps`; temp-write median: `20.940 Gbps`; temp-write share median: `51.7%`.
- Preallocate matched wins/regressions: `3/0`.
- io_uring matched wins/regressions: `0/0`.
- Dirty/Writeback correlation: Pearson r `0.471` across `31` paired rows.
- Recommendation: current STOR behavior is close enough to the observed native storage/writeback envelope that Beta should prioritize disk/filesystem/cloud-volume validation before user-space queue design.
- Default policy remains unchanged.

## Non-Goals Preserved

- No 100G migration or 100G test.
- No default policy changes.
- No independent user-space queue.
- No default bounded/dirty_poll.
- No QUIC, FEC, RDMA, or GSI work.

## Beta 1D Closeout Reference

Beta 1D reuses this storage/system attribution as the STOR writeback reference
for Beta Gate / Beta RC. The gate performs freshness or tiny smoke validation
instead of rerunning a heavy storage matrix by default. See
`docs/release/BETA_RELEASE_GATE.md`, `docs/release/BETA_RELEASE_CANDIDATE.md`,
and `docs/perf/BETA_PERFORMANCE_SUMMARY.md`.
