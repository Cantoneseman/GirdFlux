# Lab Manifest Flush Optimization

Date: 2026-05-24

## Current Conclusion

`manifest_flush_interval_chunks` now defaults to `256` after Lab Beta 2E.
`16` remains available as an explicit override for A/B and regression checks.

No protocol or integrity semantics changed:

- manifest v2 text format remains unchanged;
- `manifest_body_crc32c` remains the corruption check;
- verified chunk records remain the resume source of truth;
- STOR/RETR framed protocol is unchanged;
- `final_verify_policy=full` remains the default;
- `verified_chunks` remains opt-in.

## What Changed In Beta 2C

- Added checkpoint attribution fields:
  `manifest_sort_seconds`, `manifest_serialize_seconds`,
  `manifest_write_seconds`, `manifest_bytes_written`,
  `verified_chunk_count`, and `completed_range_count`.
- Optimized the session save path without changing manifest format:
  ordered chunk records no longer pay redundant sort cost, and completed ranges
  are rebuilt only when dirty.
- Added `manifest-flush` and `manifest-flush-20gib` lab profiles for explicit
  interval A/B testing.

## Evidence Summary

| Gate | Result | Evidence |
|---|---|---|
| Beta 2C 10GiB A/B | `22/22 pass`, `sha_mismatch=0`; interval `256` reduced manifest flush cost by about `92-95%` in primary crc32c cases | `tools/perf/results/20260524T075209Z_lab-gridflux-profile-manifest-flush/` |
| Beta 2C 20GiB subset | `8/8 pass`, `sha_mismatch=0`; same reduction pattern held | `tools/perf/results/20260524T082718Z_lab-gridflux-profile-manifest-flush-20gib/` |
| Beta 2D repeat gate | 10GiB `66/66 pass`, 20GiB `8/8 pass`, resume safety `2/2 pass`, `sha_mismatch=0` | `tools/perf/results/20260524T093758Z_lab-beta2d-manifest-flush-stability/` |
| Beta 2E default promotion | quick profile `4/4 pass`, `sha_mismatch=0`; routine profiles no longer mask the C++ default | `tools/perf/results/20260524T144503Z_lab-gridflux-profile-quick/` |

Representative Beta 2D medians:

| Size | Direction | Mode | Conn | Throughput 16 -> 256 Gbps | Manifest flush 16 -> 256 s |
|---|---|---|---:|---:|---:|
| 10GiB | STOR | crc32c+full | 1 | 3.487 -> 3.843 | 1.582 -> 0.118 |
| 10GiB | STOR | crc32c+verified_chunks | 4 | 4.465 -> 5.358 | 3.268 -> 0.223 |
| 10GiB | RETR | crc32c+full | 16 | 4.130 -> 5.451 | 6.610 -> 0.464 |
| 10GiB | RETR | crc32c+verified_chunks | 16 | 5.845 -> 11.053 | 7.835 -> 0.377 |
| 20GiB | STOR | crc32c+full | 1 | 3.301 -> 3.722 | 6.287 -> 0.429 |
| 20GiB | RETR | crc32c+verified_chunks | 16 | 4.601 -> 7.265 | 23.898 -> 1.352 |

Full retained paths are listed in [RESULTS_INDEX.md](RESULTS_INDEX.md).

## A/B Entry Points

```bash
python3 tools/perf/run_lab_gridflux_profile.py --profile manifest-flush --dry-run
python3 tools/perf/run_lab_gridflux_profile.py --profile manifest-flush \
  --manifest-flush-intervals 16,64,256,1024 --dry-run
python3 tools/perf/run_lab_gridflux_profile.py --profile manifest-flush-20gib --dry-run
```

Routine `quick` / `focused` / `release` / `heavy` profiles inherit the default
`256` interval and intentionally do not pass an explicit interval flag.

## Not Done

No manifest v3, binary manifest, raw FTP path, RDMA protocol work, 100GiB heavy
run, or default `verified_chunks` change was made in this series.
