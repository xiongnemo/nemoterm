# RTL capture and close observation

Single-image CI [43571960750](https://github.com/xiongnemo/nemoterm/actions/runs/43571960750)
at `d82d9aef2140533df0f04397c08c2ab14324d88e` failed before reaching the updated
overflow-tab test. In the Courier RTL test, requested OpenGL fell back to GDI;
all seven glyph, layout, synchronized-paint, resize and clipboard checks passed,
then the frontend did not exit within the unchanged 10-second WM_CLOSE deadline.
The private job terminated its remaining frontend. The first GDI case had exited
naturally. The failed executable's SHA-256 is
`40924e0b16b3cbf6c2b90fa5b29af2ce69076469bd74b0b1fda2decfb569f573`.

The old fixture used Frida to read the renderer and detached before WM_CLOSE.
Like the earlier [overflow failure](tabs-close-observation.md), this run has no
thread stack identifying the wait. Two fixtures using instrumentation failed
intermittently; that association does not establish instrumentation as the cause.

`tests/automation_capture.py` now reads an explicitly opted-in owned terminal's
renderer BMP through the local API. It verifies PID/HWND and session identity,
checks the complete BMP framing, and uses the same RGB conversion as the old
capture helper. The RTL fixture retains every pixel and clipboard assertion,
adds close timing and read-only thread metadata on timeout, and still requires
zero exit status within 10 seconds. Capture does not inject code, use the
clipboard or activate the window. It observes the retained renderer surface,
not the desktop compositor. Clipboard assertions retain their separately saved
and restored clipboard access.

Two finite original-fixture Courier replays of the exact failed executable
passed locally. Only timing and timeout diagnostics were added to that fixture.
The API fixture then passed Courier and SarasaTermSC Nerd Font Light against
both that image and main `8264b27`'s CI image
`11041b9d7b1ee3107827dd53336de6d46cd5f8db8f606915e936a0efdf070e8b`.
Each run exercised actual GDI, OpenGL and DirectX, including real logical-order
clipboard checks. All 18 renderer cases passed seven checks each and exited
naturally in 0.0581–0.1406 seconds. All six outer jobs also drained naturally.
These observations validate the capture replacement; they do not reproduce or
resolve the hosted CI hang. No failed CI executable was promoted.

The [manifest](rtl-capture-validation.json) retains 87 compressed records
(76,041 bytes), including the failed run, exact fixtures, finite replay driver,
screenshots and cleanup results. Hosted CI validation of this fixture change
is still required.
