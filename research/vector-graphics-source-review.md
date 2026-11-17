# ReGIS and Tektronix source review

This records source constraints and independent upstream observations, not
implemented Nemoterm protocol support. The current production candidate
remains `329019d`; its [completed 21/22 regression](terminfo-product-regression.md)
is not superseded by this work.

## Pinned upstream

Use XTerm commit `5c75ead9a75d4b2e666ca06fa94503b5766ed93f`, the same revision
as the existing hosted reference collectors. Relevant upstream files are
[graphics_regis.c](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/graphics_regis.c),
[graphics.c](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/graphics.c), and
[Tekproc.c](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/Tekproc.c).
Their file-specific copyright and permission notices must accompany any
adapted code; Tekproc also contains the original DEC notice.

The [control-sequence reference](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
describes ReGIS DCS entry and the separate Tektronix mode. These are separate
parser and display mechanisms, not additional Sixel encodings.

## Integration constraints found in source

* ReGIS uses process-global `persistent_context` and `persistent_state`.
  Nemoterm must give each terminal its own lazily allocated state: sharing
  these globals across profiles or tabs would mix independent sessions.
* `parse_regis` consumes a complete NUL-terminated string, allocates a scratch
  buffer of its length, and preserves state across requests. Modes 1 and 3
  reinitialize that state. The integration needs explicit input, work and
  memory bounds, including cancellation and split-transport tests.
* The ReGIS context includes eight alphabet slots and a 2,048-point fill
  buffer. Graphics pages, font rasterization and repaint scheduling depend
  on XTerm/Xlib. Importing the complete file would not supply a native Windows
  backend. Rendering adapters and page ownership must use the existing shared
  raster budget and terminal lifecycle.
* Upstream ReGIS emits replies through `unparse*` functions and periodically
  refreshes graphics while parsing. Both output transport and scheduling need
  native adapters; a decoder that only draws lines would leave these behaviors
  unimplemented.
* Tekproc has its own parser, X11 widget and input/display handling. Its status
  replies, graphics input, mode transitions and retained drawing operations
  need a separate implementation and reference matrix.

## Hosted reference checkpoint

[Run 44088804952](https://github.com/xiongnemo/nemoterm/actions/runs/44088804952)
at fixture `496bc34b50ae7065fd2b081e9ed6bac2ad72ad07` passes the initial ReGIS
collector on a GitHub-hosted Ubuntu 24.04 runner. The unmodified XTerm 412
binary has SHA-256
`0fc7b2f29c3777794701202c8d788a0e3392dcaba39662c14cac872a86829b84`.
The build explicitly enables ReGIS and requires effective
`OPT_REGIS_GRAPHICS=1`; its configure/build logs, packages, source hashes and
original executable remain in the artifact.

The collector runs **41 scenes twice**, each in a fresh XTerm on a private
Xvfb display: **82 processes, 140 steps and 222 initial/step frames**. Whole
and bytewise transports have identical original replies and RGB framebuffer
hashes. Every process exits zero naturally, with no forced cleanup. Both
transports pass literal position and ordinary-text cursor controls, the ReGIS
capability check, and drawing/erasing sensitivity checks. Geometry, pixel
format, all settling attempts and original PNGs are retained.

Coverage includes entry/resume modes, absolute/relative/pixel-vector movement,
position stacks, circles/arcs, fills, line patterns, writing styles, address
ranges, RGB/HLS palettes, displayed/hidden pages, reset/alternate-screen state
and CAN/SUB recovery. The single text scene uses an empty font resource.
Subsequent component comparison established that Xft still matches a system
font: its pixels show `ABC`, not missing-glyph blocks. The historical case name
`text-no-font` is retained, but does not prove that font loading was disabled.
It does not validate all font selection or uploaded alphabets.
The rectangle, circle, fill, RGB line and two page-selection images were
visually inspected as well.

Concrete observations include:

* Modes 0 and 2 preserve the position and current command; modes 1 and 3 reset
  both. The separate out-of-range mode-4 observation also resumes in this
  XTerm version; it is not presented as a documented DEC mode.
* Drawing to a hidden page produces no visible pixels until that page is
  selected for display. Returning between two pages restores their different
  horizontal lines.
* RIS clears the observed graphics and position. DECSTR preserves both.
  Entering the alternate screen hides the drawing while keeping the reported
  graphics position; the captured round trip restores the image.

## Page ownership and visible palette controls

[Run 44092344809](https://github.com/xiongnemo/nemoterm/actions/runs/44092344809)
at `9dfbf11354ce4efcfd5a26b3be5b5ca4435d520e` expands the same reference to
55 scenes, 110 processes, 228 steps and 338 frames. It passes both transports
with natural cleanup. Main/alternate-screen round trips retain their different
green/red lines. ED2 clears the observed drawing; ED3 leaves it visible; EL2
removes the intersecting one of two lines. CSI 3 S leaves one line visible,
whereas CSI 3 T produces three visible lines in this particular capture. The
raw observations are retained without treating that last effect as a normative
scrolling rule or assigning a cause that the evidence does not establish.

The shared-palette scenes in this build initially draw black on black. Those
captures cannot establish visible recolouring and remain unchanged in the
archive. [Run 44093439244](https://github.com/xiongnemo/nemoterm/actions/runs/44093439244)
at `8c27acf991b067d259d80c528142786ee89f2794` adds six separate controls that
explicitly define green before changing register 3. It also places the Sixel
below the ReGIS page to avoid occlusion. Every new step must contain exactly
101 visible line pixels or 600 visible Sixel pixels; a black frame cannot pass
that control.

The final collector passes **61 scenes, 122 processes, 264 steps and 386
initial/step frames**, all using the identical XTerm binary recorded above.
Whole and bytewise replies and RGB hashes match, all visibility controls pass,
and every process exits naturally with zero status. With private registers
enabled, the page sequence is green/red/green/red; with shared registers it is
green/red/red/red. The two cross-protocol palette-change sequences retain their
visible green pixels at the observed barriers in both modes. This establishes
the captured display result, not the absence of shared internal register state
or every later repaint behavior.

These finite observations are not full ReGIS conformance. Input-device
reports, font/alphabet loading, all curve/fill combinations, macrographs,
exhaustive cross-protocol invalidation and resource exhaustion remain open.
Tektronix still has no collector or implementation.

[The evidence archive](regis-reference-evidence.zip) contains **21 entries**:
all three complete original GitHub artifact ZIPs, each final run/job/artifact
metadata, receipts and read-only analysis, two file-only archival helpers, and
a per-file hash manifest. The original ZIP identities are:

| Run | ZIP bytes | SHA-256 |
| --- | ---: | --- |
| 44088804952 | 2,273,098 | `a74acee2ac5f2f1ffaabf88b9cf0e3fdcc7e5f49a5bb11d63a3d12646f7a1bcf` |
| 44092344809 | 2,368,798 | `90e0faf47d03c233d70769e0a3c6093c995725fb6b4ffe179dfe2a861243dbf4` |
| 44093439244 | 2,411,073 | `f1cb288263b12e35be6ffc29b4edde6f71ee65054adabb1c105198ccdaf25b00` |

The containing archive is **6,548,751 bytes**, SHA-256
`364a3ae1a0a5f206fa634f4027b6958f0053df3bdc1d8cde8bf89b2b42d4357e`.
Downloaded binary and source hashes were checked as files; no downloaded
program was executed on the development computer.

## Next implementation boundary

The decoder needs terminal-owned state and bounded storage, adapters for the
existing raster lifetime and output transport, and native Windows checks
against these independent observations. Extend the reference matrix before
claiming the additional families above. All compilation, reference execution
and product checks remain on GitHub-hosted runners.

The [native component](regis-native-component.md) now has a per-owner parser
and sparse pages. Its 70-frame parser projection passes with independent
upstream font inputs; native Windows glyph validation is separate and the
earlier failures are retained. It is not wired to terminal
input or renderers. The coverage ledger continues to mark both families
**Missing**; no new capability or product memory result is inferred.
