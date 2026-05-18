# GridFlux Alpha Release Gate

- Timestamp: `2026-05-18T16:31:07Z`
- Mode: `full`
- Source tree hash: `b130ce146f853a251f34244e80e4af52b64a3fbe89d7b5f475a60e19d46ac066`
- Result: `pass`
- Total steps: `31`
- Passed steps: `31`
- Failed steps: `0`

## Step Results

| Step | Status | Error Code | Seconds | Log |
|------|--------|------------|---------|-----|
| `build_debug` | `pass` | `ok` | `0.01` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/build_debug.log` |
| `ctest_debug` | `pass` | `ok` | `28.53` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/ctest_debug.log` |
| `ctest_iouring` | `pass` | `ok` | `28.25` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/ctest_iouring.log` |
| `ctest_iouring_smoke` | `pass` | `ok` | `0.01` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/ctest_iouring_smoke.log` |
| `public_export_hygiene` | `pass` | `ok` | `0.40` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/public_export_hygiene.log` |
| `stor_smoke` | `pass` | `ok` | `0.18` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/stor_smoke.log` |
| `retr_smoke` | `pass` | `ok` | `0.34` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/retr_smoke.log` |
| `stor_resume_smoke` | `pass` | `ok` | `0.22` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/stor_resume_smoke.log` |
| `retr_resume_smoke` | `pass` | `ok` | `0.25` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/retr_resume_smoke.log` |
| `metadata_smoke` | `pass` | `ok` | `0.12` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/metadata_smoke.log` |
| `list_smoke` | `pass` | `ok` | `0.21` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/list_smoke.log` |
| `token_auth_smoke` | `pass` | `ok` | `0.22` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/token_auth_smoke.log` |
| `tls_control_smoke` | `pass` | `ok` | `0.81` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/tls_control_smoke.log` |
| `tree_upload_smoke` | `pass` | `ok` | `0.32` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/tree_upload_smoke.log` |
| `tree_download_smoke` | `pass` | `ok` | `0.46` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/tree_download_smoke.log` |
| `tree_resume_smoke` | `pass` | `ok` | `0.76` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/tree_resume_smoke.log` |
| `tree_parallel_smoke` | `pass` | `ok` | `0.94` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/tree_parallel_smoke.log` |
| `tree_changed_file_smoke` | `pass` | `ok` | `4.21` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/tree_changed_file_smoke.log` |
| `tree_edge_cases_smoke` | `pass` | `ok` | `8.49` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/tree_edge_cases_smoke.log` |
| `tree_manifest_corrupt_smoke` | `pass` | `ok` | `0.19` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/tree_manifest_corrupt_smoke.log` |
| `alpha_demo_local` | `pass` | `ok` | `3.27` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/alpha_demo_local.log` |
| `tree_private_smoke` | `pass` | `ok` | `4.28` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/tree_private_smoke.log` |
| `alpha_demo_private` | `pass` | `ok` | `6.09` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/alpha_demo_private.log` |
| `private_token_auth_smoke` | `pass` | `ok` | `0.19` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/private_token_auth_smoke.log` |
| `private_tls_control_smoke` | `pass` | `ok` | `1.13` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/private_tls_control_smoke.log` |
| `alpha_soak_smoke` | `pass` | `ok` | `6.52` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/alpha_soak_smoke.log` |
| `private_baseline_matrix` | `pass` | `ok` | `311.34` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/private_baseline_matrix.log` |
| `remote_artifact_sync` | `pass` | `ok` | `0.86` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/remote_artifact_sync.log` |
| `remote_artifact_sync_check` | `pass` | `ok` | `0.29` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/remote_artifact_sync_check.log` |
| `remote_artifact_final_sync` | `pass` | `ok` | `0.73` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/remote_artifact_final_sync.log` |
| `remote_artifact_final_verify` | `pass` | `ok` | `0.30` | `/root/projects/GridFlux/tools/perf/results/20260518T162419Z_alpha-release-gate/remote_artifact_final_verify.log` |

## Private Baseline

- Raw CSV: `tools/perf/results/20260518T162555Z_gridftp-private-matrix-smoke.csv`
- Summary CSV: `tools/perf/results/20260518T162555Z_gridftp-private-matrix-smoke-summary.csv`
- Fail count: `0`
- Summary rows: `8`

Default baseline rows:

- direction=retr throughput_median=2.936540 spread_pct=31.230632
- direction=stor throughput_median=1.920790 spread_pct=12.291297

## Artifact Sync

- Manifest: `tools/perf/results/20260518T162419Z_alpha-artifacts.json`
- Artifacts: `762`
- Sync: checked=`763` synced=`3` missing=`0` mismatch=`0` pre_missing=`1` pre_mismatch=`2` post_missing=`0` post_mismatch=`0` status=`pass`
- Verify: checked=`763` missing=`0` mismatch=`0` status=`pass`
- Local freshness: checked=`762` stale=`0` status=`pass`

## Alpha Readiness

- Alpha scope is demonstrable GridFTP-like framed STOR/RETR, bidirectional resume, CRC32C chunk verification, and control metadata commands.
- Not beta/production: performance spread remains significant, 100G dedicated-line validation is not complete, and TLS/GSI/raw FTP stream/directory sync are out of scope.
- Defaults remain POSIX backend, full final verify, every_n_chunks manifest flush, no commit fsync, no preallocate full, and no default io_uring.

## Residual Process Check

- Local: ``
- Remote: ``

## Failures

- None.
