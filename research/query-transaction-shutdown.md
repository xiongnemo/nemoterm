# Query-transaction product: late shutdown timeout

[Single-image run 43660381407](https://github.com/xiongnemo/nemoterm/actions/runs/43660381407)
fails before reaching the new query-error checks. Source is
`88743d31c21090bf78be63fc2719a51993507310`; the unverified single executable is
4,515,840 bytes, SHA256
`214abd0b87b45397d5952cb4151ac0778cc4b436c5ba34fa1a4e4bf0ad160c47`.
Artifact `14139608856` is retained for diagnosis, not distribution acceptance.
The accepted local `dist/nemoterm.exe` remains the earlier `6e05bd1` image.

The component run passes GCC/Clang/MSVC, including real-core query replay and
GCC/Clang ASan/UBSan. The separate ordinary workflow continues independently.
Neither result overrides the failed single-image gate.

## Failure and unchanged local replay

Nine shutdown cases pass. The tenth, DirectX child-exit with the lifetime probe,
exceeds the original 10-second exit wait. Actual renderer ID is 3. The probe
reports the terminal window destroyed, successful seat release, COM cleanup
entry and return, and retirement of its heap/window/COM listeners. Failure
metadata finds one remaining frontend thread and one active process out of
three; the child and console host have exited. Only hidden timer/IME windows
remain. Frida detach then exceeds its separate 15-second bound, and the fixture
records forced cleanup of the owned frontend.

That thread's start address is not its current instruction. There is no original
dump or stack establishing the cause. This is a late shutdown timeout, distinct
from the historical MSVC access violation and the seven-process profile-close
failure. The already revised probe still encounters this timeout, so its earlier
listener-retirement change is not evidence that all exit hangs were resolved.

One local replay uses the exact failed EXE and unchanged committed fixtures.
All 12 cases pass with actual GDI/OpenGL/DirectX and natural owned-job cleanup.
This finite pass does not explain or invalidate the original failure.

## Optional failure dump

`shutdown_window_smoke.py --failure-dump <helper.exe>` adds a diagnostic action
only after a live-process check has already failed. The helper receives inherited
process and private-job handles and independently verifies live membership.
It invokes `MiniDumpWriteDump` from a separate process with thread information
and unloaded-module records. It does not attach a debugger or request full memory.
The [Microsoft API guidance](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/nf-minidumpapiset-minidumpwritedump)
recommends a separate writer process; the
[dump-type reference](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ne-minidumpapiset-minidump_type)
describes normal dumps as carrying data needed for existing thread stacks.

The helper has its own private job and a 10-second capture bound. Its job drains
or is cleaned up before ordinary terminal failure cleanup resumes. A successful
capture cannot change the failed result or extend the original exit deadline.
The helper is test tooling, never linked into the terminal or shipped beside it.

Strict local GCC compilation and three native controls pass: a live process
produces nonempty stacks and x64 thread contexts and continues to its normal exit;
a wrong job and an already-exited process are rejected without creating dumps.
An initial control exposed a zero-grace race with the helper's own hidden console
host. That failed record is retained; normal helper cleanup now allows two seconds
for its own job to drain. Terminal timeouts are unchanged.

The focused close-replay workflow can enable this capture for the exact failed
image. It verifies product source/hash, builds the helper with strict MSVC,
runs its controls, and retains three independent shutdown replays plus any
failure dumps. Successful replays alone will not establish the timeout's cause.

`query-transaction-shutdown-validation.json` retains 53 initial raw records,
including the original failure, executable identity, unchanged local replay,
preliminary control failure and final control results. Full single-image and
local memory acceptance are still pending; no replacement product is promoted.

## Reproduced timeout and captured allocation wait

[Focused run 43661529669](https://github.com/xiongnemo/nemoterm/actions/runs/43661529669)
uses fixture `a8fffe4` and the same failed EXE. Strict MSVC compilation and all
three dump controls pass. Replays one and three pass all 12 cases. Replay two
fails its eighth case, the instrumented window-close path: it requests OpenGL
but **actually uses GDI (renderer ID 1)**. It reproduces the late single-thread
timeout and forced cleanup, so the phenomenon is not confined to actual DirectX.

The helper successfully captures a **45,354-byte** dump, SHA256
`4cc9d8fe072bdc48c2668cbf49c81c8931fb270ba0c4b09e868e86add295db03`, before
Frida detach and job cleanup. The capture does not make the process exit.
The two other replays remain separate passes; the focused workflow is a failure.

Offline LLDB analysis uses Microsoft DLLs/PDBs from the official symbol server,
matched to the dump's PE timestamp, image size and CodeView GUID/age. The Frida
agent is copied from a new owned control running installed Frida 17.24.3, with
the same identity fields verified. No downloaded DLL is executed as part of this
analysis. The recorded unwind is:

```
ntdll!NtDelayExecution+20
ntdll!RtlDelayExecution+52
KERNELBASE!SleepEx+145
frida-agent+0x138815
frida-agent+0x137e28
frida-agent+0x13b66a
frida-agent+0x13972d
frida-agent+0x131391
```

The matching Frida image's PE unwind table places `0x138815` inside a spinlock
routine which calls `SleepEx(0, FALSE)` periodically, then retries an exchange on
the same lock. Its caller has the allocator's bin/size/lock layout. This places
the observed wait inside the injected instrumentation's allocation path, after
our three lifetime listeners have retired. Private Frida symbols are unavailable;
LLDB's nearest exported symbol names with large offsets are not actual private
function names and are deliberately not used as such above.

The same-version
[module registry source](https://github.com/frida/frida-gum/blob/3f82ef6a5b2413867835a45fe341913455473303/gum/backend-windows/gummoduleregistry-windows.c)
keeps its own loader hooks and resynchronizes modules on their return, allocating
an initial handle buffer. Its inlined call pattern matches the observed
`0x13b61c` function. The
[allocator source](https://github.com/frida/frida-gum/blob/3f82ef6a5b2413867835a45fe341913455473303/gum/dlmalloc.c)
contains the corresponding yielding spinlock. This source correlation is an
inference from matching machine code, not private-symbol attribution. The dump
does not identify the lock's former owner, and unwinding stops at the Frida
invocation trampoline. Raw stack-pointer candidates beyond it are not represented
as a validated call chain. The original no-dump timeout and older access violation
cannot be retroactively assigned this cause.

The validation index adds **52 records**: all hosted replays and controls, the
actual failure dump, raw debugger output, module identities, selected disassembly,
analysis scripts and pinned source fingerprints. Microsoft DLL/PDB payloads and
the Frida DLL remain local analysis inputs and are not committed or distributed.

The `--observer session` boundary attaches Frida without loading any script or
installing the lifetime probe. Hosted run
[43662734795](https://github.com/xiongnemo/nemoterm/actions/runs/43662734795)
passes all 18 cases in three fresh replays, with natural cleanup. This is
diagnostic only, not lifetime-order acceptance or proof that attach is harmless.

An external-export-resolution experiment does **not** avoid the loader hooks.
Read-only snapshots of two loader entry points in three owned opaque control
processes show both entries already changed immediately after Frida attaches,
before any script is created. Empty script, original lifetime script and externally
resolved script all retain those hooks. The candidate passes three sensitivity
controls and 12 terminal exits locally, but its intended mechanism is disproved;
the implementation is reverted. Snapshots, candidate source and results remain
in `observer-boundaries.tar.gz`.

The upstream module registry differs materially across versions:

* 17.23.3 (`1208a1266e9d28e6c958b6a167b6d944ebefaf47`) tracks the specific
  loader handle and does not unconditionally allocate a full module snapshot on
  every loader return.
* 17.24.3 adds the unconditional synchronization seen in the captured stack.
* 17.25.0 uses DLL notifications when available, retaining loader hooks only as
  a fallback. Its isolated local trial aborts at the first attach with
  `Unable to locate the ntdll loader TLS routines`, before any product case.
  It is not adopted; the owned opaque control is gone after the controller exits.
* Later versions restore loader hooks alongside notifications for executable
  images loaded as modules. Upgrading to latest would not remove that path.

These are source comparisons, not claims that a particular release fixes every
instrumentation failure. An isolated 17.23.3 environment passes the three original
sensitivity controls and all 12 original terminal assertions on the exact failed
image. Loader entry points still change, as its source predicts. The focused
workflow now permits an explicit 17.23.3 comparison; ordinary CI remains pinned
to 17.24.3 pending hosted results. The captured failure, the rejected resolution
experiment and the 17.25.0 startup failure are retained rather than overwritten.
