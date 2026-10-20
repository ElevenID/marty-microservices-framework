# MMF Rust platform migration completion record

**Status:** Complete; Python framework retired

**Completed:** 2026-08-25

## Outcome

The former Python Marty Microservices Framework was replaced by the canonical
Rust workspace. PR 89 introduced the complete crate surface and shared
behavioral contracts. Consumer migrations then removed every supported
`marty-msf` dependency and import. PR 94 froze Python publication while final
release, backup, and beta gates ran. The final retirement removes the frozen
source and Python-specific repository surfaces.

This record supersedes the pre-PR-89 work-in-progress ledger that previously
lived at this path.

## Capability disposition

| Capability family | Canonical Rust owner | Retained evidence |
|---|---|---|
| Core lifecycle and composition | `mmf-core`, `mmf-runtime` | lifecycle, readiness, and capability inventory contracts |
| Configuration and secrets | `mmf-config` | layered configuration, hosting, secret expiry, and fail-closed provider contracts |
| Data, cache, and migrations | `mmf-data` | serialization, TTL, sorted set, lease, read-model, SQL, and Redis contracts |
| Messaging, events, inbox, and outbox | `mmf-messaging` | routing, ordering, scheduling, retry, DLQ, replay, fencing, and PostgreSQL contracts |
| Workflow, saga, CQRS, and event sourcing | `mmf-workflow`, `mmf-patterns` | dependency, retry, timeout, compensation, concurrency, snapshot, and 2PC contracts |
| Security, identity, sessions, and policy | `mmf-security` | JWT, OAuth/OIDC, MFA, mTLS, session, rate-limit, Cedar, tenant, workload, and authorization contracts |
| Observability and SLOs | `mmf-observability` | correlation, trace context, redaction, metrics, SLO, health, alert, and analytics contracts |
| Resilience and performance | `mmf-resilience`, `mmf-testkit` | retry, backoff, circuit, bulkhead, fallback, load, fault, and cleanup contracts |
| Discovery, gateway, mesh, and deployment | `mmf-platform` | discovery, balancing, proxy, HTTP, Redis idempotency, gRPC TLS, and outbound destination contracts |
| Plugins | `mmf-plugins` | configuration isolation, dependency order, lifecycle, subscription, and health contracts |
| Push delivery | `mmf-push` | registration, FCM, SSE, webhook, retry, signature, and health contracts |
| Documentation and developer CLI | `mmf-cli` | command catalog, Rust-first scaffolds, API documentation, version, contract, and host-effect contracts |
| ML platform | `mmf-ml` | feature store, registry, training, serving, cache, metrics, and experiment contracts |
| Built-in services | `mmf-services` | identity HTTP/configuration/persistence/orchestration plus audit/compliance contracts |
| Facade | `mmf` | re-export-only crate; no duplicate implementation |

The machine-readable ownership inventory remains
[`contracts/mmf-capabilities.json`](../contracts/mmf-capabilities.json), and
all behavior fixtures remain under `contracts/`.

## Historical acceptance and recovery record

The completed retirement qualified consumer removal, Rust parity, the
Rust-only v1.1.202 beta lifecycle and two retention copies of the v1.0.0/v1.0.2
artifacts and complete Git history. Production configuration and data were
outside that beta deployment scope. The final machine-readable receipt is
retained in Git history at
[`c7181c8`](https://github.com/ElevenID/marty-microservices-framework/tree/c7181c86949fdb0fb415e52cee364c19615bcfc6/contracts).
This historical acceptance is not a current deployment or recovery health check.

The receipt, frozen filename inventory and tests of their recorded constants
are retired from current source. All behavior fixtures and their direct Rust
consumers remain. Current CI exercises the workspace, negative contracts,
capability owners, Python absence and release guards; it does not check old
beta IDs or infer backup availability from a recorded count/digest. Future
recovery qualification must read actual retained copies and verify complete
history/artifacts and checksums before claiming recoverability. This cleanup
changes no releases, tags, backup copies or retention policy.

## Continuing rule

New behavior must be implemented once in the lowest reusable Rust crate, be
covered by language-neutral behavior and negative-path tests, and be consumed
through crate APIs. Reintroducing Python framework source, packaging, or a
Python release workflow is a regression.
