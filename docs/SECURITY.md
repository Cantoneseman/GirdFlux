# GridFlux Security Alpha

Phase 6A adds opt-in control-plane token authentication. Phase 6C adds
opt-in control-plane TLS. These are alpha operator features, not production
security. STOR/RETR file data still uses the existing GridFlux framed data
channel; Phase 6C TLS protects the GridFTP-like control connection only.
GSI/DCAU/PROT and raw FTP TLS compatibility are not implemented.

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

## Control-Plane TLS Alpha

TLS is opt-in and disabled by default:

```bash
./build/gridflux-gridftp-server \
  --root /tmp/gridflux-root \
  --host 127.0.0.1 \
  --port 2121 \
  --tls-mode off
```

Required TLS mode starts the control listener with an immediate TLS handshake:

```bash
umask 077
openssl req -x509 -newkey rsa:2048 \
  -keyout /tmp/gridflux-control-key.pem \
  -out /tmp/gridflux-control-cert.pem \
  -sha256 -days 1 -nodes -subj '/CN=localhost'

./build/gridflux-gridftp-server \
  --root /tmp/gridflux-root \
  --host 127.0.0.1 \
  --port 2121 \
  --tls-mode required \
  --tls-cert-file /tmp/gridflux-control-cert.pem \
  --tls-key-file /tmp/gridflux-control-key.pem
```

`--tls-mode required` requires `--tls-cert-file` and `--tls-key-file`.
Private key files must be regular files and must not be group/world accessible.
If OpenSSL development/runtime support is unavailable in the build, explicit
TLS use fails with a clear configuration error while `--tls-mode off` remains
usable. `--tls-mode explicit` is reserved for a future AUTH TLS design and is
rejected in Phase 6C.

Tree clients can connect to a TLS-required control server with:

```bash
./build/gridflux-tree-upload-client \
  --host 127.0.0.1 \
  --port 2121 \
  --source-dir /tmp/demo-tree \
  --dest-dir demo-tree \
  --tls-mode required \
  --tls-ca-file /tmp/gridflux-control-cert.pem
```

Token auth and TLS can be combined: TLS is established first, then the existing
`USER token` / `PASS <token-value>` control login is performed.

Important Phase 6C limit: passive data connections are not wrapped in TLS.
STOR/RETR file data still uses GridFlux framed TCP, and LIST/NLST still use the
ASCII metadata data connection. TLS support here is not a GSI replacement and
is not production transport security.

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

Phase 6B/6C event logging follows the same rule: auth/TLS events may record
`auth_required`, `auth_failed`, `tls_required`, `tls_failed`, component names,
and result, but never token contents, passwords, `PASS <value>` strings,
certificate private keys, or file contents. Token, certificate, and key files
remain local runtime inputs and are not release artifacts.

`tools/release/check_public_hygiene.py --strict` rejects obvious token leaks and
token-like artifact paths.

## Non-Goals

Phase 6A/6C does not provide:

- GSI/DCAU/PROT or production PKI integration;
- production identity, account, or authorization management;
- encrypted file data transport;
- AUTH TLS explicit upgrade semantics;
- raw FTP STOR/RETR compatibility;
- changes to checksum, manifest, resume, or final verify semantics.
