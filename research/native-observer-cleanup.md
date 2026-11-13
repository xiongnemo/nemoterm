# Native fixture cleanup checkpoint

Commit `1b09f82ea0f813d98c82e9dae174c160bf64f545` passed both the
[comparison/core workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43431838203)
and [single-executable workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43431838348).
It is merged into main. These changes repair test observation and cleanup;
they do not change product source or replace the accepted local executable.

## Changes and checks

* Rectangle editing now records dimensions from the same acknowledged JSON
  snapshot used by the phase wait. A second unchecked mailbox read could return
  an empty result during file replacement. All pixel, Unicode clipboard,
  synchronized output and memory assertions remain. The native result includes
  60x18, 30x9 and 40x12 resize grids and 3,000 overlapping copies.
* Startup caret observation detaches while the owned frontend is alive, before
  requesting normal exit. Atomic stage records retain the point of failure.
  The fixture also checks a zero process exit code and natural job cleanup.
* GPU resize capture now detaches before normal exit. Shared cleanup avoids
  detaching an already-detached session and bounds native Frida operations to
  15 seconds. Nested cleanup still drains the private job after an error.
  The native DirectX resize record confirms capture detached before shutdown.

Frida 17.24.3's synchronous script RPC wait ignores Cancellable. The caret
fixture therefore uses its 120-second CI watchdog for those two observation
requests; it does not claim a 15-second RPC timeout. The separate shutdown
fixture retains its destruction-order assertions. Earlier controller stacks
stalled in Frida detach, but these passing repeats do not explain every
historical terminal close observation.

## Artifact

The [single-EXE artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43431838348/artifacts/14041675507)
contains only `nemoterm.exe`: **4,371,456 bytes**, SHA-256
`1ea595ce00b573335a4de1a2a5e3cdc5a547b49a8b1fa13b9b52ee9cf8f53359`.
Its downloaded hash matches the records for all **57** single-image check groups.
The [validation manifest](native-observer-cleanup-validation.json) lists retained
evidence file hashes and the exact runs.

Runtime observations came from hosted Windows runners. Local runtime tests
remain paused. This checkpoint does not resolve the development branch's
DirectX workload limit, sidecar reply-order mismatch, physical IME/multi-monitor
acceptance or the remaining protocol ledger.

## Main repeat and shutdown diagnostics

The same source's [main single-image repeat](https://github.com/xiongnemo/nemoterm/actions/runs/43434238339)
reached the 45-minute job deadline. The last completed fixture was delegated
console; the next scheduled fixture was shutdown. No completed shutdown
record or log was retained, so this does not identify a blocked call or prove
a product crash. The [core repeat](https://github.com/xiongnemo/nemoterm/actions/runs/43434238410)
passed. The earlier passing checkpoint is retained, not generalized to all runs.

Shutdown observation now writes an atomic phase record before each attach,
script operation, close request, process wait and detach. It streams destruction
events and preserves the existing lifetime assertions. CI sets a 120-second
fixture watchdog, which emits Python stacks and fails instead of waiting for
the overall job deadline; owned processes remain inside a kill-on-close job.
The other native fixtures emit periodic controller stacks after 60 seconds.
The single-image test list keeps its existing order and announces each fixture
before invoking it. Both workflows retain the shutdown JSON even on failure.
These are diagnostic changes, not a claim that the underlying intermittent
shutdown hang is fixed. Local runtime execution remains paused.

Source `52d09621ca30481836c84326251a61064d901ee9` passes both the
[core workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43449297264)
and [57-group single-image workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43449297324).
Both retain all six shutdown cases at `cleanup-complete` with zero exit codes.
The [new artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43449297324/artifacts/14050547004)
contains one 4,371,456-byte EXE; its downloaded SHA-256 is
`2f4fa075381aa90c05d91853f04ac1e6e7f2b31e8c78abf890542d98ae8768cb`.
The [new validation manifest](shutdown-diagnostics-validation.json) binds those
records. This confirms the diagnostic changes pass existing checks; the earlier
timeout remains unexplained and no local runtime acceptance is inferred.
