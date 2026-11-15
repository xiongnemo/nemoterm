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
