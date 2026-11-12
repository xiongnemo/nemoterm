# Horizontal scrolling margins

NemoTerm supports DECLRMM (`CSI ? 69 h/l`), DECSLRM (`CSI left;right s`),
DECRQM 69, DECRQSS `s`, and saved mode 69. With DECLRMM off, `CSI s` retains
ANSI cursor-save behavior. Valid regions require two columns; zero/default
and extra parameters follow the captured XTerm behavior, while parser overflow,
colon parameters and cancellation cannot partially update the state.

## Independent evidence

[Pinned XTerm(412) source](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f),
executable SHA256 `089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
`tests/xterm_margin_oracle.py` replays 118 cases on a private Xvfb display;
`margins-xterm.json` retains their raw queries/replies, 84 cells per case,
and per-cell rendition for 19 cases. `generate_margin_oracle.py` generates
114 exact comparisons for `test_margins`.

The reference uses `-ti vt420` for horizontal margins and explicitly sets
`*decGraphicsID: 340` for Sixel. VT420 alone silently ignores Sixel in this
build; that earlier diagnostic capture is not used as graphics evidence.
Five Sixel cases establish cursor/text behavior only; NemoTerm's raster
behavior is checked independently with a pixel model.

Four captured cases use direct assertions instead:

* Resize is delivered through `term_size` and actual Win32 resizing.
* Saving mode 69 while disabled preserves false. XTerm `charproc.c:8201`
  saves the constant `LEFT_RIGHT` instead of the current flag, so restoring
  its saved false unexpectedly enables the mode. We do not reproduce that.
* In the two wide-glyph scroll cases, XTerm `util.c:scrollInMargins` repairs
  boundaries on `row + amount` for all rows through the bottom margin. That
  can erase a wide glyph one row outside the region. NemoTerm repairs only
  participating rows, and direct whole-grid assertions preserve outside rows.

## Behavior and storage

Origin mode offsets/clamps both axes. CR, BS, HT, cursor movement, automatic
wrap (including a wide glyph at the right edge), LF/IND/NEL/RI, insert/delete
characters and lines, SU/SD, and rectangle coordinates honor the captured
margin rules. Attribute-stream operations still traverse whole intermediate
physical rows. Margins are global across the main/alternate screen; their
contents remain independent. Resize restores both axes to the full screen
while retaining mode 69. DECSTR/RIS clear it. Enabling it restores current
rows to normal size and suppresses DEC double-size commands while enabled.

Partial-column text scrolling uses direction-safe cell copying, preserving
combining chains, rendition/true colour, protection and hyperlink identity.
Only full-width scrolling can create complete scrollback lines. Overlapping
selection is invalidated; a selection entirely outside the region survives.

Sixel rasters have immutable shared storage and independently cropped views.
Each view owns its row anchors and erasure masks, but references the same
source bitmap. Splitting includes peak temporary metadata/masks in the
existing 4 MiB global budget, evicting old images before holding source
iterators. Storage and references are checked through eviction, pending
input, alternate screens, history, font changes and reset. Font changes keep
intrinsic pixels at their character anchor plus fixed source-pixel offset.
Sixel completion wraps the cursor once at the right margin and scrolls it
into the vertical region, matching the graphics-enabled reference; display
mode retains the cursor.

## Validation

`test_margins` includes direct one-cell-screen, malformed input, saved state,
wide-boundary, combining/protected/link, selection and history tests.
`test_sixel_terminal` adds a flat pixel-array scroll model, 400 deterministic
changing-region steps, aspect ratios, existing erasure holes and font sizes,
plus 1,200 images under eviction pressure and 80 changing column cuts.
ASan/UBSan with leak detection passed margin, image, rectangle, reflow and
state-control suites.

`margins_window_smoke.py` uses owned HWNDs and real ConPTY children. It compares
SU/SD/IL/DL pixels with explicitly rendered expected text, checks Shift-copy
of combining/CJK text under application mouse/keyboard protocols, and compares
Sixel pixel sets against an independent coordinate model during partial
scrolling, erasure, grid and font resizing. The image phase clears history
before measuring coordinates: height growth otherwise legitimately refills
old history and moves the image. Each resize policy ends with 300 image
split/scroll operations and continuous memory sampling. Clipboard contents
and temporary profiles are restored/removed.

The CI workflows run 28 core suites, 11 terminal sanitizer suites, and 26
single-executable validation checks, including this native margin fixture.
The single-executable artifact still source-links the PuTTY frontend and
Microsoft OpenConsole/ConPTY into one PE; this change adds no runtime DLL.

These are bounded conformance cases, not a claim that every xterm extension,
VT52 interaction, grapheme/emoji, IME, DPI or real agent workload is certified.

Local MinGW development binary SHA256 `817b572beedccbbffbc8dccb94c562873466da12923f99fd6b06d951b7e96d55` passed
the native margin fixture. Sampled frontend peaks: 9699328 bytes private
working set, 31789056 bytes total working set, 11317248 bytes private
commit. No working-set trimming; the host and shell are separate processes.
See `margins-window-observed.json` and the accompanying screenshots. The actual
release artifact is produced and retested by the single-executable CI.
