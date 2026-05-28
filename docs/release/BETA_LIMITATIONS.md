# GridFlux Beta Limitations

Lab Beta RC is a freeze candidate for the current GridFlux Beta feature/default
set. It is not a production certification and it is not a 100G readiness claim.

## Environment Limits

- The lab 100G links are up, but the retained baseline is not line-rate. The
  2026-05-28 recheck found TCP best `27.712/34.295 Gbps`,
  single-direction RDMA best `59.820 Gbps`, and bidirectional RDMA aggregate
  `111.960 Gbps`.
- The main ConnectX-5 is still observed as PCIe `LnkSta x8 (downgraded)` while
  its capability is x16. This is a likely single-direction RDMA cap.
- Direct storage baseline is far below 100G file-transfer needs: retained fio
  values are below `1 GB/s` on both sides, with the 2026-05-28 recheck at
  `0.525 GB/s` best on main and `0.848 GB/s` best on small.
- The small server root/tmp filesystem has about `65G` free in the retained
  checks, so accumulated 100GiB repeat output is not safe without a new storage
  plan.
- NUMA/IRQ/socket-buffer tuning has not been closed. Machine tuning must remain
  separate from GridFlux code-performance conclusions.

Detailed tracking lives in
[LAB_BOTTLENECK_REGISTER.md](../perf/LAB_BOTTLENECK_REGISTER.md).

## Default Strategy

The beta default strategy is:

- `auth-mode=anonymous`
- `tls-mode=off`
- `data-tls-mode=off`
- `file_io_backend=posix`
- `final_verify_policy=full`
- `manifest_flush_policy=every_n_chunks`
- `manifest_flush_interval_chunks=256`
- `preallocate=off`
- `posix_write_strategy=auto`
- `receiver_write_profile=default`
- `receiver_write_yield_policy=none`

The following remain opt-in diagnostics or experiments only:

- `final_verify_policy=verified_chunks`
- `file_io_backend=io_uring`
- TLS/data TLS
- `preallocate=full`
- heavy profile and 100GiB repeat

## Protocol And Security Limits

- Full GridFTP GSI is not implemented.
- DCAU, PROT, and AUTH TLS are not implemented.
- STOR/RETR data TLS exists as an opt-in alpha/beta capability, but it is not
  the default.
- LIST/NLST listing data channels still do not use the STOR/RETR data TLS
  channel.
- Raw FTP STOR/RETR streams are not supported; file data uses the GridFlux
  framed data plane.
- No RDMA data plane, QUIC, FEC, manifest v3, or binary manifest format is part
  of this Beta.

## Performance Limits

- Manifest flush has been optimized and closed for Beta:
  `manifest_flush_interval_chunks=256` is the default, while `16` remains only
  an explicit A/B value.
- Full final verify remains the default safety baseline and is a known
  performance cost for crc32c transfers.
- `verified_chunks` can remove the final reread cost when its safety conditions
  are met, but it remains opt-in.
- CRC32C cost is still material in the lab results. A threaded/pipelined
  checksum worker is only a future opt-in prototype candidate.
- `io_uring` has not shown enough stable benefit under this storage baseline to
  become a default.

## Directory And Metadata Limits

- Directory transfer is manifest-driven and file-content oriented.
- Full directory metadata preservation is not implemented for owner, group,
  xattr, ACL, or empty-directory fidelity.
- Directory sync semantics are not production complete.

## Observability Limits

- Event logs are local JSONL files, not centralized monitoring.
- Metrics and CSV reports are designed for beta diagnostics and release gates;
  they are not a replacement for production telemetry.

## Next Validation Boundary

Before claiming 100G readiness, lift or explicitly accept the lab machine
baseline and rerun independent TCP, RDMA, storage, CPU/NUMA, checksum, and
GridFlux evidence. The first larger GridFlux step after baseline lift should
remain a 10GiB smoke; 100GiB repeat should wait until storage and small-side
space are safe.

The current post-RC decision is documented in
[LAB_100G_READINESS_RECHECK.md](../perf/LAB_100G_READINESS_RECHECK.md):
do not enter 20GiB/100GiB readiness expansion yet.

Post-freeze work should pick one branch at a time: either lift the lab
baseline for 100G readiness, or build a CRC32C opt-in prototype. Neither branch
changes the Beta default strategy by default.
