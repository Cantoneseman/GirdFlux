# GridFlux Performance Notes

This page is the current lab/performance entry point. Older Phase 4 and Cloud
Beta command history was consolidated in
[PERF_HISTORY_20260524.md](../archive/PERF_HISTORY_20260524.md). Canonical result
paths are indexed in [RESULTS_INDEX.md](RESULTS_INDEX.md).

## Current Lab Runner

Use `tools/perf/run_lab_gridflux_profile.py` for routine lab validation. It
wraps `tools/perf/run_gridftp_private_matrix.py` and keeps the full 144-row /
149-row Beta 2B evidence as historical proof instead of rerunning it every turn.

| Profile | Default size | Default repeat | Rows | Purpose |
|---|---:|---:|---:|---|
| quick | 1GiB | 1 | 4 | daily smoke |
| focused | 10GiB | 1 | 6 | checksum/final verify/verified_chunks critical paths |
| release | 10GiB | 2 | 32 | stage gate; `--repeat 3` gives 48 rows |
| final-verify | 10GiB | 1 | 8 | Lab Beta 3A full vs `verified_chunks` gate |
| heavy | 20GiB | 3 | 90 | opt-in only for major releases or explicit requests |
| manifest-flush | 10GiB | 1 | 22 | explicit `16 vs 256` interval A/B |
| manifest-flush-20gib | 20GiB | 1 | 8 | explicit 20GiB interval A/B subset |

Common commands:

```bash
python3 tools/perf/run_lab_gridflux_profile.py --profile quick --dry-run
python3 tools/perf/run_lab_gridflux_profile.py --profile quick
python3 tools/perf/run_lab_gridflux_profile.py --profile focused --dry-run
python3 tools/perf/run_lab_gridflux_profile.py --profile final-verify --dry-run
python3 tools/perf/run_lab_gridflux_profile.py --profile release --dry-run
python3 tools/perf/run_lab_gridflux_profile.py --profile manifest-flush --dry-run
```

Default lab parameters are:

- remote: `gridflux-lab-small`
- server host: `192.168.100.2`
- build dir: `/home/Su/projects/GridFlux/build`
- run-root base: `/mnt/aim_sdc/gridflux-test/lab-profile-<timestamp>`
- output: `tools/perf/results/<timestamp>_lab-gridflux-profile-<profile>/`

By default the wrapper removes this run's run-root and large temporary files.
Use `--skip-cleanup` only when retaining transfer payloads for debugging.

## Current Defaults

The routine profiles inherit the C++ defaults and no longer pass an explicit
manifest flush interval:

| Setting | Default |
|---|---|
| auth mode | anonymous |
| control/data TLS | off/off |
| file I/O backend | posix |
| final verify policy | full |
| manifest flush policy | every_n_chunks |
| manifest flush interval | 256 chunks |
| preallocate | off |
| POSIX write strategy | auto |
| receiver write profile | default |
| receiver write yield | none |

`manifest-flush` and `manifest-flush-20gib` still pass explicit `16` and `256`
values for A/B. Direct `run_gridftp_private_matrix.py` invocations also default
to `256` when `--manifest-flush-interval-chunks` is omitted.

## Latest Lab Conclusions

- Lab Beta Freeze closeout is complete:
  [BETA_FREEZE.md](../release/BETA_FREEZE.md). Beta-ready is `yes` for the
  documented conservative defaults; 100G-ready is `no`.
- Lab 100G Readiness Recheck is tracked in
  [LAB_100G_READINESS_RECHECK.md](LAB_100G_READINESS_RECHECK.md). It found TCP
  best `27.712/34.295 Gbps`, single-direction RDMA best `59.820 Gbps`, and
  direct storage best main/small `0.525/0.848 GB/s`; this blocks 20GiB/100GiB
  expansion for 100G-readiness work.
- Lab Beta RC Gate passed with conservative defaults:
  [LAB_BETA_RC_GATE.md](LAB_BETA_RC_GATE.md). The release profile passed
  `32/32`, resume safety passed `2/2`, fallback safety passed `2/2`, and the
  combined RC analysis reports `fail_count=0`, `sha_mismatch=0`.
- Lab Beta 2E promoted `manifest_flush_interval_chunks` from `16` to `256`.
- The current bottleneck register is
  [LAB_BOTTLENECK_REGISTER.md](LAB_BOTTLENECK_REGISTER.md). It separates lab
  machine limits from GridFlux project costs before further Beta closeout gates.
- Lab Beta 2D repeated `16 vs 256`: 10GiB `66/66 pass`, 20GiB `8/8 pass`,
  resume safety `2/2 pass`, `sha_mismatch=0`.
- Lab Beta 2C showed interval `256` reduces manifest flush cost by about
  `92-95%` in the primary 10/20GiB crc32c cases.
- Lab Beta 2B remains the checksum/final verify evidence baseline:
  `144/144` main rows and `149/149` focused/fallback rows passed.
- Lab Beta 3A final verify gate is tracked in
  [LAB_FINAL_VERIFY_GATE.md](LAB_FINAL_VERIFY_GATE.md). It passed live
  cross-host validation and keeps default `full` final verify.
- Stage C preliminary CRC32C cost review is in
  [LAB_CHECKSUM_COST_REVIEW.md](LAB_CHECKSUM_COST_REVIEW.md). It did not change
  checksum defaults or implement a checksum worker.
- Lab Beta is freeze-ready for the documented conservative default set, but the
  current hardware/storage setup is not a tuned 100G ceiling; do not use these
  throughput numbers as a 100G upper-bound claim, and do not run 100GiB repeat
  until the baseline is lifted or explicitly accepted.

## Post-Freeze Branches

Pick one branch explicitly:

| Branch | Purpose | First actions |
|---|---|---|
| A. 100G readiness / baseline lift | Make machine evidence good enough before larger GridFlux matrices | Fix/explain main PCIe x8, tune TCP/RDMA/NUMA/IRQ, find storage near 8-12GB/s, rerun independent baselines |
| B. CRC32C opt-in prototype | Explore checksum worker/pipeline cost without changing defaults | Prototype opt-in only, keep `final_verify_policy=full`, keep `verified_chunks` opt-in, compare against retained Stage C evidence |

## Result Retention

Keep wrapper JSON, combined/raw CSV, summary CSV, analysis JSON, and cleanup
checks for canonical gates. Per-case stdout/stderr/env/jsonl logs may be moved
to the external private archive once the combined evidence exists.

Canonical evidence paths and archive notes live in
[RESULTS_INDEX.md](RESULTS_INDEX.md).
