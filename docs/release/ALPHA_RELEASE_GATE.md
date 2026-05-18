# GridFlux Alpha Release Gate

- Timestamp: `2026-05-18T07:59:09Z`
- Mode: `full`
- Source tree hash: `5a0864f8e837dff03f99636303b94b6770dc871fae82bb1e41133325245131ca`
- Result: `pass`

## Step Results

| Step | Status | Seconds | Log |
|------|--------|---------|-----|
| `build_debug` | `pass` | `0.08` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/build_debug.log` |
| `ctest_debug` | `pass` | `15.05` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/ctest_debug.log` |
| `ctest_iouring` | `pass` | `14.97` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/ctest_iouring.log` |
| `ctest_iouring_smoke` | `pass` | `0.01` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/ctest_iouring_smoke.log` |
| `public_export_hygiene` | `pass` | `0.31` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/public_export_hygiene.log` |
| `stor_smoke` | `pass` | `0.12` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/stor_smoke.log` |
| `retr_smoke` | `pass` | `0.29` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/retr_smoke.log` |
| `stor_resume_smoke` | `pass` | `0.18` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/stor_resume_smoke.log` |
| `retr_resume_smoke` | `pass` | `0.19` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/retr_resume_smoke.log` |
| `metadata_smoke` | `pass` | `0.08` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/metadata_smoke.log` |
| `list_smoke` | `pass` | `0.16` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/list_smoke.log` |
| `tree_upload_smoke` | `pass` | `0.27` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/tree_upload_smoke.log` |
| `tree_download_smoke` | `pass` | `0.45` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/tree_download_smoke.log` |
| `tree_resume_smoke` | `pass` | `0.69` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/tree_resume_smoke.log` |
| `tree_parallel_smoke` | `pass` | `0.88` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/tree_parallel_smoke.log` |
| `tree_changed_file_smoke` | `pass` | `4.16` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/tree_changed_file_smoke.log` |
| `tree_manifest_corrupt_smoke` | `pass` | `0.18` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/tree_manifest_corrupt_smoke.log` |
| `tree_private_smoke` | `pass` | `4.26` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/tree_private_smoke.log` |
| `private_baseline_matrix` | `pass` | `588.16` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/private_baseline_matrix.log` |
| `remote_artifact_sync` | `pass` | `75.20` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/remote_artifact_sync.log` |
| `remote_artifact_sync_check` | `pass` | `37.88` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/remote_artifact_sync_check.log` |
| `remote_artifact_final_sync` | `pass` | `75.65` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/remote_artifact_final_sync.log` |
| `remote_artifact_final_verify` | `pass` | `37.63` | `/root/projects/GridFlux/tools/perf/results/20260518T074837Z_alpha-release-gate/remote_artifact_final_verify.log` |

## Private Baseline

- Raw CSV: `tools/perf/results/20260518T074920Z_gridftp-private-matrix-smoke.csv`
- Summary CSV: `tools/perf/results/20260518T074920Z_gridftp-private-matrix-smoke-summary.csv`
- Fail count: `0`
- Summary rows: `8`

Default baseline rows:

- direction=retr throughput_median=1.063130 spread_pct=20.590144
- direction=stor throughput_median=0.828087 spread_pct=22.006866

## Artifact Sync

- Manifest: `tools/perf/results/20260518T074837Z_alpha-artifacts.json`
- Artifacts: `249`
- Sync: checked=`250` synced=`3` missing=`0` mismatch=`0` status=`pass`
- Verify: checked=`250` missing=`0` mismatch=`0` status=`pass`

## Alpha Readiness

- Alpha scope is demonstrable GridFTP-like framed STOR/RETR, bidirectional resume, CRC32C chunk verification, and control metadata commands.
- Not beta/production: performance spread remains significant, 100G dedicated-line validation is not complete, and TLS/GSI/raw FTP stream/directory sync are out of scope.
- Defaults remain POSIX backend, full final verify, every_n_chunks manifest flush, no commit fsync, no preallocate full, and no default io_uring.

## Residual Process Check

- Local: ``
- Remote: ``

## Failures

- None.
