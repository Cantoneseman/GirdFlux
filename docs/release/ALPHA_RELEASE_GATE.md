# GridFlux Alpha Release Gate

- Timestamp: `2026-05-20T07:33:18Z`
- Mode: `full`
- Source tree hash: `89783c70c933f4737c98431d37204f2ce5e94366ed5365395d1b34e0d3389fa4`
- Result: `pass`
- Total steps: `33`
- Passed steps: `33`
- Failed steps: `0`

## Step Results

| Step | Status | Error Code | Seconds | Log |
|------|--------|------------|---------|-----|
| `build_debug` | `pass` | `ok` | `0.04` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/build_debug.log` |
| `ctest_debug` | `pass` | `ok` | `33.11` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/ctest_debug.log` |
| `ctest_iouring` | `pass` | `ok` | `32.88` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/ctest_iouring.log` |
| `ctest_iouring_smoke` | `pass` | `ok` | `0.02` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/ctest_iouring_smoke.log` |
| `public_export_hygiene` | `pass` | `ok` | `0.45` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/public_export_hygiene.log` |
| `stor_smoke` | `pass` | `ok` | `0.18` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/stor_smoke.log` |
| `retr_smoke` | `pass` | `ok` | `0.33` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/retr_smoke.log` |
| `stor_resume_smoke` | `pass` | `ok` | `0.23` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/stor_resume_smoke.log` |
| `retr_resume_smoke` | `pass` | `ok` | `0.24` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/retr_resume_smoke.log` |
| `metadata_smoke` | `pass` | `ok` | `0.13` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/metadata_smoke.log` |
| `list_smoke` | `pass` | `ok` | `0.21` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/list_smoke.log` |
| `token_auth_smoke` | `pass` | `ok` | `0.22` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/token_auth_smoke.log` |
| `tls_control_smoke` | `pass` | `ok` | `0.44` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/tls_control_smoke.log` |
| `data_tls_smoke` | `pass` | `ok` | `1.90` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/data_tls_smoke.log` |
| `tree_upload_smoke` | `pass` | `ok` | `0.32` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/tree_upload_smoke.log` |
| `tree_download_smoke` | `pass` | `ok` | `0.46` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/tree_download_smoke.log` |
| `tree_resume_smoke` | `pass` | `ok` | `0.76` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/tree_resume_smoke.log` |
| `tree_parallel_smoke` | `pass` | `ok` | `0.93` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/tree_parallel_smoke.log` |
| `tree_changed_file_smoke` | `pass` | `ok` | `4.20` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/tree_changed_file_smoke.log` |
| `tree_edge_cases_smoke` | `pass` | `ok` | `8.47` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/tree_edge_cases_smoke.log` |
| `tree_manifest_corrupt_smoke` | `pass` | `ok` | `0.19` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/tree_manifest_corrupt_smoke.log` |
| `alpha_demo_local` | `pass` | `ok` | `3.27` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/alpha_demo_local.log` |
| `tree_private_smoke` | `pass` | `ok` | `4.37` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/tree_private_smoke.log` |
| `alpha_demo_private` | `pass` | `ok` | `6.18` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/alpha_demo_private.log` |
| `private_token_auth_smoke` | `pass` | `ok` | `0.18` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/private_token_auth_smoke.log` |
| `private_tls_control_smoke` | `pass` | `ok` | `1.21` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/private_tls_control_smoke.log` |
| `private_data_tls_smoke` | `pass` | `ok` | `1.89` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/private_data_tls_smoke.log` |
| `alpha_soak_smoke` | `pass` | `ok` | `6.57` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/alpha_soak_smoke.log` |
| `private_baseline_matrix` | `pass` | `ok` | `329.81` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/private_baseline_matrix.log` |
| `remote_artifact_sync` | `pass` | `ok` | `1.43` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/remote_artifact_sync.log` |
| `remote_artifact_sync_check` | `pass` | `ok` | `0.39` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/remote_artifact_sync_check.log` |
| `remote_artifact_final_sync` | `pass` | `ok` | `0.90` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/remote_artifact_final_sync.log` |
| `remote_artifact_final_verify` | `pass` | `ok` | `0.41` | `/root/projects/GridFlux/tools/perf/results/20260520T072557Z_alpha-release-gate/remote_artifact_final_verify.log` |

## Private Baseline

- Raw CSV: `tools/perf/results/20260520T072747Z_gridftp-private-matrix-smoke.csv`
- Summary CSV: `tools/perf/results/20260520T072747Z_gridftp-private-matrix-smoke-summary.csv`
- Fail count: `0`
- Summary rows: `8`

Default baseline rows:

- direction=retr throughput_median=3.278820 spread_pct=35.178814
- direction=stor throughput_median=1.605790 spread_pct=3.933889

## Artifact Sync

- Manifest: `tools/perf/results/20260520T072557Z_alpha-artifacts.json`
- Artifacts: `2112`
- Sync: checked=`2113` synced=`3` missing=`0` mismatch=`0` pre_missing=`1` pre_mismatch=`2` post_missing=`0` post_mismatch=`0` status=`pass`
- Verify: checked=`2113` missing=`0` mismatch=`0` status=`pass`
- Local freshness: checked=`2112` stale=`0` status=`pass`

## Alpha Readiness

- Alpha scope is demonstrable GridFTP-like framed STOR/RETR, bidirectional resume, CRC32C chunk verification, and control metadata commands.
- Not beta/production: performance spread remains significant, 100G dedicated-line validation is not complete, and TLS/GSI/raw FTP stream/directory sync are out of scope.
- Defaults remain POSIX backend, full final verify, every_n_chunks manifest flush, no commit fsync, no preallocate full, and no default io_uring.

## Residual Process Check

- Local: ``
- Remote: ``

## Failures

- None.
