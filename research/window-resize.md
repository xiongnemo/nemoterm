# Remaining application-requested resize operations

This branch starts from geometry-query/minimize validation source `9ccbad3`.
It currently adds only an independent XTerm oracle, not product resize changes.
The reference workflow is explicitly dispatched because this research commit
does not need another full OpenConsole build.

The pinned XTerm `charproc.c::window_ops` passes `optional_param(1/2)` to
`RequestResize` for operations 4 and 8. `RequestResize` distinguishes -1
(current dimension) from zero (screen dimension). Character dimensions include
border/scrollbar pixels before requesting a size; pixel requests are passed as
widget sizes. It then synchronizes X and processes geometry events before
returning. DECSLPP passes the requested row count and an unchanged column count.

The oracle resets to 83x27 before each of 31 cases, so a fallback to resource
defaults cannot masquerade as current-size preservation. It covers absent,
empty, zero, positive, extra and colon parameters; exact and non-cell-multiple
pixel dimensions; DECSLPP; and requests beyond X's Dimension limit. It uses the
same pinned XTerm and private 1024x768 Xvfb as prior references, with `fixed`
font and limitResize=1. Raw replies and executable hash are retained even if an
assertion fails. It does not validate window-manager maximization/fullscreen.

Implementation points to revisit after reading the reference:

- The existing parser already has `esc_arg_present`, so omitted and explicit
  zero parameters can be distinguished without changing the global default.
- The current CSI 8 maps zero to saved configuration and requires both axes.
  CSI 4 is empty; DECSLPP always requests 24 rows.
- `term_request_resize` uses a pending state and pauses input parsing until the
  frontend acknowledges the request. Pixel requests should retain that ordering
  and remote-resize permissions rather than directly mutating HWND in parsing.
- The existing Windows callback takes cell counts, clamps its minimum width to
  15 cells, and has font-resize/maximized/disabled branches. Exact pixel requests
  need a deliberate frontend path and cannot silently round through this API.
- Monitor/work-area furniture, huge values, fonts, Sixel, alternate buffers,
  query ordering and output while minimized need native tests. XTerm's behavior
  is reference evidence, not permission to move or resize unrelated windows.

The current accepted distribution and the geometry candidate are managed on
main / feature/window-geometry. Keep these research changes separate until
their own implementation and validation are complete.
