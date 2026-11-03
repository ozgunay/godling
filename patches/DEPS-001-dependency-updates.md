# DEPS-001: Clawblox's vulnerable crates updated

| Field | Value |
|---|---|
| Upstream SHA | `8be90a0` (v0.1.5-2), nacloos/clawblox, with [v0](v0-fix-cli-sandbox.patch) to [v3](v3-stream-reconnect.patch) applied first |
| Patch | [v4-dependency-updates.patch](v4-dependency-updates.patch) (`Cargo.lock` only) |
| Status | **Built and tested 2026-11-02** in WSL: `cargo build --release`, then the world run against a direct viewer and the relay (ADR-017) |
| Goes with | ADR-017; `.github/workflows/audit.yml`, [`clawblox-audit-ignore.txt`](clawblox-audit-ignore.txt) |

## What was wrong
`cargo audit` on Clawblox's lock file at `8be90a0` (with our patches) found **34 vulnerabilities** and a yanked crate. They are in crates Clawblox pulls in (TLS, HTTP/2, QUIC, tar, zstd), pinned at versions from months before:
- `aws-lc-sys` (5), `rustls` (4), `rustls-webpki` (5), `webpki-roots` (1): certificate and TLS checks, on the world's outgoing connections;
- `quinn-proto` (6), `h2` (1): denial of service in QUIC and HTTP/2;
- `zstd`, `zstd-safe`, `zstd-sys` (4): the recordings' compression;
- `tar` (2): unpacking;
- `crossbeam-epoch` (1), and `spin` 0.9.8, yanked.

## What it changes
Only those crates, each to the newest version Clawblox's `Cargo.toml` allows (`cargo update -p …`), and with them `tokio`, `rand` and `event-listener`, which carried "unsound" warnings: `Cargo.lock` only. The physics (rapier), Lua (mlua, Luau) and everything else stay exactly as they were.

29 of the 34 are gone. The 5 left do not reach the island, and the audit ignores them by name, each with its reason, in [`clawblox-audit-ignore.txt`](clawblox-audit-ignore.txt):
- `pyo3` (2) and `rsa` (1) are not in the `clawblox` binary at all: they belong to Clawblox's Python bindings and to sqlx's MySQL driver.
- `quick-xml` (2) is reached only through `rust-s3` (recordings to R2), whose store Godling never sets up. Its fix needs `rust-s3`'s next major version.

Left as warnings: `tokio` 1.50's `AsyncFd` constructors (RUSTSEC-2026-0386, an API that callers can misuse; no newer tokio resolves here), and `number_prefix` and `paste`, unmaintained.

## Apply
On top of v0..v3, in a clone at `8be90a0`:

```bash
git apply /path/to/godling/patches/v4-dependency-updates.patch && cargo install --path . --locked
```

## Tested
- The audit, with the ignore list: no vulnerabilities left.
- The world built on it, run with recording on: a viewer through the relay and one straight to the world held identical islands on all 343 ticks both saw, and two relay viewers on all 366 places in the stream; recordings written (zstd); a restart reached the relay viewer on its socket.
