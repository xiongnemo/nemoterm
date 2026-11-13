# Reverse wrap and cursor input synchronization

The development terminal implements xterm modes 45 (reverse wrap) and 1045
(extended reverse wrap), including mode queries and private save/restore.
Both default to off and require ordinary autowrap to be active. Normal mode
crosses only a line marked as automatically wrapped. Extended mode can cross
hard breaks and cycle through the vertical margin region. The flags are shared
across alternate screens and are not part of DECSC/DECRC's cursor slot. RIS and
DECSTR reset them; explicitly saved private modes survive those resets.

BS and CUB now use the same movement rules. The earlier inherited PuTTY BS
could cross a line even with no reverse-wrap mode enabled. Tests that previously
assumed that behavior now explicitly enable mode 45. Reverse movement counts
physical cells, including the padding cell left before a wrapped wide glyph.
It does not skip that padding as the old PuTTY behavior did.

## Reference evidence

The reference is [XTerm 412 at
5c75ead9a75d4b2e666ca06fa94503b5766ed93f](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f),
especially `cursor.c`'s `CursorBack`, `charproc.c`'s mode/reset handlers and
`util.c`'s margin scrolling. Its executable SHA-256 remains
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.

`tests/xterm_reverse_wrap_oracle.py` captures 577 cases on a private Xvfb
display, with 112 cell checks and cursor/mode/presentation reports per case.
The reference initially stopped returning replies at a cold top-edge case.
The capture therefore seeds a blank saved line before each case; cold top-edge
behavior is also directly tested on fresh Nemoterm screens. Combining coverage
uses `x` plus acute, which has no precomposed scalar; the existing checksum
normalization limitations are documented separately.

567 cases are used byte-for-byte. Ten extended-mode cases above the scrolling
region report rows outside the viewport, including row 0 and unsigned-wrapped
negative values. They remain in the raw record with explicit generator
exclusions. Nemoterm stops at the physical top edge instead of allowing a
cursor to address history. Thirteen independent cases assert those bounded
results plus the three cold top-edge mode combinations.

Pending wrap has a subtle reference behavior: with reverse wrap active,
BS(1) and CUB(2) both clear pending wrap without moving; larger CUB counts
consume an extra unit. This is independently captured rather than inferred
from repeated BS. Counts saturate at 65,535 like the reference. Extended
cycles within the margins use arithmetic, so a huge count does not require
one operation per requested cell. Physical double-size-row coordinates and
the reference's lower-margin hard-break behavior are retained.

## Row state and data lifetimes

Partial-width autowrap is recorded in a separate existing-row-attribute bit.
It permits reverse motion without making copy/reflow join unrelated columns
outside the margins. As in the reference, partial-column scrolling keeps the
row wrap marker attached to the row. Full-row scrolling moves the whole row.
Line erasure/reset clears the marker. The bit fits the existing compressed
row attribute byte; it adds no cell allocation. Two Boolean flags and two
saved-mode integers are the only additional terminal-wide state.

Core tests check selection and Sixel ownership remain unchanged during 500
cursor-motion repetitions, combining chains survive, partial rows keep line
breaks when copied through the mock clipboard, resize keeps their rows apart,
and tiny grids survive saturated counts. The local desktop clipboard is never
used. Native tests compare independently drawn pixel baselines for default,
normal and extended BS, margin editing, read-only motion, and resized cycles.

## Host fragmentation correction

The first native run passed 49 cases, then the child received a tagged internal
cursor reply after the application barrier. The exact trailing bytes and image
identity are in `reverse-wrap-input-fragment-failure.json`. The pinned host's
input parser treated an ESC/ESC[ fragment as an isolated Alt key before seeing
its first Win32 key record. That prevented the completed tagged reply from
reaching its internal dispatch path.

While a tagged cursor transaction is pending, the same-image host now retains
those prefixes as streaming input. The ordinary idle heuristic remains as
before. This is a focused correction for pending internal synchronization;
it is not a claim of exhaustive input fragmentation coverage. Native fixtures
continue to reject extra internal bytes rather than filtering them out.

`reverse-wrap-validation.json` records source and image identities, compiler,
sanitizer and native results, and the limited scope of memory measurements.
The final local candidate is 4,430,336 bytes, SHA-256
`d6a46003b58a48bc5927437af6214c5492d78273e98911da6c21dda49b5546c3`.
It passed 35 MSVC suites, six MinGW suites, five Linux ASan/UBSan suites, and
19 native window suites. The native reverse-wrap comparison covers 63,504
cell replies in addition to state reports and 13 direct cases. Renderer
regressions required actual OpenGL and DirectX, and passed alongside GDI.

The isolated distribution contains only `nemoterm.exe`. In its bounded startup
sample, the frontend used 4,358,144 bytes private working set and 22,921,216
bytes total working set; its same-image host used 1,585,152 and 10,600,448
bytes respectively. The SGR scenario sampled a frontend private peak of
6,414,336 bytes. These measurements do not establish whole-workload acceptance.
The accepted main distribution remains unchanged.

Physical IME, real-agent clipboard interactions, all remaining protocol gaps,
and full workload/process-tree memory acceptance are still separate gates.
