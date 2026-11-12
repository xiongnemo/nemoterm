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
Final single-executable CI and exact-artifact local checks are pending.
