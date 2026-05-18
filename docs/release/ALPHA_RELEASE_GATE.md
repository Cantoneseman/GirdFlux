# GridFlux Alpha Release Gate

- Timestamp: `2026-05-18T02:38:20Z`
- Mode: `full`
- Source tree hash: `0f3f9a32fcad76432b45b2b23c8648fb40296de72b69878406cb0d9edc70a72d`
- Result: `pass`

## Step Results

| Step | Status | Seconds | Log |
|------|--------|---------|-----|
| `build_debug` | `pass` | `0.01` | `/root/projects/GridFlux/tools/perf/results/20260518T023057Z_alpha-release-gate/build_debug.log` |
| `ctest_debug` | `pass` | `8.38` | `/root/projects/GridFlux/tools/perf/results/20260518T023057Z_alpha-release-gate/ctest_debug.log` |
| `ctest_iouring` | `pass` | `8.22` | `/root/projects/GridFlux/tools/perf/results/20260518T023057Z_alpha-release-gate/ctest_iouring.log` |
| `ctest_iouring_smoke` | `pass` | `0.01` | `/root/projects/GridFlux/tools/perf/results/20260518T023057Z_alpha-release-gate/ctest_iouring_smoke.log` |
| `public_export_hygiene` | `pass` | `0.30` | `/root/projects/GridFlux/tools/perf/results/20260518T023057Z_alpha-release-gate/public_export_hygiene.log` |
| `stor_smoke` | `pass` | `0.13` | `/root/projects/GridFlux/tools/perf/results/20260518T023057Z_alpha-release-gate/stor_smoke.log` |
| `retr_smoke` | `pass` | `0.29` | `/root/projects/GridFlux/tools/perf/results/20260518T023057Z_alpha-release-gate/retr_smoke.log` |
| `stor_resume_smoke` | `pass` | `0.18` | `/root/projects/GridFlux/tools/perf/results/20260518T023057Z_alpha-release-gate/stor_resume_smoke.log` |
| `retr_resume_smoke` | `pass` | `0.19` | `/root/projects/GridFlux/tools/perf/results/20260518T023057Z_alpha-release-gate/retr_resume_smoke.log` |
| `metadata_smoke` | `pass` | `0.07` | `/root/projects/GridFlux/tools/perf/results/20260518T023057Z_alpha-release-gate/metadata_smoke.log` |
| `list_smoke` | `pass` | `0.16` | `/root/projects/GridFlux/tools/perf/results/20260518T023057Z_alpha-release-gate/list_smoke.log` |
| `private_baseline_matrix` | `pass` | `423.93` | `/root/projects/GridFlux/tools/perf/results/20260518T023057Z_alpha-release-gate/private_baseline_matrix.log` |
| `artifact_rsync` | `pass` | `0.32` | `/root/projects/GridFlux/tools/perf/results/20260518T023820Z_alpha-artifact-rsync.log` |
| `remote_artifact_sync_check` | `pass` | `22.96` | `/root/projects/GridFlux/tools/perf/results/20260518T023057Z_alpha-release-gate/remote_artifact_sync_check.log` |

## Private Baseline

- Raw CSV: `tools/perf/results/20260518T023115Z_gridftp-private-matrix-smoke.csv`
- Summary CSV: `tools/perf/results/20260518T023115Z_gridftp-private-matrix-smoke-summary.csv`
- Fail count: `0`
- Summary rows: `8`

Default baseline rows:

- direction=retr throughput_median=3.395120 spread_pct=40.870720
- direction=stor throughput_median=0.919468 spread_pct=19.548261

## Alpha Readiness

- Alpha scope is demonstrable GridFTP-like framed STOR/RETR, bidirectional resume, CRC32C chunk verification, and control metadata commands.
- Not beta/production: performance spread remains significant, 100G dedicated-line validation is not complete, and TLS/GSI/raw FTP stream/directory sync are out of scope.
- Defaults remain POSIX backend, full final verify, every_n_chunks manifest flush, no commit fsync, no preallocate full, and no default io_uring.

## Residual Process Check

- Local: ``
- Remote: ``

## Failures

- None.
