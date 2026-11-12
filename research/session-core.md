# Session ownership checkpoint for tabs

This development branch establishes session lifetime in one frontend process.
It is not a completed tab UI: Duplicate Session currently opens another native
window in the same process. Top/bottom/left/right tab placement, hover previews,
tab bindings and an active-session GPU renderer remain the next host layer.
The accepted executable in the main checkout's `dist` is unchanged.

`wgs_create` now owns a session's configuration and initialization. The shared
message pump updates all live seats; an application message window receives
socket events independently of terminal windows. Closing a window, a child
exiting, and connection errors retire only the affected seat. The last seat
requests application exit. Failed shell or terminal-window creation releases
only the partial session and leaves existing sessions running.

Teardown runs as a top-level callback, after backend/WndProc stacks return.
It cancels seat callbacks/timers and OSC 52 delivery, disconnects the line
discipline and backend, destroys the HWND while its callback state is alive,
then frees terminal buffers, logs, configuration, keyboard/font resources,
caret bitmap, palette, titles and menus. Shared submenus are detached from both
parents before being destroyed once. The font-sized trust icon is per seat.

Ordinary asynchronous paste captures a monotonic session identity as well as
the HWND. Restarting a shell renews that identity. The receiving window rejects
stale-session results, including HWND reuse, and closing/disconnected seats
reject delivery. The worker never retains a seat
pointer. Clipboard text reads are bounded by the actual allocation and unlock
the handle after copying. `NemotermSessionId` is a read-only window property
for identifying a session independently of its HWND.

## Native checks

`tests/session_window_smoke.py` uses an unnamed owned job, temporary profiles
and per-child mailboxes. All input targets the fixture's HWNDs. It checks three
simultaneous sessions, input isolation, middle-child exit, original-window
closure, 12 open/close cycles with Sixel and synchronized output, shell/window
creation failure and subsequent recovery, stale/valid synthetic paste, and
natural exit of every owned process after the last session closes.

Handle, GDI, USER and memory samples precede Frida attachment. The later fault
phase changes only the owned process's requested executable/class name and
handles its expected error dialogs. Synthetic paste does not open or modify
the real clipboard and is not evidence of local physical clipboard acceptance.
GDI, OpenGL and DirectX variants are included in both GitHub pipelines; the
single-EXE workflow also retains the existing integration coverage.

Local development uses MinGW plus explicit ConPTY/OpenConsole sidecars in
isolated `build` directories. These binaries are not the accepted single-file
distribution. Initial native runs passed session isolation/lifetime in all
three renderers, six shutdown cases, all six detected shells (including Git
Bash and WSL duplicate-directory inheritance), renderer pixel comparisons and
142 window-resize cases. Exact local provenance is in the checkpoint JSON.

## Memory limitation to resolve in the tab host

The temporary multi-window implementation allocates a renderer per window.
Although native handle counts return to baseline, the initial DirectX cycle
test reached 22,265,856 bytes private WS and 54,538,240 bytes total WS after
repeated creation. This exceeds the 20 MB private-WS target and does not qualify
for distribution. Its private commit remained approximately 85–86 MB. GDI
settled near 3.9 MB private WS / 21.4 MB total WS on the 60x16 fixture. OpenGL
uses the user's previously authorized optional-mode memory exception.

The tab host must keep one active GPU renderer, suppress background rendering
while continuing to drain/parse hidden PTYs, and capture at most one bounded
hover thumbnail. Re-run the memory/resource stress with that ownership model;
do not extend the OpenGL memory exception to DirectX.
