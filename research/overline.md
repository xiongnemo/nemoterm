# ECMA-48 overline rendition

Development source `8f47b22` implements SGR **53** (overlined) and **55**
(not overlined), as specified by
[ECMA-48 fifth edition, section 8.3.117](https://ecma-international.org/wp-content/uploads/ECMA-48_5th_edition_june_1991.pdf).
These expectations are separate from the existing pinned XTerm reference
vectors; adding them does not increase the number of matched XTerm captures.

The top-of-cell line follows the rendered foreground, including inverse and
selection colours. The underline colour affects only underlining. Concealed
text also conceals the overline. Double-width text extends the line across the
full width; double-height top rows draw it, and their bottom halves do not draw
a second line. GDI rasterizes it through the existing decoration path shared
by the OpenGL and DirectX compositors.

SGR 0, DECSTR and RIS clear the style; SGR 55 leaves other attributes intact.
Cursor save/restore, the alternate screen, compressed scrollback and reflow
preserve it. DECRQSS `m` reports 53, and the common-rectangle SGR report includes
53 only when all relevant cells have it. No-argument SGR push/pop retains it;
selective selector **53** is a Nemoterm extension to the existing SGR stack.
Other selective saves leave the current overline unchanged. Invalid colon
subparameters are ignored as a whole group, as with the other simple styles.

## Storage and measurement

The existing 32-bit decoration field was full: underline colour/style, legacy
double underline, protected-cell and drawn-cell metadata occupy all its bits.
It is now 64 bits. Windows `truecolour` grows from 12 to 16 bytes and `termchar`
from 28 to 32 bytes, checked by the native core suite. This adds four bytes per
allocated character slot, with no per-cell heap allocation. Existing compressed
history uses the same low-word encoding; a high word is stored only when nonzero.
The raster-run cache key includes the full 64-bit field.

The local single executable is 4,466,688 bytes, SHA-256
`ff832c1bdc191744e5e533283cbff72f5bfadcac2835876032ff80013ec75589`.
The SarasaTermSC Nerd Font Light workload obtained actual **160x48** cells and
two tabs, including 2,000 retained history lines per tab, distinct text/links,
Sixel redraws and repeated resizing. Its uninstrumented GDI frontend peaks are
**15,749,120 private-working-set bytes**, **41,803,776 total-working-set bytes**
and **18,739,200 private-commit bytes**, across 438 samples. All nine functional
groups pass and owned processes exit naturally. Host/client samples are retained
separately. This passes the unchanged strict 20,000,000-byte GDI gate for this
workload, not an unlimited workload bound.

## Validation status

Local MinGW SGR, queries, rectangle editing, selective erase, reflow and state
control suites pass. The SGR suite exercises combined styles, independent
reset, metadata protection, current/common queries, selective/full stack,
cursor/alternate-screen state, fragmented input, malformed groups and compressed
history/reflow. Fifteen additional explicit overline reply vectors also run
through the existing query suite and native rendition-stack fixture.
The local native fixture passes all **193 unchanged XTerm vectors plus 29
direct expectations**, including the 15 new overline cases, through ConPTY.

The renderer fixture passes all 16 scene comparisons with actual local GDI,
OpenGL and DirectX, using Sarasa. Both new overline scenes match GDI byte for
byte in the GPU modes. Independent pixel assertions require the line on the
enabled blank cells and no line on cancelled/concealed cells or double-height
bottom halves. Inverse colours and underline-colour independence are checked.
Capture instrumentation is confined to the fixture processes; its working-set
measurements are not memory acceptance.

The [local evidence manifest](overline-validation.json) retains exact source and
image hashes, raw replies, scene PNGs, all memory samples and test logs.
Full remote [single-image CI](https://github.com/xiongnemo/nemoterm/actions/runs/43491888131)
and [core/compiler CI](https://github.com/xiongnemo/nemoterm/actions/runs/43491888532)
are running on `9370c1f`. The earlier `8f47b22` runs were superseded when the
additional wire vectors were committed; they are not acceptance results.
The accepted local
`dist/nemoterm.exe` has not been replaced. The preceding DirectX large-window
memory failure remains open; this feature is not a DirectX memory optimization.
Framed/encircled, ideogram and alternate-font SGR remain separate missing
families. Plain-text copy carries characters without decoration; RTF export
does not yet encode the overline style. This checkpoint does not complete the
full protocol or terminal goal.
