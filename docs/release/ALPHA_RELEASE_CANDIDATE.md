# GridFlux Alpha Release Candidate

- Timestamp: `2026-05-20T03:34:20Z`
- Result: `pass`
- Source tree hash: `f2f34520bbf10c96657ee2b927043d993ce6f3b54b17df8133faf418c31a9bc3`

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
| `alpha_release_gate_full` | `pass` | `ok` | `547.06` | `/root/projects/GridFlux/tools/perf/results/20260520T032439Z_alpha-release-candidate/alpha_release_gate_full.log` |
| `alpha_long_soak` | `pass` | `ok` | `33.09` | `/root/projects/GridFlux/tools/perf/results/20260520T032439Z_alpha-release-candidate/alpha_long_soak.log` |
| `public_export_hygiene` | `pass` | `ok` | `0.44` | `/root/projects/GridFlux/tools/perf/results/20260520T032439Z_alpha-release-candidate/public_export_hygiene.log` |
| `remote_artifact_sync` | `pass` | `ok` | `0.89` | `/root/projects/GridFlux/tools/perf/results/20260520T032439Z_alpha-release-candidate/remote_artifact_sync.log` |
| `remote_artifact_verify` | `pass` | `ok` | `0.38` | `/root/projects/GridFlux/tools/perf/results/20260520T032439Z_alpha-release-candidate/remote_artifact_verify.log` |

## Nested Full Gate

- Gate JSON: `/root/projects/GridFlux/tools/perf/results/20260520T032439Z_alpha-release-gate.json`
- Gate artifact manifest: `/root/projects/GridFlux/tools/perf/results/20260520T032439Z_alpha-artifacts.json`
- Gate passed: `True`
- Gate total steps: `33`
- Gate failed steps: `0`

## Release Candidate Artifacts

- Manifest: `tools/perf/results/20260520T032439Z_alpha-release-candidate-artifacts.json`
- Artifact count: `2000`
- Freshness: checked=`2000` stale=`0` status=`pass`
- Sync: checked=`1997` synced=`123` missing=`0` mismatch=`0` status=`pass`
- Verify: checked=`1997` missing=`0` mismatch=`0` status=`pass`

## Failures

- None.
