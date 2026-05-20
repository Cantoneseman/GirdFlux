# Beta 1B Receiver Writeback Stability

Generated: 2026-05-20T07:16:28Z

## Executive Summary

Beta 1B-4 expands the opt-in drain-budget receiver writeback candidate matrix. It does not change the receiver data path, defaults, frame format, checksum, manifest, resume, final verify, TLS, or auth semantics.

- STOR median throughput across summary rows: `9.781 Gbps`; p95 median `9.781 Gbps`; spread median `0.0%`.
- Temp-write wall share median: `47.0%`; data-receive wall share median: `19.2%`.
- Matched bounded comparisons: `52`; improvements `>=5%`: `20`; regressions `<=-5%`: `9`.
- Dirty-poll matched pairs: `26`; improvements `>=5%`: `6`; regressions `<=-5%`: `4`.
- TLS/data TLS required matched bounded rows: `24`; regressions `<=-5%`: `4`.
- Dirty/Writeback correlation: Pearson r `-0.069` across `65` raw rows.
- Native storage write median for aligned receiver-side bench rows: `24.061 Gbps`.

Beta 1B-5 follow-up: receiver bounded/dirty_poll remains opt-in only. The
storage/system attribution package (`docs/perf/BETA1B_STORAGE_SYSTEM_ATTRIBUTION.md`)
found the default probe directories on the same ext4 mount, native POSIX write
median/best `1.191/1.539 Gbps`, aligned STOR e2e median/best `1.552/1.793 Gbps`,
and temp-write wall share median `72.8%`. The next Beta work should continue
storage/system validation rather than move directly to user-space queue design.

Beta 1C follow-up: bounded/dirty_poll remains opt-in only. RETR stability is
now reviewed separately with POSIX/off/off as the primary matrix and only small
TLS/data TLS required, io_uring, and verified_chunks subsets.

## Inputs

- `tools/perf/results/20260520T071326Z_storage-bench.csv`
- `tools/perf/results/20260520T071326Z_storage-bench-summary.csv`
- `tools/perf/results/20260520T071326Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T071447Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T071613Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260520T071326Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260520T071447Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260520T071613Z_gridftp-private-matrix-smoke-summary.csv`

## Result Counts

- STOR summary rows: `65`; grouped failures `0`.
- STOR raw rows: `65`; pass `65`, fail `0`.
- Storage summary rows: `1`; storage raw rows: `2`.

## Candidate Aggregate

Wins and regressions use matched default-vs-bounded rows. `>= +5%` median throughput is an improvement; `<= -5%` is a regression.

| backend | tls pair | budget bytes | yield policy | matched rows | >=5% wins | <=-5% regressions | median delta | median temp-share delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| io_uring | off/off | 268435456 | dirty_poll | 1 | 0 | 0 | +2.3% | -2.9 pp |
| io_uring | off/off | 268435456 | none | 1 | 0 | 0 | +3.4% | -1.0 pp |
| io_uring | off/off | 67108864 | dirty_poll | 1 | 0 | 0 | +4.9% | -2.3 pp |
| io_uring | off/off | 67108864 | none | 1 | 1 | 0 | +12.4% | -4.0 pp |
| posix | off/off | 268435456 | dirty_poll | 6 | 3 | 1 | +5.9% | -1.8 pp |
| posix | off/off | 268435456 | none | 6 | 3 | 2 | +1.4% | +0.7 pp |
| posix | off/off | 67108864 | dirty_poll | 6 | 3 | 1 | +1.7% | -2.7 pp |
| posix | off/off | 67108864 | none | 6 | 2 | 1 | +2.8% | -0.1 pp |
| posix | required/required | 268435456 | dirty_poll | 6 | 2 | 1 | +2.0% | +1.9 pp |
| posix | required/required | 268435456 | none | 6 | 2 | 1 | +3.7% | +0.6 pp |
| posix | required/required | 67108864 | dirty_poll | 6 | 1 | 1 | -1.9% | -0.4 pp |
| posix | required/required | 67108864 | none | 6 | 3 | 1 | +2.9% | +1.4 pp |


## Matched Default vs Bounded

Each bounded row is matched against the same bytes/backend/connections/checksum/TLS pair and fixed storage policy with `receiver_write_profile=default`, budget `0`, and yield policy `none`.

| bounded case | base Gbps | bounded Gbps | median delta | base p95 | bounded p95 | base spread % | bounded spread % | base temp share | bounded temp share | temp delta | backpressure count | backpressure s | yield count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bytes=268435456 backend=io_uring tls=off/off conn=4 checksum=crc32c budget=268435456 yield=dirty_poll | 8.026 | 8.210 | +2.3% | 8.026 | 8.210 | 0.0 | 0.0 | 57.2% | 54.3% | -2.9 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=io_uring tls=off/off conn=4 checksum=crc32c budget=268435456 yield=none | 8.026 | 8.301 | +3.4% | 8.026 | 8.301 | 0.0 | 0.0 | 57.2% | 56.2% | -1.0 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=io_uring tls=off/off conn=4 checksum=crc32c budget=67108864 yield=dirty_poll | 8.026 | 8.418 | +4.9% | 8.026 | 8.418 | 0.0 | 0.0 | 57.2% | 54.9% | -2.3 pp | 4 | 0.005 | 4 |
| bytes=268435456 backend=io_uring tls=off/off conn=4 checksum=crc32c budget=67108864 yield=none | 8.026 | 9.019 | +12.4% | 8.026 | 9.019 | 0.0 | 0.0 | 57.2% | 53.2% | -4.0 pp | 4 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=1 checksum=crc32c budget=268435456 yield=dirty_poll | 10.766 | 9.298 | -13.6% | 10.766 | 9.298 | 0.0 | 0.0 | 43.0% | 50.7% | +7.7 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=1 checksum=crc32c budget=268435456 yield=none | 10.766 | 9.737 | -9.6% | 10.766 | 9.737 | 0.0 | 0.0 | 43.0% | 50.6% | +7.6 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=1 checksum=crc32c budget=67108864 yield=dirty_poll | 10.766 | 10.136 | -5.9% | 10.766 | 10.136 | 0.0 | 0.0 | 43.0% | 40.6% | -2.4 pp | 4 | 0.004 | 4 |
| bytes=268435456 backend=posix tls=off/off conn=1 checksum=crc32c budget=67108864 yield=none | 10.766 | 9.753 | -9.4% | 10.766 | 9.753 | 0.0 | 0.0 | 43.0% | 44.1% | +1.1 pp | 4 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=1 checksum=none budget=268435456 yield=dirty_poll | 15.683 | 17.198 | +9.7% | 15.683 | 17.198 | 0.0 | 0.0 | 82.7% | 72.3% | -10.4 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=1 checksum=none budget=268435456 yield=none | 15.683 | 16.717 | +6.6% | 15.683 | 16.717 | 0.0 | 0.0 | 82.7% | 79.0% | -3.7 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=1 checksum=none budget=67108864 yield=dirty_poll | 15.683 | 16.521 | +5.3% | 15.683 | 16.521 | 0.0 | 0.0 | 82.7% | 69.5% | -13.2 pp | 4 | 0.004 | 4 |
| bytes=268435456 backend=posix tls=off/off conn=1 checksum=none budget=67108864 yield=none | 15.683 | 15.498 | -1.2% | 15.683 | 15.498 | 0.0 | 0.0 | 82.7% | 81.3% | -1.4 pp | 4 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=4 checksum=crc32c budget=268435456 yield=dirty_poll | 9.552 | 9.914 | +3.8% | 9.552 | 9.914 | 0.0 | 0.0 | 47.0% | 46.9% | -0.1 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=4 checksum=crc32c budget=268435456 yield=none | 9.552 | 9.191 | -3.8% | 9.552 | 9.191 | 0.0 | 0.0 | 47.0% | 49.5% | +2.5 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=4 checksum=crc32c budget=67108864 yield=dirty_poll | 9.552 | 9.270 | -3.0% | 9.552 | 9.270 | 0.0 | 0.0 | 47.0% | 45.2% | -1.8 pp | 4 | 0.004 | 4 |
| bytes=268435456 backend=posix tls=off/off conn=4 checksum=crc32c budget=67108864 yield=none | 9.552 | 10.001 | +4.7% | 9.552 | 10.001 | 0.0 | 0.0 | 47.0% | 46.9% | -0.1 pp | 4 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=4 checksum=none budget=268435456 yield=dirty_poll | 11.396 | 15.492 | +35.9% | 11.396 | 15.492 | 0.0 | 0.0 | 56.0% | 82.0% | +26.0 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=4 checksum=none budget=268435456 yield=none | 11.396 | 13.957 | +22.5% | 11.396 | 13.957 | 0.0 | 0.0 | 56.0% | 71.7% | +15.6 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=4 checksum=none budget=67108864 yield=dirty_poll | 11.396 | 15.668 | +37.5% | 11.396 | 15.668 | 0.0 | 0.0 | 56.0% | 72.3% | +16.2 pp | 4 | 0.004 | 4 |
| bytes=268435456 backend=posix tls=off/off conn=4 checksum=none budget=67108864 yield=none | 11.396 | 13.056 | +14.6% | 11.396 | 13.056 | 0.0 | 0.0 | 56.0% | 72.7% | +16.7 pp | 4 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=8 checksum=crc32c budget=268435456 yield=dirty_poll | 9.118 | 9.855 | +8.1% | 9.118 | 9.855 | 0.0 | 0.0 | 49.3% | 45.9% | -3.4 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=8 checksum=crc32c budget=268435456 yield=none | 9.118 | 9.923 | +8.8% | 9.118 | 9.923 | 0.0 | 0.0 | 49.3% | 48.1% | -1.2 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=8 checksum=crc32c budget=67108864 yield=dirty_poll | 9.118 | 9.706 | +6.4% | 9.118 | 9.706 | 0.0 | 0.0 | 49.3% | 46.4% | -2.9 pp | 4 | 0.004 | 4 |
| bytes=268435456 backend=posix tls=off/off conn=8 checksum=crc32c budget=67108864 yield=none | 9.118 | 9.748 | +6.9% | 9.118 | 9.748 | 0.0 | 0.0 | 49.3% | 49.2% | -0.1 pp | 4 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=8 checksum=none budget=268435456 yield=dirty_poll | 14.664 | 15.053 | +2.7% | 14.664 | 15.053 | 0.0 | 0.0 | 79.8% | 72.8% | -7.0 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=8 checksum=none budget=268435456 yield=none | 14.664 | 13.020 | -11.2% | 14.664 | 13.020 | 0.0 | 0.0 | 79.8% | 62.4% | -17.4 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=8 checksum=none budget=67108864 yield=dirty_poll | 14.664 | 14.371 | -2.0% | 14.664 | 14.371 | 0.0 | 0.0 | 79.8% | 67.8% | -11.9 pp | 4 | 0.004 | 4 |
| bytes=268435456 backend=posix tls=off/off conn=8 checksum=none budget=67108864 yield=none | 14.664 | 14.796 | +0.9% | 14.664 | 14.796 | 0.0 | 0.0 | 79.8% | 72.8% | -7.0 pp | 4 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=1 checksum=crc32c budget=268435456 yield=dirty_poll | 7.387 | 7.047 | -4.6% | 7.387 | 7.047 | 0.0 | 0.0 | 33.4% | 36.9% | +3.5 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=1 checksum=crc32c budget=268435456 yield=none | 7.387 | 7.680 | +4.0% | 7.387 | 7.680 | 0.0 | 0.0 | 33.4% | 34.1% | +0.7 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=1 checksum=crc32c budget=67108864 yield=dirty_poll | 7.387 | 7.189 | -2.7% | 7.387 | 7.189 | 0.0 | 0.0 | 33.4% | 33.1% | -0.3 pp | 4 | 0.004 | 4 |
| bytes=268435456 backend=posix tls=required/required conn=1 checksum=crc32c budget=67108864 yield=none | 7.387 | 7.377 | -0.1% | 7.387 | 7.377 | 0.0 | 0.0 | 33.4% | 34.5% | +1.1 pp | 4 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=1 checksum=none budget=268435456 yield=dirty_poll | 10.260 | 10.586 | +3.2% | 10.260 | 10.586 | 0.0 | 0.0 | 48.1% | 45.2% | -3.0 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=1 checksum=none budget=268435456 yield=none | 10.260 | 10.153 | -1.0% | 10.260 | 10.153 | 0.0 | 0.0 | 48.1% | 48.7% | +0.5 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=1 checksum=none budget=67108864 yield=dirty_poll | 10.260 | 10.153 | -1.0% | 10.260 | 10.153 | 0.0 | 0.0 | 48.1% | 43.6% | -4.5 pp | 4 | 0.005 | 4 |
| bytes=268435456 backend=posix tls=required/required conn=1 checksum=none budget=67108864 yield=none | 10.260 | 9.274 | -9.6% | 10.260 | 9.274 | 0.0 | 0.0 | 48.1% | 50.7% | +2.5 pp | 4 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=4 checksum=crc32c budget=268435456 yield=dirty_poll | 7.027 | 7.088 | +0.9% | 7.027 | 7.088 | 0.0 | 0.0 | 33.7% | 33.8% | +0.0 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=4 checksum=crc32c budget=268435456 yield=none | 7.027 | 7.382 | +5.0% | 7.027 | 7.382 | 0.0 | 0.0 | 33.7% | 33.6% | -0.1 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=4 checksum=crc32c budget=67108864 yield=dirty_poll | 7.027 | 7.223 | +2.8% | 7.027 | 7.223 | 0.0 | 0.0 | 33.7% | 34.2% | +0.4 pp | 4 | 0.004 | 4 |
| bytes=268435456 backend=posix tls=required/required conn=4 checksum=crc32c budget=67108864 yield=none | 7.027 | 7.438 | +5.9% | 7.027 | 7.438 | 0.0 | 0.0 | 33.7% | 33.7% | -0.0 pp | 4 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=4 checksum=none budget=268435456 yield=dirty_poll | 9.781 | 10.564 | +8.0% | 9.781 | 10.564 | 0.0 | 0.0 | 44.5% | 47.5% | +3.0 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=4 checksum=none budget=268435456 yield=none | 9.781 | 10.123 | +3.5% | 9.781 | 10.123 | 0.0 | 0.0 | 44.5% | 43.4% | -1.1 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=4 checksum=none budget=67108864 yield=dirty_poll | 9.781 | 8.699 | -11.1% | 9.781 | 8.699 | 0.0 | 0.0 | 44.5% | 42.2% | -2.3 pp | 4 | 0.004 | 4 |
| bytes=268435456 backend=posix tls=required/required conn=4 checksum=none budget=67108864 yield=none | 9.781 | 10.363 | +6.0% | 9.781 | 10.363 | 0.0 | 0.0 | 44.5% | 48.2% | +3.7 pp | 4 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=8 checksum=crc32c budget=268435456 yield=dirty_poll | 7.457 | 6.890 | -7.6% | 7.457 | 6.890 | 0.0 | 0.0 | 32.4% | 33.3% | +0.9 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=8 checksum=crc32c budget=268435456 yield=none | 7.457 | 6.880 | -7.7% | 7.457 | 6.880 | 0.0 | 0.0 | 32.4% | 36.4% | +4.0 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=8 checksum=crc32c budget=67108864 yield=dirty_poll | 7.457 | 7.085 | -5.0% | 7.457 | 7.085 | 0.0 | 0.0 | 32.4% | 31.8% | -0.6 pp | 4 | 0.004 | 4 |
| bytes=268435456 backend=posix tls=required/required conn=8 checksum=crc32c budget=67108864 yield=none | 7.457 | 7.427 | -0.4% | 7.457 | 7.427 | 0.0 | 0.0 | 32.4% | 33.7% | +1.3 pp | 4 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=8 checksum=none budget=268435456 yield=dirty_poll | 9.241 | 9.952 | +7.7% | 9.241 | 9.952 | 0.0 | 0.0 | 42.9% | 47.8% | +5.0 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=8 checksum=none budget=268435456 yield=none | 9.241 | 9.929 | +7.4% | 9.241 | 9.929 | 0.0 | 0.0 | 42.9% | 46.3% | +3.4 pp | 1 | 0.000 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=8 checksum=none budget=67108864 yield=dirty_poll | 9.241 | 10.182 | +10.2% | 9.241 | 10.182 | 0.0 | 0.0 | 42.9% | 43.6% | +0.7 pp | 4 | 0.004 | 4 |
| bytes=268435456 backend=posix tls=required/required conn=8 checksum=none budget=67108864 yield=none | 9.241 | 9.989 | +8.1% | 9.241 | 9.989 | 0.0 | 0.0 | 42.9% | 44.3% | +1.4 pp | 4 | 0.000 | 0 |


## Dirty Poll Independent Value

`dirty_poll` is compared with `none` for the same bounded budget and matched transfer dimensions. The Dirty+Writeback threshold remains tied to `receiver_max_pending_bytes`.

| dirty_poll case | none Gbps | dirty_poll Gbps | delta | none spread % | dirty spread % | yield count |
| --- | --- | --- | --- | --- | --- | --- |
| bytes=268435456 backend=io_uring tls=off/off conn=4 checksum=crc32c budget=268435456 yield=dirty_poll | 8.301 | 8.210 | -1.1% | 0.0 | 0.0 | 0 |
| bytes=268435456 backend=io_uring tls=off/off conn=4 checksum=crc32c budget=67108864 yield=dirty_poll | 9.019 | 8.418 | -6.7% | 0.0 | 0.0 | 4 |
| bytes=268435456 backend=posix tls=off/off conn=1 checksum=crc32c budget=268435456 yield=dirty_poll | 9.737 | 9.298 | -4.5% | 0.0 | 0.0 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=1 checksum=crc32c budget=67108864 yield=dirty_poll | 9.753 | 10.136 | +3.9% | 0.0 | 0.0 | 4 |
| bytes=268435456 backend=posix tls=off/off conn=1 checksum=none budget=268435456 yield=dirty_poll | 16.717 | 17.198 | +2.9% | 0.0 | 0.0 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=1 checksum=none budget=67108864 yield=dirty_poll | 15.498 | 16.521 | +6.6% | 0.0 | 0.0 | 4 |
| bytes=268435456 backend=posix tls=off/off conn=4 checksum=crc32c budget=268435456 yield=dirty_poll | 9.191 | 9.914 | +7.9% | 0.0 | 0.0 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=4 checksum=crc32c budget=67108864 yield=dirty_poll | 10.001 | 9.270 | -7.3% | 0.0 | 0.0 | 4 |
| bytes=268435456 backend=posix tls=off/off conn=4 checksum=none budget=268435456 yield=dirty_poll | 13.957 | 15.492 | +11.0% | 0.0 | 0.0 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=4 checksum=none budget=67108864 yield=dirty_poll | 13.056 | 15.668 | +20.0% | 0.0 | 0.0 | 4 |
| bytes=268435456 backend=posix tls=off/off conn=8 checksum=crc32c budget=268435456 yield=dirty_poll | 9.923 | 9.855 | -0.7% | 0.0 | 0.0 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=8 checksum=crc32c budget=67108864 yield=dirty_poll | 9.748 | 9.706 | -0.4% | 0.0 | 0.0 | 4 |
| bytes=268435456 backend=posix tls=off/off conn=8 checksum=none budget=268435456 yield=dirty_poll | 13.020 | 15.053 | +15.6% | 0.0 | 0.0 | 0 |
| bytes=268435456 backend=posix tls=off/off conn=8 checksum=none budget=67108864 yield=dirty_poll | 14.796 | 14.371 | -2.9% | 0.0 | 0.0 | 4 |
| bytes=268435456 backend=posix tls=required/required conn=1 checksum=crc32c budget=268435456 yield=dirty_poll | 7.680 | 7.047 | -8.2% | 0.0 | 0.0 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=1 checksum=crc32c budget=67108864 yield=dirty_poll | 7.377 | 7.189 | -2.5% | 0.0 | 0.0 | 4 |
| bytes=268435456 backend=posix tls=required/required conn=1 checksum=none budget=268435456 yield=dirty_poll | 10.153 | 10.586 | +4.3% | 0.0 | 0.0 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=1 checksum=none budget=67108864 yield=dirty_poll | 9.274 | 10.153 | +9.5% | 0.0 | 0.0 | 4 |
| bytes=268435456 backend=posix tls=required/required conn=4 checksum=crc32c budget=268435456 yield=dirty_poll | 7.382 | 7.088 | -4.0% | 0.0 | 0.0 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=4 checksum=crc32c budget=67108864 yield=dirty_poll | 7.438 | 7.223 | -2.9% | 0.0 | 0.0 | 4 |
| bytes=268435456 backend=posix tls=required/required conn=4 checksum=none budget=268435456 yield=dirty_poll | 10.123 | 10.564 | +4.4% | 0.0 | 0.0 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=4 checksum=none budget=67108864 yield=dirty_poll | 10.363 | 8.699 | -16.1% | 0.0 | 0.0 | 4 |
| bytes=268435456 backend=posix tls=required/required conn=8 checksum=crc32c budget=268435456 yield=dirty_poll | 6.880 | 6.890 | +0.1% | 0.0 | 0.0 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=8 checksum=crc32c budget=67108864 yield=dirty_poll | 7.427 | 7.085 | -4.6% | 0.0 | 0.0 | 4 |
| bytes=268435456 backend=posix tls=required/required conn=8 checksum=none budget=268435456 yield=dirty_poll | 9.929 | 9.952 | +0.2% | 0.0 | 0.0 | 0 |
| bytes=268435456 backend=posix tls=required/required conn=8 checksum=none budget=67108864 yield=dirty_poll | 9.989 | 10.182 | +1.9% | 0.0 | 0.0 | 4 |


## Dirty/Writeback And Artifacts

Dirty, Writeback, and Cached values are read from the existing environment sidecars before and after each case. Event logs and iostat sidecars remain per-case artifacts.

| event log | server env before | server env after | iostat |
| --- | --- | --- | --- |
| /root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071327Z_c0000r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwdef0n_tlsoff_dtlsoff_server_events.jsonl;/root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071327Z_c0000r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwdef0n_tlsoff_dtlsoff_client_events.jsonl | tools/perf/results/20260520T071327Z_c0000r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwdef0n_tlsoff_dtlsoff_server_env_before.log | tools/perf/results/20260520T071327Z_c0000r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwdef0n_tlsoff_dtlsoff_server_env_after.log | tools/perf/results/20260520T071327Z_c0000r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwdef0n_tlsoff_dtlsoff_server_env_after.log#section=iostat |
| /root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071330Z_c0001r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mn_tlsoff_dtlsoff_server_events.jsonl;/root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071330Z_c0001r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mn_tlsoff_dtlsoff_client_events.jsonl | tools/perf/results/20260520T071330Z_c0001r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mn_tlsoff_dtlsoff_server_env_before.log | tools/perf/results/20260520T071330Z_c0001r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mn_tlsoff_dtlsoff_server_env_after.log | tools/perf/results/20260520T071330Z_c0001r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mn_tlsoff_dtlsoff_server_env_after.log#section=iostat |
| /root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071332Z_c0002r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mdp_tlsoff_dtlsoff_server_events.jsonl;/root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071332Z_c0002r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mdp_tlsoff_dtlsoff_client_events.jsonl | tools/perf/results/20260520T071332Z_c0002r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mdp_tlsoff_dtlsoff_server_env_before.log | tools/perf/results/20260520T071332Z_c0002r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mdp_tlsoff_dtlsoff_server_env_after.log | tools/perf/results/20260520T071332Z_c0002r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mdp_tlsoff_dtlsoff_server_env_after.log#section=iostat |
| /root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071335Z_c0003r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd256mn_tlsoff_dtlsoff_server_events.jsonl;/root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071335Z_c0003r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd256mn_tlsoff_dtlsoff_client_events.jsonl | tools/perf/results/20260520T071335Z_c0003r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd256mn_tlsoff_dtlsoff_server_env_before.log | tools/perf/results/20260520T071335Z_c0003r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd256mn_tlsoff_dtlsoff_server_env_after.log | tools/perf/results/20260520T071335Z_c0003r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd256mn_tlsoff_dtlsoff_server_env_after.log#section=iostat |
| /root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071338Z_c0004r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd256mdp_tlsoff_dtlsoff_server_events.jsonl;/root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071338Z_c0004r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd256mdp_tlsoff_dtlsoff_client_events.jsonl | tools/perf/results/20260520T071338Z_c0004r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd256mdp_tlsoff_dtlsoff_server_env_before.log | tools/perf/results/20260520T071338Z_c0004r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd256mdp_tlsoff_dtlsoff_server_env_after.log | tools/perf/results/20260520T071338Z_c0004r00_stor_b268435456_c1_k4194304_nb262144_crc32c_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd256mdp_tlsoff_dtlsoff_server_env_after.log#section=iostat |
| /root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071340Z_c0005r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwdef0n_tlsoff_dtlsoff_server_events.jsonl;/root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071340Z_c0005r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwdef0n_tlsoff_dtlsoff_client_events.jsonl | tools/perf/results/20260520T071340Z_c0005r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwdef0n_tlsoff_dtlsoff_server_env_before.log | tools/perf/results/20260520T071340Z_c0005r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwdef0n_tlsoff_dtlsoff_server_env_after.log | tools/perf/results/20260520T071340Z_c0005r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwdef0n_tlsoff_dtlsoff_server_env_after.log#section=iostat |
| /root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071343Z_c0006r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mn_tlsoff_dtlsoff_server_events.jsonl;/root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071343Z_c0006r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mn_tlsoff_dtlsoff_client_events.jsonl | tools/perf/results/20260520T071343Z_c0006r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mn_tlsoff_dtlsoff_server_env_before.log | tools/perf/results/20260520T071343Z_c0006r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mn_tlsoff_dtlsoff_server_env_after.log | tools/perf/results/20260520T071343Z_c0006r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mn_tlsoff_dtlsoff_server_env_after.log#section=iostat |
| /root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071346Z_c0007r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mdp_tlsoff_dtlsoff_server_events.jsonl;/root/projects/GridFlux/tools/perf/results/20260520T071326Z_beta1b-receiver-writeback-stability/events/20260520T071346Z_c0007r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mdp_tlsoff_dtlsoff_client_events.jsonl | tools/perf/results/20260520T071346Z_c0007r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mdp_tlsoff_dtlsoff_server_env_before.log | tools/perf/results/20260520T071346Z_c0007r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mdp_tlsoff_dtlsoff_server_env_after.log | tools/perf/results/20260520T071346Z_c0007r00_stor_b268435456_c1_k4194304_nb262144_n_preoff_fvfull_mfenc16_csn_fioposix0_q1x1_advoff_pwsauto_rwbnd64mdp_tlsoff_dtlsoff_server_env_after.log#section=iostat |


## Required Answers

- Stable improvements: see the aggregate table `>=5% wins` and the matched comparison table.
- Stable regressions: see the aggregate table `<=-5% regressions` and matched median deltas.
- Dirty-poll value: see the dirty_poll independent table; value requires wins without matching regressions.
- TLS/data TLS impact: required/required rows are counted in the executive summary and gate decision.
- User-space queue: only recommended if bounded wins clearly dominate regressions and TLS required/required does not net regress.
- Storage/system direction: recommended when bounded regressions match or exceed wins.

## Gate Decision

- Grouped fail count: `0`.
- Matched bounded comparisons: `52`.
- Median-throughput improvements `>=5%`: `20`.
- Median-throughput regressions `<=-5%`: `9`.
- Dirty-poll independent pairs: `26`; wins `6`, regressions `4`.
- TLS/data TLS required bounded rows: `24`; regressions `4`.
- Recommendation: keep bounded receiver writeback opt-in and expand only the winning budget/yield rows before designing an independent user-space queue.
- Default policy remains unchanged.

## Non-Goals Preserved

- No default policy changes.
- No independent user-space write queue or worker pool.
- No QUIC, FEC, RDMA, or GSI work.
- No root-only OS tuning.
