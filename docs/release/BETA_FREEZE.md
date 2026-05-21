# GridFlux Beta Freeze

- Timestamp: `2026-05-21T03:53:07Z`
- Result: `pass`
- Scope: current two-cloud-server Beta RC freeze before any 100G migration.
- 100G status: not certified and not tested in this freeze.

## Default Strategy

- `auth-mode=anonymous`
- `tls-mode=off`
- `data-tls-mode=off`
- `file_io_backend=posix`
- `final_verify_policy=full`
- `manifest_flush_policy=every_n_chunks`
- `preallocate=off`
- `posix_write_strategy=auto`
- `receiver_write_profile=default`
- `receiver_write_yield_policy=none`

## Freeze Checks

- Latest Beta Gate: `/root/projects/GridFlux/tools/perf/results/20260521T024502Z_beta-release-gate.json` pass=`True`
- Latest Beta RC: `/root/projects/GridFlux/tools/perf/results/20260520T182602Z_beta-release-candidate.json` pass=`True`
- Artifact final verify: `/root/projects/GridFlux/tools/perf/results/20260520T182602Z_beta-release-candidate-final-verify.json` pass=`True`
- Public hygiene from latest Beta Gate: `True`
- Required docs present: `True`
- Default strategy check: `True`
- Residual process check local: ``
- Residual process check remote: ``

## Migration Guardrails

- Current Beta is a cloud-server candidate, not a 100G-certified build.
- Before moving to 100G, run `iperf3`, `gridflux-storage-bench`, memory sink, and CRC32C benchmark baselines.
- On 100G, run 10GiB smoke first, then 100GiB repeat after network/storage baselines are clean.
- Keep conservative defaults until 100G data proves a stable opt-in should graduate.

## Failures

- None.
