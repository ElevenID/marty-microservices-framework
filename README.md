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

The former `marty-msf` Python distribution is retired. Its source, packaging,
examples, generated reports, and Python-specific operations tooling were
removed only after:

1. every supported consumer moved to Rust;
2. language-neutral parity and negative-path contracts passed;
3. source and released artifacts showed no supported Python consumer;
4. the v1.0.0 and v1.0.2 distributions, SBOMs, attestations, checksums, tags,
   and complete Git history had two verified retention copies; and
5. the aggregate Rust-only v1.1.202 beta deployment and acceptance gates
   passed without changing the production release.

The immutable Git history and retained release evidence are the rollback and
historical record. Python framework behavior must not be reintroduced. See
[`docs/RUST_PLATFORM_MIGRATION_ROADMAP.md`](docs/RUST_PLATFORM_MIGRATION_ROADMAP.md)
for the capability disposition.

Rust platform releases use annotated `vMAJOR.MINOR.PATCH` tags. The release
workflow re-runs the complete workspace gates, validates every crate package,
emits a source archive and SPDX SBOM, signs every asset, and publishes
provenance. Registry publication runs in dependency order and supports safe
retries.

## License

Licensed under the GNU Affero General Public License v3.0 only
(`AGPL-3.0-only`). See [LICENSE](LICENSE).
