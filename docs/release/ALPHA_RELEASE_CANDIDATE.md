# GridFlux Alpha Release Candidate

- Timestamp: `2026-05-19T09:37:59Z`
- Result: `pass`
- Source tree hash: `211c40b434db7d2fccbce380b283046451e09c59cb28eb494f0ff8f9ab3f5b85`

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
| `alpha_release_gate_full` | `pass` | `ok` | `538.56` | `/root/projects/GridFlux/tools/perf/results/20260519T092826Z_alpha-release-candidate/alpha_release_gate_full.log` |
| `alpha_long_soak` | `pass` | `ok` | `33.39` | `/root/projects/GridFlux/tools/perf/results/20260519T092826Z_alpha-release-candidate/alpha_long_soak.log` |
| `public_export_hygiene` | `pass` | `ok` | `0.41` | `/root/projects/GridFlux/tools/perf/results/20260519T092826Z_alpha-release-candidate/public_export_hygiene.log` |
| `remote_artifact_sync` | `pass` | `ok` | `0.81` | `/root/projects/GridFlux/tools/perf/results/20260519T092826Z_alpha-release-candidate/remote_artifact_sync.log` |
| `remote_artifact_verify` | `pass` | `ok` | `0.34` | `/root/projects/GridFlux/tools/perf/results/20260519T092826Z_alpha-release-candidate/remote_artifact_verify.log` |

## Nested Full Gate

- Gate JSON: `/root/projects/GridFlux/tools/perf/results/20260519T092826Z_alpha-release-gate.json`
- Gate artifact manifest: `/root/projects/GridFlux/tools/perf/results/20260519T092826Z_alpha-artifacts.json`
- Gate passed: `True`
- Gate total steps: `33`
- Gate failed steps: `0`

## Release Candidate Artifacts

- Manifest: `tools/perf/results/20260519T092826Z_alpha-release-candidate-artifacts.json`
- Artifact count: `1470`
- Freshness: checked=`1470` stale=`0` status=`pass`
- Sync: checked=`1467` synced=`123` missing=`0` mismatch=`0` status=`pass`
- Verify: checked=`1467` missing=`0` mismatch=`0` status=`pass`

## Failures

- None.
