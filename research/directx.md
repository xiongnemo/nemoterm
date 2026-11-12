# DirectX frontend integration

This branch adds a Direct2D hardware compositor behind the same strip/run API
as OpenGL. It is a frontend implementation, separate from the Microsoft host's
existing DirectX imports. GDI remains the default and creates no GPU object.

The compositor is C and dynamically loads the system `d2d1.dll`. A small C++
translation unit calls the official SDK COM methods through a C ABI; it uses
no STL, allocation or exceptions. This avoids relying on MinGW-only C helper
macros, which caused the first MSVC link to fail (run 43278434993). It adds
no distributed DLL, toolkit, WebView or shader compiler. Existing
GDI glyph rasterization, font fallback, decoration and Sixel pixels are reused.
One retained GPU frame is bounded at 128 MiB. The 256-entry run cache is bounded
at 4 MiB of pixel data, with keys limited to 16 KiB each. Reusable CPU and
upload strips each have a separate 4 MiB limit. These bounds are not measured
working-set guarantees; actual ordinary strips are much smaller.

Window/Rendering stores 0=GDI, 1=OpenGL, 2=DirectX. The native observation
property retains 1=GDI, 2=OpenGL and adds 3=DirectX. Changing modes releases the
old compositor and invalidates terminal output. GPU failure selects GDI; a
later explicit mode change can retry the chosen backend. Minimized windows
retain their frame and pending output without attempting a zero-sized target.

Direct2D requests a hardware render target explicitly, sets 96-DPI coordinates
to match physical Win32 cell pixels, and uses nearest-neighbor bitmap copies.
The compatible retained target permits GDI interop only for cursor overlays
and explicit frame capture. Normal uncached text is uploaded; cache hits do no
font rasterization or upload. Readback respects BeginDraw/GetDC/ReleaseDC/EndDraw
ordering. On device failure the target and its dependent resources are released.
See Microsoft's [GDI interoperability](https://learn.microsoft.com/en-us/windows/win32/direct2d/direct2d-and-gdi-interoperation-overview),
[GetDC contract](https://learn.microsoft.com/en-us/windows/win32/api/d2d1/nf-d2d1-id2d1gdiinteroprendertarget-getdc)
and [resource domains](https://learn.microsoft.com/en-us/windows/win32/direct2d/resources-and-resource-domains).

## Development evidence; exact single-file acceptance pending

The local MinGW frontend passes three-mode pixel comparison for Chinese,
combining characters, styles, Sixel, synchronized output, retained repaint,
resize, palette and cursor shapes. DirectX text differs from display-DC GDI by
at most two channel units at the same few ClearType pixels as OpenGL; Sixel
and retained-frame scenes match exactly. DirectX geometry/minimize/restore
passes seven phases. Its application-resize profile passes 42 checks, followed
by the shared permission, locked-window and font-resize profiles.

The resize fixture now samples all phases before loading the retained-frame
capture helper. This development run reaches 15,056,896 private WS,
46,874,624 total WS and 81,596,416 private-commit bytes. The renderer pixel test
samples 12,365,824 / 47,316,992 / 60,596,224 before capture instrumentation;
the later 15,585,280 private-WS sample includes Frida. These are finite frontend
observations, not all-workload limits or a speed benchmark. The native settings
test saves/reloads DirectX and switches GDI/OpenGL/DirectX/GDI successfully.

The local SDK-adapter build (`7d1839338d5dca808ef27f6508455dc53c440d3a05cd9c068e62a94da509a3cf`)
passes injected factory, EndDraw and Resize failures: each selects GDI, still
answers DSR and displays fresh pixels, then can explicitly retry DirectX.
Four further GDI/DirectX cycles keep GDI objects at 31 versus baseline 32,
USER objects at 32 versus 31 and handles at 457-459 versus 459. All seven owned
processes drain without forced termination. The test takes 187 seconds.
MinGW's adapter object has no undefined runtime symbols and the resulting
frontend imports no C++ runtime DLL. Exact single-EXE CI and its local hardware
run are still required. The lifecycle fixture's
first resize-recovery timeout was its child reaching the default 60-second
lifetime during modal settings operations; its retained last phase and elapsed
time identify that cause. Only this long fixture opts into a five-minute bound.
This branch has not replaced the accepted resize distribution on main. Tabs/previews and the remaining
protocol/physical-device requirements remain open.

## Cursor cache regression and deterministic capture

The SDK adapter builds successfully in MSVC (run 43281415204). That run's
cursor comparison exposed a fixture focus race: its GDI image has a focused
solid cursor while its DirectX image has an unfocused outline. The fixture now
uses the existing owned-process focus probe, never desktop activation, and
covers all three shapes both focused and unfocused. It samples memory before
instrumentation and labels all later samples, including GDI, as instrumented.

The stronger test then exposed a real shared GPU cache defect: rasterized text
with ATTR_ACTCURS depends on whether the active cursor is a block. Changing
DECSCUSR from block to underline retained the old cached block background.
The run key now includes that effective block state (including big_cursor).
The corrected development executable passes 11 scenes in each of GDI,
hardware OpenGL and hardware DirectX, with both Consolas and SarasaTermSC Nerd
Font Light. Retained GPU frames remain byte-exact during synchronized output.
GDI's bounded snapshot rerasterization with Consolas changes two combining-mark
channels by one on this machine; the freeze assertion permits at most the same
two-level ClearType rounding as text comparison, only in the two text rows.
Sixel and all remaining pixels must stay exact.

Core run 43281415376 independently caught the hyperlink fixture sampling GDI
between two underline runs. The first sample spans x=10..45 at y=31, while its
saved hover PNG already contains both expected spans x=10..45 and x=91..126.
The fixture now waits for the complete exact two-run pixel set, with bounded
waiting and diagnostic samples, instead of treating the first changed pixel
as a completed paint. No hyperlink rendering behavior or pixel criterion changes.

Core/sanitizer run 43283989982 passes. Single-file run 43283990051 passes the
three-mode pixels (including hardware DirectX on that runner), then exposes a
selection-fixture mailbox race: a transient empty read raises KeyError after
successful rectangle/pixel/copy checks. Its final snapshot still has exactly
the expected DSR. Selection now uses the fixture's ordered input barrier and
retains one complete acknowledged snapshot before checking all input bytes;
partial results are also saved on failure. Full single-file acceptance remains
pending; no failed-run executable is promoted to dist.
