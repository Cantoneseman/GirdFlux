# Beta 1A 100G Readiness Diagnosis

Generated: 2026-05-19T08:27:30Z

## Executive Summary

Best observed median throughput in the supplied summaries is 4.217 Gbps, about 23.7x below 100 Gbps. Dominant measured stages by row: receiver temp write=101, sender network send=35. Treat this as a readiness diagnosis, not a default-policy change.

Defaults remain unchanged: anonymous auth, TLS off, data TLS off, POSIX backend, full final verify, every-n-chunks manifest flush, preallocate off, and POSIX write strategy auto.

## Beta 1B-0 Follow-up: Data TLS Resume Blocker

Beta 1A-1 exposed a correctness blocker before the 4 GiB repeat=3 heavy run was
continued: `STOR resume + tls=required + data_tls=required` could close the
control connection after a partial upload rather than returning a recoverable
`550` for `REST GFID` resume. Beta 1B fixed the issue by preventing OpenSSL
data-channel writes/shutdown from delivering `SIGPIPE` to the server process.

Focused validation after the fix:

- raw CSV: `tools/perf/results/20260519T101941Z_gridftp-private-matrix-smoke.csv`
- summary CSV: `tools/perf/results/20260519T101941Z_gridftp-private-matrix-smoke-summary.csv`
- coverage: STOR/RETR resume, TLS off/required, data TLS off/required, checksum
  `crc32c|none`, backend `posix|io_uring`, connections `1,2,4,8`
- result: 96/96 pass, hash mismatch=0

This does not change the Beta 1A readiness conclusion: the environment remains
far below 100G, CRC32C hardware is not the main bottleneck, STOR is still
receiver temp write/writeback dominated, and RETR alternates between sender
network send and receiver download temp write pressure.

## Beta 1B-2 Follow-up: STOR Writeback Diagnosis

Beta 1B-2 narrows the next performance question to STOR receiver temp
write/writeback. The new focused package aligns receiver-side native
`gridflux-storage-bench` write results with GridFlux STOR temp write and
end-to-end throughput, while keeping all defaults unchanged.

New artifacts:

- runner: `tools/perf/run_beta1b_stor_writeback.py`
- analyzer: `tools/perf/analyze_beta1b_stor_writeback.py`
- report: `docs/perf/BETA1B_STOR_WRITEBACK_DIAGNOSIS.md`

The focused runner avoids the 4 GiB repeat=3 full heavy matrix. It scans only
small opt-in STOR A/B batches for backend/connections, POSIX write
strategy/file buffer, preallocate/manifest flush, and crc32c-only final verify
policy.

## Beta 1B-3 Follow-up: Receiver Writeback Opt-In

Beta 1B-3 keeps the Beta 1A readiness conclusion unchanged and narrows the
next experiment to receiver-side writeback/backpressure. It adds only opt-in
controls: `receiver_write_profile=bounded`, `receiver_max_pending_bytes`, and
`receiver_write_yield_policy=dirty_poll`.

`receiver_write_profile=default` remains the old receive/write path. The
bounded profile uses a drain budget rather than an independent user-space queue
or worker pool. `dirty_poll` reuses `receiver_max_pending_bytes` as the
Dirty+Writeback budget threshold; no separate threshold flag is introduced for
Beta 1B-3.

New artifacts:

- runner mode: `tools/perf/run_beta1b_stor_writeback.py --receiver-writeback-optin`
- analyzer: `tools/perf/analyze_beta1b_receiver_writeback.py`
- report: `docs/perf/BETA1B_RECEIVER_WRITEBACK_OPTIN.md`

Focused result: `tools/perf/results/20260519T165059Z_beta1b-receiver-writeback-optin.json`
passed with STOR raw `90/90` pass and hash mismatch `0`. Summary median
throughput was `1.711 Gbps`, baseline median `1.724 Gbps`, opt-in median
`1.701 Gbps`; temp-write wall share median remained high at `83.6%`, while
data_receive stayed small at `1.9%`. Bounded drain-budget produced selective
temp-share/spread improvements, but `4` matched opt-in rows regressed median
throughput by more than `5%`; default policy therefore remains unchanged.

## Host / Link / Storage Baseline

| side | category | tool | bytes | Gbps | result |
| --- | --- | --- | --- | --- | --- |
| link | network | gridflux_memory_sink | 1073741824 | 19.1167 | pass |
| server | disk_write | python | 1073741824 | 1.013480 | pass |
| server | disk_read | python | 1073741824 | 0.928677 | pass |
| client | disk_write | python | 1073741824 | 1.029056 | pass |
| client | disk_read | python | 1073741824 | 71.761104 | pass |
| server | checksum | gridflux-checksum-bench | 1073741824 | 76.3407 | pass |
| client | checksum | gridflux-checksum-bench | 1073741824 | 76.2174 | pass |


## Single-file STOR/RETR Matrix

| direction | bytes | conn | checksum | TLS | data TLS | backend | final verify | median Gbps | spread % | fail | dominant measured stage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| retr | 1073741824 | 1 | crc32c | off | off | io_uring | full | 2.487 | 0.000 | 0 | sender network send (82.0% of elapsed) |
| retr | 1073741824 | 1 | crc32c | off | off | posix | full | 2.391 | 0.000 | 0 | sender network send (72.5% of elapsed) |
| retr | 1073741824 | 1 | crc32c | required | off | io_uring | full | 2.190 | 0.000 | 0 | sender network send (73.8% of elapsed) |
| retr | 1073741824 | 1 | crc32c | required | off | posix | full | 2.549 | 0.000 | 0 | sender network send (82.8% of elapsed) |
| retr | 1073741824 | 1 | crc32c | required | required | io_uring | full | 2.344 | 0.000 | 0 | sender network send (80.9% of elapsed) |
| retr | 1073741824 | 1 | crc32c | required | required | posix | full | 2.392 | 0.000 | 0 | sender network send (81.9% of elapsed) |
| retr | 1073741824 | 1 | none | off | off | io_uring | full | 2.615 | 0.000 | 0 | sender network send (90.0% of elapsed) |
| retr | 1073741824 | 1 | none | off | off | posix | full | 2.482 | 0.000 | 0 | sender network send (79.6% of elapsed) |
| retr | 1073741824 | 1 | none | required | off | io_uring | full | 2.277 | 0.000 | 0 | sender network send (78.4% of elapsed) |
| retr | 1073741824 | 1 | none | required | off | posix | full | 2.790 | 0.000 | 0 | sender network send (91.2% of elapsed) |
| retr | 1073741824 | 1 | none | required | required | io_uring | full | 2.083 | 0.000 | 0 | sender network send (77.1% of elapsed) |
| retr | 1073741824 | 1 | none | required | required | posix | full | 2.494 | 0.000 | 0 | sender network send (89.9% of elapsed) |
| retr | 1073741824 | 4 | crc32c | off | off | io_uring | full | 3.907 | 0.000 | 0 | sender network send (273.2% of elapsed) |
| retr | 1073741824 | 4 | crc32c | off | off | posix | full | 3.920 | 0.000 | 0 | sender network send (282.2% of elapsed) |
| retr | 1073741824 | 4 | crc32c | required | off | io_uring | full | 3.871 | 0.000 | 0 | sender network send (319.5% of elapsed) |
| retr | 1073741824 | 4 | crc32c | required | off | posix | full | 3.483 | 0.000 | 0 | sender network send (280.0% of elapsed) |
| retr | 1073741824 | 4 | crc32c | required | required | io_uring | full | 3.383 | 0.000 | 0 | sender network send (302.1% of elapsed) |
| retr | 1073741824 | 4 | crc32c | required | required | posix | full | 2.581 | 0.000 | 0 | sender network send (321.6% of elapsed) |
| retr | 1073741824 | 4 | none | off | off | io_uring | full | 3.310 | 0.000 | 0 | sender network send (371.8% of elapsed) |
| retr | 1073741824 | 4 | none | off | off | posix | full | 4.190 | 0.000 | 0 | sender network send (288.7% of elapsed) |
| retr | 1073741824 | 4 | none | required | off | io_uring | full | 4.217 | 0.000 | 0 | sender network send (339.3% of elapsed) |
| retr | 1073741824 | 4 | none | required | off | posix | full | 3.272 | 0.000 | 0 | sender network send (352.9% of elapsed) |
| retr | 1073741824 | 4 | none | required | required | io_uring | full | 4.035 | 0.000 | 0 | sender network send (335.8% of elapsed) |
| retr | 1073741824 | 4 | none | required | required | posix | full | 2.967 | 0.000 | 0 | sender network send (234.6% of elapsed) |
| retr | 1073741824 | 8 | crc32c | off | off | io_uring | full | 3.695 | 0.000 | 0 | sender network send (485.3% of elapsed) |
| retr | 1073741824 | 8 | crc32c | off | off | posix | full | 3.246 | 0.000 | 0 | sender network send (382.4% of elapsed) |
| retr | 1073741824 | 8 | crc32c | required | off | io_uring | full | 3.354 | 0.000 | 0 | receiver temp write (403.4% of elapsed) |
| retr | 1073741824 | 8 | crc32c | required | off | posix | full | 2.376 | 0.000 | 0 | sender network send (488.9% of elapsed) |
| retr | 1073741824 | 8 | crc32c | required | required | io_uring | full | 3.406 | 0.000 | 0 | sender network send (515.0% of elapsed) |
| retr | 1073741824 | 8 | crc32c | required | required | posix | full | 3.534 | 0.000 | 0 | sender network send (482.6% of elapsed) |
| retr | 1073741824 | 8 | none | off | off | io_uring | full | 3.594 | 0.000 | 0 | sender network send (591.4% of elapsed) |
| retr | 1073741824 | 8 | none | off | off | posix | full | 4.215 | 0.000 | 0 | sender network send (437.5% of elapsed) |
| retr | 1073741824 | 8 | none | required | off | io_uring | full | 3.859 | 0.000 | 0 | sender network send (410.5% of elapsed) |
| retr | 1073741824 | 8 | none | required | off | posix | full | 3.968 | 0.000 | 0 | receiver temp write (548.5% of elapsed) |
| retr | 1073741824 | 8 | none | required | required | io_uring | full | 3.691 | 0.000 | 0 | sender network send (575.2% of elapsed) |
| retr | 1073741824 | 8 | none | required | required | posix | full | 2.133 | 0.000 | 0 | sender network send (588.7% of elapsed) |
| retr-resume | 1073741824 | 1 | crc32c | off | off | io_uring | full | 0.883 | 0.000 | 0 | receiver temp write (86.6% of elapsed) |
| retr-resume | 1073741824 | 1 | crc32c | off | off | posix | full | 0.961 | 0.000 | 0 | receiver temp write (92.1% of elapsed) |
| retr-resume | 1073741824 | 1 | crc32c | required | off | io_uring | full | 1.032 | 0.000 | 0 | receiver temp write (93.7% of elapsed) |
| retr-resume | 1073741824 | 1 | crc32c | required | off | posix | full | 2.487 | 0.000 | 0 | receiver temp write (83.4% of elapsed) |
| retr-resume | 1073741824 | 1 | none | off | off | io_uring | full | 1.005 | 0.000 | 0 | receiver temp write (97.8% of elapsed) |
| retr-resume | 1073741824 | 1 | none | off | off | posix | full | 2.484 | 0.000 | 0 | receiver temp write (87.0% of elapsed) |
| retr-resume | 1073741824 | 1 | none | required | off | io_uring | full | 1.058 | 0.000 | 0 | receiver temp write (98.8% of elapsed) |
| retr-resume | 1073741824 | 1 | none | required | off | posix | full | 2.720 | 0.000 | 0 | receiver temp write (95.3% of elapsed) |
| retr-resume | 1073741824 | 2 | crc32c | off | off | io_uring | full | 2.721 | 0.000 | 0 | receiver temp write (169.1% of elapsed) |
| retr-resume | 1073741824 | 2 | crc32c | off | off | posix | full | 2.380 | 0.000 | 0 | sender network send (167.0% of elapsed) |
| retr-resume | 1073741824 | 2 | crc32c | required | off | io_uring | full | 2.857 | 0.000 | 0 | receiver temp write (168.1% of elapsed) |
| retr-resume | 1073741824 | 2 | crc32c | required | off | posix | full | 2.594 | 0.000 | 0 | receiver temp write (150.5% of elapsed) |
| retr-resume | 1073741824 | 2 | none | off | off | io_uring | full | 2.719 | 0.000 | 0 | receiver temp write (178.3% of elapsed) |
| retr-resume | 1073741824 | 2 | none | off | off | posix | full | 2.633 | 0.000 | 0 | receiver temp write (104.3% of elapsed) |
| retr-resume | 1073741824 | 2 | none | required | off | io_uring | full | 3.630 | 0.000 | 0 | receiver temp write (185.0% of elapsed) |
| retr-resume | 1073741824 | 2 | none | required | off | posix | full | 2.898 | 0.000 | 0 | receiver temp write (155.0% of elapsed) |
| retr-resume | 1073741824 | 4 | crc32c | off | off | io_uring | full | 2.810 | 0.000 | 0 | receiver temp write (296.9% of elapsed) |
| retr-resume | 1073741824 | 4 | crc32c | off | off | posix | full | 2.601 | 0.000 | 0 | receiver temp write (247.9% of elapsed) |
| retr-resume | 1073741824 | 4 | crc32c | required | off | io_uring | full | 1.043 | 0.000 | 0 | receiver temp write (361.1% of elapsed) |
| retr-resume | 1073741824 | 4 | crc32c | required | off | posix | full | 1.083 | 0.000 | 0 | receiver temp write (286.7% of elapsed) |
| retr-resume | 1073741824 | 4 | none | off | off | io_uring | full | 3.348 | 0.000 | 0 | receiver temp write (366.0% of elapsed) |
| retr-resume | 1073741824 | 4 | none | off | off | posix | full | 1.143 | 0.000 | 0 | receiver temp write (363.0% of elapsed) |
| retr-resume | 1073741824 | 4 | none | required | off | io_uring | full | 1.056 | 0.000 | 0 | receiver temp write (374.8% of elapsed) |
| retr-resume | 1073741824 | 4 | none | required | off | posix | full | 2.674 | 0.000 | 0 | receiver temp write (271.5% of elapsed) |
| retr-resume | 1073741824 | 8 | crc32c | off | off | io_uring | full | 1.113 | 0.000 | 0 | receiver temp write (711.4% of elapsed) |
| retr-resume | 1073741824 | 8 | crc32c | off | off | posix | full | 1.102 | 0.000 | 0 | receiver temp write (719.0% of elapsed) |
| retr-resume | 1073741824 | 8 | crc32c | required | off | io_uring | full | 2.079 | 0.000 | 0 | receiver temp write (404.1% of elapsed) |
| retr-resume | 1073741824 | 8 | crc32c | required | off | posix | full | 0.987 | 0.000 | 0 | receiver temp write (570.1% of elapsed) |
| retr-resume | 1073741824 | 8 | none | off | off | io_uring | full | 1.001 | 0.000 | 0 | receiver temp write (690.3% of elapsed) |
| retr-resume | 1073741824 | 8 | none | off | off | posix | full | 1.018 | 0.000 | 0 | receiver temp write (587.9% of elapsed) |
| retr-resume | 1073741824 | 8 | none | required | off | io_uring | full | 1.198 | 0.000 | 0 | receiver temp write (738.0% of elapsed) |
| retr-resume | 1073741824 | 8 | none | required | off | posix | full | 1.012 | 0.000 | 0 | receiver temp write (583.7% of elapsed) |
| stor | 1073741824 | 1 | crc32c | off | off | io_uring | full | 1.459 | 0.000 | 0 | receiver temp write (87.6% of elapsed) |
| stor | 1073741824 | 1 | crc32c | off | off | posix | full | 1.423 | 0.000 | 0 | receiver temp write (88.3% of elapsed) |
| stor | 1073741824 | 1 | crc32c | required | off | io_uring | full | 1.443 | 0.000 | 0 | receiver temp write (87.9% of elapsed) |
| stor | 1073741824 | 1 | crc32c | required | off | posix | full | 1.466 | 0.000 | 0 | receiver temp write (86.7% of elapsed) |
| stor | 1073741824 | 1 | crc32c | required | required | io_uring | full | 1.449 | 0.000 | 0 | receiver temp write (83.7% of elapsed) |
| stor | 1073741824 | 1 | crc32c | required | required | posix | full | 1.421 | 0.000 | 0 | receiver temp write (81.3% of elapsed) |
| stor | 1073741824 | 1 | none | off | off | io_uring | full | 1.465 | 0.000 | 0 | receiver temp write (88.7% of elapsed) |
| stor | 1073741824 | 1 | none | off | off | posix | full | 1.483 | 0.000 | 0 | receiver temp write (94.8% of elapsed) |
| stor | 1073741824 | 1 | none | required | off | io_uring | full | 1.469 | 0.000 | 0 | receiver temp write (91.7% of elapsed) |
| stor | 1073741824 | 1 | none | required | off | posix | full | 1.452 | 0.000 | 0 | receiver temp write (92.9% of elapsed) |
| stor | 1073741824 | 1 | none | required | required | io_uring | full | 1.476 | 0.000 | 0 | receiver temp write (88.0% of elapsed) |
| stor | 1073741824 | 1 | none | required | required | posix | full | 1.447 | 0.000 | 0 | receiver temp write (84.7% of elapsed) |


## TLS and Data TLS Delta

| direction | bytes | conn | checksum | base | compare | base Gbps | compare Gbps | delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| retr | 1073741824 | 1 | crc32c | off/off | required/required | 2.487 | 2.344 | -5.8% |
| retr | 1073741824 | 1 | crc32c | off/off | required/required | 2.391 | 2.392 | +0.0% |
| retr | 1073741824 | 1 | none | off/off | required/required | 2.615 | 2.083 | -20.3% |
| retr | 1073741824 | 1 | none | off/off | required/required | 2.482 | 2.494 | +0.5% |
| retr | 1073741824 | 4 | crc32c | off/off | required/required | 3.907 | 3.383 | -13.4% |
| retr | 1073741824 | 4 | crc32c | off/off | required/required | 3.920 | 2.581 | -34.1% |
| retr | 1073741824 | 4 | none | off/off | required/required | 3.310 | 4.035 | +21.9% |
| retr | 1073741824 | 4 | none | off/off | required/required | 4.190 | 2.967 | -29.2% |
| retr | 1073741824 | 8 | crc32c | off/off | required/required | 3.695 | 3.406 | -7.8% |
| retr | 1073741824 | 8 | crc32c | off/off | required/required | 3.246 | 3.534 | +8.9% |
| retr | 1073741824 | 8 | none | off/off | required/required | 3.594 | 3.691 | +2.7% |
| retr | 1073741824 | 8 | none | off/off | required/required | 4.215 | 2.133 | -49.4% |
| stor | 1073741824 | 1 | crc32c | off/off | required/required | 1.459 | 1.449 | -0.7% |
| stor | 1073741824 | 1 | crc32c | off/off | required/required | 1.423 | 1.421 | -0.1% |
| stor | 1073741824 | 1 | none | off/off | required/required | 1.465 | 1.476 | +0.7% |
| stor | 1073741824 | 1 | none | off/off | required/required | 1.483 | 1.447 | -2.4% |
| stor | 1073741824 | 4 | crc32c | off/off | required/required | 1.461 | 1.483 | +1.5% |
| stor | 1073741824 | 4 | crc32c | off/off | required/required | 1.423 | 1.414 | -0.6% |
| stor | 1073741824 | 4 | none | off/off | required/required | 1.423 | 1.365 | -4.1% |
| stor | 1073741824 | 4 | none | off/off | required/required | 1.518 | 1.439 | -5.2% |
| stor | 1073741824 | 8 | crc32c | off/off | required/required | 1.371 | 1.386 | +1.1% |
| stor | 1073741824 | 8 | crc32c | off/off | required/required | 1.385 | 1.439 | +3.9% |
| stor | 1073741824 | 8 | none | off/off | required/required | 1.316 | 1.487 | +12.9% |
| stor | 1073741824 | 8 | none | off/off | required/required | 1.500 | 1.402 | -6.5% |


## POSIX vs io_uring Delta

| direction | bytes | conn | checksum | base | compare | base Gbps | compare Gbps | delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| retr | 1073741824 | 1 | crc32c | posix | io_uring | 2.391 | 2.487 | +4.0% |
| retr | 1073741824 | 1 | crc32c | posix | io_uring | 2.549 | 2.190 | -14.1% |
| retr | 1073741824 | 1 | crc32c | posix | io_uring | 2.392 | 2.344 | -2.0% |
| retr | 1073741824 | 1 | none | posix | io_uring | 2.482 | 2.615 | +5.3% |
| retr | 1073741824 | 1 | none | posix | io_uring | 2.790 | 2.277 | -18.4% |
| retr | 1073741824 | 1 | none | posix | io_uring | 2.494 | 2.083 | -16.5% |
| retr | 1073741824 | 4 | crc32c | posix | io_uring | 3.920 | 3.907 | -0.3% |
| retr | 1073741824 | 4 | crc32c | posix | io_uring | 3.483 | 3.871 | +11.1% |
| retr | 1073741824 | 4 | crc32c | posix | io_uring | 2.581 | 3.383 | +31.0% |
| retr | 1073741824 | 4 | none | posix | io_uring | 4.190 | 3.310 | -21.0% |
| retr | 1073741824 | 4 | none | posix | io_uring | 3.272 | 4.217 | +28.9% |
| retr | 1073741824 | 4 | none | posix | io_uring | 2.967 | 4.035 | +36.0% |
| retr | 1073741824 | 8 | crc32c | posix | io_uring | 3.246 | 3.695 | +13.9% |
| retr | 1073741824 | 8 | crc32c | posix | io_uring | 2.376 | 3.354 | +41.2% |
| retr | 1073741824 | 8 | crc32c | posix | io_uring | 3.534 | 3.406 | -3.6% |
| retr | 1073741824 | 8 | none | posix | io_uring | 4.215 | 3.594 | -14.7% |
| retr | 1073741824 | 8 | none | posix | io_uring | 3.968 | 3.859 | -2.8% |
| retr | 1073741824 | 8 | none | posix | io_uring | 2.133 | 3.691 | +73.0% |
| retr-resume | 1073741824 | 1 | crc32c | posix | io_uring | 0.961 | 0.883 | -8.1% |
| retr-resume | 1073741824 | 1 | crc32c | posix | io_uring | 2.487 | 1.032 | -58.5% |
| retr-resume | 1073741824 | 1 | none | posix | io_uring | 2.484 | 1.005 | -59.5% |
| retr-resume | 1073741824 | 1 | none | posix | io_uring | 2.720 | 1.058 | -61.1% |
| retr-resume | 1073741824 | 2 | crc32c | posix | io_uring | 2.380 | 2.721 | +14.3% |
| retr-resume | 1073741824 | 2 | crc32c | posix | io_uring | 2.594 | 2.857 | +10.1% |
| retr-resume | 1073741824 | 2 | none | posix | io_uring | 2.633 | 2.719 | +3.3% |
| retr-resume | 1073741824 | 2 | none | posix | io_uring | 2.898 | 3.630 | +25.2% |
| retr-resume | 1073741824 | 4 | crc32c | posix | io_uring | 2.601 | 2.810 | +8.0% |
| retr-resume | 1073741824 | 4 | crc32c | posix | io_uring | 1.083 | 1.043 | -3.7% |
| retr-resume | 1073741824 | 4 | none | posix | io_uring | 1.143 | 3.348 | +192.9% |
| retr-resume | 1073741824 | 4 | none | posix | io_uring | 2.674 | 1.056 | -60.5% |
| retr-resume | 1073741824 | 8 | crc32c | posix | io_uring | 1.102 | 1.113 | +0.9% |
| retr-resume | 1073741824 | 8 | crc32c | posix | io_uring | 0.987 | 2.079 | +110.6% |
| retr-resume | 1073741824 | 8 | none | posix | io_uring | 1.018 | 1.001 | -1.6% |
| retr-resume | 1073741824 | 8 | none | posix | io_uring | 1.012 | 1.198 | +18.3% |
| stor | 1073741824 | 1 | crc32c | posix | io_uring | 1.423 | 1.459 | +2.6% |
| stor | 1073741824 | 1 | crc32c | posix | io_uring | 1.466 | 1.443 | -1.5% |
| stor | 1073741824 | 1 | crc32c | posix | io_uring | 1.421 | 1.449 | +2.0% |
| stor | 1073741824 | 1 | none | posix | io_uring | 1.483 | 1.465 | -1.2% |
| stor | 1073741824 | 1 | none | posix | io_uring | 1.452 | 1.469 | +1.1% |
| stor | 1073741824 | 1 | none | posix | io_uring | 1.447 | 1.476 | +2.0% |
| stor | 1073741824 | 4 | crc32c | posix | io_uring | 1.423 | 1.461 | +2.7% |
| stor | 1073741824 | 4 | crc32c | posix | io_uring | 1.351 | 1.456 | +7.8% |
| stor | 1073741824 | 4 | crc32c | posix | io_uring | 1.414 | 1.483 | +4.9% |
| stor | 1073741824 | 4 | none | posix | io_uring | 1.518 | 1.423 | -6.3% |
| stor | 1073741824 | 4 | none | posix | io_uring | 1.503 | 1.450 | -3.6% |
| stor | 1073741824 | 4 | none | posix | io_uring | 1.439 | 1.365 | -5.1% |
| stor | 1073741824 | 8 | crc32c | posix | io_uring | 1.385 | 1.371 | -1.0% |
| stor | 1073741824 | 8 | crc32c | posix | io_uring | 1.398 | 1.383 | -1.1% |
| stor | 1073741824 | 8 | crc32c | posix | io_uring | 1.439 | 1.386 | -3.7% |
| stor | 1073741824 | 8 | none | posix | io_uring | 1.500 | 1.316 | -12.2% |
| stor | 1073741824 | 8 | none | posix | io_uring | 1.459 | 1.382 | -5.3% |
| stor | 1073741824 | 8 | none | posix | io_uring | 1.402 | 1.487 | +6.0% |
| stor-resume | 1073741824 | 1 | crc32c | posix | io_uring | 1.349 | 1.352 | +0.2% |
| stor-resume | 1073741824 | 1 | crc32c | posix | io_uring | 1.314 | 1.322 | +0.6% |
| stor-resume | 1073741824 | 1 | none | posix | io_uring | 1.327 | 1.434 | +8.1% |
| stor-resume | 1073741824 | 1 | none | posix | io_uring | 1.288 | 1.392 | +8.1% |
| stor-resume | 1073741824 | 2 | crc32c | posix | io_uring | 1.395 | 1.349 | -3.3% |
| stor-resume | 1073741824 | 2 | crc32c | posix | io_uring | 1.234 | 1.366 | +10.8% |
| stor-resume | 1073741824 | 2 | none | posix | io_uring | 1.481 | 1.405 | -5.1% |
| stor-resume | 1073741824 | 2 | none | posix | io_uring | 1.460 | 1.439 | -1.4% |


## Directory Matrix

| dataset | direction | fp | conn | checksum | TLS | data TLS | backend | median Gbps | fail | hash mismatch |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed | download | 1 | 4 | crc32c | off | off | io_uring | 0.266 | 0 | 0 |
| mixed | download | 1 | 4 | crc32c | off | off | posix | 0.266 | 0 | 0 |
| mixed | download | 1 | 4 | crc32c | required | off | io_uring | 0.138 | 0 | 0 |
| mixed | download | 1 | 4 | crc32c | required | required | io_uring | 0.077 | 0 | 0 |
| mixed | download | 1 | 4 | crc32c | required | off | posix | 0.138 | 0 | 0 |
| mixed | download | 1 | 4 | crc32c | required | required | posix | 0.076 | 0 | 0 |
| mixed | download | 1 | 4 | none | off | off | io_uring | 0.267 | 0 | 0 |
| mixed | download | 1 | 4 | none | off | off | posix | 0.269 | 0 | 0 |
| mixed | download | 1 | 4 | none | required | off | io_uring | 0.136 | 0 | 0 |
| mixed | download | 1 | 4 | none | required | required | io_uring | 0.077 | 0 | 0 |
| mixed | download | 1 | 4 | none | required | off | posix | 0.138 | 0 | 0 |
| mixed | download | 1 | 4 | none | required | required | posix | 0.077 | 0 | 0 |
| mixed | download | 2 | 4 | crc32c | off | off | io_uring | 0.490 | 0 | 0 |
| mixed | download | 2 | 4 | crc32c | off | off | posix | 0.490 | 0 | 0 |
| mixed | download | 2 | 4 | crc32c | required | off | io_uring | 0.259 | 0 | 0 |
| mixed | download | 2 | 4 | crc32c | required | required | io_uring | 0.145 | 0 | 0 |
| mixed | download | 2 | 4 | crc32c | required | off | posix | 0.258 | 0 | 0 |
| mixed | download | 2 | 4 | crc32c | required | required | posix | 0.145 | 0 | 0 |
| mixed | download | 2 | 4 | none | off | off | io_uring | 0.486 | 0 | 0 |
| mixed | download | 2 | 4 | none | off | off | posix | 0.486 | 0 | 0 |
| mixed | download | 2 | 4 | none | required | off | io_uring | 0.258 | 0 | 0 |
| mixed | download | 2 | 4 | none | required | required | io_uring | 0.147 | 0 | 0 |
| mixed | download | 2 | 4 | none | required | off | posix | 0.260 | 0 | 0 |
| mixed | download | 2 | 4 | none | required | required | posix | 0.129 | 0 | 0 |
| mixed | download | 4 | 4 | crc32c | off | off | io_uring | 0.833 | 0 | 0 |
| mixed | download | 4 | 4 | crc32c | off | off | posix | 0.820 | 0 | 0 |
| mixed | download | 4 | 4 | crc32c | required | off | io_uring | 0.456 | 0 | 0 |
| mixed | download | 4 | 4 | crc32c | required | required | io_uring | 0.269 | 0 | 0 |
| mixed | download | 4 | 4 | crc32c | required | off | posix | 0.456 | 0 | 0 |
| mixed | download | 4 | 4 | crc32c | required | required | posix | 0.265 | 0 | 0 |
| mixed | download | 4 | 4 | none | off | off | io_uring | 0.846 | 0 | 0 |
| mixed | download | 4 | 4 | none | off | off | posix | 0.829 | 0 | 0 |
| mixed | download | 4 | 4 | none | required | off | io_uring | 0.458 | 0 | 0 |
| mixed | download | 4 | 4 | none | required | required | io_uring | 0.271 | 0 | 0 |
| mixed | download | 4 | 4 | none | required | off | posix | 0.454 | 0 | 0 |
| mixed | download | 4 | 4 | none | required | required | posix | 0.264 | 0 | 0 |
| mixed | upload | 1 | 4 | crc32c | off | off | io_uring | 0.289 | 0 | 0 |
| mixed | upload | 1 | 4 | crc32c | off | off | posix | 0.289 | 0 | 0 |
| mixed | upload | 1 | 4 | crc32c | required | off | io_uring | 0.145 | 0 | 0 |
| mixed | upload | 1 | 4 | crc32c | required | required | io_uring | 0.100 | 0 | 0 |
| mixed | upload | 1 | 4 | crc32c | required | off | posix | 0.146 | 0 | 0 |
| mixed | upload | 1 | 4 | crc32c | required | required | posix | 0.101 | 0 | 0 |
| mixed | upload | 1 | 4 | none | off | off | io_uring | 0.291 | 0 | 0 |
| mixed | upload | 1 | 4 | none | off | off | posix | 0.286 | 0 | 0 |
| mixed | upload | 1 | 4 | none | required | off | io_uring | 0.144 | 0 | 0 |
| mixed | upload | 1 | 4 | none | required | required | io_uring | 0.101 | 0 | 0 |
| mixed | upload | 1 | 4 | none | required | off | posix | 0.145 | 0 | 0 |
| mixed | upload | 1 | 4 | none | required | required | posix | 0.102 | 0 | 0 |
| mixed | upload | 2 | 4 | crc32c | off | off | io_uring | 0.565 | 0 | 0 |
| mixed | upload | 2 | 4 | crc32c | off | off | posix | 0.567 | 0 | 0 |
| mixed | upload | 2 | 4 | crc32c | required | off | io_uring | 0.284 | 0 | 0 |
| mixed | upload | 2 | 4 | crc32c | required | required | io_uring | 0.198 | 0 | 0 |
| mixed | upload | 2 | 4 | crc32c | required | off | posix | 0.287 | 0 | 0 |
| mixed | upload | 2 | 4 | crc32c | required | required | posix | 0.195 | 0 | 0 |
| mixed | upload | 2 | 4 | none | off | off | io_uring | 0.565 | 0 | 0 |
| mixed | upload | 2 | 4 | none | off | off | posix | 0.567 | 0 | 0 |
| mixed | upload | 2 | 4 | none | required | off | io_uring | 0.286 | 0 | 0 |
| mixed | upload | 2 | 4 | none | required | required | io_uring | 0.197 | 0 | 0 |
| mixed | upload | 2 | 4 | none | required | off | posix | 0.283 | 0 | 0 |
| mixed | upload | 2 | 4 | none | required | required | posix | 0.196 | 0 | 0 |
| mixed | upload | 4 | 4 | crc32c | off | off | io_uring | 1.082 | 0 | 0 |
| mixed | upload | 4 | 4 | crc32c | off | off | posix | 1.105 | 0 | 0 |
| mixed | upload | 4 | 4 | crc32c | required | off | io_uring | 0.549 | 0 | 0 |
| mixed | upload | 4 | 4 | crc32c | required | required | io_uring | 0.381 | 0 | 0 |
| mixed | upload | 4 | 4 | crc32c | required | off | posix | 0.544 | 0 | 0 |
| mixed | upload | 4 | 4 | crc32c | required | required | posix | 0.371 | 0 | 0 |
| mixed | upload | 4 | 4 | none | off | off | io_uring | 1.097 | 0 | 0 |
| mixed | upload | 4 | 4 | none | off | off | posix | 1.090 | 0 | 0 |
| mixed | upload | 4 | 4 | none | required | off | io_uring | 0.547 | 0 | 0 |
| mixed | upload | 4 | 4 | none | required | required | io_uring | 0.372 | 0 | 0 |
| mixed | upload | 4 | 4 | none | required | off | posix | 0.549 | 0 | 0 |
| mixed | upload | 4 | 4 | none | required | required | posix | 0.372 | 0 | 0 |


## Readiness Gate

- 100G is not considered ready unless repeat median approaches link baseline with low spread and zero hash mismatches.
- Failed rows, hash mismatches, or high spread must be investigated from the referenced raw CSV logs and JSONL event logs.
- LIST/NLST listing data TLS remains outside the Phase 6D/Beta 1A data TLS scope; Beta 1A TLS conclusions cover STOR/RETR framed file data only.

## Beta 1A-1 Execution Notes

This report uses the following private-run artifacts from 2026-05-19:

- Host baseline: `tools/perf/results/20260519T071223Z_host-baseline.csv`
- Single-file smoke raw/summary: `tools/perf/results/20260519T071253Z_gridftp-private-matrix-smoke.csv`, `tools/perf/results/20260519T071253Z_gridftp-private-matrix-smoke-summary.csv`
- Tree smoke raw/summary: `tools/perf/results/20260519T073021Z_gridftp-tree-private-matrix.csv`, `tools/perf/results/20260519T073021Z_gridftp-tree-private-matrix-summary.csv`
- Resume subset raw/summary: `tools/perf/results/20260519T080947Z_gridftp-private-matrix-full.csv`, `tools/perf/results/20260519T080947Z_gridftp-private-matrix-full-summary.csv`
- Readiness wrapper JSON: `tools/perf/results/20260519T071223Z_beta1a-readiness.json`

The first full wrapper attempt with `--full --bytes 1073741824 --repeat 1` was stopped after exposing a repeatable `stor-resume + tls=required + data_tls=required` failure (`control connection closed`, event count `unknown_error=1`). A minimized 64MiB reproduction is preserved at `tools/perf/results/20260519T080840Z_gridftp-private-matrix-full.csv`. This is treated as a Beta 1A readiness blocker for data-TLS resume coverage, not as a performance data point. The successful resume subset intentionally covers `data_tls_mode=off` with control TLS off/required.

## Key Median Results

| area | best observed median | case |
| --- | ---: | --- |
| Single-file STOR | 1.518 Gbps | 1GiB, 4 connections, checksum none, POSIX, TLS off, data TLS off |
| Single-file RETR | 4.217 Gbps | 1GiB, 4 connections, checksum none, io_uring, control TLS required, data TLS off |
| STOR resume subset | 1.508 Gbps | 1GiB, 8 connections, checksum none, POSIX, TLS off, data TLS off |
| RETR resume subset | 3.630 Gbps | 1GiB, 2 connections, checksum none, io_uring, control TLS required, data TLS off |
| Tree upload mixed | 1.105 Gbps | file parallelism 4, crc32c, POSIX, TLS off, data TLS off |
| Tree download mixed | 0.846 Gbps | file parallelism 4, checksum none, io_uring, TLS off, data TLS off |

Host/link/storage baseline shows memory-sink network at 19.117 Gbps, CRC32C hardware at about 76 Gbps on both machines, but Python disk write/read around 1 Gbps on the server. This matches the phase-stage evidence: STOR is dominated by receiver temp write/writeback, while RETR is usually dominated by sender network send and/or receiver temp write depending on connection count and TLS/backend combination.

## 100G Readiness Gate

Beta 1A-1 is not 100G-ready on the current two-machine private environment. The best single-file median is 4.217 Gbps, roughly 23.7x below 100 Gbps, and the memory-sink baseline itself is about 19.1 Gbps, roughly 5.2x below 100 Gbps. The current evidence points to environment and storage/writeback limits before checksum or io_uring queue mechanics:

- CRC32C is not the primary bottleneck: checksum bench is about 76 Gbps.
- STOR remains storage/writeback limited: measured receiver temp write dominates the stage breakdown and server disk baseline is around 1 Gbps.
- RETR scales better than STOR but remains far below link target; sender network send and receiver write alternate as dominant stages.
- io_uring is not a clear default win; deltas vary by direction/TLS/checksum and remain opt-in only.
- TLS/data TLS overhead is mixed in single-file transfer and clearly costly for directory mixed datasets because per-file handshakes amplify overhead.
- `stor-resume` with data TLS required has a repeatable correctness/interop blocker in the current readiness tooling/path and must be fixed before claiming data-TLS resume readiness.

## Beta 1B Recommendation

Do not change defaults. Recommended Beta 1B direction:

1. Fix and harden `STOR resume + data TLS required` before using data TLS in resume readiness conclusions.
2. Run native storage benchmark and OS writeback observation next to the single-file STOR path in the same window, because STOR throughput tracks storage/writeback limits.
3. Investigate RETR sender network-send scheduling and receiver temp-write coupling with repeat=3 before adding new io_uring features.
4. If 100G remains a goal, validate the private link and disk subsystem independently of GridFlux; the current memory-sink and disk baselines are already below the target by large margins.
5. After the data-TLS resume blocker is fixed, rerun a reduced 4GiB repeat=3 matrix focused on default POSIX, io_uring opt-in, TLS/data TLS, and connections 4/8.

## Beta 1B-2 Follow-Up

The follow-up STOR writeback diagnosis completed a focused 1GiB/repeat=3 run without expanding to the 4GiB full heavy matrix. Artifacts:

- Wrapper JSON: `tools/perf/results/20260519T124750Z_beta1b-stor-writeback.json`
- Report: `docs/perf/BETA1B_STOR_WRITEBACK_DIAGNOSIS.md`
- Result: storage summary `64` rows / `192` pass cases / `0` fail cases; STOR raw `120/120` pass; STOR summary `40` rows / `120` pass cases / `0` fail cases; hash mismatch `0`.

Key result: STOR receiver temp write/writeback is still dominant. STOR row medians median `1.419 Gbps`, best `1.544 Gbps`, default-like crc32c/POSIX best `1.488 Gbps`; temp-write wall share median `86.7%`, max `95.7%`; data_receive wall share median `1.6%`; native storage write median `1.078 Gbps`, best `1.328 Gbps`. POSIX vs io_uring, file buffer/coalesced, preallocate, final_only, and verified_chunks did not show a stable default-worthy win. Beta 1B-3 should continue as opt-in receiver writeback/backpressure/profile work plus OS storage/writeback comparison, with defaults unchanged.
