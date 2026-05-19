# GridFlux Alpha Release Candidate

- Timestamp: `2026-05-19T16:06:57Z`
- Result: `pass`
- Source tree hash: `dfd84e210d4dee6ef172dbb8caed7212de11ce9a7d8d4f2d5bea5b183577fdad`

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
| `alpha_release_gate_full` | `pass` | `ok` | `471.97` | `/root/projects/GridFlux/tools/perf/results/20260519T155829Z_alpha-release-candidate/alpha_release_gate_full.log` |
| `alpha_long_soak` | `pass` | `ok` | `34.45` | `/root/projects/GridFlux/tools/perf/results/20260519T155829Z_alpha-release-candidate/alpha_long_soak.log` |
| `public_export_hygiene` | `pass` | `ok` | `0.51` | `/root/projects/GridFlux/tools/perf/results/20260519T155829Z_alpha-release-candidate/public_export_hygiene.log` |
| `remote_artifact_sync` | `pass` | `ok` | `0.87` | `/root/projects/GridFlux/tools/perf/results/20260519T155829Z_alpha-release-candidate/remote_artifact_sync.log` |
| `remote_artifact_verify` | `pass` | `ok` | `0.38` | `/root/projects/GridFlux/tools/perf/results/20260519T155829Z_alpha-release-candidate/remote_artifact_verify.log` |

## Nested Full Gate

- Gate JSON: `/root/projects/GridFlux/tools/perf/results/20260519T155829Z_alpha-release-gate.json`
- Gate artifact manifest: `/root/projects/GridFlux/tools/perf/results/20260519T155829Z_alpha-artifacts.json`
- Gate passed: `True`
- Gate total steps: `33`
- Gate failed steps: `0`

## Release Candidate Artifacts

- Manifest: `tools/perf/results/20260519T155829Z_alpha-release-candidate-artifacts.json`
- Artifact count: `1793`
- Freshness: checked=`1793` stale=`0` status=`pass`
- Sync: checked=`1790` synced=`123` missing=`0` mismatch=`0` status=`pass`
- Verify: checked=`1790` missing=`0` mismatch=`0` status=`pass`

## Failures

- None.
