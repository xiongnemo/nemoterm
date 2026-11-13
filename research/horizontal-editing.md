# Horizontal editing and native reply fragmentation

The development frontend implements backward/forward index (`ESC 6/9`),
left/right shifts (`CSI Ps SP @/A`), insert/delete columns (`CSI Ps ' }/~`),
and the scroll-down alias (`CSI Ps ^`). The DEC column controls require
VT420 compatibility. Horizontal edits retain the cursor and pending wrap;
index controls move the cursor until it reaches a horizontal boundary.
Scrolling is restricted to the configured row and column margins and is
ignored when the cursor is outside the applicable region.

The work also corrects SU/SD clearing a pending wrap. The reference retains
that state, so the next printable character can wrap to the following row.
Reverse-wrap modes 45/1045 remain a separate open item.

## Independent reference

The source is [XTerm 412, pinned at
5c75ead9a75d4b2e666ca06fa94503b5766ed93f](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f),
especially `charproc.c` and `util.c`'s `xtermColIndex`, `xtermScrollLR`,
and `xtermColScroll`. The reference executable SHA-256 is
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.

`tests/xterm_horizontal_oracle.py` runs on a private Xvfb display. It records
198 cases without exclusions, covering screen/margin boundaries, outside
positions, omitted/zero/large/multiple arguments, origin mode, pending wrap,
double-size lines, wide characters and background-color erase. Each case
has exact cursor replies and 104 independently captured cell values.
The raw capture is `horizontal-xterm.json`; generated core tests compare
actual cells, and the native test compares the complete reply byte stream.

## Text, selection and raster ownership

Horizontal movement preserves combining characters, hyperlinks, protection,
truecolor and underline decoration. Split wide cells are repaired before
moving. Affected selections are invalidated, while selections outside the
changed cells remain. Main-screen shell markers follow surviving cells;
markers shifted out are invalidated and alternate screens stay isolated.

Sixel uses shared immutable raster storage with bounded column/row views,
preserving pixels outside the rectangle and existing erasure masks. Admission
includes the temporary view and mask allocations before an iteration can
hold a source pointer. Completely erased cropped views are now released;
the new accounting test exposed that omission in the earlier splitting helper.
No per-text-cell storage was added.

Direct core tests compare the complete result to a separate flat pixel canvas,
including changed cell sizes, partial masks, aspect scaling, alternate screens,
240 changing rectangles and 1,200-source budget pressure. Native GDI captures
compare moved Chinese/combining text and raster pixels to separately drawn
baselines, verify all six horizontal operations, and repeat inverse shifts
40 times. These are bounded scenarios, not a full workload memory acceptance.

## OpenConsole input correction

The first native run failed even though the frontend/core comparisons passed.
The application received 1,273 bytes instead of 1,276: the three-byte prefix
`ESC P 4` of a checksum reply was missing. The exact difference and executable
identity are recorded in `horizontal-input-fragment-failure.json`.

The pinned host input engine buffers DCS replies until their terminator.
`StateMachine::_EnterDcsIgnore` nevertheless discarded a prefix cached by an
earlier `ProcessString` call when a DCS header crossed pipe reads. The overlay
now retains that cache only for the input engine. Output-engine string handling
keeps its existing behavior. The fixed native matrix compares all 20,592 cell
replies without relaxing expectations or reducing the batch size. The overlay
patch was also applied to fresh pinned source files and compared to the built
source. This is native batch coverage, not exhaustive fragmentation fuzzing.

`horizontal-validation.json` records the final executable/source hashes,
compiler and sanitizer results, native evidence and measured memory scope.
The original accepted distribution stays separate. Clipboard, real-agent,
physical IME and whole-process-tree memory gates remain open as documented
in the protocol inventory and prior records.
