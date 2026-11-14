# Stream I/O shutdown lifetime

Closing a session can race a completed pipe operation. The frontend marks its
I/O context `moribund` and waits for the worker. On input EOF/read error or
output write error, the worker publishes its completion and exits immediately.
Previously the moribund branch requested a second shutdown acknowledgement;
that worker had already exited, leaving the context, event and any queued
output allocated. Successful I/O still needs the existing acknowledgement.

Commit `7a3b95e` recognizes these terminal completions and retires the context
directly. The worker accesses only local variables after publishing them, and
ready-list synchronization publishes the completion fields before they are read.
The change does not cancel pending I/O or claim to synchronously join workers.

Before the fix, isolated real-pipe tests pass idle output shutdown and a 64 KiB
transfer, but both close-during-EOF and close-during-write-error fail their
two-second retirement deadline with one live closing context. Their source,
logs and image hash are retained, including the initial missing-stub link failure.
The final regression covers seven cases: idle output, input EOF, input error,
output error, successful read/write already completed before close, and full
bidirectional transfer. Both MinGW and MSVC builds pass 40 repetitions per case
and exact OS handle-count equality after each iteration. This includes 280
cases per compiler plus one warm-up before the baseline measurement.

The opt-in automation API now adds read-only `io_handles` counts to discovery
and list responses; [the API documentation](../docs/AUTOMATION.md) defines their
scope. Observed counts are `(input=1, output=1, closing=0)` for one live session,
`(2,2,0)` for two sessions, and `(1,1,0)` again after closing the second session.
The test also checks cumulative creation/destruction balance. Counters do not
flush callbacks or wait for cleanup, and are not OS/driver handle counts.

The development frontend, SHA-256
`d95d46d73c39256ca5e3878b42467eb6aa63480fac332eb71b65180d8ae1ecf2`, passes
ten automation groups with identical API/reference pixels, seven session
lifetime groups, the retained-session restart fixture, and all six combinations
of GDI/OpenGL/DirectX with child exit or window close. The four outer owned jobs
drain 10, 36, 15 and 20 processes naturally. Tests target only newly created
processes. Session fault injection and shutdown probes are diagnostic checks;
none of these small-window runs is full-grid memory acceptance.

The [manifest](io-lifetime-validation.json) verifies 41 compressed evidence
records. [Core/compiler CI](https://github.com/xiongnemo/nemoterm/actions/runs/43539455051)
and [single-image CI](https://github.com/xiongnemo/nemoterm/actions/runs/43539454999)
are pending. The existing DirectX resource-growth failure remains a separate
question until the original workload is repeated. The accepted local executable
has not been replaced.
