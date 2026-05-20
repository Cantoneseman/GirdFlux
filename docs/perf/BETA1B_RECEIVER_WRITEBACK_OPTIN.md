# Beta 1B Receiver Writeback Opt-In

Generated: 2026-05-20T03:13:07Z

## Executive Summary

Beta 1B-3 tests the drain-budget form of `receiver_write_profile=bounded`. The default remains unchanged: the default profile keeps the old receive/write path with no drain budget, no Dirty/Writeback polling, and no yield.

- Bounded profile temp-write wall-share best delta versus matched baseline: `-27.9` percentage points.
- STOR median throughput across all rows: `11.752 Gbps`; p95 median `11.752 Gbps`; spread median `0.0%`.
- Baseline median throughput: `11.752 Gbps`; opt-in median throughput: `11.933 Gbps`.
- Temp-write wall share median: `59.4%`; data-receive wall share median: `13.2%`.
- Throughput regressions beyond 5%: `13` matched opt-in rows.
- Dirty/Writeback correlation: Pearson r `0.775` across `30` raw rows.
- Native storage write median for aligned POSIX/default policy rows: `21.975 Gbps`.

## Inputs

- `tools/perf/results/20260520T031141Z_storage-bench.csv`
- `tools/perf/results/20260520T031141Z_storage-bench-summary.csv`
- `tools/perf/results/20260520T031141Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T031141Z_gridftp-private-matrix-smoke-summary.csv`

## Result Counts

- STOR summary rows: `30`; grouped failures `0`.
- STOR raw rows: `30`; pass `30`, fail `0`.
- Storage summary rows: `1`; storage raw rows: `2`.

## Opt-In Coverage

The `dirty_poll` threshold is intentionally bound to `receiver_max_pending_bytes`; Beta 1B-3 does not add a separate Dirty/Writeback threshold flag.

| receiver profile | max pending bytes | yield policy |
| --- | --- | --- |
| bounded | 268435456 | dirty_poll |
| bounded | 268435456 | none |
| bounded | 67108864 | dirty_poll |
| bounded | 67108864 | none |
| default | 0 | none |


## Matched Baseline Comparisons

Each opt-in row is compared against the same connections/checksum baseline with `default + none + max_pending=0`.

| opt-in case | base Gbps | opt Gbps | throughput delta | base temp share | opt temp share | temp-share delta | base spread % | opt spread % | backpressure count | backpressure s | yield count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| conn=1 checksum=crc32c profile=bounded budget=268435456 yield=dirty_poll | 9.440 | 8.350 | -11.6% | 44.6% | 47.5% | +2.9 pp | 0.0 | 0.0 | 1 | 0.000 | 0 |
| conn=1 checksum=crc32c profile=bounded budget=268435456 yield=none | 9.440 | 8.368 | -11.4% | 44.6% | 43.9% | -0.7 pp | 0.0 | 0.0 | 1 | 0.000 | 0 |
| conn=1 checksum=crc32c profile=bounded budget=67108864 yield=dirty_poll | 9.440 | 9.167 | -2.9% | 44.6% | 42.3% | -2.4 pp | 0.0 | 0.0 | 4 | 0.004 | 4 |
| conn=1 checksum=crc32c profile=bounded budget=67108864 yield=none | 9.440 | 3.120 | -67.0% | 44.6% | 16.7% | -27.9 pp | 0.0 | 0.0 | 4 | 0.000 | 0 |
| conn=1 checksum=none profile=bounded budget=268435456 yield=dirty_poll | 15.875 | 16.783 | +5.7% | 74.8% | 72.4% | -2.4 pp | 0.0 | 0.0 | 1 | 0.000 | 0 |
| conn=1 checksum=none profile=bounded budget=268435456 yield=none | 15.875 | 18.111 | +14.1% | 74.8% | 77.6% | +2.8 pp | 0.0 | 0.0 | 1 | 0.000 | 0 |
| conn=1 checksum=none profile=bounded budget=67108864 yield=dirty_poll | 15.875 | 16.126 | +1.6% | 74.8% | 71.3% | -3.5 pp | 0.0 | 0.0 | 4 | 0.004 | 4 |
| conn=1 checksum=none profile=bounded budget=67108864 yield=none | 15.875 | 16.762 | +5.6% | 74.8% | 78.2% | +3.5 pp | 0.0 | 0.0 | 4 | 0.000 | 0 |
| conn=4 checksum=crc32c profile=bounded budget=268435456 yield=dirty_poll | 9.337 | 5.459 | -41.5% | 45.0% | 25.3% | -19.7 pp | 0.0 | 0.0 | 1 | 0.000 | 0 |
| conn=4 checksum=crc32c profile=bounded budget=268435456 yield=none | 9.337 | 4.304 | -53.9% | 45.0% | 22.8% | -22.2 pp | 0.0 | 0.0 | 1 | 0.000 | 0 |
| conn=4 checksum=crc32c profile=bounded budget=67108864 yield=dirty_poll | 9.337 | 4.520 | -51.6% | 45.0% | 23.5% | -21.5 pp | 0.0 | 0.0 | 4 | 0.004 | 4 |
| conn=4 checksum=crc32c profile=bounded budget=67108864 yield=none | 9.337 | 7.007 | -24.9% | 45.0% | 37.7% | -7.3 pp | 0.0 | 0.0 | 4 | 0.000 | 0 |
| conn=4 checksum=none profile=bounded budget=268435456 yield=dirty_poll | 16.616 | 15.618 | -6.0% | 77.1% | 76.6% | -0.5 pp | 0.0 | 0.0 | 1 | 0.000 | 0 |
| conn=4 checksum=none profile=bounded budget=268435456 yield=none | 16.616 | 15.236 | -8.3% | 77.1% | 80.3% | +3.2 pp | 0.0 | 0.0 | 1 | 0.000 | 0 |
| conn=4 checksum=none profile=bounded budget=67108864 yield=dirty_poll | 16.616 | 15.435 | -7.1% | 77.1% | 75.3% | -1.9 pp | 0.0 | 0.0 | 4 | 0.004 | 4 |
| conn=4 checksum=none profile=bounded budget=67108864 yield=none | 16.616 | 15.282 | -8.0% | 77.1% | 72.1% | -5.0 pp | 0.0 | 0.0 | 4 | 0.000 | 0 |
| conn=8 checksum=crc32c profile=bounded budget=268435456 yield=dirty_poll | 4.673 | 9.011 | +92.8% | 23.9% | 44.0% | +20.1 pp | 0.0 | 0.0 | 1 | 0.000 | 0 |
| conn=8 checksum=crc32c profile=bounded budget=268435456 yield=none | 4.673 | 6.562 | +40.4% | 23.9% | 32.8% | +9.0 pp | 0.0 | 0.0 | 1 | 0.000 | 0 |
| conn=8 checksum=crc32c profile=bounded budget=67108864 yield=dirty_poll | 4.673 | 4.127 | -11.7% | 23.9% | 19.6% | -4.3 pp | 0.0 | 0.0 | 4 | 0.004 | 4 |
| conn=8 checksum=crc32c profile=bounded budget=67108864 yield=none | 4.673 | 4.144 | -11.3% | 23.9% | 18.6% | -5.3 pp | 0.0 | 0.0 | 4 | 0.000 | 0 |
| conn=8 checksum=none profile=bounded budget=268435456 yield=dirty_poll | 14.065 | 15.549 | +10.6% | 79.8% | 77.3% | -2.5 pp | 0.0 | 0.0 | 1 | 0.000 | 0 |
| conn=8 checksum=none profile=bounded budget=268435456 yield=none | 14.065 | 14.721 | +4.7% | 79.8% | 74.4% | -5.4 pp | 0.0 | 0.0 | 1 | 0.000 | 0 |
| conn=8 checksum=none profile=bounded budget=67108864 yield=dirty_poll | 14.065 | 15.020 | +6.8% | 79.8% | 74.1% | -5.7 pp | 0.0 | 0.0 | 4 | 0.004 | 4 |
| conn=8 checksum=none profile=bounded budget=67108864 yield=none | 14.065 | 14.698 | +4.5% | 79.8% | 75.6% | -4.2 pp | 0.0 | 0.0 | 4 | 0.000 | 0 |


## Required Answers

- Bounded profile temp-write wall share: see the matched temp-share delta column; negative values are improvements.
- STOR median / p95 / spread: reported in the executive summary and matched comparison table.
- Throughput regression rule: any matched median throughput delta below `-5%` is counted as a regression.
- Dirty/Writeback relation to throughput: Dirty+Writeback after-sidecar values are correlated with raw transfer throughput when enough paired samples exist.
- Evidence for larger matrix: decided below from correctness, regression count, temp-share delta, spread delta, and p95 delta.

## Gate Decision

- Grouped fail count: `0`.
- Matched opt-in comparisons: `24`.
- Matched opt-in rows with >5% throughput regression: `13`.
- Matched opt-in rows with temp-share/spread/p95 signal and no >5% regression: `8`.
- Recommendation: keep the opt-in implementation for more evidence, but do not change defaults or promote to a larger matrix yet.
- Beta 1B-3 next step: compare only the best bounded budget/yield rows against the same storage bench window before considering a user-space queue experiment.

## Non-Goals Preserved

- No default policy changes.
- No independent user-space write queue or worker pool.
- No frame, checksum, manifest, resume, final verify, TLS, or auth semantic changes.
- `dirty_poll` remains opt-in and reuses `receiver_max_pending_bytes` as the Dirty+Writeback budget.
