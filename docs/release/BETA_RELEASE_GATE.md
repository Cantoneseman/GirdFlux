# GridFlux Beta Release Gate

- Timestamp: `2026-05-21T04:27:10Z`
- Result: `pass`
- Source tree hash: `230e6b2c17f1c892e83dd4161db580b7eede215c3cf0548f4c004da05c091cd3`
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
| `local_build_debug` | `pass` | `ok` | `0.04` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/local_build_debug.log` |
| `local_ctest_debug` | `pass` | `ok` | `33.27` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/local_ctest_debug.log` |
| `local_build_iouring_release` | `pass` | `ok` | `0.03` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/local_build_iouring_release.log` |
| `local_ctest_iouring_release` | `pass` | `ok` | `32.81` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/local_ctest_iouring_release.log` |
| `local_ctest_iouring_smoke` | `pass` | `ok` | `0.01` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/local_ctest_iouring_smoke.log` |
| `remote_build_debug` | `pass` | `ok` | `0.40` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/remote_build_debug.log` |
| `remote_ctest_debug` | `pass` | `ok` | `32.78` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/remote_ctest_debug.log` |
| `remote_build_iouring_release` | `pass` | `ok` | `0.16` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/remote_build_iouring_release.log` |
| `remote_ctest_iouring_release` | `pass` | `ok` | `32.89` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/remote_ctest_iouring_release.log` |
| `remote_ctest_iouring_smoke` | `pass` | `ok` | `0.35` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/remote_ctest_iouring_smoke.log` |
| `quick_alpha_gate` | `pass` | `ok` | `90.68` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/quick_alpha_gate.log` |
| `full_alpha_gate` | `pass` | `ok` | `749.99` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/full_alpha_gate.log` |
| `alpha_release_candidate` | `pass` | `ok` | `786.42` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/alpha_release_candidate.log` |
| `beta1c_retr_smoke` | `pass` | `ok` | `19.62` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/beta1c_retr_smoke.log` |
| `beta1b_storage_system_freshness` | `pass` | `ok` | `0.00` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/beta1b_storage_system_freshness.log` |
| `public_export_strict_hygiene` | `pass` | `ok` | `0.55` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/public_export_strict_hygiene.log` |
| `remote_beta_artifact_sync` | `pass` | `ok` | `1.03` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/remote_beta_artifact_sync.log` |
| `remote_beta_artifact_verify` | `pass` | `ok` | `0.47` | `/root/projects/GridFlux/tools/perf/results/20260521T035729Z_beta-release-gate/remote_beta_artifact_verify.log` |

## Beta Smoke Summary

- Beta 1C RETR smoke raw rows: `10`
- Beta 1C RETR smoke pass/fail: `10` / `0`
- Beta 1C grouped fail: `0`
- Beta 1C hash mismatch: `0`
- Beta 1B storage/system check: `pass`

## Beta 1E Freeze/Soak References

- Latest long soak: path=`tools/perf/results/20260521T035242Z_beta-long-soak.json` profile=`standard` pass=`True` fail_count=`0`
- Latest freeze check: path=`tools/perf/results/20260521T035305Z_beta-freeze-check.json` pass=`True`

## Nested Alpha Gates

- quick_alpha_gate: status=`pass` json=`/root/projects/GridFlux/tools/perf/results/20260521T035942Z_alpha-release-gate.json`
- full_alpha_gate: status=`pass` json=`/root/projects/GridFlux/tools/perf/results/20260521T040112Z_alpha-release-gate.json`
- alpha_release_candidate: status=`pass` json=`/root/projects/GridFlux/tools/perf/results/20260521T041342Z_alpha-release-candidate.json`

## Artifact Closure

- Manifest: `tools/perf/results/20260521T035729Z_beta-artifacts.json`
- Artifact count: `2929`
- Freshness: checked=`2929` stale=`0` status=`pass`
- Sync: checked=`2930` missing=`0` mismatch=`0` status=`pass`
- Verify: checked=`2930` missing=`0` mismatch=`0` status=`pass`

## Residual Process Check

- Local: ``
- Remote: ``

## Failures

- None.
