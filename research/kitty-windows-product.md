# Kitty compositor: accepted single-executable checkpoint

The accepted executable comes from production source
`97d60254e3bae94fbba9803ff15e1abfce5373f8`. It is **4,509,184 bytes**, SHA-256
`07c8d279c526b13eb75586afe1a2b980d21253adf125e3d11f68574572e8e9d6`.
The distribution contains only `nemoterm.exe`; its hidden console host uses
that same executable. This checkpoint adds bounded Kitty image composition,
OSC 1337 static images/GIF, font zoom, bell controls and the intervening fixes
to the previously accepted `8ff214f` image.

The [core workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43633479250)
and [single-executable workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43633479299)
both completed successfully. The latter passed **129 mandatory check groups**.
[Product artifact 14130247748](https://github.com/xiongnemo/nemoterm/actions/runs/43633479299/artifacts/14130247748)
expires on 2026-12-14 at 20:12:10 UTC. Its executable hash matches the full
single-image validation manifest and every local run reported below.

The [machine-readable evidence](kitty-windows-product-validation.json) retains
workflow metadata, logs, complete core/single/MSVC/sanitizer/portable evidence
bundles, byte-hashed inventories, native captures, fixture identities, full
memory samples and cleanup records. The product identity is separate from
the later fixture-only CI image and the independent source-host precheck.

## Exact-image native graphics

Tests use SarasaTermSC Nerd Font Light and real ConPTY input. All three actual
renderers pass 24 Kitty pixel stages, 12 Kitty zoom/resize stages, 32 static
OSC 1337 stages and 36 GIF stages: **312 stages in total**. OpenGL and DirectX
are required to initialize their requested backend; a GDI fallback cannot
pass these local GPU runs. Each of the 12 suites drains three owned processes
naturally, with no forced termination.

The Kitty stages cover RGB/RGBA/PNG, crops, scale, transparency, three layer
positions, text clusters, ordering, deletion, repeated presentation, screen
switching and frozen output. Geometry checks exercise native font commands
and window resizing, including the difference between intrinsic pixel sizes
and cell-sized placements. This is synthetic application traffic, not a
physical keyboard/wheel or comprehensive real-agent test.

## Reading the presented GDI client

The GDI automation image route reconstructs a frame. A second run therefore
uses `GetDC(owned HWND)` and `BitBlt` to read the visible owned client surface,
without requesting the image API or `WM_PRINTCLIENT`. All **104 GDI stages**
pass again, including repeated translucent image rendering and animated GIFs.
The client capture method follows the [Windows GDI capture APIs](https://learn.microsoft.com/en-us/windows/win32/gdi/capturing-an-image).

The optional `--presented-gdi` fixture checks HWND/process ownership on every
read, temporarily raises only its own test window without activation, then
restores its previous topmost state. It does not read the desktop DC, move
the pointer, send global input or access the clipboard. This requires an
interactive desktop and is not enabled in headless CI. It validates the GDI
client pixels, not the complete physical display/DWM composition pipeline.
All four jobs drain naturally. The default API route is separately rechecked
with 24 Kitty plus 12 geometry stages after adding this optional capture path.

The presented fixture changes were uncommitted when these runs executed.
Their exact source snapshots and LF-normalized hashes are retained separately
from the base fixture commit `6648458`; the product binary is unchanged.

## Local memory and tab lifetime

Each run uses actual 160-by-48 Sarasa cells, two 2000-line histories, dense
Unicode text, Sixel, image traffic, tab switching, 24 redraw/resize transitions
and 12 temporary-tab close cycles. GDI uses a top tab bar; DirectX uses left.
The sampler includes startup and resource settling, runs without injection
or working-set trimming, and stops before image capture and later hover/input
instrumentation. Host and client process memory is recorded separately.

| Workload | Renderer | Samples | Frontend private WS | Frontend total WS | Frontend private commit |
| --- | --- | ---: | ---: | ---: | ---: |
| Kitty | GDI | 617 | 16,384,000 | 38,801,408 | 19,496,960 |
| Kitty | DirectX | 660 | 23,416,832 | 59,056,128 | 86,372,352 |
| Inline PNG | GDI | 514 | 16,744,448 | 39,448,576 | 19,054,592 |
| Inline PNG | DirectX | 567 | 23,818,240 | 59,379,712 | 88,260,608 |
| Animated GIF | GDI | 509 | 17,145,856 | 39,907,328 | 19,898,368 |
| Animated GIF | DirectX | 520 | 24,207,360 | 59,817,984 | 92,307,456 |

All quantities are peak bytes. All six pass the unchanged private-WS gates:
GDI strictly below 20,000,000 and DX at most 25,000,000. DX total WS still
exceeds the desired approximately 50 MB. The 10 Kitty or 9 legacy graphics
check groups pass per run; all 56 owned processes per workload exit naturally.
Active/inactive image patches, GIF frames and hidden-tab previews are retained
as post-sampling evidence. These are bounded workloads, not a guarantee for
arbitrary output, more tabs or long-lived agents.

## Other builds and remaining scope

The geometry fixture follow-up `d8d8854` also passes both complete workflows:
[core](https://github.com/xiongnemo/nemoterm/actions/runs/43634649279) and
[single image](https://github.com/xiongnemo/nemoterm/actions/runs/43634649253),
now with **132** mandatory groups. Its production sources are unchanged,
but its independently built EXE has SHA-256
`7985c90a8e8490d1d44c1ffb3b34068b478be2a12b3fe7fd7e4cd48fae3e9ade`.
The local results above apply to `07c8d279`, not that different image.

The independent same-source precheck EXE `355d0e83` also differs from the
formal product. Its 108 native stages and six memory workloads remain in
the [separate precheck manifest](kitty-single-image-precheck.json). None of
those results were substituted for the exact-product local tests.

The user confirmed hearing the Windows prompt sound in the earlier local
`69cd5a4` bell test. That listening evidence is recorded in
[font zoom and bell](font-zoom-and-bell.md); it is not a new listening test
of this product image.

Kitty file/shared-memory transport, compression, animation, relative placement
and Unicode placeholders remain unsupported. The 4 MiB shared raster budget,
2 MiB transfer cap and 128-image/512-placement per-screen limits still apply.
Full xterm/OSC coverage, physical input/IME, multi-monitor DPI and sustained
real-agent acceptance remain open. Earlier intermittent resource/shutdown
failures remain preserved; passing these runs does not prove those failures
resolved. The optional OpenGL memory exception remains unchanged.
