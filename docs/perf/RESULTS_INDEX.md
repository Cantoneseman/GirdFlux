# Lab Performance Results Index

Date: 2026-05-28

This index lists the canonical retained evidence after Lab Beta 2F slimming.
Old duplicate reruns and per-case logs are archived outside the repo under
`/home/Su/gridflux-archive/perf-results/`.

## Canonical Evidence

Current bottleneck triage is tracked in
[LAB_BOTTLENECK_REGISTER.md](LAB_BOTTLENECK_REGISTER.md).
Lab Beta 3A final verify gate and CRC32C cost review are tracked in
[LAB_FINAL_VERIFY_GATE.md](LAB_FINAL_VERIFY_GATE.md). Lab Beta RC evidence is
tracked in [LAB_BETA_RC_GATE.md](LAB_BETA_RC_GATE.md). The post-RC 100G
readiness recheck is tracked in
[LAB_100G_READINESS_RECHECK.md](LAB_100G_READINESS_RECHECK.md).
Beta freeze closeout is tracked in
[BETA_FREEZE.md](../release/BETA_FREEZE.md) and
[BETA_LIMITATIONS.md](../release/BETA_LIMITATIONS.md).

| Area | Keep Path | Key Evidence |
|---|---|---|
| Lab baseline diagnosis | `tools/perf/results/20260522T150508Z_lab-baseline-diag/` | TCP/RDMA/storage baseline and environment diagnostics |
| Lab GridFlux performance snapshot | `tools/perf/results/20260522T180406Z_lab-gridflux-performance/` | 10/20GiB GridFlux Beta snapshot and summary JSON |
| Lab Beta 2B checksum/final verify | `tools/perf/results/20260523T065043Z_lab-beta2b-checksum-final-verify/` | `analysis_summary.json`, `gridflux-beta2b-main-combined.csv`, `gridflux-beta2b-all-runs-combined.csv`, cleanup evidence |
| Lab Beta 2C 10GiB manifest flush | `tools/perf/results/20260524T075209Z_lab-gridflux-profile-manifest-flush/` | wrapper JSON, raw CSV, summary CSV, cleanup check |
| Lab Beta 2C 20GiB manifest flush | `tools/perf/results/20260524T082718Z_lab-gridflux-profile-manifest-flush-20gib/` | wrapper JSON, raw CSV, summary CSV, cleanup check |
| Lab Beta 2D stability analysis | `tools/perf/results/20260524T093758Z_lab-beta2d-manifest-flush-stability/` | combined JSON, combined summary CSV, delta CSV, resume safety CSV |
| Lab Beta 2D 10GiB repeat input | `tools/perf/results/20260524T093758Z_lab-gridflux-profile-manifest-flush/` | 10GiB repeat wrapper JSON, raw CSV, summary CSV |
| Lab Beta 2D 20GiB subset input | `tools/perf/results/20260524T112133Z_lab-gridflux-profile-manifest-flush-20gib/` | 20GiB subset wrapper JSON, raw CSV, summary CSV |
| Lab Beta 2E default 256 quick | `tools/perf/results/20260524T144503Z_lab-gridflux-profile-quick/` | wrapper JSON, raw CSV, summary CSV, cleanup check |
| Lab Beta 3A final verify historical baseline | `tools/perf/results/20260527T140404Z_lab-final-verify-gate-historical/` | analyzer JSON, per-policy summary CSV, full-vs-verified delta CSV |
| Lab Beta 3A final verify live gate | `tools/perf/results/20260527T150541Z_lab-final-verify-gate/`, `tools/perf/results/20260527T150541Z_lab-gridflux-profile-final-verify/` | live profile wrapper JSON/CSV/summary, combined gate JSON/summary/delta, resume and fallback safety CSVs |
| Lab Beta 3A CRC32C cost review | `tools/perf/results/20260528T165246Z_lab-checksum-cost-review/` | 6-row preliminary matrix, combined CSV, summary CSV, analysis JSON |
| Lab Beta RC release gate | `tools/perf/results/20260527T174327Z_lab-gridflux-profile-release/`, `tools/perf/results/20260527T183315Z_lab-beta-rc-gate/` | release wrapper JSON/raw CSV/summary/cleanup, resume safety CSV, fallback safety CSV, combined RC JSON/summary/delta, final cleanup check |
| Lab 100G readiness recheck | `tools/perf/results/20260528T013912Z_lab-100g-readiness-recheck/` | redacted inventory, TCP iperf summary, RDMA perftest summary, fio direct-I/O summary, readiness decision JSON, final cleanup check |
| Lab Beta freeze docs | `docs/release/BETA_FREEZE.md`, `docs/release/BETA_LIMITATIONS.md` | Beta-ready yes, 100G-ready no, defaults unchanged, next branch guidance |

## External Archive

Archived items are retained privately but are no longer part of the project tree:

| Archive Path | Contents |
|---|---|
| `/home/Su/gridflux-archive/perf-results/duplicate-reruns/` | superseded quick/manifest-flush rerun directories |
| `/home/Su/gridflux-archive/perf-results/canonical-per-case-logs/` | per-case `logs/` and `steps/` from canonical 2C/2D/2E runs |
| `/home/Su/gridflux-archive/perf-results/root-level-20260522/` | old root-level per-case logs, env snapshots, JSONL event logs, and raw CSV files |
| `/home/Su/gridflux-archive/perf-results/beta2d_sanity/` | superseded Beta 2D sanity scratch output |

The archive is not a public export target.
