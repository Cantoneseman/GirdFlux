# GridFlux Alpha Release Gate

- Timestamp: `2026-05-18T11:16:47Z`
- Mode: `full`
- Source tree hash: `f44db05a0f70b48737fbfd0a7de97146cf2891a51a36e8f6e70b29f952b323eb`
- Result: `pass`

## Step Results

| Step | Status | Seconds | Log |
|------|--------|---------|-----|
| `build_debug` | `pass` | `0.11` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/build_debug.log` |
| `ctest_debug` | `pass` | `23.85` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/ctest_debug.log` |
| `ctest_iouring` | `pass` | `23.63` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/ctest_iouring.log` |
| `ctest_iouring_smoke` | `pass` | `0.01` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/ctest_iouring_smoke.log` |
| `public_export_hygiene` | `pass` | `0.33` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/public_export_hygiene.log` |
| `stor_smoke` | `pass` | `0.12` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/stor_smoke.log` |
| `retr_smoke` | `pass` | `0.29` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/retr_smoke.log` |
| `stor_resume_smoke` | `pass` | `0.19` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/stor_resume_smoke.log` |
| `retr_resume_smoke` | `pass` | `0.24` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/retr_resume_smoke.log` |
| `metadata_smoke` | `pass` | `0.07` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/metadata_smoke.log` |
| `list_smoke` | `pass` | `0.21` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/list_smoke.log` |
| `tree_upload_smoke` | `pass` | `0.27` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/tree_upload_smoke.log` |
| `tree_download_smoke` | `pass` | `0.45` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/tree_download_smoke.log` |
| `tree_resume_smoke` | `pass` | `0.72` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/tree_resume_smoke.log` |
| `tree_parallel_smoke` | `pass` | `0.87` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/tree_parallel_smoke.log` |
| `tree_changed_file_smoke` | `pass` | `4.16` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/tree_changed_file_smoke.log` |
| `tree_edge_cases_smoke` | `pass` | `8.42` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/tree_edge_cases_smoke.log` |
| `tree_manifest_corrupt_smoke` | `pass` | `0.19` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/tree_manifest_corrupt_smoke.log` |
| `alpha_demo_local` | `pass` | `3.20` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/alpha_demo_local.log` |
| `tree_private_smoke` | `pass` | `4.26` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/tree_private_smoke.log` |
| `alpha_demo_private` | `pass` | `6.04` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/alpha_demo_private.log` |
| `private_baseline_matrix` | `pass` | `461.05` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/private_baseline_matrix.log` |
| `remote_artifact_sync` | `pass` | `139.22` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/remote_artifact_sync.log` |
| `remote_artifact_sync_check` | `pass` | `69.57` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/remote_artifact_sync_check.log` |
| `remote_artifact_final_sync` | `pass` | `139.42` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/remote_artifact_final_sync.log` |
| `remote_artifact_final_verify` | `pass` | `69.60` | `/root/projects/GridFlux/tools/perf/results/20260518T110747Z_alpha-release-gate/remote_artifact_final_verify.log` |

## Private Baseline

- Raw CSV: `tools/perf/results/20260518T110905Z_gridftp-private-matrix-smoke.csv`
- Summary CSV: `tools/perf/results/20260518T110905Z_gridftp-private-matrix-smoke-summary.csv`
- Fail count: `0`
- Summary rows: `8`

Default baseline rows:

- direction=retr throughput_median=2.788190 spread_pct=42.258239
- direction=stor throughput_median=0.954290 spread_pct=20.095673

## Artifact Sync

- Manifest: `tools/perf/results/20260518T110747Z_alpha-artifacts.json`
- Artifacts: `458`
- Sync: checked=`459` synced=`3` missing=`0` mismatch=`0` pre_missing=`1` pre_mismatch=`2` post_missing=`0` post_mismatch=`0` status=`pass`
- Verify: checked=`459` missing=`0` mismatch=`0` status=`pass`
- Local freshness: checked=`458` stale=`0` status=`pass`

## Alpha Readiness

- Alpha scope is demonstrable GridFTP-like framed STOR/RETR, bidirectional resume, CRC32C chunk verification, and control metadata commands.
- Not beta/production: performance spread remains significant, 100G dedicated-line validation is not complete, and TLS/GSI/raw FTP stream/directory sync are out of scope.
- Defaults remain POSIX backend, full final verify, every_n_chunks manifest flush, no commit fsync, no preallocate full, and no default io_uring.

## Residual Process Check

- Local: ``
- Remote: ``

## Failures

- None.
