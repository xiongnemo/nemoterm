# DirectX frontend integration

This branch adds a Direct2D hardware compositor behind the same strip/run API
as OpenGL. It is a frontend implementation, separate from the Microsoft host's
existing DirectX imports. GDI remains the default and creates no GPU object.

The implementation is C and dynamically loads the system `d2d1.dll`; it adds
no distributed DLL, toolkit, WebView, shader compiler or C++ runtime. Existing
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

Device-failure injection, repeated resource lifetime checks, exact single-EXE
CI and its local hardware run are still required. This branch has not replaced
the accepted resize distribution on main. Tabs/previews and the remaining
protocol/physical-device requirements remain open.
