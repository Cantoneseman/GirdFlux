# Beta 1B STOR Writeback Diagnosis

Generated: 2026-05-19T15:43:42Z

## Executive Summary

- Passing summary rows: `40`.
- Median of STOR row medians: `9.755 Gbps`.
- Best STOR median: `18.027 Gbps` from `conn=4 checksum=none backend=posix pre=full fiobuf=0 pws=auto->direct mfp=final_only fv=full->full`.
- Best default-like crc32c/POSIX row: `9.866 Gbps` from `conn=8 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full`.

Defaults remain unchanged: anonymous auth, TLS off, data TLS off, POSIX backend, full final verify, every-n-chunks manifest flush, preallocate off, and POSIX write strategy auto.

Grouped fail count across supplied summaries: `0`.

- STOR end-to-end best median: `18.027 Gbps` from `conn=4 checksum=none backend=posix pre=full fiobuf=0 pws=auto->direct mfp=final_only fv=full->full`.
- STOR end-to-end median across row medians: `9.755 Gbps`.
- Temp-write wall share: median `52.3%`, max `84.0%`.
- Data-receive wall share: median `10.4%`, max `21.1%`; this is small next to temp write.
- Manifest/final-verify/rename shares: medians `8.5%`, `8.5%`, `3.0%`; max rename share was `35.1%`.
- Native storage write throughput: median `5.426 Gbps`, best `23.857 Gbps` across supplied storage rows.
- POSIX vs io_uring, file buffer/coalesced, preallocate, final_only, and verified_chunks do not show a stable default-worthy win in this sample.
- Evidence does not yet justify a default policy change; Beta 1B-3 should keep optimization opt-in and profile receiver writeback/backpressure more narrowly.

## Inputs

- `tools/perf/results/20260519T154026Z_storage-bench.csv`
- `tools/perf/results/20260519T154026Z_storage-bench-summary.csv`
- `tools/perf/results/20260519T154152Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260519T154225Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260519T154309Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260519T154330Z_gridftp-private-matrix-smoke.csv`
- `tools/perf/results/20260519T154152Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260519T154225Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260519T154309Z_gridftp-private-matrix-smoke-summary.csv`
- `tools/perf/results/20260519T154330Z_gridftp-private-matrix-smoke-summary.csv`

## Result Counts

- Storage summary rows: `64`; pass cases `64`, fail cases `0`.
- STOR raw transfer rows: `40`; pass `40`, fail `0`.
- STOR summary rows: `40`; pass cases `40`, fail cases `0`.
- Storage raw rows supplied to analyzer: `128`.

## Diagnostic Field Coverage

The focused runner reuses existing C++ metrics. Required STOR fields are present in raw CSVs and carried into grouped summaries.

| field | raw CSV | raw non-empty rows | summary CSV |
| --- | --- | --- | --- |
| temp_write_seconds | yes | 40 | yes |
| data_receive_seconds | yes | 40 | yes |
| manifest_flush_seconds | yes | 40 | yes |
| final_verify_seconds | yes | 40 | yes |
| rename_commit_seconds | yes | 40 | yes |
| write_call_count | yes | 40 | yes |
| write_syscall_count | yes | 40 | yes |
| write_avg_bytes_per_call | yes | 40 | yes |
| write_avg_bytes_per_syscall | yes | 40 | yes |
| file_io_backend | yes | 40 | yes |
| posix_write_strategy | yes | 40 | yes |
| preallocate | yes | 40 | yes |
| file_io_buffer_size | yes | 40 | yes |
| server_dirty_kb_before | yes | 40 | yes |
| server_writeback_kb_before | yes | 40 | yes |
| server_cached_kb_before | yes | 40 | yes |
| server_dirty_kb_after | yes | 40 | yes |
| server_writeback_kb_after | yes | 40 | yes |
| server_cached_kb_after | yes | 40 | yes |
| client_dirty_kb_before | yes | 40 | yes |
| client_writeback_kb_before | yes | 40 | yes |
| client_cached_kb_before | yes | 40 | yes |
| client_dirty_kb_after | yes | 40 | yes |
| client_writeback_kb_after | yes | 40 | yes |
| client_cached_kb_after | yes | 40 | yes |


Environment sidecars carry Dirty/Writeback/Cached before/after values; iostat is kept as a sidecar and `iostat=unavailable` is accepted.

| sidecar field | non-empty | sample path |
| --- | --- | --- |
| server_env_before_log | 40/40 | tools/perf/results/20260519T154153Z_case0000_r00_stor_bytes268435456_c1_chunk4194304_buf262144_crc32c_preoff_fvfull_mfpevery_n_chunks_mfi16_cspnone_fiobuf0_fioqd1_fiobs1_fioadvoff_pwsauto_tlsoff_dtlsoff_server_env_before.log |
| server_env_after_log | 40/40 | tools/perf/results/20260519T154153Z_case0000_r00_stor_bytes268435456_c1_chunk4194304_buf262144_crc32c_preoff_fvfull_mfpevery_n_chunks_mfi16_cspnone_fiobuf0_fioqd1_fiobs1_fioadvoff_pwsauto_tlsoff_dtlsoff_server_env_after.log |
| client_env_before_log | 40/40 | tools/perf/results/20260519T154153Z_case0000_r00_stor_bytes268435456_c1_chunk4194304_buf262144_crc32c_preoff_fvfull_mfpevery_n_chunks_mfi16_cspnone_fiobuf0_fioqd1_fiobs1_fioadvoff_pwsauto_tlsoff_dtlsoff_client_env_before.log |
| client_env_after_log | 40/40 | tools/perf/results/20260519T154153Z_case0000_r00_stor_bytes268435456_c1_chunk4194304_buf262144_crc32c_preoff_fvfull_mfpevery_n_chunks_mfi16_cspnone_fiobuf0_fioqd1_fiobs1_fioadvoff_pwsauto_tlsoff_dtlsoff_client_env_after.log |

- iostat sidecars with device output: `160`.
- iostat sidecars explicitly unavailable: `0`.


## STOR Stage Breakdown

STOR stage percentages use receiver wall-clock elapsed time. Stage values are medians from grouped summary rows.

| case | median Gbps | elapsed s | temp write | data receive | manifest | final verify | rename | spread % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| conn=1 checksum=none backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 12.430 | 0.173 | 0.145 (84.0%) | 0.021 (12.3%) | 0.006 (3.5%) | 0.000 (0.0%) | 0.001 (0.5%) | 0.0 |
| conn=4 checksum=none backend=posix pre=off fiobuf=262144 pws=auto->coalesced mfp=every_n_chunks fv=full->full | 15.812 | 0.136 | 0.111 (81.7%) | 0.023 (17.1%) | 0.001 (0.9%) | 0.000 (0.0%) | 0.000 (0.1%) | 0.0 |
| conn=4 checksum=none backend=posix pre=off fiobuf=262144 pws=coalesced->coalesced mfp=every_n_chunks fv=full->full | 15.502 | 0.139 | 0.112 (80.9%) | 0.023 (16.9%) | 0.003 (1.9%) | 0.000 (0.0%) | 0.000 (0.1%) | 0.0 |
| conn=4 checksum=none backend=posix pre=off fiobuf=0 pws=direct->direct mfp=every_n_chunks fv=full->full | 16.736 | 0.128 | 0.102 (79.7%) | 0.024 (18.8%) | 0.001 (1.2%) | 0.000 (0.0%) | 0.001 (0.5%) | 0.0 |
| conn=4 checksum=none backend=posix pre=off fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 15.355 | 0.140 | 0.110 (78.9%) | 0.022 (15.8%) | 0.007 (4.9%) | 0.000 (0.0%) | 0.006 (4.2%) | 0.0 |
| conn=4 checksum=none backend=posix pre=full fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 17.041 | 0.126 | 0.099 (78.6%) | 0.025 (19.5%) | 0.002 (1.5%) | 0.000 (0.0%) | 0.000 (0.2%) | 0.0 |
| conn=4 checksum=none backend=posix pre=off fiobuf=1048576 pws=direct->direct mfp=every_n_chunks fv=full->full | 17.057 | 0.126 | 0.098 (77.9%) | 0.024 (19.1%) | 0.003 (2.6%) | 0.000 (0.0%) | 0.000 (0.4%) | 0.0 |
| conn=4 checksum=none backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 15.027 | 0.143 | 0.109 (76.0%) | 0.022 (15.4%) | 0.012 (8.4%) | 0.000 (0.0%) | 0.000 (0.1%) | 0.0 |
| conn=4 checksum=none backend=posix pre=full fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 18.027 | 0.119 | 0.090 (75.3%) | 0.025 (21.1%) | 0.004 (3.2%) | 0.000 (0.0%) | 0.001 (1.1%) | 0.0 |
| conn=4 checksum=none backend=posix pre=off fiobuf=1048576 pws=auto->coalesced mfp=every_n_chunks fv=full->full | 13.312 | 0.161 | 0.121 (75.0%) | 0.030 (18.7%) | 0.009 (5.8%) | 0.000 (0.0%) | 0.003 (2.2%) | 0.0 |
| conn=4 checksum=none backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 15.310 | 0.140 | 0.104 (74.4%) | 0.023 (16.6%) | 0.012 (8.6%) | 0.000 (0.0%) | 0.000 (0.2%) | 0.0 |
| conn=4 checksum=none backend=posix pre=off fiobuf=1048576 pws=coalesced->coalesced mfp=every_n_chunks fv=full->full | 13.490 | 0.159 | 0.118 (74.3%) | 0.029 (18.3%) | 0.010 (6.6%) | 0.000 (0.0%) | 0.006 (3.7%) | 0.0 |
| conn=4 checksum=none backend=posix pre=off fiobuf=262144 pws=direct->direct mfp=every_n_chunks fv=full->full | 15.076 | 0.142 | 0.105 (74.0%) | 0.023 (16.1%) | 0.014 (9.6%) | 0.000 (0.0%) | 0.001 (0.6%) | 0.0 |
| conn=4 checksum=none backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 13.888 | 0.155 | 0.114 (73.7%) | 0.020 (13.0%) | 0.020 (13.0%) | 0.000 (0.0%) | 0.007 (4.8%) | 0.0 |
| conn=8 checksum=none backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 14.681 | 0.146 | 0.104 (71.3%) | 0.023 (16.0%) | 0.018 (12.3%) | 0.000 (0.0%) | 0.001 (0.8%) | 0.0 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=final_only fv=verified_chunks->verified_chunks | 12.954 | 0.166 | 0.106 (64.2%) | 0.021 (12.7%) | 0.006 (3.8%) | 0.000 (0.0%) | 0.004 (2.2%) | 0.0 |
| conn=8 checksum=crc32c backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 7.793 | 0.276 | 0.149 (53.9%) | 0.022 (7.9%) | 0.005 (1.8%) | 0.067 (24.4%) | 0.000 (0.2%) | 0.0 |
| conn=8 checksum=none backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 7.498 | 0.286 | 0.152 (53.1%) | 0.023 (8.2%) | 0.111 (38.6%) | 0.000 (0.0%) | 0.101 (35.1%) | 0.0 |


## Receiver Write Call Shape

| case | write calls | write syscalls | avg bytes/call | avg bytes/syscall | file IO wait s |
| --- | --- | --- | --- | --- | --- |
| conn=1 checksum=crc32c backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 1024 | 0 | 262144 | 0 | 0.144 |
| conn=4 checksum=crc32c backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 1024 | 0 | 262144 | 0 | 0.158 |
| conn=8 checksum=crc32c backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 1024 | 0 | 262144 | 0 | 0.148 |
| conn=1 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.113 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.088 |
| conn=8 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.103 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.100 |
| conn=4 checksum=crc32c backend=posix pre=full fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.094 |
| conn=4 checksum=crc32c backend=posix pre=full fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.097 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.100 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.101 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.109 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=verified_chunks->verified_chunks | 1024 | 1024 | 262144 | 262144 | 0.095 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.091 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=final_only fv=verified_chunks->verified_chunks | 1024 | 1024 | 262144 | 262144 | 0.106 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=direct->direct mfp=every_n_chunks fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.106 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=1048576 pws=auto->coalesced mfp=every_n_chunks fv=full->full | 256 | 256 | 1048580 | 1048580 | 0.099 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=1048576 pws=coalesced->coalesced mfp=every_n_chunks fv=full->full | 256 | 256 | 1048580 | 1048580 | 0.113 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=1048576 pws=direct->direct mfp=every_n_chunks fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.092 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=262144 pws=auto->coalesced mfp=every_n_chunks fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.114 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=262144 pws=coalesced->coalesced mfp=every_n_chunks fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.110 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=262144 pws=direct->direct mfp=every_n_chunks fv=full->full | 1024 | 1024 | 262144 | 262144 | 0.104 |
| conn=1 checksum=none backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 1024 | 0 | 262144 | 0 | 0.145 |
| conn=4 checksum=none backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 1024 | 0 | 262144 | 0 | 0.151 |


## Opt-in A/B Deltas

### POSIX vs io_uring

| case | posix Gbps | io_uring Gbps | delta | compare temp write s | spread % |
| --- | --- | --- | --- | --- | --- |
| conn=1 checksum=crc32c backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 9.019 | 7.722 | -14.4% | 0.144 | 0.0 |
| conn=1 checksum=none backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 12.234 | 12.430 | +1.6% | 0.145 | 0.0 |
| conn=4 checksum=crc32c backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 9.226 | 6.979 | -24.4% | 0.158 | 0.0 |
| conn=4 checksum=none backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 15.310 | 7.520 | -50.9% | 0.151 | 0.0 |
| conn=8 checksum=crc32c backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 9.866 | 7.793 | -21.0% | 0.149 | 0.0 |
| conn=8 checksum=none backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 14.681 | 7.498 | -48.9% | 0.152 | 0.0 |


### preallocate full vs off

| case | off Gbps | full Gbps | delta | compare temp write s | spread % |
| --- | --- | --- | --- | --- | --- |
| conn=4 checksum=crc32c backend=posix pre=full fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 9.226 | 9.001 | -2.4% | 0.094 | 0.0 |
| conn=4 checksum=crc32c backend=posix pre=full fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 7.942 | 10.263 | +29.2% | 0.097 | 0.0 |
| conn=4 checksum=none backend=posix pre=full fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 15.310 | 17.041 | +11.3% | 0.099 | 0.0 |
| conn=4 checksum=none backend=posix pre=full fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 15.355 | 18.027 | +17.4% | 0.090 | 0.0 |


### manifest final_only vs every_n_chunks

| case | every_n_chunks Gbps | final_only Gbps | delta | compare temp write s | spread % |
| --- | --- | --- | --- | --- | --- |
| conn=4 checksum=crc32c backend=posix pre=full fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 9.001 | 10.263 | +14.0% | 0.097 | 0.0 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 9.226 | 7.942 | -13.9% | 0.091 | 0.0 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=final_only fv=verified_chunks->verified_chunks | 11.874 | 12.954 | +9.1% | 0.106 | 0.0 |
| conn=4 checksum=none backend=posix pre=full fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 17.041 | 18.027 | +5.8% | 0.090 | 0.0 |
| conn=4 checksum=none backend=posix pre=off fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 15.310 | 15.355 | +0.3% | 0.110 | 0.0 |


### final verify verified_chunks vs full

| case | full Gbps | verified_chunks Gbps | delta | compare temp write s | spread % |
| --- | --- | --- | --- | --- | --- |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=verified_chunks->verified_chunks | 9.226 | 11.874 | +28.7% | 0.095 | 0.0 |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=final_only fv=verified_chunks->verified_chunks | 7.942 | 12.954 | +63.1% | 0.106 | 0.0 |


## Native Storage vs GridFlux STOR

Exact native matches require same bytes, STOR network buffer size, preallocate, backend, file IO buffer size, and POSIX write strategy. Unmatched rows are reported explicitly.

| case | native write Gbps | GridFlux temp-write Gbps | GridFlux e2e Gbps | temp vs native | e2e vs native |
| --- | --- | --- | --- | --- | --- |
| conn=1 checksum=crc32c backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 0.922 | 14.913 | 7.722 | +1518.2% | +737.9% |
| conn=1 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 23.857 | 18.970 | 9.019 | -20.5% | -62.2% |
| conn=4 checksum=crc32c backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 0.922 | 13.580 | 6.979 | +1373.6% | +657.2% |
| conn=4 checksum=crc32c backend=posix pre=full fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 7.174 | 22.771 | 9.001 | +217.4% | +25.5% |
| conn=4 checksum=crc32c backend=posix pre=full fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 7.174 | 22.084 | 10.263 | +207.8% | +43.0% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 23.857 | 24.305 | 8.986 | +1.9% | -62.3% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 23.857 | 21.401 | 7.683 | -10.3% | -67.8% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 23.857 | 21.428 | 7.195 | -10.2% | -69.8% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 23.857 | 21.302 | 9.446 | -10.7% | -60.4% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 23.857 | 19.743 | 9.226 | -17.2% | -61.3% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=verified_chunks->verified_chunks | 23.857 | 22.587 | 11.874 | -5.3% | -50.2% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 23.857 | 23.513 | 7.942 | -1.4% | -66.7% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=final_only fv=verified_chunks->verified_chunks | 23.857 | 20.167 | 12.954 | -15.5% | -45.7% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=0 pws=direct->direct mfp=every_n_chunks fv=full->full | 1.263 | 20.308 | 9.396 | +1508.1% | +644.1% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=1048576 pws=auto->coalesced mfp=every_n_chunks fv=full->full | 0.909 | 19.192 | 6.713 | +2012.1% | +638.7% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=1048576 pws=coalesced->coalesced mfp=every_n_chunks fv=full->full | 0.934 | 16.981 | 7.655 | +1717.1% | +719.1% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=1048576 pws=direct->direct mfp=every_n_chunks fv=full->full | 0.932 | 23.247 | 9.589 | +2394.2% | +928.8% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=262144 pws=auto->coalesced mfp=every_n_chunks fv=full->full | 0.897 | 17.794 | 7.083 | +1884.3% | +689.8% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=262144 pws=coalesced->coalesced mfp=every_n_chunks fv=full->full | 0.929 | 18.500 | 8.076 | +1891.4% | +769.4% |
| conn=4 checksum=crc32c backend=posix pre=off fiobuf=262144 pws=direct->direct mfp=every_n_chunks fv=full->full | 0.929 | 20.563 | 9.643 | +2114.5% | +938.5% |
| conn=8 checksum=crc32c backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 0.922 | 14.450 | 7.793 | +1468.0% | +745.6% |
| conn=8 checksum=crc32c backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 23.857 | 20.760 | 9.866 | -13.0% | -58.6% |
| conn=1 checksum=none backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 0.922 | 14.789 | 12.430 | +1504.7% | +1248.8% |
| conn=1 checksum=none backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 23.857 | 23.512 | 12.234 | -1.4% | -48.7% |
| conn=4 checksum=none backend=io_uring pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 0.922 | 14.227 | 7.520 | +1443.8% | +716.0% |
| conn=4 checksum=none backend=posix pre=full fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 7.174 | 21.670 | 17.041 | +202.0% | +137.5% |
| conn=4 checksum=none backend=posix pre=full fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 7.174 | 23.942 | 18.027 | +233.7% | +151.3% |
| conn=4 checksum=none backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 23.857 | 18.842 | 13.888 | -21.0% | -41.8% |
| conn=4 checksum=none backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 23.857 | 19.782 | 15.027 | -17.1% | -37.0% |
| conn=4 checksum=none backend=posix pre=off fiobuf=0 pws=auto->direct mfp=every_n_chunks fv=full->full | 23.857 | 20.585 | 15.310 | -13.7% | -35.8% |
| conn=4 checksum=none backend=posix pre=off fiobuf=0 pws=auto->direct mfp=final_only fv=full->full | 23.857 | 19.468 | 15.355 | -18.4% | -35.6% |
| conn=4 checksum=none backend=posix pre=off fiobuf=0 pws=direct->direct mfp=every_n_chunks fv=full->full | 1.263 | 20.989 | 16.736 | +1562.0% | +1225.2% |


## Gate Decision And Beta 1B-3 Direction

- Grouped fail count: `0`.
- Highest observed temp-write wall share: `84.0%`.
- Largest exact native-write / GridFlux-temp-write ratio: `1.27x`.
- Median throughput spread across passing STOR rows: `0.0%`.
- Recommendation: evidence is sufficient to enter Beta 1B-3 code optimization; focus on receiver write scheduling/backpressure and default-safe write batching experiments.
- Beta 1B-3 candidate 1: inspect receiver temp write scheduling and socket-to-file backpressure under connections 4/8.
- Beta 1B-3 candidate 2: prototype a bounded receiver-side write queue only behind an opt-in flag, preserving current commit/resume semantics.
- Beta 1B-3 candidate 3: if native storage remains the ceiling, add OS writeback/iostat profiling guidance instead of changing GridFlux defaults.

## Non-Goals Preserved

- No default-policy changes.
- No new protocol behavior, no raw FTP STOR/RETR, no production auth or GSI.
- `io_uring`, `final_only`, `verified_chunks`, `preallocate=full`, and coalesced writes remain opt-in diagnostics.
