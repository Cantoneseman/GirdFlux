# Beta 1C RETR Stability

Generated: 2026-05-21T04:27:08Z

## Executive Summary

Beta 1C re-checks the RETR path on the existing two cloud servers and closes the beta performance investigation without changing defaults. The matrix isolates POSIX off/off scaling, a required/required TLS data point, an io_uring data point, and a crc32c verified_chunks opt-in comparison.

- RETR summary median/best throughput: `9.915 / 15.806 Gbps`.
- RETR median p95/spread: `9.915 Gbps / 0.0%`.
- Sender network-send stage/elapsed ratio median: `145.2%`.
- Receiver download temp-write stage/elapsed ratio median: `204.6%`.
- Receiver final verify / rename share medians: `16.2%` / `0.2%`.
- Dirty/Writeback correlation: Pearson r `-0.200` across `10` paired RETR rows.
- Stage ratios are computed from existing aggregate multi-stream stage counters divided by transfer elapsed time; values above 100% indicate parallel per-connection work and should be read as dominance indicators, not exclusive wall-time shares.

## Inputs

- `tools/perf/results/20260521T042649Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260521T042659Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260521T042702Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260521T042704Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260521T042649Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260521T042659Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260521T042702Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260521T042704Z_gridftp-private-matrix-smoke-summary.csv`

## Result Counts

- RETR raw rows: `10`; pass `10`, fail `0`.
- RETR summary rows: `10`; grouped failures `0`.

## RETR Stage Breakdown

| case | median Gbps | p95 Gbps | spread % | sender send ratio | source read | sender checksum | recv temp write ratio | final verify | rename |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bytes=67108864 backend=io_uring tls=off/off conn=4 checksum=crc32c fv=full | 8.706 | 8.706 | 0.0 | 96.3% | 45.8% | 52.3% | 225.8% | 23.4% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=1 checksum=crc32c fv=full | 9.836 | 9.836 | 0.0 | 30.6% | 17.9% | 13.4% | 40.7% | 25.9% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=1 checksum=none fv=full | 15.806 | 15.806 | 0.0 | 59.1% | 27.9% | 0.0% | 74.8% | 0.0% | 1.0% |
| bytes=67108864 backend=posix tls=off/off conn=4 checksum=crc32c fv=full | 9.994 | 9.994 | 0.0 | 157.9% | 20.7% | 14.9% | 179.1% | 26.0% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=4 checksum=crc32c fv=full | 9.496 | 9.496 | 0.0 | 132.6% | 22.5% | 15.3% | 183.3% | 24.9% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=4 checksum=crc32c fv=verified_chunks | 12.572 | 12.572 | 0.0 | 209.9% | 27.7% | 23.1% | 299.7% | 0.0% | 0.3% |
| bytes=67108864 backend=posix tls=off/off conn=4 checksum=none fv=full | 14.503 | 14.503 | 0.0 | 245.6% | 34.8% | 0.0% | 291.5% | 0.0% | 1.0% |
| bytes=67108864 backend=posix tls=off/off conn=8 checksum=crc32c fv=full | 9.791 | 9.791 | 0.0 | 196.9% | 27.8% | 28.5% | 392.5% | 25.5% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=8 checksum=none fv=full | 13.896 | 13.896 | 0.0 | 285.2% | 42.5% | 0.0% | 483.3% | 0.0% | 1.0% |
| bytes=67108864 backend=posix tls=required/required conn=4 checksum=crc32c fv=full | 3.373 | 3.373 | 0.0 | 68.7% | 8.2% | 5.9% | 37.3% | 8.9% | 0.1% |


## Connections Scaling

| case | conn1 | conn4 | conn8 | 4 vs 1 | 8 vs 4 |
| --- | --- | --- | --- | --- | --- |
| bytes=67108864 checksum=crc32c | 9.836 | 9.496 | 9.791 | -3.4% | +3.1% |
| bytes=67108864 checksum=none | 15.806 | 14.503 | 13.896 | -8.2% | -4.2% |


## TLS/Data TLS Overhead

| case | off/off Gbps | required/required Gbps | delta |
| --- | --- | --- | --- |
| bytes=67108864 conn=4 checksum=crc32c | 9.496 | 3.373 | -64.5% |


## Final Verify Policy Opt-In

| case | full Gbps | verified_chunks Gbps | delta | full fv share | verified fv share |
| --- | --- | --- | --- | --- | --- |
| bytes=67108864 conn=4 | 9.496 | 12.572 | 32.4% | 24.9% | 0.0% |


## POSIX vs io_uring

| case | POSIX Gbps | io_uring Gbps | delta |
| --- | --- | --- | --- |
| bytes=67108864 conn=4 checksum=crc32c | 9.496 | 8.706 | -8.3% |


## Required Answers

- RETR best/median throughput: see the executive summary and stage table.
- Sender network send bottleneck: use the sender send ratio column and dominant-stage recommendation.
- Receiver download temp write: see `recv temp write ratio` in the stage table.
- final verify full vs verified_chunks: see the opt-in table; verified_chunks remains opt-in.
- TLS/data TLS overhead: see the required/required comparison table.
- connections 1/4/8 scaling: see the scaling table.
- POSIX vs io_uring: see the io_uring comparison table.
- Beta Gate / Beta RC readiness: see the recommendation below.

## Recommendation

- RETR median/best summary throughput: `9.915 / 15.806 Gbps`; median spread `0.0%`.
- Dominant-stage count: sender network send `1`, receiver temp write `9` across `10` passing summary rows.
- TLS/data TLS median delta: `-64.5%`.
- verified_chunks median delta: `32.4%`.
- Dirty/Writeback correlation: Pearson r `-0.200` across `10` paired RETR rows.
- Recommendation: do not add user-space queue; investigate receiver download temp-write and storage/system behavior before RETR feature work.
- Default policy remains unchanged.

## Non-Goals Preserved

- No 100G migration or 100G test.
- No default policy changes.
- No user-space queue.
- No default verified_chunks, io_uring, bounded, or dirty_poll.
- No QUIC, FEC, RDMA, or GSI work.
