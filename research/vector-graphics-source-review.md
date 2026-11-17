# ReGIS and Tektronix source review

This records source constraints and independent upstream observations, not
implemented Nemoterm protocol support. The current production candidate
remains `329019d`; its ongoing full regression is not superseded by this work.

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
and CAN/SUB recovery. The single text scene explicitly uses the upstream
missing-font glyph; it does not validate font selection or uploaded alphabets.
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

These finite observations are not full ReGIS conformance. Input-device
reports, font/alphabet loading, all curve/fill combinations, macrographs,
cross-protocol palette interactions and resource exhaustion remain outside
this initial reference. Tektronix still has no collector or implementation.

[The evidence archive](regis-reference-evidence.zip) contains seven entries:
the complete original GitHub artifact ZIP, final run/job/artifact metadata,
download receipt, read-only analysis and a per-file hash manifest. The original
ZIP is **2,273,098 bytes**, SHA-256
`a74acee2ac5f2f1ffaabf88b9cf0e3fdcc7e5f49a5bb11d63a3d12646f7a1bcf`.
The containing archive is **2,145,846 bytes**, SHA-256
`bc572667666fd440fd071aa33d015707896f93531f4ec7168b4e84f76cdbd0f8`.
Downloaded binary and source hashes were checked as files; no downloaded
program was executed on the development computer.

## Next implementation boundary

The decoder needs terminal-owned state and bounded storage, adapters for the
existing raster lifetime and output transport, and native Windows checks
against these independent observations. Extend the reference matrix before
claiming the additional families above. All compilation, reference execution
and product checks remain on GitHub-hosted runners.

The coverage ledger continues to mark both families **Missing**. No new
capability is advertised and no memory result is inferred from this review.
