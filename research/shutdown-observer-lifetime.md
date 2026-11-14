# Shutdown observer lifetime diagnosis

The formal [single-image run 43644077420](https://github.com/xiongnemo/nemoterm/actions/runs/43644077420)
failed the GDI window-close case before reaching compression pixels. Product source
is `48a02634323302fddd955b9bc25f2bd90ca7a6d3`; the unverified executable is
4,515,328 bytes, SHA256
`7f3979dbd740604af2aa4075546c13d0e085a3ffa65514fa423ce449f08a0dd8`.
The failure remains a failure. No product code is changed by this diagnosis and
the accepted local executable has not been replaced.

## What the failed run establishes

The child-exit case passed. In the following window-close case, the observer
reported that the terminal HWND was gone when its seat was freed, then observed
entry to `CoUninitialize` with the seat already freed. The original 10-second
process-exit wait expired. The owned job had one active process out of three:
the frontend remained, while its console host and child had exited. The failure
snapshot found one frontend thread and no pending I/O on that thread. The
terminal window was absent; helper timer/IME windows remained. Frida detach also
timed out, and the fixture recorded forced cleanup of the owned frontend.

This narrows the failure to a late exit stage. It does not establish the thread's
current instruction, a deadlock stack, or whether the observer caused the hang.
It is distinct from the earlier mixed-profile close failure where all seven
owned processes remained alive.

## Observer change and sensitivity controls

The old heap callback remained installed through process shutdown. The revised
observer verifies successful release of the watched allocation on function
return and then detaches its heap listener. It keeps the window callback through
the complete `CoUninitialize` call, requires its return, and retires its remaining
listeners there. It never changes application arguments, return values, window
messages or process lifetime. The original 10-second exit limit and destruction
ordering assertions remain, with successful-free and COM-return assertions added.

This lifetime boundary is deliberate: Windows documents that `ExitProcess`
terminates other threads before DLL detach and that locks held by terminated
threads can cause detach to deadlock. This is a reason to avoid leaving callback
machinery installed unnecessarily, not proof of the cause here.
[Microsoft ExitProcess documentation](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-exitprocess).
Frida documents per-listener `detach()` and per-invocation callback state; only
this script's listeners are detached.
[Frida Interceptor API](https://frida.re/docs/javascript-api/#interceptor).

The smoke fixture now pairs each instrumented case with a separate uninjected
case: three renderers, two close paths and two observer modes, 12 owned lifetimes.
The uninjected cases never attach Frida. A small separate native program checks
that the observer accepts orderly destruction, detects release before window
destruction, and detects release after COM cleanup. Its window data is an opaque
marker: the window procedure never reads released storage. These three controls
pass locally with strict GCC compilation; MSVC execution is a separate CI gate.

## Exact-image local evidence

Using the exact failed executable above, the old GDI fixture passed both close
paths in three fresh repetitions. Thus the CI failure did not reproduce locally
even before the observer change. With the revised fixture, three repetitions of
all 12 cases passed: 18 instrumented and 18 uninjected lifetimes, each ending
naturally without terminating remaining owned processes. These passes support
the revised test's operation; they do not prove the original failure's cause.

`shutdown-observer-lifetime-validation.json` indexes 35 deterministic gzip records
with raw byte lengths and SHA256 hashes: the failed CI records, executable
identity, all old/new local repetitions, and all three observer controls. The
manual close-replay workflow can select `fixture=shutdown`, verify the unchanged
product source and exact executable hash, and run the controls plus three fresh
repetitions on a Windows runner. A successful diagnostic replay will still not
constitute full product acceptance.
