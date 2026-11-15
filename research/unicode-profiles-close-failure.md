# Mixed-profile close failure at the Unicode memory checkpoint

[Ordinary CI 43684006470](https://github.com/xiongnemo/nemoterm/actions/runs/43684006470)
at `eae896846561f73fa1c444808ca3f7319707857a` passes the sanitizer, MSVC diagnostic
and source-console-host jobs. Its MinGW native job fails the mixed-profile
fixture at the final zero-exit assertion, after all seven functional checks.
The frontend exits with Windows access violation `0xC0000005`.

The recorded frontend SHA256 is
`d59a8d1e8e0094cc1bc2435d5a65de94659d881845a1cb3fd8fabf6ceb25a8d6`.
The three tabs use actual GDI, GDI fallback from requested OpenGL, and DirectX.
The fixture completes saved-profile creation, session input isolation, font
zoom, hidden-window request isolation, 36 renderer switches and synchronized
output across renderer recreation. It closes its capture helpers and detaches
the key probe, posts `WM_CLOSE` to the owned host, then sees the nonzero exit.
This ordering does not identify which operation caused the fault.

The owned job still has four active processes at cleanup, so the fixture
terminates the remainder. The retained application-event file is an empty
JSON array; no terminal dump or faulting-thread stack was captured. Later
Unicode native and dense-memory steps were not reached. The separate
single-image workflow remains independent of this failed job.

The workflow retained test results (artifact `14149956745`), but its portable
product upload required all native checks to pass. The original MinGW EXE
therefore is not present in the artifact list. A source rebuild would not be
an exact-image replay. Future failures now retain the complete runtime directory
as `unverified-mingw-runtime-<source>` for seven days; it remains clearly distinct
from a passed portable package. No original failed executable is reconstructed
or represented as retained by this change.

This precedes the image-cell index optimization and is not evidence of a
regression caused by that later change. Earlier intermittent close/probe
incidents remain documented in [tab-probe-detach.md](tab-probe-detach.md) and
[native-exception-observer.md](native-exception-observer.md); an equivalent
root cause has not been established. A targeted diagnostic needs an external
exception observer attached to a newly owned mixed-profile process, plus the
existing observer controls. Local desktop testing stays paused.
