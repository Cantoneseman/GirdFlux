# GridFlux Release Gate

This directory records the alpha release gate for GridFlux. The gate packages
existing build, CTest, smoke, hygiene, and private baseline checks into one
repeatable flow. It does not change transfer defaults or run new protocol code.

## Quick Gate

Prepare both build directories first, then run:

```bash
python3 tools/release/run_alpha_release_gate.py \
  --quick \
  --build-dir build \
  --io-uring-build-dir build-io-uring-real \
  --remote <remote> \
  --remote-root /root/projects/GridFlux \
  --results-dir tools/perf/results
```

Quick mode runs local build, default CTest, io_uring CTest, public export
hygiene, loopback STOR/RETR full and resume smoke, metadata/list smoke, and
residual process checks.

## Full Gate

Full mode adds a private 1GiB repeat=3 STOR/RETR baseline matrix:

```bash
GRIDFLUX_SSH_PASSWORD='***' python3 tools/release/run_alpha_release_gate.py \
  --full \
  --build-dir build \
  --io-uring-build-dir build-io-uring-real \
  --remote <remote> \
  --remote-root /root/projects/GridFlux \
  --server-host <server-host> \
  --results-dir tools/perf/results
```

The full matrix keeps project defaults and only compares checksum
`crc32c|none` plus final verify `full|verified_chunks`. The default baseline
row is reported separately.

## Outputs

- Markdown report: `docs/release/ALPHA_RELEASE_GATE.md`
- JSON report: `tools/perf/results/<timestamp>_alpha-release-gate.json`
- Artifact manifest: `tools/perf/results/<timestamp>_alpha-artifacts.json`
- Logs: `tools/perf/results/<timestamp>_alpha-release-gate/`

Full gate writes an artifact manifest and syncs only those required artifacts
to the remote tree without deleting remote files. The manifest includes release
docs, release helper scripts, gate JSON, private matrix raw/summary CSV, and
CSV-referenced sidecar logs. `AGENTS.md`, build outputs, secrets, keys, tokens,
and password-like paths are rejected.

Manual verification:

```bash
python3 tools/release/sync_remote_artifacts.py \
  --manifest tools/perf/results/<timestamp>_alpha-artifacts.json \
  --remote <remote> \
  --local-root /root/projects/GridFlux \
  --remote-root <remote-root> \
  --verify-only \
  --json-output tools/perf/results/<timestamp>_artifact-verify.json
```

Dry-run and sync modes:

```bash
python3 tools/release/sync_remote_artifacts.py --manifest <manifest> --remote <remote> --dry-run
python3 tools/release/sync_remote_artifacts.py --manifest <manifest> --remote <remote> --sync
```

`check_remote_artifact_sync.py --manifest <manifest>` remains available as a
verify-only checker for release reports and CI-style gates.

## Public Hygiene

`AGENTS.md` is private and must not enter public exports. Public publishing must
use:

```bash
rm -rf /tmp/gridflux-public
python3 tools/release/export_public_repo.py --output /tmp/gridflux-public --force
python3 tools/release/check_public_hygiene.py --path /tmp/gridflux-public --strict
```

Do not place passwords, tokens, private keys, cookies, or real private topology
values in public documents. Use placeholders such as `<remote>` and
`<server-host>`.
