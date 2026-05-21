# GridFlux Alpha Release Candidate

- Timestamp: `2026-05-20T18:25:08Z`
- Result: `pass`
- Source tree hash: `5656cf8821f2f310a88cd35beb1cc63e7fc1876733ac3bf9ffc4b8c54c3b3ea6`

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
| `alpha_release_gate_full` | `pass` | `ok` | `458.17` | `/root/projects/GridFlux/tools/perf/results/20260520T181655Z_alpha-release-candidate/alpha_release_gate_full.log` |
| `alpha_long_soak` | `pass` | `ok` | `33.76` | `/root/projects/GridFlux/tools/perf/results/20260520T181655Z_alpha-release-candidate/alpha_long_soak.log` |
| `public_export_hygiene` | `pass` | `ok` | `0.54` | `/root/projects/GridFlux/tools/perf/results/20260520T181655Z_alpha-release-candidate/public_export_hygiene.log` |
| `remote_artifact_sync` | `pass` | `ok` | `1.00` | `/root/projects/GridFlux/tools/perf/results/20260520T181655Z_alpha-release-candidate/remote_artifact_sync.log` |
| `remote_artifact_verify` | `pass` | `ok` | `0.46` | `/root/projects/GridFlux/tools/perf/results/20260520T181655Z_alpha-release-candidate/remote_artifact_verify.log` |

## Nested Full Gate

- Gate JSON: `/root/projects/GridFlux/tools/perf/results/20260520T181655Z_alpha-release-gate.json`
- Gate artifact manifest: `/root/projects/GridFlux/tools/perf/results/20260520T181655Z_alpha-artifacts.json`
- Gate passed: `True`
- Gate total steps: `33`
- Gate failed steps: `0`

## Release Candidate Artifacts

- Manifest: `tools/perf/results/20260520T181655Z_alpha-release-candidate-artifacts.json`
- Artifact count: `2898`
- Freshness: checked=`2898` stale=`0` status=`pass`
- Sync: checked=`2895` synced=`123` missing=`0` mismatch=`0` status=`pass`
- Verify: checked=`2895` missing=`0` mismatch=`0` status=`pass`

## Failures

- None.
