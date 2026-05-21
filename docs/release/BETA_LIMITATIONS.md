# GridFlux Beta Limitations

Beta RC is a closeout for the current two-cloud-server validation path. It is
not a production certification and it is not a 100G result.

## Environment Limits

- GridFlux has not yet been validated on self-owned 100G servers.
- The current cloud-server private TCP baseline is about `15.5 Gbps`, so it is
  not a 100G environment.
- Current STOR performance is primarily constrained by receiver temp
  write/writeback plus cloud volume, filesystem, page-cache, and OS writeback
  behavior.
- RETR correctness and focused stability pass, but throughput spread remains
  high in full-size focused matrices.

## Default Strategy

The beta default strategy remains:

- `auth-mode=anonymous`
- `tls-mode=off`
- `data-tls-mode=off`
- `file_io_backend=posix`
- `final_verify_policy=full`
- `manifest_flush_policy=every_n_chunks`
- `preallocate=off`
- `posix_write_strategy=auto`
- `receiver_write_profile=default`
- `receiver_write_yield_policy=none`

The following remain opt-in diagnostics only:

- `receiver_write_profile=bounded`
- `receiver_write_yield_policy=dirty_poll`
- `file_io_backend=io_uring`
- `final_verify_policy=verified_chunks`
- `preallocate=full`

## Protocol And Security Limits

- Full GridFTP GSI is not implemented.
- DCAU, PROT, and AUTH TLS are not implemented.
- STOR/RETR data TLS exists as an opt-in alpha/beta capability, but it is not
  the default.
- LIST/NLST listing data channels still do not use the STOR/RETR data TLS
  channel.
- Raw FTP STOR/RETR streams are not supported; file data uses the GridFlux
  framed data plane.

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

Before claiming 100G readiness, run the 100G migration checklist in
`docs/perf/100G_MIGRATION_CHECKLIST.md` on a dedicated 100G-capable environment
with independent TCP, storage, CPU, TLS, checksum, and GridFlux evidence.
