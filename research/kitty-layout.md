# Ordinary kitty placement geometry

`nemo_kitty_layout.c` calculates source cropping, ordinary image rectangles and
cursor deltas without allocation or terminal state. It follows the independently
captured kitty model at `8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f` described in
[the reference record](kitty-graphics-reference.md). No upstream implementation
is copied and no additional runtime dependency is introduced.

Both explicit dimensions fill the available cell rectangle. A single explicit
axis preserves the cropped source aspect ratio. Pixel offsets are clamped to
the current cell and reduce the explicit drawable extent. Cursor occupancy has
separate offset arithmetic; the retained one-axis cases catch that distinction.
`C=1` suppresses cursor movement. Crops are limited to the source boundaries,
and signed z values are retained for the future compositor.

All source/cell axes are bounded to 8,192. Integer intermediates use 64 bits:
even a maximum 32-bit cell count, a maximum cell size and maximum source aspect
fit within that range. An inferred cell count exceeding 32 bits returns a limit
error. Empty/outside crops and invalid cursor policy return errors without
changing the output. Relative and Unicode virtual placements are explicitly
unsupported by this component.

The generated reference header contains literal observations from 13 upstream
cases. Its generator verifies the complete retained capture's SHA-256 and
upstream identity before extracting headers, pixel/source rectangles and cursor
positions. It does not implement a second layout algorithm. Comparison allows
0.00002 pixels for kitty's recorded float rounding. Simple right-edge cursor wrap
is applied only by the comparison harness; bottom scrolling is excluded because
it belongs to the future terminal owner. No GPU pixels are compared here.

The local strict C99 test passes 153 assertions, covering the 13 observations,
changed font-cell metrics, signed coordinates/z, oversized crops, offset clamps,
integer limits, invalid input and unchanged output on failure. Focused GCC,
Clang, MSVC, ASan and UBSan checks are added alongside the full core workflows.
Their remote results are pending. The raw local log and source hashes are in
[the validation record](kitty-layout-validation.json).

The terminal still does **not** implement or advertise kitty graphics. This
geometry component has no placement store, source references, deletion, quota,
scroll/history lifetime, alternate-screen behavior, animation, synchronization
or rendering. The owner must apply cursor deltas through its normal bounded
terminal path, move existing placements with scrolling, clip visible geometry,
and re-evaluate it after font/DPI changes. The integrated source-to-frame path
and actual Sarasa memory acceptance remain open.
