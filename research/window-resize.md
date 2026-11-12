# Remaining application-requested resize operations

This branch starts from geometry-query/minimize validation source `9ccbad3`.
The implementation now covers the character/pixel resize operations and their
completion ordering. Final single-executable CI is pending. The reference
workflow is explicitly dispatched while extending independent edge cases.

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

## Independent result

Run [43265081881](https://github.com/xiongnemo/nemoterm/actions/runs/43265081881)
passed all 31 cases (oracle source `ec8c46a24117855fd5dbd8ace894ba0085c59afa`,
artifact 13964289769). Exact replies are in `geometry-xterm.json`.
Empty/absent axes preserve 83x27, explicit zero uses the screen-sized widget,
and extra semicolon parameters are ignored. Colon subparameters cancel these
operations. DECSLPP 31 and 31;99 both produce 31x83, not 24 rows.

The reference has four total border pixels per axis and 6x13 cells. A 210x482
pixel request reports 206x478 text pixels but a 15x79 grid; non-cell-multiple
pixels remain in XTerm's text area. This differs from Nemoterm's centered cell
grid, whose current geometry callback treats leftover pixels as padding.
Do not use a cell-aligned query test as proof of exact pixel-resize parity.
Explicit zero height gives 764 text pixels and 58 rows inside the 768-pixel
widget, while screen-character query 19 reports 59 rows (no furniture).
The 65536 pixel-height case was limited to screen height, whereas the same
character-height request was ignored; inspect parser saturation and bounds
before deciding the compatible policy. The pinned parser saturates each numeric
parameter at 65535 (`ptyx.h::MAX_I_PARAM` and `CASE_ESC_DIGIT` in `charproc.c`),
which explains the large-pixel result. The implementation applies this bound
only to the window-size parameters, without changing other protocol parsers.

## Implementation and local validation in progress

XTWINOPS 4 and 8 preserve absent axes and interpret explicit zero as the current
monitor's available client size. Character requests account for the configured
padding and cell dimensions; pixel requests set the client rectangle directly.
Windows non-client furniture is added separately. DECSLPP now uses its argument
and ignores extra semicolon parameters, while zero/default operation is ignored.
The pure size planner allocates nothing and rejects cell multiplication beyond
the reference's 16-bit pixel dimension before applying the monitor limit.

Requests use the existing deferred resize/acknowledgment state machine, so
following output and queries wait for frontend completion. Disabled remote
resize, a locked window, maximized/fullscreen windows and backend restrictions
are honored. Font-resize policy changes the grid inside the current window for
character requests; pixel requests change the window and refit its font.
Minimized requests update the restore rectangle without showing the window,
and the parser continues to drain output with the corresponding child grid.

The initial native run exposed a real ConPTY mismatch: even when the frontend
rejected CSI 8, the child's console had already changed to 90x30. Rejected or
unchanged requests now reassert the frontend's authoritative grid to the backend.
The test waits for that separate size-control pipe to settle before comparing
child console dimensions. Pre-fix failure evidence is kept separately.

`test_queries` replays all 31 frozen independent replies through the actual
parser and a geometry model. It also checks asynchronous acknowledgment, output
ordering, permission revocation and backend size reassertion. Query, resize,
mode and terminal core suites pass. The native fixture currently passes 84
checks across GDI, hardware GL, remote-denied, locked-window and font-resize
profiles, including alternate buffers, maximize/restore, minimize-time resize
and output preservation. GDI sampled private WS peaks at 5,730,304 bytes;
GL samples after retained-frame capture include Frida. The development frontend
is SHA-256 `389b38a9e249e8fd01e8d424468d7fc05cf1762f113b6bfaca544c34cdd7323a`,
using accepted single-image OpenConsole and the pinned ConPTY DLL.

Exact single-file validation, additional tiny-size reference cases, physical
DPI behavior, axis maximization/fullscreen controls and remaining protocol
families are still open. Main's accepted distribution has not changed yet.
