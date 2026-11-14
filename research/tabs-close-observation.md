# Overflow-tab close observation and automation coverage

Single-image CI [43567290829](https://github.com/xiongnemo/nemoterm/actions/runs/43567290829)
at transport-only source `3a60e4f` passed the bottom overflow case's five
interaction checks, then timed out waiting 15 seconds for the frontend to close.
The private job still contained one live frontend; its remaining processes had
exited. Cleanup forcibly terminated that frontend. This remains an unexplained
CI timeout. No stack was captured in that run, so neither the terminal nor
Frida can be identified as its cause from that record alone.

The exact failed image has SHA-256
`3160d72182db4c1760f664d75293837f34ddc49315fe44d75d0c36732c6c37c3`.
A finite three-run local replay of its original bottom-side fixture did not
reproduce the timeout: close took 0.0901, 0.0836 and 0.0869 seconds. The only
fixture changes for those observations added close timing and read-only thread
metadata on timeout. Navigation still used the original Frida key probe.
These passing replays are not evidence that the intermittent failure is fixed.

## Fixture change

`tests/tabs_overflow_window_smoke.py` now starts its own instance with
`--automation`, verifies the discovered PID, maps every terminal HWND to an
explicit session ID, and sends Ctrl+Tab / Ctrl+Shift+Tab through the public key
operation. Active-session IDs and titles supplement the existing visible-window
and exact active-stripe pixel checks. No Frida attach, injected script or global
keyboard input is used. Native wheel, middle-click, background close and host
WM_CLOSE operations keep their original target HWNDs and semantics.

All five original interaction assertions remain. The 15-second close deadline
is unchanged, zero exit status is required, and discovery must no longer expose
the closed process. A timeout still fails; it now also records whether the host
HWND exists and attempts a read-only owned-thread metadata snapshot before the
private job cleanup. A metadata error is recorded separately and cannot turn a
timeout into a pass.

This removes an instrumentation dependency from this test and exercises the
real automation interface. It is a fixture improvement, not a terminal product
fix or a claim that the original CI hang was caused by injection.

## Results

The updated fixture passed top, bottom, left and right strips against both the
failed CI image above and main `8264b27`'s successful CI image:
`11041b9d7b1ee3107827dd53336de6d46cd5f8db8f606915e936a0efdf070e8b`.
All eight runs passed the original five interaction groups plus session identity
and endpoint teardown assertions. Close took 0.0802–0.0991 seconds. All 23 outer
job processes per run exited naturally; the three original-fixture replay jobs
also drained naturally. No failed CI product was promoted to `dist`.

The [validation manifest](tabs-close-observation-validation.json) retains 64
compressed records (96,729 bytes): the original CI failure/log/identity,
original and updated fixtures, replay drivers, finite comparison results,
screenshots and cleanup records. New CI must still validate the changed fixture
on hosted runners. The original intermittent failure remains tracked rather
than being relabeled as resolved by a successful rerun.
