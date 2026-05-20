# GridFlux Alpha Release Candidate

- Timestamp: `2026-05-20T09:22:02Z`
- Result: `pass`
- Source tree hash: `cb48be4de75bdec375466d744f2f243521c85de4ac4f7b92cd555d08a8966185`

## Default Strategy

- `auth_mode`: `anonymous`
- `data_tls_mode`: `off`
- `file_io_backend`: `posix`
- `final_verify_policy`: `full`
- `manifest_flush_policy`: `every_n_chunks`
- `posix_write_strategy`: `auto`
- `preallocate`: `off`
- `tls_mode`: `off`

## Step Results

| Step | Status | Error Code | Seconds | Log |
|------|--------|------------|---------|-----|
| `alpha_release_gate_full` | `pass` | `ok` | `456.06` | `/root/projects/GridFlux/tools/perf/results/20260520T091351Z_alpha-release-candidate/alpha_release_gate_full.log` |
| `alpha_long_soak` | `pass` | `ok` | `33.04` | `/root/projects/GridFlux/tools/perf/results/20260520T091351Z_alpha-release-candidate/alpha_long_soak.log` |
| `public_export_hygiene` | `pass` | `ok` | `0.47` | `/root/projects/GridFlux/tools/perf/results/20260520T091351Z_alpha-release-candidate/public_export_hygiene.log` |
| `remote_artifact_sync` | `pass` | `ok` | `0.96` | `/root/projects/GridFlux/tools/perf/results/20260520T091351Z_alpha-release-candidate/remote_artifact_sync.log` |
| `remote_artifact_verify` | `pass` | `ok` | `0.43` | `/root/projects/GridFlux/tools/perf/results/20260520T091351Z_alpha-release-candidate/remote_artifact_verify.log` |

## Nested Full Gate

- Gate JSON: `/root/projects/GridFlux/tools/perf/results/20260520T091351Z_alpha-release-gate.json`
- Gate artifact manifest: `/root/projects/GridFlux/tools/perf/results/20260520T091351Z_alpha-artifacts.json`
- Gate passed: `True`
- Gate total steps: `33`
- Gate failed steps: `0`

## Release Candidate Artifacts

- Manifest: `tools/perf/results/20260520T091351Z_alpha-release-candidate-artifacts.json`
- Artifact count: `2444`
- Freshness: checked=`2444` stale=`0` status=`pass`
- Sync: checked=`2441` synced=`123` missing=`0` mismatch=`0` status=`pass`
- Verify: checked=`2441` missing=`0` mismatch=`0` status=`pass`

## Failures

- None.
