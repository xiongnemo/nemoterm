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

## Font integration under development

`windows/nemo_regis_font.c` supplies the native glyph callback using GDI and
the profile's selected Windows face. Resources are lazy and owned by one
provider; each provider retains at most one DC, one font and one offscreen
bitmap (at most 8,192 pixels / 32 KiB of pixel storage). It returns binary
Latin-1 glyph masks in a common bounding box. The ReGIS parser handles text
placement, rotation and scaling. Named-font extensions currently accept a
Windows family name, not Fontconfig pattern syntax. This provider is still a
component and is not installed in the production frontend's `TermWin` yet.

The native hosted test uses the pinned `SarasaTermSC Nerd Light` font. It
compares the mask against a separate offscreen `TextOutW` DIB for each Latin-1
printable code at three sizes, exercises multiple owners and failed lookups,
and measures GDI handles before creation and after release. It also retains a
frame rendered through the real ReGIS component and the native callback.
Glyphs are drawn with
[`ExtTextOutW` and explicit glyph indices](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-exttextoutw)
into a bounded colour DIB, then converted to the decoder's packed binary mask.
The independent `TextOutW` test surface is larger than the provider's box and
checks its surrounding pixels too, so a clipped accent cannot pass simply
because both comparison crops omitted it.

The cross-platform parser comparison now supplies **independent font input**.
`scripts/generate-regis-font-probe.py` verifies the pinned upstream source hash
and extracts only its Xft lookup/bitmap functions into a hosted probe. That
probe has no terminal parser, reference images or Nemoterm code. It captures
the empty-name system font's masks, font paths and identities at five sizes.
All three compiler jobs consume the same captured input; the 37 original
scene streams, 70 expected frames and replies remain unchanged. This separates
platform font selection from protocol drawing. It does not assert that a
Windows Sarasa glyph has the same shape as Linux's default font.

The first font run,
[44105082566](https://github.com/xiongnemo/nemoterm/actions/runs/44105082566)
at `b5dc74e9e2163182332f6aa4a098a8d71fc2a883`, compiles all three decoders and
the Windows provider and passes ownership checks. Its comparisons fail:
diagnostic text was interleaved with the binary Xft fixture, so the strict
loader rejected it on all three platforms. The native font check also finds
six unsuccessful glyph requests and 42 accent-glyph comparisons differing from
`TextOutW`; all handles return from zero to zero. The native provider owns
192 bytes of explicit heap state, which does not include GDI's system-managed
allocations. The original failure is retained; these are not waived gates.

[44105914272](https://github.com/xiongnemo/nemoterm/actions/runs/44105914272)
at `bf7b2fbb25273c3b51e4e36b12d1c04cbc7808a1` separates binary and diagnostic
files. All three compiler jobs' parser comparisons now pass all 70 original
frames and replies. The Windows font test still fails the same 48 checks.

[44106680058](https://github.com/xiongnemo/nemoterm/actions/runs/44106680058)
at `eb8c51e` fixes space and nonbreaking space. All 573 native glyph requests
succeed, but 42 pixel comparisons still fail. A diagnostic using explicit
glyph indices has the same differences, so mapping text to glyph indices is
not the source of the discrepancy.
[44107534886](https://github.com/xiongnemo/nemoterm/actions/runs/44107534886)
at `4d46d93` realizes the font on a 32-bit colour surface; the same 42
differences remain. Both runs pass the three parser comparisons and retain
zero GDI handles after provider destruction. Neither native failure is waived.

The current provider renders each selected glyph through GDI instead of
returning `GetGlyphOutline(GGO_BITMAP)` pixels, which differ from actual GDI
drawing for these Sarasa composite glyphs. The original all-character
`TextOutW` comparison is still the gate, with the extra clipping check above.

[44108290137](https://github.com/xiongnemo/nemoterm/actions/runs/44108290137)
at **`c89fa96f3fe9b2387403c38728bc4053e611fb16`** passes all four jobs:

- GCC and Clang compile with warnings as errors and run ownership and original
  37-scene / 70-frame comparisons under ASan+UBSan; MSVC passes the same decoder
  checks. There are zero pixel or reply differences. The same 24 terminal-level
  exclusions remain explicit, not counted as passes.
- The native Windows provider passes **573 glyph comparisons** (191 printable
  Latin-1 codes at three sizes), including surrounding-pixel clipping checks.
  Space, nonbreaking space, accents, named-face overrides, interleaved owners,
  failed lookups and subsequent recovery pass. No character is excluded to
  avoid a mismatch.
- The actual pinned face is `SarasaTermSC Nerd Light`, font-file SHA-256
  `257913e04fe01695a6672feee02f7e0d7417d793ac9c3f760f5b9bb542bc3449`.
  GDI handles return **0 -> 0** after release. The default 8x20 glyph cell
  retains **864 accountable bytes** (224-byte owner plus 640-byte DIB pixels),
  excluding GDI system-managed allocations. This is not a frontend
  private-working-set measurement or shared-image-budget integration result.
- The native ReGIS text frame has 196 foreground pixels; the ASCII space
  remains black instead of becoming a solid missing-glyph block. The retained
  frame was also visually inspected.

[The font evidence archive](regis-font-evidence.zip) retains all five runs'
20 original artifact ZIPs, download receipts, initial and final run/job
metadata, logs, the native frame and a per-file hash manifest: **72 entries,
37,035,717 bytes**, SHA-256
`baf591946039233073a51aca096b8ac9d00ab888e1f038eb159d5b47597bf316`.
The passing run's independent Xft font input is SHA-256
`24c2aa660a9089b862d426c0d185184253e32350a9af5bcc080167368cea2cf5`;
the resolved `DejaVuSansMono.ttf` is SHA-256
`c805f9436dbc268644c1d9584f01a601a653e028e08fd74b9b949f6cf8304d88`.
These are test inputs, not embedded production fonts.

## Remaining integration

Connect the validated native glyph provider with terminal-owned state, complete/cancelled DCS
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
