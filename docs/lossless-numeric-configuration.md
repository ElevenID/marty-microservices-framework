# Lossless numeric configuration

`mmf_config::numeric_config` provides opt-in native Rust parsers for the frozen
CPython 3.12.13 configuration behavior. No Python runtime, new dependency, or
change to existing MMF JSON/TOML/environment scalar handling is introduced.
Service defaults, worker identity and SQL/time error phases remain consumer-owned.

- `PythonConfigInteger`: validated, canonical signed decimal storage. Accepts
  the selected runtime's 4,300-digit policy without i64/u64/usize narrowing.
  Ordering and `min`/`max` preserve exact values; `to_i64`, `to_u64`, `to_usize`
  are explicitly checked and return `None` on range failure. It is intentionally
  a configuration value, not an arbitrary-precision arithmetic implementation.
- `parse_python_config_float`: decimal/separator/Unicode grammar with the
  original non-finite values retained for consumer policy.
- `parse_bounded_python_config_float`: ordered `max(low, min(high, value))`
  semantics with finite supplied bounds. NaN selects the upper bound; signed-zero
  ties select the bound operand. Ordinary Rust `clamp` does not preserve this.
- `InvalidConfigNumber`: value-free errors suitable for adding a reviewed field
  name at the consumer without retaining or logging the supplied configuration.

## Frozen evidence and tests

The 64-case lexical fixture is vendored byte-for-byte from credentials protected
revision `2a8360558d91fea0c50b43af2590fb750ae5c37e`, path
`contracts/canvas-worker-numeric-lexical-oracle.json`.
Git blob: `3a9e8df0b605191eaf39990baf3e2e1821a63302`.
SHA256: `2a99ab2e95ed041a888d35dcf1414c4ed220bc3cb0cebfa4766705a5ee73973a`.
Do not maintain a separate hand-written list of its expected numeric values.

`contracts/python-numeric-unicode-oracle.json` was observed by enumerating every
codepoint in that same immutable issuance image's Python 3.12.13 runtime:
`ghcr.io/elevenid/marty-credentials-issuance@sha256:9f15b64bc0ec7a693339cada3142b2952a575d2b50ee89230aabe078d0026176`.
For each Unicode decimal character, both `int(character)` and `float(character)`
were checked against `unicodedata.decimal(character)`. All 680 decimal digits
form 68 consecutive ten-digit blocks in Unicode 15.0.0. For every `isspace`
character, prefix/suffix integer and float parsing was attempted: 25 are accepted,
while ASCII U+001C through U+001F are rejected. The original observed runtime
policy accepts 4,300 digits (including leading zeroes), rejects 4,301, and ignores
valid separators for this count. Additional finite-bound observations retain
exact IEEE-754 bits, including signed-zero ties. These are observed versioned
tables, not a claim of compatibility with every future Python/Unicode version.

Rust tests replay all 64 lexical vectors without skips, all Unicode scalar values
against the observed digit map, accepted/rejected whitespace, digit-limit edges,
ordered non-finite/signed-zero bounds, 289 ordering comparisons, checked machine
boundaries, lossless OAuth-style capping and value-free errors. This is parser
proof, not full Canvas configuration or database/loop acceptance.

```sh
cargo +1.93.0 test --locked -p mmf-config
cargo +1.93.0 clippy --locked -p mmf-config --all-targets -- -D warnings
```

## Consumer migration requirement

All behavior fixtures remain directly consumed by Rust tests. The completed
migration receipt and frozen 41-filename inventory are retired from current
source: historical deployment IDs, backup digests and filename existence were
not behavioral or recovery-availability checks. Their final versions remain
in Git history at `c7181c8`. No numeric oracle, fixture, parser case or consumer
migration gate is removed. Capability ownership, Python-absence and release
guards continue alongside the executable positive and negative contracts.

Canvas must adopt the shared owner through a reviewed protected dependency pin,
preserve explicit identity whitespace, replay its full configuration corpus and
the separate consumer-range oracle, and check conversions at the observed SQL/
time boundary. A parser passing these tests does not authorize changing routing
or deleting the retained Python worker. Whole-worker concurrency, cancellation,
fencing, providers, readiness and beta cutover gates remain required.
