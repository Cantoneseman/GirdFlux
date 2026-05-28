# GridFlux Project State

Historical detail was consolidated on 2026-05-24:
[PROJECT_STATE_HISTORY_20260524.md](archive/PROJECT_STATE_HISTORY_20260524.md).
Performance evidence is indexed in
[RESULTS_INDEX.md](perf/RESULTS_INDEX.md).

## Current Status

- Lab Beta Freeze closeout is complete:
  [BETA_FREEZE.md](release/BETA_FREEZE.md) and
  [BETA_LIMITATIONS.md](release/BETA_LIMITATIONS.md) capture the final Beta
  boundary. Beta-ready is `yes` for the documented conservative default set;
  100G-ready is `no`.
- Lab 100G Readiness Recheck is complete:
  [LAB_100G_READINESS_RECHECK.md](perf/LAB_100G_READINESS_RECHECK.md).
  The lab remains not 100G-ready; do not enter 20GiB/100GiB expansion for
  100G-readiness work until machine/storage blockers are fixed or accepted.
- Lab Beta RC Gate is complete: the release-style 10GiB profile, resume
  safety, fallback safety, focused CTest, and cleanup checks all passed:
  [LAB_BETA_RC_GATE.md](perf/LAB_BETA_RC_GATE.md).
- Lab Beta 2E is complete: `manifest_flush_interval_chunks` now defaults to
  `256`.
- Lab Beta closeout has started with a bottleneck register that separates lab
  machine limits from GridFlux project costs:
  [LAB_BOTTLENECK_REGISTER.md](perf/LAB_BOTTLENECK_REGISTER.md).
- Lab Beta 3A / Stage B final verify safety/performance is complete:
  [LAB_FINAL_VERIFY_GATE.md](perf/LAB_FINAL_VERIFY_GATE.md).
- Lab Beta 3A / Stage B is complete: live cross-host final-verify, focused
  CTest, resume safety, fallback safety, and key repeat all passed.
- Stage C preliminary CRC32C cost review is complete:
  [LAB_CHECKSUM_COST_REVIEW.md](perf/LAB_CHECKSUM_COST_REVIEW.md).
- `quick` / `focused` / `release` / `heavy` lab profiles inherit the C++
  default and no longer pass an explicit manifest flush interval.
- `manifest-flush` and `manifest-flush-20gib` remain the explicit A/B profiles
  for `16 vs 256`.
- The current tree is ready for Beta freeze documentation under the documented
  conservative Beta scope; no open item requires changing STOR/RETR framing,
  manifest v2, checksum semantics, or resume facts.

## Current Defaults

| Setting | Default |
|---|---|
| auth mode | anonymous |
| control TLS | off |
| data TLS | off |
| file I/O backend | posix |
| final verify policy | full |
| manifest flush policy | every_n_chunks |
| manifest flush interval | 256 chunks |
| preallocate | off |
| POSIX write strategy | auto |
| receiver write profile | default |
| receiver write yield policy | none |
| verified_chunks final verify | opt-in only |

`16` remains a valid explicit manifest flush interval for A/B and regression
checks. No default enables `verified_chunks`.

## Latest Acceptance

| Gate | Result | Evidence |
|---|---|---|
| Lab Beta Freeze closeout | Beta-ready `yes`, 100G-ready `no`, defaults unchanged, next branch is 100G baseline lift or CRC32C opt-in prototype | `docs/release/BETA_FREEZE.md`, `docs/release/BETA_LIMITATIONS.md` |
| Lab 100G Readiness Recheck | TCP best `27.712/34.295 Gbps`, RDMA single-direction best `59.820 Gbps`, storage best main/small `0.525/0.848 GB/s`; not ready for 20GiB/100GiB expansion | `tools/perf/results/20260528T013912Z_lab-100g-readiness-recheck/` |
| Lab Beta RC Gate | release profile `32/32 pass`, resume safety `2/2 pass`, fallback safety `2/2 pass`, combined `row_count=36`, `fail_count=0`, `sha_mismatch=0`, `gate_pass=true` | `tools/perf/results/20260527T174327Z_lab-gridflux-profile-release/`, `tools/perf/results/20260527T183315Z_lab-beta-rc-gate/` |
| Lab Beta 2E default 256 | quick `4/4 pass`, `sha_mismatch=0`, cleanup clean | `tools/perf/results/20260524T144503Z_lab-gridflux-profile-quick/` |
| Lab Beta 2D stability | 10GiB `66/66 pass`, 20GiB `8/8 pass`, resume safety `2/2 pass`, `sha_mismatch=0` | `tools/perf/results/20260524T093758Z_lab-beta2d-manifest-flush-stability/` |
| Lab Beta 2C manifest flush | 10GiB `22/22 pass`, 20GiB `8/8 pass`; interval `256` cut manifest flush cost by about `92-95%` | `tools/perf/results/20260524T075209Z_lab-gridflux-profile-manifest-flush/`, `tools/perf/results/20260524T082718Z_lab-gridflux-profile-manifest-flush-20gib/` |
| Lab Beta 2B checksum/final verify | main matrix `144/144 pass`, focused/fallback `149/149 pass`, `sha_mismatch=0` | `tools/perf/results/20260523T065043Z_lab-beta2b-checksum-final-verify/` |
| Lab Beta 3A historical final verify analysis | Beta 2B CSV re-analysis `row_count=149`, `matched_delta_count=18`, `fail_count=0`, `sha_mismatch=0`, `fallback_row_count=2` | `tools/perf/results/20260527T140404Z_lab-final-verify-gate-historical/` |
| Lab Beta 3A live final verify gate | combined Stage B `row_count=20`, `matched_delta_count=4`, `fail_count=0`, `sha_mismatch=0`, `fallback_row_count=2`, `gate_pass=true` | `tools/perf/results/20260527T150541Z_lab-final-verify-gate/` |
| Lab Beta 3A CRC32C cost review | Stage C small matrix `6/6 pass`, `sha_mismatch=0`; preliminary only, no checksum optimization implemented | `tools/perf/results/20260528T165246Z_lab-checksum-cost-review/` |
| Lab performance snapshot | 10/20GiB beta snapshot retained; GridFlux correctness clean under constrained storage/network baseline | `tools/perf/results/20260522T180406Z_lab-gridflux-performance/` |
| Lab baseline diagnosis | TCP/RDMA/storage baseline retained; environment did not represent a tuned 100G ceiling | `tools/perf/results/20260522T150508Z_lab-baseline-diag/` |

## Key Decisions

- `manifest_flush_interval_chunks=256` is the active default after Beta 2E.
- `16` is retained only as an explicit comparison/regression value.
- Manifest v2 text format, `manifest_body_crc32c`, resume source of truth,
  STOR/RETR framed protocol, and `final_verify_policy=full` are unchanged.
- `verified_chunks` remains opt-in; it is not a default behavior.
- Full heavy matrices and 100GiB repeat runs are opt-in only.
- Lab Beta is freeze-ready for the current conservative feature/default set.
- GridFlux/lab is not 100G-ready under the current lab machine baseline; the
  latest recheck blocks both 20GiB and 100GiB readiness expansion.
- Per-case historical logs can be archived once wrapper JSON, combined CSV,
  summary CSV, and cleanup evidence are retained.

## Next Recommended Work

Choose one follow-up track:

- A. reversible lab machine baseline lift, if 100G readiness is the next goal;
- B. opt-in CRC32C pipeline prototype, if checksum cost is the next project
  experiment.

Do not claim 100G readiness until the machine baseline is lifted or explicitly
accepted as the test ceiling.

## Historical Index

| Stage | Status | Pointer |
|---|---|---|
| Alpha | Release gate, hygiene, artifact verification, tree transfer smoke completed | `docs/archive/PROJECT_STATE_HISTORY_20260524.md` |
| Cloud Beta | Cloud GridFTP/GridFlux, disk/writeback attribution, and beta limitations captured | `docs/archive/PERF_HISTORY_20260524.md` |
| Lab baseline | 100G/RDMA/storage baseline diagnosed; bottlenecks documented before code optimization | `docs/perf/LAB_100G_ENVIRONMENT_READINESS.md`, results index |
| Lab 100G recheck | Post-RC TCP/RDMA/storage recheck confirmed machine blockers; no 20GiB/100GiB expansion | `docs/perf/LAB_100G_READINESS_RECHECK.md` |
| Lab Beta 2B | crc32c stability fix and checksum/final verify decomposition completed | `docs/perf/LAB_CHECKSUM_FINAL_VERIFY_DIAGNOSIS.md` |
| Lab Beta 2C | Manifest save metrics and low-risk save-path optimization completed | `docs/perf/LAB_MANIFEST_FLUSH_OPTIMIZATION.md` |
| Lab Beta 2D | Interval `256` stability gate passed and became a default candidate | `docs/perf/LAB_MANIFEST_FLUSH_OPTIMIZATION.md` |
| Lab Beta 2E | Default manifest flush interval promoted from `16` to `256` | `docs/perf/LAB_MANIFEST_FLUSH_OPTIMIZATION.md` |
| Lab Beta 3A | Final verify safety/performance gate passed; CRC32C cost review completed as preliminary evidence | `docs/perf/LAB_FINAL_VERIFY_GATE.md`, `docs/perf/LAB_CHECKSUM_COST_REVIEW.md` |
| Lab Beta RC | Conservative release-style gate passed; Beta freeze can proceed, but 100G readiness remains false | `docs/perf/LAB_BETA_RC_GATE.md`, `docs/release/BETA_FREEZE.md` |
| Lab Beta Freeze | Freeze docs closed; next stage is either 100G baseline lift or CRC32C opt-in prototype | `docs/release/BETA_FREEZE.md`, `docs/release/BETA_LIMITATIONS.md` |
