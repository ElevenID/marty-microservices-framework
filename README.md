# Marty Microservices Framework

MMF is ElevenID's canonical Rust microservice crate platform. It provides one
DRY implementation for common service capabilities while keeping
product-specific credential protocols in `marty-core` and application behavior
in consumer services.

## Crate platform

- `mmf-core`, `mmf-config`, `mmf-runtime`, and `mmf-platform` own common
  contracts, configuration, lifecycle, readiness, transports, discovery, and
  deployment models.
- `mmf-security`, `mmf-data`, and `mmf-messaging` own reusable security,
  persistence, caching, event, inbox, outbox, and transport behavior.
- `mmf-observability`, `mmf-resilience`, and `mmf-workflow` own cross-cutting
  runtime behavior.
- `mmf-plugins`, `mmf-services`, `mmf-push`, `mmf-ml`, `mmf-patterns`,
  `mmf-testkit`, and `mmf-cli` provide higher-level capabilities and tooling.
- `mmf` is the facade crate; it does not contain a second implementation.
- `mmf-aws-kms` owns explicit AWS credentials, exact key references and bounded
  signing, MAC and symmetric operations. Its `sdk` feature and the
  `mmf-platform/aws-kms` TLS adapter are optional. Rust 1.95 is required.

Language-neutral fixtures in [`contracts`](contracts) define the retained
behavior. Rust implementations execute those contracts in CI.

```shell
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
```

Dev and test builds use line-table debug information for faster iteration.
Use `cargo build --profile debugging` or `cargo test --profile debugging`
when a debugger needs full local-variable information.

Consumers may pin a reviewed immutable repository revision. Governed Rust
releases also package every crate and can publish them to crates.io when the
separate registry environment gate is enabled.

## Python retirement

The former `marty-msf` Python distribution is retired. Source and release
history retain the completed migration, beta acceptance and recovery record;
the final machine-readable receipts are available at revision
[`c7181c8`](https://github.com/ElevenID/marty-microservices-framework/tree/c7181c86949fdb0fb415e52cee364c19615bcfc6/contracts).
CI no longer reasserts historical deployment IDs, backup counts or checksum
shapes. Those assertions could not observe current recovery-copy availability.

Current Rust tests directly consume every retained behavior fixture, and
capability ownership, Python absence and release workflow guards remain.
See [`docs/RUST_PLATFORM_MIGRATION_ROADMAP.md`](docs/RUST_PLATFORM_MIGRATION_ROADMAP.md)
for the current capability owners and continuing migration requirements.

Rust platform releases use annotated `vMAJOR.MINOR.PATCH` tags. The release
workflow re-runs the complete workspace gates, validates every crate package,
emits a source archive and SPDX SBOM, signs every asset, and publishes
provenance. Registry publication runs in dependency order and supports safe
retries.

## License

Licensed under the GNU Affero General Public License v3.0 only
(`AGPL-3.0-only`). See [LICENSE](LICENSE).
