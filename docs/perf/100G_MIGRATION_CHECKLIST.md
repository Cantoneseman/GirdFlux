# 100G Migration Checklist

This checklist prepares the next validation environment. It does not migrate the
current beta run and it does not claim 100G readiness.

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
