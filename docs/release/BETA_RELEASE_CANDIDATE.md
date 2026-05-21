# GridFlux Beta Release Candidate

- Timestamp: `2026-05-20T18:26:03Z`
- Result: `pass`
- Source tree hash: `ea8cb1985fe3a2ee7535a61fa0b3f119887995a7ab36664d78afe5b62de29d8b`

## Default Strategy

- `auth-mode`: `anonymous`
- `tls-mode`: `off`
- `data-tls-mode`: `off`
- `file_io_backend`: `posix`
- `final_verify_policy`: `full`
- `manifest_flush_policy`: `every_n_chunks`
- `preallocate`: `off`
- `posix_write_strategy`: `auto`
- `receiver_write_profile`: `default`
- `receiver_write_yield_policy`: `none`

## Beta Gate

- Gate JSON: `tools/perf/results/20260520T180530Z_beta-release-gate.json`
- Gate report: `docs/release/BETA_RELEASE_GATE.md`
- Gate passed: `True`
- Gate failed steps: `0`

## Key Performance Numbers

- `summary_csv`: `tools/perf/results/20260520T120942Z_ftp-gridftp-gridflux-summary.csv`
- `host_baseline_csv`: `tools/perf/results/20260520T120942Z_three-way-host-baseline.csv`
- `plain_ftp_1g_upload_best`: `{'protocol': 'plain_ftp', 'direction': 'upload', 'size_bytes': '1073741824', 'best_Gbps': 1.046, 'median_Gbps': 0.895, 'parallelism': '1', 'checksum': ''}`
- `plain_ftp_1g_download_best`: `{'protocol': 'plain_ftp', 'direction': 'download', 'size_bytes': '1073741824', 'best_Gbps': 0.953, 'median_Gbps': 0.905, 'parallelism': '1', 'checksum': ''}`
- `native_gridftp_1g_upload_best`: `{'protocol': 'native_gridftp', 'direction': 'upload', 'size_bytes': '1073741824', 'best_Gbps': 1.7, 'median_Gbps': 1.665, 'parallelism': '4', 'checksum': ''}`
- `native_gridftp_1g_download_best`: `{'protocol': 'native_gridftp', 'direction': 'download', 'size_bytes': '1073741824', 'best_Gbps': 0.998, 'median_Gbps': 0.991, 'parallelism': '8', 'checksum': ''}`
- `gridflux_1g_stor_best`: `{'protocol': 'gridflux', 'direction': 'stor', 'size_bytes': '1073741824', 'best_Gbps': 1.692, 'median_Gbps': 1.664, 'parallelism': '8', 'checksum': 'none'}`
- `gridflux_1g_retr_best`: `{'protocol': 'gridflux', 'direction': 'retr', 'size_bytes': '1073741824', 'best_Gbps': 5.566, 'median_Gbps': 5.337, 'parallelism': '8', 'checksum': 'none'}`
- `iperf3_gbps`: `[{'parallelism': '1', 'Gbps': 15.687}, {'parallelism': '4', 'Gbps': 15.688}, {'parallelism': '8', 'Gbps': 15.203}]`
- `storage_write_gbps`: `[{'machine': 'server', 'Gbps': 1.03}, {'machine': 'client', 'Gbps': 1.028}]`
- `stor_storage_system_report`: `docs/perf/BETA1B_STORAGE_SYSTEM_ATTRIBUTION.md`
- `stor_e2e_median_best`: `9.921 / 17.128 Gbps`
- `retr_stability_report`: `docs/perf/BETA1C_RETR_STABILITY.md`
- `retr_median_best`: `9.991 / 16.536 Gbps`

## Known Bottlenecks

- Current cloud-server environment is not a 100G validation target.
- STOR remains constrained by receiver temp write/writeback and cloud storage/filesystem behavior.
- RETR correctness/stability is green, but throughput spread remains high in full-size focused data.
- TLS/data TLS, verified_chunks, io_uring, bounded/dirty_poll, and preallocate full remain opt-in.
- Full GSI/DCAU/PROT/AUTH TLS and raw FTP STOR/RETR are not implemented.

## Artifact Closure

- Manifest: `tools/perf/results/20260520T182602Z_beta-release-candidate-artifacts.json`
- Artifact count: `2602`
- Freshness: checked=`2602` stale=`0` status=`pass`
- Sync: checked=`2603` missing=`0` mismatch=`0` status=`pass`
- Verify: checked=`2603` missing=`0` mismatch=`0` status=`pass`

## Failures

- None.
