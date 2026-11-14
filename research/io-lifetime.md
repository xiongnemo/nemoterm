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

The [manifest](io-lifetime-validation.json) verifies 140 compressed evidence
records. [Core/compiler CI](https://github.com/xiongnemo/nemoterm/actions/runs/43539455051)
passes all four jobs, including the new MinGW and MSVC lifetime tests.
[Single-image CI](https://github.com/xiongnemo/nemoterm/actions/runs/43539454999)
passes 101 groups. Artifact 14092218719 contains a 4,450,816-byte EXE, SHA-256
`b1a1f25ca3014714b03de2559ce695281b3ef26bc3c2b450f8ca3e85cdceec50`.
Its local automation check passes all ten groups, with identical reference/API
pixels and natural cleanup.

The downloaded image's unmodified local Sarasa 160x48 GDI workload fails early:
361 handles at baseline become 407, with corresponding GDI/USER growth. A
same-session comparison uses the identical fixture with the previous C1 image
and this image. The C1 control completes all nine groups from a 405-handle
baseline; this image again starts at 361 and fails at 407 on cycle index 1.
Both failures are retained, with bounded cleanup of the five remaining inner
processes and empty outer jobs. Neither failed run reaches full memory acceptance.
The differing startup baselines need investigation; the comparison does not
establish which initialization or source change causes them. This fix remains
unmerged despite green CI. The accepted local executable has not been replaced.
