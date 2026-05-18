# GridFlux Security Alpha

Phase 6A adds opt-in control-plane token authentication. It is an alpha
operator feature, not production security. STOR/RETR file data still uses the
existing GridFlux framed data channel, and TLS/GSI/DCAU/PROT are not
implemented in this phase.

## Modes

Default mode remains anonymous:

```bash
./build/gridflux-gridftp-server \
  --root /tmp/gridflux-root \
  --host 127.0.0.1 \
  --port 2121 \
  --auth-mode anonymous
```

Anonymous mode preserves the existing `USER gridflux` / `PASS gridflux`
placeholder behavior for demos and compatibility tests.

Token mode is explicit:

```bash
umask 077
printf '%s\n' '<token-value>' > /tmp/gridflux-token.txt

./build/gridflux-gridftp-server \
  --root /tmp/gridflux-root \
  --host 127.0.0.1 \
  --port 2121 \
  --auth-mode token \
  --auth-token-file /tmp/gridflux-token.txt
```

The token is read once at startup. Token files must be regular files, non-empty,
and must not be group/world accessible. Token values are not accepted directly
on the command line.

## Client Login

In token mode a GridFlux-aware control client logs in with:

```text
USER token
PASS <token-value>
```

Protected commands return `530` until authentication succeeds. Protected
commands include `TYPE`, `EPSV`, `PASV`, `OPTS`, `REST`, `STOR`, `RETR`,
`SIZE`, `MDTM`, `CWD`, `CDUP`, `LIST`, and `NLST`.

`FEAT`, `SYST`, `NOOP`, `QUIT`, `USER`, and `PASS` remain available before
login so clients can discover capabilities and complete authentication.

## Tree Clients

Directory clients support the same auth settings:

```bash
./build/gridflux-tree-upload-client \
  --host 127.0.0.1 \
  --port 2121 \
  --source-dir /tmp/demo-tree \
  --dest-dir demo-tree \
  --auth-mode token \
  --auth-token-file /tmp/gridflux-token.txt
```

`--auth-token-file` is read locally by the client and is never written to JSON
summary output.

## Release And Public Hygiene

Token files are runtime-only private inputs. They must not be committed,
included in artifact manifests, copied to public export, or written to demo/perf
logs. Public docs should use placeholders such as `<token-value>` rather than
real token contents.

`tools/release/check_public_hygiene.py --strict` rejects obvious token leaks and
token-like artifact paths.

## Non-Goals

Phase 6A does not provide:

- TLS/GSI/DCAU/PROT;
- production identity, account, or authorization management;
- encrypted file data transport;
- raw FTP STOR/RETR compatibility;
- changes to checksum, manifest, resume, or final verify semantics.
