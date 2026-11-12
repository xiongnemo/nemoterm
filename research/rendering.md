# Native rendering, startup geometry and bindings

GDI remains the default and retains the original private-working-set target.
OpenGL is explicitly opt-in: the user permits this mode to exceed that target.
Both modes ship in the same executable. OpenGL entry points are loaded only
when selected, from the Windows system OpenGL DLL. No GLFW, SDL, WebView,
external GL loader or shader runtime is distributed.

`windows/nemo_gl.c` owns a non-interactive child surface and a retained GPU
framebuffer. Uncached text runs use the existing GDI font/fallback/combining
implementation in a bounded reusable DIB strip. Complete run textures are
cached (256 entries, 4 MiB texture payload). Hits skip rasterization and upload.
Sixel spans, borders and text are composed on the GPU. Small cursor overlays
read back their cell; normal text does not. The framebuffer is capped at
128 MiB, and GL failures drop back to GDI. Device loss is not silently retried
in a tight loop. Switching to GDI destroys the GL context and child surface;
vendor driver memory may persist until process exit.

The separate child surface is required for reliable switching: a window's
pixel format can only be set once. The parent excludes child windows from
GDI paint, preventing a paint loop from starving terminal timers.
Sources: [Microsoft SetPixelFormat](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-setpixelformat),
[Khronos framebuffer objects](https://registry.khronos.org/OpenGL/extensions/EXT/EXT_framebuffer_object.txt).

Local development tests with SarasaTermSC Nerd Font Light and an NVIDIA
RTX 3060 Laptop GPU cover text, Unicode/combining/fallback glyphs, decoration,
double-width/height lines, Sixel, palette invalidation, resizing, expose,
synchronized updates, and all three cursor shapes. Cross-renderer image
comparison allows at most 2/255 per channel in at most 0.1% of channels for
Windows font antialias rounding. Sixel, retained repaint and sync comparisons
are exact. This is correctness evidence, not a rendering-speed benchmark.

`renderer_window_smoke.py` runs hardware acceptance when
`NEMOTERM_REQUIRE_OPENGL=1`; on headless CI it verifies the fallback if no
hardware context is available. `settings_window_smoke.ps1` checks live mode
switches, saved configuration, control bounds, binding reset and conflicts.
`startup_size_window_smoke.py` checks the 160x48 default and a 1000x1000 request
with a large font against the actual monitor work area and child console size.
The clamp happens before screen allocation, and peak total working set is
checked to catch a transient oversized allocation even if it is later freed.
`bindings_window_smoke.py` checks custom Alt/Ctrl combinations, Unicode copy
and bracketed paste, and forwarding of keys whose default binding was removed.

Bindings currently expose copy, paste, copy-and-paste, and rectangle modifiers.
Shift-only remains reserved for local selection; AltGr remains text input.
Additional actions will be registered as their features are implemented.

Source `8fb697a933ee56f3b5cb49b1bf4199d3a3dd278e` has successful
[single-executable CI](https://github.com/xiongnemo/nemoterm/actions/runs/43225946626)
and [core/sanitizer CI](https://github.com/xiongnemo/nemoterm/actions/runs/43225946477).
The single EXE is 4,329,472 bytes, SHA-256
`6dd61201097f31083d9339ebfa809628857fb3ed7634b3d499fa5a29986d8684`;
[download the artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43225946626/artifacts/13948278905).
There are 36 native single-file checks, 29 C core suites, 12 terminal sanitizer
suites and four process-identity cases. The [checkpoint](rendering-checkpoint.json)
matches 37 CI JSON records to the artifact hash and preserves the earlier local
evidence separately. [REA import inspection](rendering-pe-imports.json) covered
79 descriptors, 604 regular imports and 11 delay imports without parsing issues;
dynamic loads remain outside static import-table coverage.

Cloud Codex frontend GDI peaks were 5,308,416 private WS bytes (5.31 MB / 5.06 MiB)
and 36,950,016 total WS bytes (36.95 MB / 35.24 MiB) in default mode; inline mode
used 5,382,144 private WS bytes (5.38 MB / 5.13 MiB) and 37,212,160 total WS bytes
(37.21 MB / 35.49 MiB). Private commit and separate host/client processes are in
the checkpoint. Cloud OpenGL selection exercised GDI fallback, not GPU rendering.

Earlier runs exposed fixture cleanup races and queued desktop pointer motion.
Owned-window input isolation, process creation times and the unique copied-image
directory now constrain the fixtures. The final directory test waited for 36
owned process exits with no pending processes. An earlier MinGW Sixel restoration
failure has not reproduced locally or in the final MinGW/MSVC runs; its strict
assertion and geometry diagnostics remain in place. No product fix is attributed
to that unconfirmed failure.

Local interactive validation was paused at the user's request on 2026-11-13
(Sydney). No local windows, input/clipboard actions or GPU probes may resume
until the user says the computer is free. Before that pause, the `317b54d`
artifact passed startup sizing, GDI/OpenGL pixels, custom bindings, rectangle
selection, IMM/DPI and Sixel font tests. Its full run stopped on external
unbuttoned mouse motion in the reflow fixture; it is not a full acceptance pass.
The earlier `1495d2c` artifact passed real Codex in both OpenGL modes, but that
does not replace exact-final-artifact hardware validation. `dist/nemoterm.exe`
therefore still holds the previous verified `2862f67` single executable.

Screenshots: [custom bindings](rendering-ci-bindings.png) and
[renderer settings](rendering-ci-settings.png) are from the final cloud artifact.
[OpenGL text](rendering-local-opengl-text.png) and
[Ctrl rectangle](rendering-local-rectangle.png) are from the prior local
`317b54d` artifact, not a local run of the final artifact.

## Follow-up requested during implementation

DirectX is feasible through the Windows Direct2D/Direct3D APIs, without a
third-party renderer package. The local hardware-only Direct2D probe creates
a 1280x960 compatible render target, a 1024x1024 BGRA bitmap and draws 120
frames with verified pixel readback: private WS 14,254,080 bytes, total WS
39,784,448, private commit 71,438,336. Destroying the device leaves private WS
9,289,728 bytes. The preceding no-readback run measured 14,798,848 bytes of
private WS; these are individual probe observations, not a fixed memory cost.
This is a feasibility measurement, not a full terminal benchmark. Integration,
fallback validation and the same pixel/client tests are still required.
[Microsoft Direct2D architecture](https://learn.microsoft.com/en-us/windows/win32/direct2d/direct2d-overview).

The pinned Microsoft source already includes `src/renderer/atlas`, and
`src/host/exe/Host.EXE.vcxproj` references it. The single-image import table
therefore includes Direct2D, DirectWrite, DXGI and D3D11 even while the frontend
uses GDI. Their presence is not evidence of a DirectX frontend renderer.
`AtlasEngine` implements Microsoft's `IRenderEngine` using `TextBuffer`,
`TextAttribute`, `ImageSlice`, `IRenderData` and its own shaping/font pipeline.
Reusing it directly would require a substantial adapter and new pixel/font
acceptance; it is not a drop-in replacement for PuTTY's drawing callbacks.

A smaller first integration can retain the current GDI font rasterizer and
bounded run cache, replacing GL composition with a hardware Direct2D window
target and a retained compatible bitmap target. Use physical pixels (96-DPI
target units, with the existing frontend DPI/font sizing), opaque BGRA run
bitmaps, and the same 4 MiB cache budget. Device-loss errors must release target
resources and fall back to GDI. Cursor readback, synchronized-frame retention,
`WM_PRINTCLIENT`, live renderer changes and hidden-tab previews need explicit
coverage; GDI interoperation can synchronize GPU work and must be profiled.
The standalone probe does not establish the complete renderer's memory or
speed. See [Microsoft GDI interoperation](https://learn.microsoft.com/en-us/windows/win32/direct2d/direct2d-and-gdi-interoperation-overview).

Tabs are requested with a bar on any of the four sides and terminal previews
on hover. The current frontend has per-window terminal state but a single
startup path; first extract session lifecycle from WinMain into a tab host.
Keep independent terminal/backend/input state per tab, continue reading hidden
PTYs, resize hidden grids consistently, and route keyboard, mouse, IME,
clipboard and close requests to the correct tab. Render a thumbnail on demand
for the hovered tab, with a bounded cache and cancellation on close/switch;
do not retain a full-resolution screenshot for every inactive tab. This work
is not implemented or validated by the renderer changes above.
