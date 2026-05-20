# Baseline FTP / GridFTP Smoke

Generated: 2026-05-20T11:22:13Z

## Executive Summary

This is a lightweight comparison baseline on the existing two cloud servers. It is not a GridFlux release gate, and it does not change GridFlux defaults or C++ transfer code.

- FTP baseline status: `pass`.
- GridFTP baseline status: `unavailable_requires_gsi_or_server_start_failed:globus-gridftp-server did not open the baseline GridFTP port`.
- FTP 80 MB/s comparison: no, median 235.9 MiB/s is not near 80 MB/s.
- GridFTP 80 MB/s comparison: no passing rows.

## Artifacts

- Environment: `tools/perf/results/20260520T112036Z_baseline_env.txt`
- FTP CSV: `tools/perf/results/20260520T112036Z_ftp-baseline.csv`
- GridFTP status: `tools/perf/results/20260520T112036Z_gridftp-baseline-status.txt`

## FTP Results

| protocol | direction | bytes | MiB/s | Gbps | status | sha256 | notes |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| ftp | upload | 268435456 | 188.012 | 1.577 | pass | yes |  |
| ftp | download | 268435456 | 1474.680 | 12.371 | pass | yes |  |
| ftp | upload | 1073741824 | 122.772 | 1.030 | pass | yes |  |
| ftp | download | 1073741824 | 235.891 | 1.979 | pass | yes |  |

## GridFTP Results

_No passing rows._

## Current GridFlux Context

Beta 1C RETR focused matrix reported median/best RETR throughput of `3.457 / 4.675 Gbps`; Beta 1B-5 attributed STOR write bottlenecks mostly to cloud storage, filesystem, page cache, and OS writeback behavior. This baseline smoke is only a comparison point for ordinary FTP/GridFTP in the same environment.

## Cleanup

- Removed directories: `/tmp/gridflux-baseline-*`
- Server cleanup status: `pass`
- Client cleanup status: `pass`
- Server residual processes: `none`
- Client residual processes: `none`

## Limits

- Only `256MiB` and `1GiB` are tested by default.
- GridFTP uses system packages only. If packages or anonymous/no-GSI operation are unavailable, the result is recorded as unavailable rather than compiled from source.
- No server passwords, tokens, or private keys are written to this report.
