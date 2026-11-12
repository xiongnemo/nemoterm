# Retire native windows before freeing callback state

The settings fixture in single-EXE run
[43243023916](https://github.com/xiongnemo/nemoterm/actions/runs/43243023916)
completed its settings and live renderer checks but exited with `0xC000041D`.
That exit code alone does not identify the failing callback; no crash stack was
captured in that run.

Source inspection found a lifetime defect in the natural child-exit path:
`exit_callback` posts WM_QUIT, then `cleanup_exit` frees WinGuiSeat while its
HWND still exists. GWLP_USERDATA still points at that allocation. The subsequent
[CoUninitialize](https://learn.microsoft.com/en-us/windows/win32/api/combaseapi/nf-combaseapi-couninitialize)
can dispatch pending COM messages, which makes retaining that window unsafe.

An observation-only Frida probe reproduced the stale window deterministically
on the previously accepted single EXE, SHA-256
`453db4ea641cedf56a8a80b843dc51c2bf5690a5190ad7b22aa0df15a9583571`.
Both the seat's RtlFreeHeap entry and the UI thread's CoUninitialize entry saw
`IsWindow(hwnd) == true`. See `shutdown-before-observed.json`. This reproduces
the lifetime error, not the exact intermittent CI exception stack.

Cleanup now destroys the remaining owned terminal HWND before releasing its
seat, font and keyboard state. An already-closed HWND is not destroyed again;
the userdata identity check also excludes a reused handle. OpenGL resources and
clipboard/link UI are released first while their parent is still usable.

The same probe passes four local MinGW comparison cases: natural child exit and
WM_CLOSE, each with GDI and actual OpenGL. Each window is gone at seat release
and COM teardown, no callback is observed after seat release, and all four roots
exit with code 0. `shutdown-window-observed.json` records the exact EXE hash and
active renderer. This is a sidecar comparison build, not a new accepted single
EXE. Both CI workflows now run this regression; single-EXE validation remains
required before distribution.

The same local build also passed the native settings fixture: saving and
reloading bindings/shell preferences, opening the terminal, switching
OpenGL -> GDI -> OpenGL -> GDI, and natural fixture exit. The observed renderer
values are 1 -> 2 -> 1 for those three switches. Exact settings evidence is in
`shutdown-settings-local.json`; `shutdown-rendering-settings.png` shows the
rendering panel. This run used owned-window UI Automation, not physical input.

The new process-job helper separately bounds real-client test descendants from
creation, including late Git workers. Two native lifecycle tests verify a late
child is drained after its parent exits, an unrelated process survives, and a
natural exit needs no forced termination. It sets no CPU, working-set or UI
limits. The local Codex retry was blocked before clipboard preservation by
Windows access-denied; that attempt is not counted as a successful client test.

The verified identity-query branch was merged into revision 80c6cf2. The merged
local MinGW build passes the core query suite, all 65 native identity checks
with existing cursor/keyboard checks, and the four native shutdown cases.
Evidence is in `shutdown-identity-query-local.json` and
`shutdown-combined-local.json`, both for SHA-256
`3594290cf9442b566bdc2028432183e5cc53f73410265922c03bcc169ffa0b64`.
The query fixture sampled 4,149,248 bytes peak private WS.
The merged independent XTerm reference run 43249194173, core run 43249194149
and [single-EXE run 43249194284](https://github.com/xiongnemo/nemoterm/actions/runs/43249194284)
all passed. Earlier isolated shutdown CI runs were superseded by this combined
revision, not accepted.

## Accepted single executable

The downloaded 80c6cf2 single EXE is 4,338,176 bytes, SHA-256
`50b58e1f5f07901bfa3bc496a6e2d5e4b1eaa8397bb4152de29a0fa8c3024822`.
Its 38 CI check groups include native shutdown, settings, and default/inline
real Codex. The inline job drained five late processes before deleting its
temporary home, directly exercising the previously failing cleanup path.
`shutdown-single-ci.json` and `shutdown-codex-*-ci.json` retain these results.
Uninstrumented GDI frontend private WS peaks in those two CI client scenarios
were 5,074,944 and 5,242,880 bytes; total WS was 34,852,864 and 35,008,512.
Host and client measurements remain separate in the underlying evidence.

The exact downloaded EXE also passed all four local shutdown cases (actual
OpenGL included), 65 identity queries, and existing cursor/keyboard checks.
`shutdown-single-local.json` and `shutdown-single-query-local.json` record the
same hash; local query peak private WS was 4,681,728 bytes. The local Codex
clipboard restriction is not treated as a passing local client run.

REA import inspection completed all 79 import descriptors, 605 regular and 11
delay imports with no parsing issues; see `shutdown-single-pe-imports.json`.
The executable directory contains this EXE alone. These checks do not establish
completion of the remaining title modes, geometry, tabs, DirectX, or broader
terminal protocol requirements.
