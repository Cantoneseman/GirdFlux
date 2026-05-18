# GridFlux Alpha Release Gate

- Timestamp: `2026-05-18T04:14:28Z`
- Mode: `full`
- Source tree hash: `1bd02f2ba74cd1a25a7a8c9866413ac037d83a0f2a6af984073a34a5c4491699`
- Result: `pass`

## Step Results

| Step | Status | Seconds | Log |
|------|--------|---------|-----|
| `build_debug` | `pass` | `0.01` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/build_debug.log` |
| `ctest_debug` | `pass` | `8.45` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/ctest_debug.log` |
| `ctest_iouring` | `pass` | `8.17` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/ctest_iouring.log` |
| `ctest_iouring_smoke` | `pass` | `0.01` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/ctest_iouring_smoke.log` |
| `public_export_hygiene` | `pass` | `0.28` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/public_export_hygiene.log` |
| `stor_smoke` | `pass` | `0.18` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/stor_smoke.log` |
| `retr_smoke` | `pass` | `0.35` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/retr_smoke.log` |
| `stor_resume_smoke` | `pass` | `0.17` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/stor_resume_smoke.log` |
| `retr_resume_smoke` | `pass` | `0.19` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/retr_resume_smoke.log` |
| `metadata_smoke` | `pass` | `0.07` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/metadata_smoke.log` |
| `list_smoke` | `pass` | `0.16` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/list_smoke.log` |
| `private_baseline_matrix` | `pass` | `484.29` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/private_baseline_matrix.log` |
| `remote_artifact_sync` | `pass` | `48.88` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/remote_artifact_sync.log` |
| `remote_artifact_sync_check` | `pass` | `24.41` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/remote_artifact_sync_check.log` |
| `remote_artifact_final_sync` | `pass` | `49.46` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/remote_artifact_final_sync.log` |
| `remote_artifact_final_verify` | `pass` | `24.50` | `/root/projects/GridFlux/tools/perf/results/20260518T040604Z_alpha-release-gate/remote_artifact_final_verify.log` |

## Private Baseline

- Raw CSV: `tools/perf/results/20260518T040622Z_gridftp-private-matrix-smoke.csv`
- Summary CSV: `tools/perf/results/20260518T040622Z_gridftp-private-matrix-smoke-summary.csv`
- Fail count: `0`
- Summary rows: `8`

Default baseline rows:

- direction=retr throughput_median=3.486370 spread_pct=68.874216
- direction=stor throughput_median=0.912762 spread_pct=9.167779

## Artifact Sync

- Manifest: `tools/perf/results/20260518T040604Z_alpha-artifacts.json`
- Artifacts: `161`
- Sync: checked=`162` synced=`3` missing=`0` mismatch=`0` status=`pass`
- Verify: checked=`162` missing=`0` mismatch=`0` status=`pass`

## Alpha Readiness

- Alpha scope is demonstrable GridFTP-like framed STOR/RETR, bidirectional resume, CRC32C chunk verification, and control metadata commands.
- Not beta/production: performance spread remains significant, 100G dedicated-line validation is not complete, and TLS/GSI/raw FTP stream/directory sync are out of scope.
- Defaults remain POSIX backend, full final verify, every_n_chunks manifest flush, no commit fsync, no preallocate full, and no default io_uring.

## Residual Process Check

- Local: ``
- Remote: ``

## Failures

- None.
