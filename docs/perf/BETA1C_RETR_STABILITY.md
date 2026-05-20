# Beta 1C RETR Stability

Generated: 2026-05-20T16:48:28Z

## Executive Summary

Beta 1C re-checks the RETR path on the existing two cloud servers and closes the beta performance investigation without changing defaults. The matrix isolates POSIX off/off scaling, a required/required TLS data point, an io_uring data point, and a crc32c verified_chunks opt-in comparison.

- RETR summary median/best throughput: `10.727 / 15.310 Gbps`.
- RETR median p95/spread: `10.727 Gbps / 0.0%`.
- Sender network-send stage/elapsed ratio median: `164.9%`.
- Receiver download temp-write stage/elapsed ratio median: `225.4%`.
- Receiver final verify / rename share medians: `15.9%` / `0.2%`.
- Dirty/Writeback correlation: Pearson r `-0.230` across `10` paired RETR rows.
- Stage ratios are computed from existing aggregate multi-stream stage counters divided by transfer elapsed time; values above 100% indicate parallel per-connection work and should be read as dominance indicators, not exclusive wall-time shares.

## Inputs

- `tools/perf/results/20260520T164808Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T164818Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T164821Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T164824Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T164808Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260520T164818Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260520T164821Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260520T164824Z_gridftp-private-matrix-smoke-summary.csv`

## Result Counts

- RETR raw rows: `10`; pass `10`, fail `0`.
- RETR summary rows: `10`; grouped failures `0`.

## RETR Stage Breakdown

| case | median Gbps | p95 Gbps | spread % | sender send ratio | source read | sender checksum | recv temp write ratio | final verify | rename |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bytes=67108864 backend=io_uring tls=off/off conn=4 checksum=crc32c fv=full | 8.853 | 8.853 | 0.0 | 154.4% | 33.8% | 15.4% | 225.8% | 22.9% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=1 checksum=crc32c fv=full | 10.913 | 10.913 | 0.0 | 31.5% | 18.0% | 14.4% | 41.9% | 28.0% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=1 checksum=none fv=full | 15.014 | 15.014 | 0.0 | 61.5% | 27.9% | 0.0% | 79.4% | 0.0% | 1.0% |
| bytes=67108864 backend=posix tls=off/off conn=4 checksum=crc32c fv=full | 10.097 | 10.097 | 0.0 | 169.9% | 29.2% | 19.9% | 225.1% | 25.4% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=4 checksum=crc32c fv=full | 10.542 | 10.542 | 0.0 | 160.0% | 30.8% | 17.7% | 206.1% | 26.6% | 0.3% |
| bytes=67108864 backend=posix tls=off/off conn=4 checksum=crc32c fv=verified_chunks | 13.682 | 13.682 | 0.0 | 190.0% | 42.2% | 27.3% | 282.8% | 0.0% | 0.4% |
| bytes=67108864 backend=posix tls=off/off conn=4 checksum=none fv=full | 15.310 | 15.310 | 0.0 | 202.9% | 39.8% | 0.0% | 258.2% | 0.0% | 1.2% |
| bytes=67108864 backend=posix tls=off/off conn=8 checksum=crc32c fv=full | 9.548 | 9.548 | 0.0 | 237.6% | 23.6% | 17.8% | 325.9% | 24.0% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=8 checksum=none fv=full | 14.817 | 14.817 | 0.0 | 275.5% | 50.3% | 0.0% | 456.2% | 0.0% | 1.0% |
| bytes=67108864 backend=posix tls=required/required conn=4 checksum=crc32c fv=full | 3.511 | 3.511 | 0.0 | 59.6% | 9.2% | 8.2% | 33.4% | 8.9% | 0.1% |


## Connections Scaling

| case | conn1 | conn4 | conn8 | 4 vs 1 | 8 vs 4 |
| --- | --- | --- | --- | --- | --- |
| bytes=67108864 checksum=crc32c | 10.913 | 10.542 | 9.548 | -3.4% | -9.4% |
| bytes=67108864 checksum=none | 15.014 | 15.310 | 14.817 | +2.0% | -3.2% |


## TLS/Data TLS Overhead

| case | off/off Gbps | required/required Gbps | delta |
| --- | --- | --- | --- |
| bytes=67108864 conn=4 checksum=crc32c | 10.542 | 3.511 | -66.7% |


## Final Verify Policy Opt-In

| case | full Gbps | verified_chunks Gbps | delta | full fv share | verified fv share |
| --- | --- | --- | --- | --- | --- |
| bytes=67108864 conn=4 | 10.542 | 13.682 | 29.8% | 26.6% | 0.0% |


## POSIX vs io_uring

| case | POSIX Gbps | io_uring Gbps | delta |
| --- | --- | --- | --- |
| bytes=67108864 conn=4 checksum=crc32c | 10.542 | 8.853 | -16.0% |


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

- RETR median/best summary throughput: `10.727 / 15.310 Gbps`; median spread `0.0%`.
- Dominant-stage count: sender network send `1`, receiver temp write `9` across `10` passing summary rows.
- TLS/data TLS median delta: `-66.7%`.
- verified_chunks median delta: `29.8%`.
- Dirty/Writeback correlation: Pearson r `-0.230` across `10` paired RETR rows.
- Recommendation: do not add user-space queue; investigate receiver download temp-write and storage/system behavior before RETR feature work.
- Default policy remains unchanged.

## Non-Goals Preserved

- No 100G migration or 100G test.
- No default policy changes.
- No user-space queue.
- No default verified_chunks, io_uring, bounded, or dirty_poll.
- No QUIC, FEC, RDMA, or GSI work.
