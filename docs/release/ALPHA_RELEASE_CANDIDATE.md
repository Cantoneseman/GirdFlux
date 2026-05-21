# GridFlux Alpha Release Candidate

- Timestamp: `2026-05-21T04:26:44Z`
- Result: `pass`
- Source tree hash: `d80b777a77317fc0aa59d677c5a85fa3938c7ffcdd10440abb66d86c8ff291b2`

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
| `alpha_release_gate_full` | `pass` | `ok` | `747.16` | `/root/projects/GridFlux/tools/perf/results/20260521T041342Z_alpha-release-candidate/alpha_release_gate_full.log` |
| `alpha_long_soak` | `pass` | `ok` | `33.31` | `/root/projects/GridFlux/tools/perf/results/20260521T041342Z_alpha-release-candidate/alpha_long_soak.log` |
| `public_export_hygiene` | `pass` | `ok` | `0.57` | `/root/projects/GridFlux/tools/perf/results/20260521T041342Z_alpha-release-candidate/public_export_hygiene.log` |
| `remote_artifact_sync` | `pass` | `ok` | `1.02` | `/root/projects/GridFlux/tools/perf/results/20260521T041342Z_alpha-release-candidate/remote_artifact_sync.log` |
| `remote_artifact_verify` | `pass` | `ok` | `0.48` | `/root/projects/GridFlux/tools/perf/results/20260521T041342Z_alpha-release-candidate/remote_artifact_verify.log` |

## Nested Full Gate

- Gate JSON: `/root/projects/GridFlux/tools/perf/results/20260521T041342Z_alpha-release-gate.json`
- Gate artifact manifest: `/root/projects/GridFlux/tools/perf/results/20260521T041342Z_alpha-artifacts.json`
- Gate passed: `True`
- Gate total steps: `33`
- Gate failed steps: `0`

## Release Candidate Artifacts

- Manifest: `tools/perf/results/20260521T041342Z_alpha-release-candidate-artifacts.json`
- Artifact count: `3137`
- Freshness: checked=`3137` stale=`0` status=`pass`
- Sync: checked=`3134` synced=`123` missing=`0` mismatch=`0` status=`pass`
- Verify: checked=`3134` missing=`0` mismatch=`0` status=`pass`

## Failures

- None.
