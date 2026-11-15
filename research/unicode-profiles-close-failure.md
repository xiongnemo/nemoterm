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

`profiles-close-diagnostic.yml` now builds the selected full source commit with
the original MinGW release flags and downloads that source run's identified
console host. It records the rebuilt frontend and every runtime file hash,
then runs three ordinary and three debugger-observed independent lifetimes.
The existing four debugger controls must pass first. Neither repetition arm
changes the close timeout, resource limits or zero-exit assertion. Optional
`--exception-observer` support in the profile fixture retains exception metadata
and dumps through its normal private-job cleanup. A source rebuild and debugger
attachment can both change behavior; successful attempts will not explain the
original failure by themselves.

The first source-diagnostic dispatch (`43686389665`, fixture `f01927a`) stopped
before building or running Nemoterm because the MSYS shell had no `git` command.
The dependency list now explicitly includes MSYS Git for the source-identity
check. That failed setup is not a terminal reproduction or a successful replay.

## Rebuilt-source observations

[Run 43686629800](https://github.com/xiongnemo/nemoterm/actions/runs/43686629800)
at fixture source `8fe8a64` passes all four debugger controls and six independent
profile lifetimes (three ordinary, three with the external debugger). Each
passes the seven functional groups, exits with zero and drains its seven owned
processes naturally. Each debugger log contains only its initial attachment
breakpoint and an ordinary zero process exit; no application exception or
terminal dump was recorded. The deliberate crash control does produce the
expected access-violation dump, kept separately.

The rebuilt frontend SHA256 is
`dd71610cf78514e05d8e4d6f2daa2c2ea4c3eb2a13cbfc46de30871460bd8dd3`,
which differs from the original failed image. Its production source is still
`eae8968`, and its source-host artifact comes from the original core run.
`unicode-profiles-close-validation.json` indexes 66 original records, including
all logs, controls, rebuilt runtime files, per-file hashes and the earlier setup
failure, in `profiles-source-replays.tar.gz`. These finite rebuilt-source passes
do not reproduce or explain the original crash. Its cause remains unresolved;
there is no product close-path fix or acceptance claim from this diagnostic.
