# GridFlux Beta Release Gate

- Timestamp: `2026-05-20T18:25:34Z`
- Result: `pass`
- Source tree hash: `316dda745be8166de62f0969111889992cb06c3e75d0507be19f0775d0a8e62c`
- Remote: `root@<redacted>`
- Server host: `<redacted>`

## Default Strategy

- `auth-mode`: `anonymous`
- `tls-mode`: `off`
- `data-tls-mode`: `off`
- `file_io_backend`: `posix`
- `final_verify_policy`: `full`
- `manifest_flush_policy`: `every_n_chunks`
- `preallocate`: `off`
- `posix_write_strategy`: `auto`
- `receiver_write_profile`: `default`
- `receiver_write_yield_policy`: `none`

## Step Results

| Step | Status | Error Code | Seconds | Log |
|------|--------|------------|---------|-----|
| `local_build_debug` | `pass` | `ok` | `0.09` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/local_build_debug.log` |
| `local_ctest_debug` | `pass` | `ok` | `33.34` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/local_ctest_debug.log` |
| `local_build_iouring_release` | `pass` | `ok` | `0.02` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/local_build_iouring_release.log` |
| `local_ctest_iouring_release` | `pass` | `ok` | `32.92` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/local_ctest_iouring_release.log` |
| `local_ctest_iouring_smoke` | `pass` | `ok` | `0.01` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/local_ctest_iouring_smoke.log` |
| `remote_build_debug` | `pass` | `ok` | `0.42` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/remote_build_debug.log` |
| `remote_ctest_debug` | `pass` | `ok` | `33.31` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/remote_ctest_debug.log` |
| `remote_build_iouring_release` | `pass` | `ok` | `0.16` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/remote_build_iouring_release.log` |
| `remote_ctest_iouring_release` | `pass` | `ok` | `32.69` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/remote_ctest_iouring_release.log` |
| `remote_ctest_iouring_smoke` | `pass` | `ok` | `0.36` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/remote_ctest_iouring_smoke.log` |
| `quick_alpha_gate` | `pass` | `ok` | `90.79` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/quick_alpha_gate.log` |
| `full_alpha_gate` | `pass` | `ok` | `461.00` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/full_alpha_gate.log` |
| `alpha_release_candidate` | `pass` | `ok` | `497.90` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/alpha_release_candidate.log` |
| `beta1c_retr_smoke` | `pass` | `ok` | `19.87` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/beta1c_retr_smoke.log` |
| `beta1b_storage_system_freshness` | `pass` | `ok` | `0.00` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/beta1b_storage_system_freshness.log` |
| `public_export_strict_hygiene` | `pass` | `ok` | `0.57` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/public_export_strict_hygiene.log` |
| `remote_beta_artifact_sync` | `pass` | `ok` | `0.96` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/remote_beta_artifact_sync.log` |
| `remote_beta_artifact_verify` | `pass` | `ok` | `0.44` | `/root/projects/GridFlux/tools/perf/results/20260520T180530Z_beta-release-gate/remote_beta_artifact_verify.log` |

## Beta Smoke Summary

- Beta 1C RETR smoke raw rows: `10`
- Beta 1C RETR smoke pass/fail: `10` / `0`
- Beta 1C grouped fail: `0`
- Beta 1C hash mismatch: `0`
- Beta 1B storage/system check: `pass`

## Nested Alpha Gates

- quick_alpha_gate: status=`pass` json=`/root/projects/GridFlux/tools/perf/results/20260520T180743Z_alpha-release-gate.json`
- full_alpha_gate: status=`pass` json=`/root/projects/GridFlux/tools/perf/results/20260520T180914Z_alpha-release-gate.json`
- alpha_release_candidate: status=`pass` json=`/root/projects/GridFlux/tools/perf/results/20260520T181655Z_alpha-release-candidate.json`

## Artifact Closure

- Manifest: `tools/perf/results/20260520T180530Z_beta-artifacts.json`
- Artifact count: `2688`
- Freshness: checked=`2688` stale=`0` status=`pass`
- Sync: checked=`2689` missing=`0` mismatch=`0` status=`pass`
- Verify: checked=`2689` missing=`0` mismatch=`0` status=`pass`

## Residual Process Check

- Local: ``
- Remote: ``

## Failures

- None.
