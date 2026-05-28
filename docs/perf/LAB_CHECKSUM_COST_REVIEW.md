# Lab Beta 3A CRC32C Cost Review

Date: 2026-05-28

This is a preliminary Stage C review. It decides whether CRC32C deserves a
future optimization plan; it does not implement a checksum pipeline, does not
change defaults, and does not claim 100G readiness.

## Inputs

- Live Stage B final verify gate:
  `tools/perf/results/20260527T150541Z_lab-final-verify-gate/`
- Stage C 10GiB six-row matrix:
  `tools/perf/results/20260528T165246Z_lab-checksum-cost-review/`
- Historical Beta 2B checksum/final verify matrix:
  `tools/perf/results/20260523T065043Z_lab-beta2b-checksum-final-verify/`

Stage C rows were:

- STOR none/full c1
- STOR crc32c/full c1
- STOR crc32c/verified_chunks c1
- RETR none/full c16
- RETR crc32c/full c16
- RETR crc32c/verified_chunks c16

The matrix passed `6/6`, with `fail_count=0` and `sha_mismatch=0`.

## Key Data

| Direction | Conn | none/full Gbps | crc32c/full Gbps | crc32c/verified_chunks Gbps | crc32c/full drop vs none | crc32c/vc drop vs none |
|---|---:|---:|---:|---:|---:|---:|
| STOR | 1 | 13.709 | 3.677 | 5.824 | -73.2% | -57.5% |
| RETR | 16 | 11.269 | 5.337 | 11.453 | -52.6% | +1.6% |

| Direction | crc32c/full final verify s | crc32c/vc final verify s | crc32c sender checksum s | crc32c receiver checksum s |
|---|---:|---:|---:|---:|
| STOR c1 | 8.50 | 0.00 | 7.38 / 7.04 | 8.36 / 7.41 |
| RETR c16 | 8.37 | 0.00 | 24.04 / 23.39 | 0.00 / 0.00 |

For STOR, the numbers before and after the slash are `full` and
`verified_chunks`. For RETR, checksum work is primarily on the sender side.

## Interpretation

- Full final verify is a major removable opt-in cost: Stage B showed
  `verified_chunks` removes the 10GiB reread verify pass and improves crc32c
  throughput by about `51-95%` in the focused cases.
- After final verify is removed, RETR crc32c/verified_chunks is roughly tied
  with none/full in this sample (`11.453` vs `11.269 Gbps`).
- After final verify is removed, STOR crc32c/verified_chunks still trails
  none/full by about `57.5%`; both sender and receiver still checksum the full
  10GiB, and the lab storage/network baseline is also constrained.
- CRC32C is worth a future opt-in prototype discussion, most likely around
  threaded/pipelined checksum work, but not before preserving the safety
  default and keeping machine baseline limits explicit.

## Decisions

- Default checksum behavior is unchanged.
- Default `final_verify_policy=full` is unchanged.
- `verified_chunks` remains opt-in only.
- No checksum worker, no protocol change, no manifest change, and no 100GiB
  repeat was done in this review.

## Next Recommendation

Do not make a checksum optimization the next default-track change yet. First
carry the Beta RC gate with the current conservative defaults, then decide
whether a checksum worker prototype is worth a separate opt-in experiment. The
machine baseline still needs a separate lift/review before any 100G-readiness
claim.
