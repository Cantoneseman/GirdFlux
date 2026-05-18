# GridFlux Directory Transfer Alpha

Phase 5A adds alpha-grade multi-file directory transfer on top of the existing
single-file GridFTP-like control plane. It does not add raw FTP recursive
transfer: every file still uses the GridFlux framed STOR/RETR data channel.

## Commands

Upload a local directory into a server root-relative directory:

```bash
gridflux-tree-upload-client \
  --host <server-host> \
  --port <control-port> \
  --source-dir <local-dir> \
  --dest-dir <remote-dir> \
  --connections 2
```

Download a server root-relative directory into a local directory:

```bash
gridflux-tree-download-client \
  --host <server-host> \
  --port <control-port> \
  --source-dir <remote-dir> \
  --dest-dir <local-dir> \
  --connections 2
```

Common options include `--file-parallelism`, `--chunk-size`, `--buffer-size`,
`--checksum`, `--checksum-backend`, `--resume`, `--max-files`, `--user`, and
`--password`. Phase 5A validates `--file-parallelism` but keeps execution
conservative; files are processed in stable order.

## Manifests

Directory transfer adds a file-level manifest:

- Upload: `<source_dir>.gridflux.tree.upload.manifest`
- Download: `<dest_dir>.gridflux.tree.download.manifest`

The tree manifest records the transfer mode, logical root path, checksum
policy, and one record per regular file: relative path, size, mtime,
transfer_id, status, and error text. It is atomically saved and protected by a
CRC32C body checksum.

Each file still has its existing single-file manifest:

- Upload/STOR uses server-side `<output>.gridflux.manifest`.
- Download/RETR uses receiver-side `<output>.gridflux.download.manifest`.

## Resume

Use `--resume` to continue a directory transfer. Completed files are skipped
only after size validation. Pending or failed files reuse their stored
`transfer_id` and enter the existing `REST GFID:<transfer_id>` per-file resume
path.

If the tree manifest is corrupt, resume fails. If a source or destination file
has changed relative to the tree manifest, the file is marked `changed` and the
transfer fails safely. Phase 5A does not automatically overwrite or delete
already committed files.

`--max-files <N>` intentionally stops after N completed files and exits nonzero;
it is intended for smoke tests and recovery drills.

## Path And Metadata Limits

The scanner only includes regular files. Symlinks, non-regular files, absolute
paths, `..`, Windows drive-style paths, backslashes, and control characters are
rejected. Remote paths are always interpreted relative to the configured
`gridflux-gridftp-server --root`.

Phase 5A does not preserve empty directories, permissions, owner/group, xattrs,
ACLs, or directory mtimes. It is not a replacement for production rsync.

## Boundaries

Directory transfer does not change defaults:

- `file_io_backend=posix`
- `final_verify_policy=full`
- `manifest_flush_policy=every_n_chunks`
- `preallocate=off`
- `posix_write_strategy=auto`

It also does not implement raw FTP STOR/RETR streams, TLS/GSI, production
authentication, MLST/MLSD, third-party server-to-server transfer, or Mode E.
