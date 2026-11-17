# Owned async lifecycle and disposal

`mmf_runtime::managed_task` is the shared owner for an initialized async
operation and its asynchronous resource cleanup. It extends the existing
synchronous service-container shutdown API; that API and HTTP/runtime
readiness semantics remain unchanged.

## Behavioral boundary

`ManagedTask::spawn` starts the operation with a retained cleanup closure.
`cancel()` or a cloned `cancellation_handle()` requests cancellation. `join()`
is the completion boundary: it does not return until the operation has exited
and its cleanup has finished. Cancellation aborts and **awaits** the operation
before starting cleanup. Cancellation requests cannot abort cleanup.

The returned `TaskCompletion` keeps operation and cleanup outcomes separate.
An operation error is not erased by cleanup failure, and successful work is
not proof of successful disposal. Panics are reported without exposing their
payload through the result. The process panic hook still applies; this API
does not itself add logging or replace application privacy controls.

Dropping the owner, including an in-progress join future, requests cancellation
and leaves the supervisor to finish cleanup. Drop is not an acknowledgment:
keep the Tokio runtime alive and await `join()` when completion matters.
Forced runtime shutdown, process abort and host failure cannot promise async
cleanup. A supervisor join error must not be counted as successful disposal.
The caller must own its child work; this primitive cannot discover arbitrary
detached tasks created inside an operation. The Canvas owned-cycle correction
is therefore still required when this owner is adopted there.

## Frozen evidence and tests

`contracts/async-task-lifecycle.json` records the language-neutral initialized
entry-point floor already observed by credentials' actual Python lifecycle
tests at protected `b027e834d71dee0cc3550aac1150cdb0c40946ae`, test Git blob
`b3c85cfa7bf03c11c90ed440221f47343ee1ae36`: operation return, error and
cancellation all await engine disposal; active operation cleanup precedes
completion acknowledgment. No Python module or runtime implementation is copied.

The Rust replay blocks cleanup on a controlled gate and verifies join cannot
finish early on both current-thread and multi-thread runtimes. It checks exact
event order and preserves returned values and errors. Finishing cleanup despite
late cancellation is a deliberate stronger native property, not a claim that
legacy repeated cancellation was observed. Native-only extensions also cover
panics, separate cleanup errors, pre-start
cancellation, and dropped-owner/join requests. A regression test demonstrated
that directly dropping a pre-cancelled future in the supervisor could panic
and skip disposal; the corrected implementation observes even that destructor
inside the operation task before proceeding to cleanup.

A separate regression verifies that resource disposal precedes release of a
panic result even when that result's destructor also panics. The existing owner
already satisfies this ordering; no runtime behavior change was needed. The
caller receives a supervisor join error rather than a false success, while the
test independently observes that cleanup completed before result destruction.

Tokio moves from a development-only to a normal runtime dependency; it was
already resolved in the lockfile. No dependency version or crypto pin changes.
The existing synchronous/HTTP runtime and retirement inventory contracts remain
mandatory alongside these new tests.

## Consumer verification

Each consuming service must adopt the shared owner through a reviewed dependency
pin and use its explicit cancellation and join boundary. Its resource lifecycle
tests must verify disposal on every initialized exit and distinguish graceful
drain from cancellation. The primitive alone does not prove that a database
pool, HTTP client or external provider is correctly integrated by its caller.

Service implementation retirement, release qualification and deployment are
separate decisions owned by that service; they are not shared-library gates.
