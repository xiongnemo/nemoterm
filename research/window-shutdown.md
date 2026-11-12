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
