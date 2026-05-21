# Beta 1C RETR Stability

Generated: 2026-05-20T18:25:32Z

## Executive Summary

Beta 1C re-checks the RETR path on the existing two cloud servers and closes the beta performance investigation without changing defaults. The matrix isolates POSIX off/off scaling, a required/required TLS data point, an io_uring data point, and a crc32c verified_chunks opt-in comparison.

- RETR summary median/best throughput: `9.991 / 16.536 Gbps`.
- RETR median p95/spread: `9.991 Gbps / 0.0%`.
- Sender network-send stage/elapsed ratio median: `130.1%`.
- Receiver download temp-write stage/elapsed ratio median: `198.1%`.
- Receiver final verify / rename share medians: `16.2%` / `0.2%`.
- Dirty/Writeback correlation: Pearson r `-0.332` across `10` paired RETR rows.
- Stage ratios are computed from existing aggregate multi-stream stage counters divided by transfer elapsed time; values above 100% indicate parallel per-connection work and should be read as dominance indicators, not exclusive wall-time shares.

## Inputs

- `tools/perf/results/20260520T182513Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T182523Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T182526Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T182528Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T182513Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260520T182523Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260520T182526Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260520T182528Z_gridftp-private-matrix-smoke-summary.csv`

## Result Counts

- RETR raw rows: `10`; pass `10`, fail `0`.
- RETR summary rows: `10`; grouped failures `0`.

## RETR Stage Breakdown

| case | median Gbps | p95 Gbps | spread % | sender send ratio | source read | sender checksum | recv temp write ratio | final verify | rename |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bytes=67108864 backend=io_uring tls=off/off conn=4 checksum=crc32c fv=full | 8.547 | 8.547 | 0.0 | 115.0% | 31.5% | 13.7% | 204.6% | 23.2% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=1 checksum=crc32c fv=full | 9.958 | 9.958 | 0.0 | 34.7% | 17.8% | 13.2% | 44.3% | 26.3% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=1 checksum=none fv=full | 16.536 | 16.536 | 0.0 | 58.8% | 30.0% | 0.0% | 72.1% | 0.0% | 1.1% |
| bytes=67108864 backend=posix tls=off/off conn=4 checksum=crc32c fv=full | 10.025 | 10.025 | 0.0 | 145.1% | 22.1% | 17.9% | 190.7% | 26.5% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=4 checksum=crc32c fv=full | 9.696 | 9.696 | 0.0 | 113.3% | 35.0% | 23.3% | 191.6% | 26.1% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=4 checksum=crc32c fv=verified_chunks | 13.326 | 13.326 | 0.0 | 197.8% | 34.9% | 20.2% | 288.5% | 0.0% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=4 checksum=none fv=full | 14.318 | 14.318 | 0.0 | 223.8% | 36.8% | 0.0% | 315.7% | 0.0% | 1.1% |
| bytes=67108864 backend=posix tls=off/off conn=8 checksum=crc32c fv=full | 9.677 | 9.677 | 0.0 | 148.8% | 29.5% | 15.3% | 372.9% | 25.9% | 0.2% |
| bytes=67108864 backend=posix tls=off/off conn=8 checksum=none fv=full | 13.474 | 13.474 | 0.0 | 292.1% | 35.9% | 0.0% | 476.5% | 0.0% | 1.3% |
| bytes=67108864 backend=posix tls=required/required conn=4 checksum=crc32c fv=full | 3.424 | 3.424 | 0.0 | 75.3% | 8.2% | 5.2% | 63.8% | 9.2% | 0.1% |


## Connections Scaling

| case | conn1 | conn4 | conn8 | 4 vs 1 | 8 vs 4 |
| --- | --- | --- | --- | --- | --- |
| bytes=67108864 checksum=crc32c | 9.958 | 9.696 | 9.677 | -2.6% | -0.2% |
| bytes=67108864 checksum=none | 16.536 | 14.318 | 13.474 | -13.4% | -5.9% |


## TLS/Data TLS Overhead

| case | off/off Gbps | required/required Gbps | delta |
| --- | --- | --- | --- |
| bytes=67108864 conn=4 checksum=crc32c | 9.696 | 3.424 | -64.7% |


## Final Verify Policy Opt-In

| case | full Gbps | verified_chunks Gbps | delta | full fv share | verified fv share |
| --- | --- | --- | --- | --- | --- |
| bytes=67108864 conn=4 | 9.696 | 13.326 | 37.4% | 26.1% | 0.0% |


## POSIX vs io_uring

| case | POSIX Gbps | io_uring Gbps | delta |
| --- | --- | --- | --- |
| bytes=67108864 conn=4 checksum=crc32c | 9.696 | 8.547 | -11.8% |


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

- RETR median/best summary throughput: `9.991 / 16.536 Gbps`; median spread `0.0%`.
- Dominant-stage count: sender network send `1`, receiver temp write `9` across `10` passing summary rows.
- TLS/data TLS median delta: `-64.7%`.
- verified_chunks median delta: `37.4%`.
- Dirty/Writeback correlation: Pearson r `-0.332` across `10` paired RETR rows.
- Recommendation: do not add user-space queue; investigate receiver download temp-write and storage/system behavior before RETR feature work.
- Default policy remains unchanged.

## Non-Goals Preserved

- No 100G migration or 100G test.
- No default policy changes.
- No user-space queue.
- No default verified_chunks, io_uring, bounded, or dirty_poll.
- No QUIC, FEC, RDMA, or GSI work.
