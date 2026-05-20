# FTP / GridFTP / GridFlux Three-Way Comparison

Generated: 2026-05-20T12:27:24Z

## Executive Summary

This report compares plain FTP, native Globus GridFTP, and the current GridFlux prototype between the two Alibaba Cloud servers over the private network. It is a measurement report only: no GridFlux C++ code or default policy was changed.

- Plain FTP rows: `8`.
- Native GridFTP rows: `24`.
- GridFlux rows: `48`.
- Fair 1GiB upload/STOR best comparison: FTP `1.046 Gbps`, native GridFTP `1.700 Gbps`, GridFlux `1.692 Gbps`.
- Fair 1GiB download/RETR best comparison: FTP `0.953 Gbps`, native GridFTP `0.998 Gbps`, GridFlux `5.566 Gbps`.
- GridFlux 256MiB peaks are much higher, but they are short-file/page-cache observations and are not presented as long-duration sustained throughput.

## Artifacts

- environment: `tools/perf/results/20260520T120942Z_three-way-env.txt`
- host_baseline: `tools/perf/results/20260520T120942Z_three-way-host-baseline.csv`
- input_sha256: `tools/perf/results/20260520T120942Z_three-way-input-sha256.txt`
- plain_ftp: `tools/perf/results/20260520T120942Z_plain-ftp-three-way.csv`
- native_gridftp: `tools/perf/results/20260520T120942Z_native-gridftp-three-way.csv`
- gridflux: `tools/perf/results/20260520T120942Z_gridflux-three-way.csv`
- summary: `tools/perf/results/20260520T120942Z_ftp-gridftp-gridflux-summary.csv`
- report: `docs/perf/FTP_GRIDFTP_GRIDFLUX_COMPARISON.md`
- GridFlux raw matrix: `tools/perf/results/20260520T121744Z_gridftp-private-matrix-smoke.csv`
- GridFlux matrix summary: `tools/perf/results/20260520T121744Z_gridftp-private-matrix-smoke-summary.csv`

## Visual Summary / 图表摘要

![1GiB upload / STOR best throughput](figures/three_way_1g_upload_best.png)

GridFlux and native GridFTP are effectively tied on the fair 1GiB upload/STOR view, and both are clearly faster than plain FTP.

![1GiB download / RETR best throughput](figures/three_way_1g_download_best.png)

GridFlux is clearly ahead on the fair 1GiB download/RETR view in this run.

![10GB estimated transfer time from 1GiB best throughput](figures/three_way_10gb_estimated_time.png)

Using the best 1GiB throughput as the estimate input, GridFlux's strongest practical advantage in this run is download/RETR time.

![Network and storage baseline context](figures/three_way_baseline_context.png)

The cloud servers have about `15.5 Gbps` private-network headroom but only about `128.6 MB/s` local write throughput, which is the key context for STOR bottlenecks.

![GridFlux short-file peak versus 1GiB best](figures/gridflux_short_vs_1g.png)

The 256MiB GridFlux peaks are shown only as short-file/cache observations. They are not used as the fair sustained headline.

## Network And Storage Baseline

| kind | machine | operation | parallelism | MBps | Gbps | status |
| --- | --- | --- | ---: | ---: | ---: | --- |
| iperf3 | client_to_server | network | 1 |  | 15.687 | pass |
| iperf3 | client_to_server | network | 4 |  | 15.688 | pass |
| iperf3 | client_to_server | network | 8 |  | 15.203 | pass |
| storage | server | write_1GiB_tmp | 1 | 128.731 | 1.030 | pass |
| storage | client | write_1GiB_tmp | 1 | 128.512 | 1.028 | pass |

## Summary Table

| protocol | direction | size | p/conn | checksum | median Gbps | best Gbps | samples | fail | mismatch |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| gridflux | retr | 1073741824 | 1 | crc32c | 0.245 | 0.266 | 2 | 0 | 0 |
| gridflux | retr | 1073741824 | 1 | none | 3.461 | 3.712 | 2 | 0 | 0 |
| gridflux | retr | 1073741824 | 4 | crc32c | 3.712 | 3.948 | 2 | 0 | 0 |
| gridflux | retr | 1073741824 | 4 | none | 4.861 | 4.882 | 2 | 0 | 0 |
| gridflux | retr | 1073741824 | 8 | crc32c | 3.845 | 3.901 | 2 | 0 | 0 |
| gridflux | retr | 1073741824 | 8 | none | 5.337 | 5.566 | 2 | 0 | 0 |
| gridflux | retr | 268435456 | 1 | crc32c | 6.015 | 8.037 | 2 | 0 | 0 |
| gridflux | retr | 268435456 | 1 | none | 9.733 | 18.385 | 2 | 0 | 0 |
| gridflux | retr | 268435456 | 4 | crc32c | 3.968 | 6.413 | 2 | 0 | 0 |
| gridflux | retr | 268435456 | 4 | none | 12.204 | 13.683 | 2 | 0 | 0 |
| gridflux | retr | 268435456 | 8 | crc32c | 4.192 | 7.173 | 2 | 0 | 0 |
| gridflux | retr | 268435456 | 8 | none | 6.093 | 6.139 | 2 | 0 | 0 |
| gridflux | stor | 1073741824 | 1 | crc32c | 1.020 | 1.564 | 2 | 0 | 0 |
| gridflux | stor | 1073741824 | 1 | none | 1.615 | 1.652 | 2 | 0 | 0 |
| gridflux | stor | 1073741824 | 4 | crc32c | 1.579 | 1.599 | 2 | 0 | 0 |
| gridflux | stor | 1073741824 | 4 | none | 1.610 | 1.611 | 2 | 0 | 0 |
| gridflux | stor | 1073741824 | 8 | crc32c | 1.476 | 1.527 | 2 | 0 | 0 |
| gridflux | stor | 1073741824 | 8 | none | 1.664 | 1.692 | 2 | 0 | 0 |
| gridflux | stor | 268435456 | 1 | crc32c | 7.534 | 7.887 | 2 | 0 | 0 |
| gridflux | stor | 268435456 | 1 | none | 16.239 | 17.593 | 2 | 0 | 0 |
| gridflux | stor | 268435456 | 4 | crc32c | 6.832 | 7.741 | 2 | 0 | 0 |
| gridflux | stor | 268435456 | 4 | none | 15.160 | 15.767 | 2 | 0 | 0 |
| gridflux | stor | 268435456 | 8 | crc32c | 7.094 | 7.294 | 2 | 0 | 0 |
| gridflux | stor | 268435456 | 8 | none | 13.402 | 14.385 | 2 | 0 | 0 |
| native_gridftp | download | 1073741824 | 1 |  | 0.937 | 0.941 | 2 | 0 | 0 |
| native_gridftp | download | 1073741824 | 4 |  | 0.967 | 0.976 | 2 | 0 | 0 |
| native_gridftp | download | 1073741824 | 8 |  | 0.991 | 0.998 | 2 | 0 | 0 |
| native_gridftp | download | 268435456 | 1 |  | 5.712 | 10.485 | 2 | 0 | 0 |
| native_gridftp | download | 268435456 | 4 |  | 6.082 | 10.277 | 2 | 0 | 0 |
| native_gridftp | download | 268435456 | 8 |  | 7.739 | 10.370 | 2 | 0 | 0 |
| native_gridftp | upload | 1073741824 | 1 |  | 1.544 | 1.624 | 2 | 0 | 0 |
| native_gridftp | upload | 1073741824 | 4 |  | 1.665 | 1.700 | 2 | 0 | 0 |
| native_gridftp | upload | 1073741824 | 8 |  | 1.654 | 1.687 | 2 | 0 | 0 |
| native_gridftp | upload | 268435456 | 1 |  | 4.348 | 6.945 | 2 | 0 | 0 |
| native_gridftp | upload | 268435456 | 4 |  | 6.873 | 8.151 | 2 | 0 | 0 |
| native_gridftp | upload | 268435456 | 8 |  | 8.418 | 10.321 | 2 | 0 | 0 |
| plain_ftp | download | 1073741824 | 1 |  | 0.905 | 0.953 | 2 | 0 | 0 |
| plain_ftp | download | 268435456 | 1 |  | 6.976 | 12.243 | 2 | 0 | 0 |
| plain_ftp | upload | 1073741824 | 1 |  | 0.895 | 1.046 | 2 | 0 | 0 |
| plain_ftp | upload | 268435456 | 1 |  | 1.633 | 1.671 | 2 | 0 | 0 |

## Short-File Observations

- 256MiB GridFlux STOR checksum `none` peaks at `17.593 Gbps`.
- 256MiB GridFlux RETR checksum `none` peaks at `18.385 Gbps`.
- These values are useful for observing cache-friendly short-file behavior, but they are not treated as sustained long-duration throughput claims.

## Best 1GiB Results

- best 1GiB upload/STOR: `native_gridftp` `upload` best `1.700 Gbps`; 1GiB measured-size estimate `5.05s`, 10GB estimate `47.06s`.
- best 1GiB download/RETR: `gridflux` `retr` best `5.566 Gbps`; 1GiB measured-size estimate `1.54s`, 10GB estimate `14.37s`.
- 10GB estimated upload/STOR time from best 1GiB rows: FTP `76.48s`, native GridFTP `47.06s`, GridFlux `47.28s`.
- 10GB estimated download/RETR time from best 1GiB rows: FTP `83.94s`, native GridFTP `80.16s`, GridFlux `14.37s`.

## Fair Conclusion

- Plain FTP is a low-friction single-stream baseline.
- Native GridFTP is the mature high-performance baseline when anonymous/no-GSI operation succeeds in this temporary setup.
- GridFlux is the current prototype; any advantage is based only on hash-valid CSV rows in this report.
- If GridFlux is not faster in every scenario, its current differentiators remain reliable resume semantics, manifest/checksum verification, event logs, directory transfer, and room for targeted optimization.

## Cleanup

- Removed paths: `/tmp/gridflux-three-way-* /tmp/xtransfer-baseline-*`
- Server residual processes: `none`
- Client residual processes: `none`
- Temporary GridFTP user removed: `yes`
