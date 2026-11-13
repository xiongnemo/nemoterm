# DirectX frontend integration

The current user-approved frontend private-working-set ceiling is **25 MB**
(25,000,000 bytes, inclusive), adjusted on 2026-11-14; further DirectX memory
optimization is deferred. GDI keeps its strict 20 MB limit. Historical results
below retain their original thresholds and executable identities.

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

## Accepted single-executable validation

Source `9d24b2fe63cccc564e743f8709d1e4c563c693ae` builds a 4,350,976-byte
single executable, SHA-256
`88759c693b3fd0a7a8d2e80ef1708a062c68b44fe874487c0abcb9d0ca8281e8`.
[Single-file CI 43286283156](https://github.com/xiongnemo/nemoterm/actions/runs/43286283156)
passes all 44 groups, including real Codex default/inline tests, DirectX
selection/copy (16 Ctrl rectangles), three-mode pixels, settings, geometry,
application resize, six shutdown cases and injected GPU failures.
[Core CI 43286283098](https://github.com/xiongnemo/nemoterm/actions/runs/43286283098)
passes Windows regressions and Linux ASan/UBSan. The artifact has exactly one
EXE; all 46 hash-bearing CI JSON records match it.

The final downloaded EXE passes five local groups: single-file isolation,
three-mode pixels (11 scenes each, with real OpenGL and DirectX), 21 geometry
checks, 142 resize checks and six shutdown cases. The preceding binary from
`fee689f`, whose production/build sources are identical (only later test and
documentation changes differ), additionally passed the full 13-group local
suite including settings and a 187-second failure/recovery/lifetime test.
Both binary hashes and their separate evidence are retained in
[the checkpoint](directx-checkpoint.json); these are not claimed to be the same
file. All local fixture processes exited.

Final EXE resize peaks, sampled before loading capture instrumentation:

| Renderer | Private WS bytes | Total WS bytes | Private commit bytes |
| --- | ---: | ---: | ---: |
| GDI | 6,131,712 | 24,768,512 | 7,393,280 |
| OpenGL | 35,430,400 | 65,486,848 | 160,940,032 |
| DirectX | 15,405,056 | 48,533,504 | 81,453,056 |

These are finite frontend observations, excluding the hidden console host and
shell, not all-workload limits or speed benchmarks. DirectX meets this machine's
20 MB private-WS and roughly 50 MB total-WS targets in these scenarios. The
previously authorized optional OpenGL exception remains separate. All pixel
fixture samples after focus/capture injection, including GDI, are labelled as
instrumented; the resize figures above are not instrumented.

CI also exercises genuine DirectX target creation: the requested renderer is
observed as 3 for pixels, selection, saved settings and lifecycle tests. Its
four extra GDI/DirectX cycles keep handles exactly at baseline 410, GDI objects
at 31, and USER objects at 26-27 versus baseline 26. All seven owned lifecycle
processes drain without forced termination. Local hardware lifecycle samples
on the preceding production-identical EXE are likewise stable and drain cleanly.

[REA PE evidence](directx-pe-imports.json) completely examines 79 import/delay
DLL descriptors, 605 standard imports and 11 delay imports, with no issues.
No new distributed DLL or C++ runtime DLL is required. Explicit runtime loading
of system graphics libraries is separate from PE import-table coverage.
[Rendering settings](directx-settings.png) are captured from the exact CI EXE;
[local DirectX text](directx-text.png) is captured from the final EXE's retained
frame, not from the desktop compositor.

## Regressions retained by the tests

The Microsoft SDK leaves Direct2D C interfaces opaque, unlike MinGW's COM
helper macros. The small SDK C++ adapter fixes the first MSVC link failure
(run 43278434993) without copying a COM vtable or introducing runtime objects.

A synthetic WM_KILLFOCUS alone is undone by the main loop's real foreground
check. Pixel tests now use the existing owned-process focus probe, without
changing desktop focus, to compare all three cursor shapes both active and
inactive. This exposed a real shared GPU cache bug: active block text uses
cursor colours, while underline/bar text does not, even though ATTR_ACTCURS is
unchanged. The cache key now includes that effective block state (including
big_cursor). Both Consolas and SarasaTermSC Nerd Font Light pass the expanded
three-mode regression. Retained GPU frames stay byte-exact during synchronized
output. GDI snapshots rerasterize bounded memory-DC bands: a few combining-mark
channels can round by up to two; that allowance is restricted to the two text
rows. Sixel and every other frozen pixel remain exact.

The hyperlink fixture now awaits both complete underline runs instead of the
first changed GDI pixels; its failed-run saved image already contained both
expected spans. Selection uses an ordered DSR input barrier and one complete
mailbox snapshot, avoiding a transient empty read during atomic replacement.
The lifecycle child explicitly opts into a five-minute bound because repeated
native settings interactions exceed its ordinary one-minute lifetime. These
fixes retain exact input/pixel assertions and save partial failure evidence.

## Remaining scope

Four-sided tabs and hover previews are still a design in [tabs-design.md](tabs-design.md),
not implemented. Remaining protocol coverage, full grapheme behavior, physical
IME/multi-monitor DPI, live Claude Code and local real-Codex clipboard acceptance
remain open. This renderer milestone does not complete the overall terminal goal.
