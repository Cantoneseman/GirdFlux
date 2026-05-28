# Lab Beta 3A Final Verify Gate

Date: 2026-05-28

## Current Status

Stage B is complete. The gate keeps the current conservative defaults:

- `final_verify_policy=full` remains the default.
- `verified_chunks` remains opt-in only.
- `manifest_flush_interval_chunks=256` remains the default.
- STOR/RETR framed protocol, manifest v2, and resume facts are unchanged.

The live cross-host final verify gate passed on the lab main/small servers.

## Evidence

| Item | Result | Path |
|---|---|---|
| Historical Beta 2B re-analysis | `row_count=149`, `matched_delta_count=18`, `fail_count=0`, `sha_mismatch=0`, `fallback_row_count=2`, `gate_pass=true` | `tools/perf/results/20260527T140404Z_lab-final-verify-gate-historical/` |
| Live final-verify profile | 10GiB `8/8 pass`, `sha_mismatch=0` | `tools/perf/results/20260527T150541Z_lab-gridflux-profile-final-verify/` |
| Combined Stage B analysis | `row_count=20`, `matched_delta_count=4`, `fail_count=0`, `sha_mismatch=0`, `fallback_row_count=2`, `gate_pass=true` | `tools/perf/results/20260527T150541Z_lab-final-verify-gate/20260527T150541Z_lab-final-verify-gate-all.json` |
| Resume safety | 1GiB STOR/RETR resume `2/2 pass`, effective policy `full` | `tools/perf/results/20260527T150541Z_lab-final-verify-gate/safety_resume_full/` |
| Fallback safety | `checksum=none + verified_chunks` STOR/RETR `2/2 pass`, requested=`verified_chunks`, effective=`full` | `tools/perf/results/20260527T150541Z_lab-final-verify-gate/safety_none_verified_chunks_fallback/` |
| Key repeat | STOR c1 and RETR c16 full/verified_chunks repeat=2, `8/8 pass` | `tools/perf/results/20260527T150541Z_lab-final-verify-gate/key_repeat2_stor_c1/`, `tools/perf/results/20260527T150541Z_lab-final-verify-gate/key_repeat2_retr_c16/` |

## Gate Shape

The `final-verify` profile is a 10GiB, repeat=1, crc32c-only focused matrix:

| Direction | Connections | Policies |
|---|---:|---|
| STOR | 1, 4 | `full`, `verified_chunks` |
| RETR | 4, 16 | `full`, `verified_chunks` |

The profile intentionally inherits the C++ default manifest flush interval and
does not pass an explicit `--manifest-flush-interval-chunks-list`.

## Live Key Data

| Direction | Conn | Full Gbps | verified_chunks Gbps | Gain | Full final verify s | verified_chunks final verify s |
|---|---:|---:|---:|---:|---:|---:|
| STOR | 1 | 3.816 | 5.988 | +56.9% | 8.51 | 0.00 |
| STOR | 4 | 3.591 | 5.431 | +51.2% | 8.50 | 0.00 |
| RETR | 4 | 5.816 | 11.184 | +92.3% | 7.36 | 0.00 |
| RETR | 16 | 5.663 | 11.024 | +94.7% | 7.79 | 0.00 |

In all crc32c rows, `full` verified the full 10GiB again
(`bytes_final_verified=10737418240`), while `verified_chunks` had
`bytes_final_verified=0`. This is the expected opt-in behavior and explains
the throughput delta. The default remains `full`.

## Analyzer

`tools/perf/analyze_lab_final_verify_gate.py` reads one or more raw CSV files
and emits:

- per-case median throughput, final verify seconds, bytes final verified,
  bytes checksummed, manifest flush seconds, pass/fail counts;
- matched `full` vs `verified_chunks` deltas for the same
  size/direction/checksum/connections tuple;
- a JSON gate summary with fail, sha mismatch, and crc32c policy mismatch
  counts.

## Acceptance Criteria

- main and small Debug builds passed;
- main and small focused CTest passed: `62/62` on each host;
- final-verify profile has `fail_count=0` and `sha_mismatch=0`;
- requested/effective final verify policies are recorded correctly;
- `checksum=none + verified_chunks` falls back to effective `full`;
- STOR/RETR resume smoke passed;
- run-root and large temporary files were removed;
- final residual process checks were clean on both hosts.

## Stage C Handoff

Stage C was started only after this gate was green. Its result is a preliminary
CRC32C cost review, not a checksum optimization implementation:
[LAB_CHECKSUM_COST_REVIEW.md](LAB_CHECKSUM_COST_REVIEW.md).

This gate does not make GridFlux 100G-ready. The lab machine baseline remains
below 100G and is tracked in
[LAB_BOTTLENECK_REGISTER.md](LAB_BOTTLENECK_REGISTER.md).
