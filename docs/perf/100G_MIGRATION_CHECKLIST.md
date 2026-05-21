# 100G Migration Checklist

This checklist prepares the next validation environment. It does not migrate the
current beta run and it does not claim 100G readiness.

## Beta Freeze Boundary

The current Beta RC is a two-cloud-server candidate, not a 100G-certified
release. Keep the conservative default strategy during migration preparation:

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

Before moving GridFlux to a 100G environment, collect four independent
baselines on the target hosts: `iperf3`, `gridflux-storage-bench`, memory sink,
and `gridflux-checksum-bench` CRC32C throughput. Do not start 100GiB repeat
tests until these baselines explain the available network, storage, memory, and
checksum headroom.

## Required Environment Inputs

For each 100G-capable server, record:

- private IP address
- NIC name and link speed
- NUMA layout and CPU model
- test source directory
- test destination/root directory
- available disk or filesystem type
- whether the test path is local SSD, cloud block volume, network filesystem, or
  parallel filesystem

Do not store passwords, tokens, private keys, or certificate private keys in
reports.

## Network Baseline

Run `iperf3` before GridFlux:

- server one -> server two, parallel `1`, `4`, `8`, `16`
- server two -> server one, parallel `1`, `4`, `8`, `16`
- record retransmits, CPU utilization, and achieved Gbps

Target interpretation:

- If `iperf3` is far below expected 100G, diagnose NIC, route, MTU, firewall,
  security group, IRQ/RSS, CPU, or provider limits before GridFlux.
- If `iperf3` is near line rate but GridFlux is not, continue to storage and
  GridFlux stage analysis.

## Storage Baseline

Run storage bench on each target directory before STOR/RETR:

- `gridflux-storage-bench` write/read/rewrite
- buffer sizes `256KiB`, `1MiB`, `4MiB`
- preallocate `off/full`
- POSIX first; io_uring as opt-in comparison
- optional `fio` if already available

Record Dirty/Writeback/Cached, `df`, `mount`, `lsblk`, and iostat sidecars.

## Memory And Checksum Baselines

Run memory sink before file tests to separate network framing from disk effects:

- GridFlux memory sink server/client with parallelism `1`, `4`, `8`, `16`
- same private IP pair and NIC route intended for file tests
- record CPU utilization and achieved Gbps

Run CRC32C benchmark before checksum-enabled transfers:

- `gridflux-checksum-bench` with `auto`, `hardware`, and `software` if
  available
- sizes at least `1GiB` equivalent total work, repeated enough to smooth noise
- record selected backend and GiB/s or Gbps equivalent

If memory sink is far below `iperf3`, inspect GridFlux network framing, socket
buffers, CPU scheduling, and interrupt/RSS placement before storage tests. If
CRC32C is below desired transfer throughput, checksum can become a first-order
limit on 100G even though it was not the main cloud-server bottleneck.

Target interpretation:

- If sequential write is below desired STOR throughput, STOR cannot exceed it
  reliably without changing storage topology.
- If read is high but write is low, expect RETR to scale better than STOR.
- If Dirty/Writeback grows strongly during tests, OS writeback behavior is part
  of the bottleneck.

## GridFlux 10GiB Smoke Order

Run small-to-medium GridFlux checks first:

1. STOR 10GiB, connections `1`, checksum `crc32c`, defaults.
2. STOR 10GiB, connections `4`, checksum `crc32c`, defaults.
3. STOR 10GiB, connections `8`, checksum `crc32c`, defaults.
4. RETR 10GiB, connections `1`, checksum `crc32c`, defaults.
5. RETR 10GiB, connections `4`, checksum `crc32c`, defaults.
6. RETR 10GiB, connections `8`, checksum `crc32c`, defaults.
7. Repeat with `checksum=none` only after crc32c hash-consistent rows pass.

All rows must record sha256 and hash-consistent rows only should be used for
throughput conclusions.

## GridFlux 100GiB Repeat Order

After 10GiB smoke:

1. STOR 100GiB, connections `4`, checksum `crc32c`, repeat `2`.
2. STOR 100GiB, connections `8`, checksum `crc32c`, repeat `2`.
3. RETR 100GiB, connections `4`, checksum `crc32c`, repeat `2`.
4. RETR 100GiB, connections `8`, checksum `crc32c`, repeat `2`.
5. Only then run `checksum=none`, TLS/data TLS, io_uring, preallocate, or
   verified_chunks opt-in variants.

Avoid starting with a full Cartesian 100GiB matrix.

## Bottleneck Attribution

Use this order:

- Network: compare GridFlux to bidirectional `iperf3` with similar parallelism.
- Disk/writeback: compare STOR temp-write throughput to native storage write and
  Dirty/Writeback sidecars.
- Source read: compare RETR source-read time to native read.
- CPU/checksum: compare crc32c vs none, and inspect CPU utilization.
- TLS: compare off/off to required/required only after plaintext rows pass.
- GridFlux path: only suspect GridFlux-specific overhead after network and
  storage baselines show adequate independent headroom.

## Exit Criteria For 100G Claims

Do not claim 100G readiness unless:

- independent TCP baseline is close to expected 100G in both directions;
- storage write/read baselines can sustain the claimed STOR/RETR target;
- 10GiB and 100GiB GridFlux rows are hash-consistent;
- repeat spread is understood and acceptable;
- artifact manifests, logs, CSVs, and sidecars are preserved and verified.
