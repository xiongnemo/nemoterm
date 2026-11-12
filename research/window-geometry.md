# Geometry queries and OpenGL minimization

The terminal answers XTWINOPS 11, 13, 13;2, 14, 14;2, 15, 16, 18 and 19 from
a synchronous Win32 snapshot. The text origin includes padding; text size is
the cell grid, while outer size includes window furniture. Screen queries use
the containing monitor, not the desktop union. The query does not allocate,
draw, change synchronized-update state or resize the window.

`test_queries` retains the exact nine replies from independent XTerm run
[43244992756](https://github.com/xiongnemo/nemoterm/actions/runs/43244992756),
using its captured geometry as a mock. It also covers negative positions,
unknown secondary selectors, zero cell dimensions, changed monitor/cell sizes,
fragmentation, cancellation and an optional-callback fallback. Position replies
use unsigned 16-bit parameters, matching `ParmType`/`UParmOf` and `unparseseq` in
the pinned XTerm source. A negative decimal contains a non-parameter `-` byte
and was rejected by the native ConPTY path. Native signed rectangles are saved
separately in the evidence; a reply such as 65376 means -160 in this encoding.

The native fixture independently derives cell dimensions and text offsets from
two colored pixel rectangles. It compares nine replies with actual HWND/client/
monitor rectangles and the child console grid at initial size, negative desktop
position, a second position, resized grid, minimized, restored and synchronized
output. Both GDI and hardware OpenGL passed all seven phases locally with
Sarasa Term SC Nerd Font Light. The development executable SHA-256 is
`a43d8ad789d5263762dd4b63f3e59bcafc5c06efc271da83dc86132048331bbb`;
its accepted OpenConsole host and pinned DLL are recorded in the JSON. This
development run is not final single-file acceptance.

## Capture investigation and reproduced defect

External PrintWindow returned a uniform white image for valid OpenGL frames on
this machine, including the previously accepted title-stack executable. Owned-
process observation found correct texture uploads and retained framebuffer
pixels, successful SwapBuffers and no reported GL errors. Passing an external
memory HDC through WM_PRINTCLIENT also failed: GetObjectType and GetClipBox
returned zero inside the target. These failures do not prove a blank display.

`tests/gl_capture.py` and its test-only Frida script now create the DIB/DC in the
fixture-owned process, send WM_PRINTCLIENT to its UI thread and return the
retained framebuffer. All handles are released. The helper checks the HWND's
PID and bounds capture to 4,194,304 pixels. It tests the actual retained GPU
frame, not physical monitor output or compositor presentation. GDI keeps the
external PrintWindow path. Frida is a test dependency only, never a product
dependency, and all post-attach memory samples are explicitly labelled.

This working readback exposed a separate real defect: minimizing produced a
zero-sized drawing surface, which was treated as GL failure and permanently
selected GDI. The renderer now skips drawing while iconic and retains its
context and dirty cells for restoration. The native fixture asserts that the
renderer remains unchanged after every phase. StretchDIBits returning zero is
also correctly treated as readback failure. The failed pre-fix run is retained
as `geometry-minimize-before-fix.json`; it is not a passing result.

`renderer_window_smoke.py` uses the same GL readback to compare text (including
Chinese, combining marks and emoji), Sixel, synchronized output, retained
repaint, resize, palette and three cursor shapes with GDI. The local regression
passed. Geometry GDI samples peaked at 3,727,360 bytes private WS / 20,844,544
total WS; the renderer scene sample was 4,554,752 / 22,073,344. GL renderer
samples include instrumentation and are not used for the GDI memory criterion.
Samples are not continuous peaks and exclude host/client processes.

This change does not implement the remaining geometry mutations (pixel-size,
zero/omitted resize dimensions, axis maximization/fullscreen and DECSLPP),
physical multi-monitor DPI validation, DirectX rendering or tab previews.

## Final single-executable checkpoint

Source `9ccbad39fac2c308909220eccd201258b2af12d6` passed
[core / ASan / UBSan CI](https://github.com/xiongnemo/nemoterm/actions/runs/43264272761)
and [all 41 single-executable native groups](https://github.com/xiongnemo/nemoterm/actions/runs/43264272710).
The [single EXE artifact 13966162536](https://github.com/xiongnemo/nemoterm/actions/runs/43264272710/artifacts/13966162536)
is 4,342,272 bytes, SHA-256
`9d8133f2cf4bbaa709d0e6b98014359c485125364d06a2c47cb91f1f55c5f909`.
Evidence artifact 13966362340 contains 46 JSON records; all 42 records with a
top-level executable hash match that EXE. The isolated directory contains only
`nemoterm.exe`. PE inspection covers all 79 import descriptors, 605 regular and
11 delayed imports with no reported issues; it does not cover dynamic loading.

The exact download passed nine sequential local groups: geometry (GDI and
hardware OpenGL), renderer pixels, 23 title-stack checks, startup size, sync,
font resize, Sixel, queries and 87 title-mode checks. The geometry test also
changes its colored pixels while minimized and verifies them after restoration
without resending the drawing. These exact results use the `geometry-*-local`
evidence files; development results remain separately named.

The local GDI geometry samples peak at 4,173,824 private WS / 23,552,000 total
WS, with 5,378,048 private commit. Across these nine local groups, the largest
reported GDI private-WS peak is 6,164,480 bytes in the sync test. Startup gives
160x48 at 8x20 pixels per cell on the 1920x1040 work area; an oversized request
clamps to 117x24 at 16x40 pixels. Hardware GL's geometry sample before test
injection is 29,462,528 private WS / 59,371,520 total WS; post-attach samples
include Frida and are labelled. The user's optional-GL memory exception applies.

Cloud real-Codex default/inline GDI peaks are 5,345,280 / 5,513,216 private WS
bytes and 37,531,648 / 38,416,384 total WS; host and client are separate in those
records. Local clipboard access still returns access-denied, so this checkpoint
does not claim a new local real-Codex copy/paste pass. Cloud GL selection falls
back to GDI; hardware evidence comes only from the local exact-artifact run.

The first core CI attempt failed a hyperlink first-changed-frame comparison:
LINK alone was underlined instead of the LINK/MORE group. Attempt two failed
before building because MSYS2 mirrors timed out. Attempt three passed the full
core/native pipeline, including that hyperlink test, without a source change.
The single-file pipeline passed the same complete hyperlink test independently.
The first failure and screenshots are retained in `geometry-ci-first-failure.json`
and its companion images; its cause is not established and no fix is attributed
to it. The reduced local hover diagnostic was inconclusive, not a pass.

The accepted artifact replaces `dist/nemoterm.exe`; the title-stack executable
is retained under `build/dist-before-geometry-9ccbad3/`. Remaining window mutations
have a separate 31-case XTerm oracle on `feature/window-resize`. DirectX frontend
rendering, four-sided tabs/previews, physical input/DPI, full grapheme behavior
and the remaining protocol ledger are still open.
