# DEC rectangle editing

Implemented DECFRA (`CSI Pc;Pt;Pl;Pb;Pr $ x`), DECCRA (`... $ v`),
DECCARA (`... $ r`), DECRARA (`... $ t`) and DECSACE (`CSI Ps * x`),
including DECRQSS `*x`. DECERA/DECSERA now share the coordinate parser.
This checkpoint does not implement DECLRMM/DECSLRM: horizontal scrolling
needs Sixel columns to split at the margins, rather than moving whole raster rows.

## Independent reference

The oracle uses the existing private Xvfb harness and XTerm(412), built from
[Thomas Dickey's pinned source](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f).
Its executable SHA256 is
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
The controls are documented in that revision's
[ctlseqs.txt](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.txt);
[screen.c](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/screen.c)
provides the reference rectangle implementation. No events are sent to the
user's X display or existing terminal sessions.

`tests/xterm_rectangle_oracle.py` captures 50 cases in `rectangle-xterm.json`.
`tests/generate_rectangle_oracle.py` regenerates C expectations from that
independent capture. The core regression compares 60 cells per case, including
attribute flags. The combining-character copy case is checked directly as
original Unicode plus combining chains, since XTerm's checksum reports its
composed character while PuTTY preserves the separate code points. Colour and
protection semantics also have direct assertions; the reference's SGR colour
numbers include its bold-colour policy and are not blindly compared as indexes.

## Semantics and storage

* Coordinates are one-based, default/zero values are handled, unsigned values
  clamp before conversion, inverted rectangles do nothing. Origin mode offsets
  the vertical region. Cursor, saved cursor, pending wrap and line attributes
  are retained. Main and alternate screen content stay separate.
* Copy handles overlap in every direction and retains rendition, true colour,
  underline colour/style, protection, combining chains and hyperlink identity.
  Partial wide-glyph source boundaries become blanks. Target clipping is bounded.
  Page parameters are ignored like XTerm: there is one current page, not a
  multi-page backing store. One temporary row is traversed in the safe vertical
  direction; there is no full-rectangle scratch bitmap or cell array.
* Fill accepts DEC ASCII/Latin-1 and XTerm's printable Unicode extension. Each
  position is one cell; the existing renderer narrows a naturally wide glyph
  for that extension. GL line drawing/UK mapping is applied. Current rendition
  and DECSCA apply, while default current foreground/background retain existing
  cell colours. Fill removes old combining chains and links.
* Attribute extent 2 means an exact rectangle; every other stored value uses
  stream semantics. The stream starts/ends at the specified cells, traverses
  whole intervening rows, and skips undrawn cells. Rectangle mode marks blank
  cells as drawn. The extent survives DECSTR, screen switches and resize, and
  RIS resets it, matching the observed XTerm behavior.
* DECCARA supports 0/1/4/5/7/8 and 22/24/25/27/28; DECRARA toggles 0/1/4/5/7/8.
  Zero affects bold/underline/blink/reverse, not colour or the other styles.
  Other parameters are ignored. An absent attribute list does not synthesize
  an extra zero. Styles, text selection, protection, links and images outside
  the requested operation remain intact.
* A spare bit in the existing four-byte decoration word tracks undrawn cells;
  no bytes are added to a terminal cell. It survives compression and reflow.
  ECH/ICH and rectangle writes mark their inserted cells drawn; EL/ED and DCH
  trailing blanks remain undrawn. The ordinary SGR state never carries this bit.
* Filling/copying text clears Sixel only at the overwritten target cells.
  Attribute-only operations preserve raster pixels. Copy moves character cells,
  not the source Sixel bitmap. This image policy is validated in NemoTerm; the
  independent XTerm oracle above establishes text/attribute behavior only.

## Validation

All 27 core suites passed locally, including the independent oracle and tests
for copied links/protection/combining chains, overlap, history, alternate/reset
state, malformed input, Unicode and Sixel intersections. Linux ASan/UBSan also
passed rectangle, selective-erasure and reflow suites with leak detection.

`tests/rectangle_window_smoke.py` uses a newly owned Win32 window and a real
ConPTY child. It checks exact pixels against explicitly rendered text,
origin-relative fill, stream/rectangle attributes, Unicode cell clipping,
Shift-copy under application mouse tracking, local Sixel erasure, synchronized
presentation and edit-after-resize (40x12 -> 60x18 -> 30x9 -> 40x12).
It then runs 3,000 overlapping copies and continuously samples memory.
The user's clipboard is restored and the temporary profile/process is removed.

Local MinGW executable SHA256
`203ad359ea9eebe5bfa6288a291b444525ba15b85dec3c7d0a9ecc4bf75a69b8`
passed the complete fixture. Frontend sampled peaks were 5,079,040 bytes private
working set (5.079 MB / 4.844 MiB), 26,595,328 total working set
(26.595 MB / 25.363 MiB), and 6,615,040 private commit (6.615 MB / 6.309 MiB).
There was no working-set trimming; host and shell are separate processes.
The CI test/build workflow includes this core suite and sanitizer run. Both
Windows workflows include the native fixture and upload its JSON and PrintWindow
captures; the source-linked single executable now has 25 validation checks.

The full requested terminal scope remains open. Horizontal margins, remaining
control families, complete Unicode/IME and real-agent/DPI acceptance still need
work; this checkpoint does not claim to resolve earlier intermittent local
hyperlink fixture timeouts.
