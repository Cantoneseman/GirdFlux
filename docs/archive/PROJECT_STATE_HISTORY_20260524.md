# Project State History Archive

Date: 2026-05-24

This archive replaces the former long-running `docs/PROJECT_STATE.md` timeline.
The live status page now keeps only current defaults, latest gates, key
decisions, and next steps.

## Condensed Timeline

| Stage | Summary | Evidence |
|---|---|---|
| Alpha | Core transfer, release hygiene, artifact verification, tree upload/download, resume smokes, and beta freeze checks were completed. | `docs/release/BETA_FREEZE.md`, `docs/release/BETA_LIMITATIONS.md` |
| Cloud Beta | Cloud GridFTP/GridFlux comparisons and disk/writeback attribution established that cloud results were environment-specific and not a 100G ceiling. | `docs/perf/BETA_PERFORMANCE_SUMMARY.md`, `docs/perf/GRIDFTP_VS_GRIDFLUX_CLOUD_COMPARISON.md`, `docs/perf/CLOUD_DISK_BOTTLENECK_PROOF.md` |
| Lab baseline | 100G link/RDMA/storage baseline was diagnosed before GridFlux tuning; TCP and storage did not represent a tuned 100G ceiling. | `tools/perf/results/20260522T150508Z_lab-baseline-diag/` |
| Lab performance snapshot | GridFlux Beta correctness passed under the lab baseline, with 10/20GiB long-file measurements retained for context. | `docs/perf/LAB_GRIDFLUX_PERFORMANCE_SNAPSHOT.md`, `tools/perf/results/20260522T180406Z_lab-gridflux-performance/` |
| Lab Beta 2B | Fixed the 20GiB STOR crc32c c4 EAGAIN path and decomposed checksum/final verify costs. Main matrix `144/144` and focused/fallback `149/149` passed with `sha_mismatch=0`. | `docs/perf/LAB_CHECKSUM_FINAL_VERIFY_DIAGNOSIS.md`, `tools/perf/results/20260523T065043Z_lab-beta2b-checksum-final-verify/` |
| Lab Test Plan Slimdown | Added `quick` / `focused` / `release` / `heavy` lab profiles to avoid rerunning the full Beta 2B matrix every turn. | `tools/perf/run_lab_gridflux_profile.py`, `docs/perf/README.md` |
| Lab Beta 2C | Added manifest save detail metrics and optimized save-path sorting/range rebuilds without changing manifest format or reliability semantics. | `docs/perf/LAB_MANIFEST_FLUSH_OPTIMIZATION.md` |
| Lab Beta 2D | Proved interval `256` stability with 10GiB repeat, 20GiB subset, resume safety, and manifest corruption coverage. | `tools/perf/results/20260524T093758Z_lab-beta2d-manifest-flush-stability/` |
| Lab Beta 2E | Promoted default `manifest_flush_interval_chunks` from `16` to `256`; explicit `16` A/B remains supported. | `tools/perf/results/20260524T144503Z_lab-gridflux-profile-quick/` |

## Policy Preserved Across These Stages

- Manifest v2 text format stayed unchanged.
- `manifest_body_crc32c` stayed the corruption guard.
- Verified chunk records stayed the resume source of truth.
- STOR/RETR framed protocol stayed unchanged.
- `final_verify_policy=full` stayed the default.
- `verified_chunks` stayed opt-in.
- Heavy matrices and 100GiB repeat runs stayed opt-in.
