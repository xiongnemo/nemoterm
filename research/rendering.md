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

The development build is not the final single-EXE deliverable. Exact MSVC
artifact hash, CI run and final local evidence are recorded after CI succeeds.

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

Tabs are requested with a bar on any of the four sides and terminal previews
on hover. The current frontend has per-window terminal state but a single
startup path; first extract session lifecycle from WinMain into a tab host.
Keep independent terminal/backend/input state per tab, continue reading hidden
PTYs, resize hidden grids consistently, and route keyboard, mouse, IME,
clipboard and close requests to the correct tab. Render a thumbnail on demand
for the hovered tab, with a bounded cache and cancellation on close/switch;
do not retain a full-resolution screenshot for every inactive tab. This work
is not implemented or validated by the renderer changes above.
