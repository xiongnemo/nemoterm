# Native ReGIS component under development

The repository now contains a native adaptation of the pinned XTerm ReGIS
parser without X11 dependencies. It is **not connected to the production
terminal parser or renderers** and adds no capability to the downloadable
executable. Product-level ReGIS coverage remains missing.

Parser state, spline context and temporary strings belong to one lazily created
owner. Indexed pages use sparse 32x32 tiles and a uniform background instead
of allocating full blank bitmaps. The memory budget counts the owner, pages,
tiles, uploaded alphabets and input buffers. A reservation callback is ready
for the terminal's shared image budget; that caller is not yet connected.
Errors release decoder resources before another request. Delay requests go to
a scheduling callback; the component does not sleep.

Input length, recursive depth, memory and counted parser/pixel visits have
finite checks. This does not establish that every arithmetic, parser-progress
or resource boundary has been audited; more stress coverage is needed before
connecting the decoder to terminal input.

## Remote results

[Run 44098880382](https://github.com/xiongnemo/nemoterm/actions/runs/44098880382)
at `5c6193ed325588c64a43d7ce9ea4258c518af3b8` fails compilation: missing X11
aliases/constants, MSVC alignment/CRT diagnostics and a conversion from widened
coordinates back to Windows' 32-bit `long`. Its original logs are retained.

[Run 44099478077](https://github.com/xiongnemo/nemoterm/actions/runs/44099478077)
at `a8724b09d1a6832f7c986a523d232a27e04f5590` compiles with GCC, Clang and MSVC,
with warnings treated as errors. GCC/Clang run under ASan+UBSan. All three pass
ownership tests: independent owners, parsing on a second owner from a callback,
reservation/release accounting, reset, embedded-NUL rejection, recursion,
memory-pressure recovery and work-budget exhaustion. The owner itself is
39,384 bytes on these Linux builds and 39,440 bytes on MSVC, allocated on demand.

The component comparison reads the unchanged upstream artifact from run
`44093439244`, SHA-256
`f1cb288263b12e35be6ffc29b4edde6f71ee65054adabb1c105198ccdaf25b00`.
Each compiler compares **37 pure-ReGIS scenes / 70 steps**. All replies match;
**69 pixel frames match and one fails**. Twenty-four other original scenes
remain explicit exclusions at this stage because they require terminal CSI,
Sixel, cancellation or screen lifecycle integration. They are not passes.

The failure is `text-no-font`, with 389 differing pixels. The case name was
misleading: an empty `regisDefaultFont` still lets Xft match a system font.
Upstream draws `ABC`, while the component with no font callback draws missing
glyph blocks. Both report the same final position. The images were visually
inspected; no expected output was rewritten or comparison disabled. The
workflow remains failed until font integration is implemented and validated.

## Remaining integration

Connect native glyph rendering, terminal-owned state, complete/cancelled DCS
input, page selection, alternate screens, resets, text/image occlusion,
scrolling, the shared raster budget, repaint scheduling and Windows renderers.
Add font/alphabet, curve and numeric/resource coverage. Then replay complete
original streams through the real terminal and run full CI. Component checks
do not establish native window pixels or frontend memory.

```powershell
gh workflow run protocol-reference.yml --ref <branch> -f family=regis-core
```

All compilation and runtime checks execute on GitHub-hosted runners; local
operations only edit source or inspect downloaded evidence.

[The evidence archive](regis-component-evidence.zip) retains 21 entries:
both final runs' metadata, all six original artifact ZIPs and download receipts,
failed-job logs and a per-file hash manifest. It is **4,368,333 bytes**, SHA-256
`9b357bac7457fa136ea0472afe1f29f7c825e671b7b34322ffb12997ffa3e6a9`.
The successful compilation/ownership steps do not change the failed comparison
jobs into passes.
