# MSVC tab-selection access violation at 8655aae

This failure remains unresolved. The MSVC native-renderer job in
[run 43768960240](https://github.com/xiongnemo/nemoterm/actions/runs/43768960240/job/132980310939)
completed seven nine-check tab replays, then failed the eighth replay while
selecting the first tab immediately after detaching the key/fault/hover probes.
The original image is 3,538,432 bytes, SHA256
`11d36b78d616b27407e485bf4df36f304d84f292127432b6617749d5b6b37244`,
from source `8655aae163a81c927537e18845f930d42df6cafc`.

The visible fixture error is a wait for tab visibility. Its retained process
record establishes an earlier frontend exit with `0xc0000005` (access
violation). The failure occurred after 26.469 seconds, with a 300-second
client lifetime and no client-exit receipts. It is not the previously diagnosed
client-lifetime limit. The job's 54 processes were already inactive at cleanup;
this does not make the crashing test a successful shutdown check.

The requested renderer was OpenGL; the actual renderer was GDI (1), at
88x35 with Consolas and a right-hand tab bar. Read-only boundary snapshots show
the host window-procedure entry patched before detachment and its original
bytes restored immediately afterward. The process was still alive at that
snapshot. These observations establish timing, not a product or instrumentation
root cause. The original runner produced no usable crash dump or application
error record.

## Exact-image diagnosis

The original MSVC image and both console sidecars were downloaded from the
failed job, with GitHub ZIP digests and member hashes verified. The original
fixture source and Frida 17.24.3 were retained.

* Three ordinary local replays and three local replays with an external
  exception observer pass all nine checks. They request GDI explicitly to match
  the original actual renderer; their grid, font and client deadline are unchanged.
* [Hosted diagnostic run 43771071811](https://github.com/xiongnemo/nemoterm/actions/runs/43771071811)
  passes twelve external-observer replays on the exact image and source-matched
  fixture. It retains the original OpenGL request, GDI fallback, 88x35 Consolas
  and 300-second client deadline. All 648 owned processes drain naturally.
* The hosted observer captures no second-chance exception or crash dump in
  those twelve replays. It records one first-chance `0x40080201` event per
  replay. Four explicit observer controls verify normal exit, intentional crash
  capture, detach and debugger-exit behavior.

The external debugger changes timing and exception dispatch. These finite
replays are diagnostic evidence, not a fix, acceptance replacement, or an
explanation of the original failure. The separate earlier `23c90fe` callback
exception remains a separate observation.

`tab-select-msvc-8655aae.tar.gz` and its validation manifest retain the original
failed job log and ZIPs, the seven successes and eighth failure, exact image and
sidecars, local source snapshots/replies, all hosted event records and observer
controls. Every archived member is rehashed after compression.

Further investigation needs an exception address/stack from a recurrence or
a controlled comparison isolating the detached probes. No speculative product
change, relaxed timeout, skipped assertion or accepted-image replacement has
been made for this failure.
