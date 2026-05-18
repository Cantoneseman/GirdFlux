# GridFlux Alpha Release Gate

- Timestamp: `2026-05-18T05:31:53Z`
- Mode: `full`
- Source tree hash: `efe66e252a8cc1e061225cecc681e90ddb8871fd96c09c75f1a5e21892c5ffc0`
- Result: `pass`

## Step Results

| Step | Status | Seconds | Log |
|------|--------|---------|-----|
| `build_debug` | `pass` | `0.12` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/build_debug.log` |
| `ctest_debug` | `pass` | `10.14` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/ctest_debug.log` |
| `ctest_iouring` | `pass` | `9.86` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/ctest_iouring.log` |
| `ctest_iouring_smoke` | `pass` | `0.01` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/ctest_iouring_smoke.log` |
| `public_export_hygiene` | `pass` | `0.30` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/public_export_hygiene.log` |
| `stor_smoke` | `pass` | `0.17` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/stor_smoke.log` |
| `retr_smoke` | `pass` | `0.28` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/retr_smoke.log` |
| `stor_resume_smoke` | `pass` | `0.17` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/stor_resume_smoke.log` |
| `retr_resume_smoke` | `pass` | `0.19` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/retr_resume_smoke.log` |
| `metadata_smoke` | `pass` | `0.07` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/metadata_smoke.log` |
| `list_smoke` | `pass` | `0.16` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/list_smoke.log` |
| `tree_upload_smoke` | `pass` | `0.32` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/tree_upload_smoke.log` |
| `tree_download_smoke` | `pass` | `0.40` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/tree_download_smoke.log` |
| `tree_resume_smoke` | `pass` | `0.75` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/tree_resume_smoke.log` |
| `tree_manifest_corrupt_smoke` | `pass` | `0.13` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/tree_manifest_corrupt_smoke.log` |
| `private_baseline_matrix` | `pass` | `528.11` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/private_baseline_matrix.log` |
| `remote_artifact_sync` | `pass` | `51.28` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/remote_artifact_sync.log` |
| `remote_artifact_sync_check` | `pass` | `25.84` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/remote_artifact_sync_check.log` |
| `remote_artifact_final_sync` | `pass` | `51.81` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/remote_artifact_final_sync.log` |
| `remote_artifact_final_verify` | `pass` | `25.77` | `/root/projects/GridFlux/tools/perf/results/20260518T052241Z_alpha-release-gate/remote_artifact_final_verify.log` |

## Private Baseline

- Raw CSV: `tools/perf/results/20260518T052304Z_gridftp-private-matrix-smoke.csv`
- Summary CSV: `tools/perf/results/20260518T052304Z_gridftp-private-matrix-smoke-summary.csv`
- Fail count: `0`
- Summary rows: `8`

Default baseline rows:

- direction=retr throughput_median=2.093320 spread_pct=53.894292
- direction=stor throughput_median=0.915823 spread_pct=20.899126

## Artifact Sync

- Manifest: `tools/perf/results/20260518T052241Z_alpha-artifacts.json`
- Artifacts: `170`
- Sync: checked=`171` synced=`3` missing=`0` mismatch=`0` status=`pass`
- Verify: checked=`171` missing=`0` mismatch=`0` status=`pass`

## Alpha Readiness

- Alpha scope is demonstrable GridFTP-like framed STOR/RETR, bidirectional resume, CRC32C chunk verification, and control metadata commands.
- Not beta/production: performance spread remains significant, 100G dedicated-line validation is not complete, and TLS/GSI/raw FTP stream/directory sync are out of scope.
- Defaults remain POSIX backend, full final verify, every_n_chunks manifest flush, no commit fsync, no preallocate full, and no default io_uring.

## Residual Process Check

- Local: ``
- Remote: ``

## Failures

- None.
