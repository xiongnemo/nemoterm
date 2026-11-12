# Remaining application-requested resize operations

This branch starts from geometry-query/minimize validation source `9ccbad3`.
The implementation covers character/pixel resize operations and their
completion ordering. Source `44ac455` passed core/sanitizer and single-file CI,
then exact-artifact local validation. Final provenance is recorded below.

The pinned XTerm `charproc.c::window_ops` passes `optional_param(1/2)` to
`RequestResize` for operations 4 and 8. `RequestResize` distinguishes -1
(current dimension) from zero (screen dimension). Character dimensions include
border/scrollbar pixels before requesting a size; pixel requests are passed as
widget sizes. It then synchronizes X and processes geometry events before
returning. DECSLPP passes the requested row count and an unchanged column count.

The oracle resets to 83x27 before each of 39 cases, so a fallback to resource
defaults cannot masquerade as current-size preservation. It covers absent,
empty, zero, positive, extra and colon parameters; exact and non-cell-multiple
pixel dimensions; DECSLPP; and requests beyond X's Dimension limit. It uses the
same pinned XTerm and private 1024x768 Xvfb as prior references, with `fixed`
font and limitResize=1. Raw replies and executable hash are retained even if an
assertion fails. It does not validate window-manager maximization/fullscreen.

Implementation constraints established from the starting source:

- The existing parser already has `esc_arg_present`, so omitted and explicit
  zero parameters can be distinguished without changing the global default.
- The starting CSI 8 mapped zero to saved configuration and required both axes.
  CSI 4 was empty; DECSLPP always requested 24 rows. These are now corrected.
- `term_request_resize` uses a pending state and pauses input parsing until the
  frontend acknowledges the request. Pixel requests should retain that ordering
  and remote-resize permissions rather than directly mutating HWND in parsing.
- The existing Windows callback takes cell counts, clamps its minimum width to
  15 cells, and has font-resize/maximized/disabled branches. Exact pixel requests
  need a deliberate frontend path and cannot silently round through this API.
- Monitor/work-area furniture, huge values, fonts, Sixel, alternate buffers,
  query ordering and output while minimized need native tests. XTerm's behavior
  is reference evidence, not permission to move or resize unrelated windows.

Main's accepted distribution remains source 9ccbad3 until this branch's exact
single-file implementation and validation are complete.

## Independent result

Run [43265081881](https://github.com/xiongnemo/nemoterm/actions/runs/43265081881)
passed all 31 cases (oracle source `ec8c46a24117855fd5dbd8ace894ba0085c59afa`,
artifact 13964289769). Its replies are retained in `geometry-xterm-initial.json`.
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

Expanded run [43271622637](https://github.com/xiongnemo/nemoterm/actions/runs/43271622637)
captured 39 cases from oracle source `f251c27` (artifact 13967623349). Exact original responses are in
`geometry-xterm.json`. The replay header retains all 39 original replies, with
36 exact matches and three explicitly separate expected differences:

- Pixel requests 1x1 and 7x7 retain at least one complete cell plus padding in
  Nemoterm. XTerm permits sub-cell geometry and reports 65533x65533 text pixels
  for 1x1 (unsigned subtraction), while its grid still has one cell.
- Character resize with both axes absent after a non-cell-aligned pixel resize
  snaps to the current cell grid. XTerm reports the new outer size but stale
  text dimensions in the captured immediate reply; Nemoterm reports the
  current dimensions consistently.

Win32 can impose an additional caption minimum. On this machine all three
tiny requests result in a 103x22 client and 12x1 grid; native checks compare the
actual HWND, current protocol replies and the child's console grid. The
reference's Xvfb sizes are not asserted as Windows window-manager behavior.

## Implementation and development validation

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

`test_queries` replays all 39 frozen cases through the actual parser and a
geometry model, preserving the three documented differences. It also checks asynchronous acknowledgment, output
ordering, permission revocation and backend size reassertion. Query, resize,
mode and terminal core suites pass. The native fixture currently passes 100
checks across GDI, hardware GL, remote-denied, locked-window and font-resize
profiles, including alternate buffers, maximize/restore, minimize-time resize
and output preservation. GDI sampled private WS peaks at 5,767,168 bytes;
GL samples after retained-frame capture include Frida. The development frontend
is SHA-256 `e0ba55cfa746f277a300f579931b2c4a1739cdf5d98523cbdc9bcf3c286714c3`,
using accepted single-image OpenConsole and the pinned ConPTY DLL.

## Accepted single-file checkpoint

Source `44ac4554d13405fb2c4c673bd83fec2bbd0cc0ec` passed
[core, sanitizer and MinGW native CI](https://github.com/xiongnemo/nemoterm/actions/runs/43272768601)
and [all 42 single-file native groups](https://github.com/xiongnemo/nemoterm/actions/runs/43272768588).
The [EXE artifact 13969802687](https://github.com/xiongnemo/nemoterm/actions/runs/43272768588/artifacts/13969802687)
is 4,343,808 bytes, SHA-256
`9e9e9d663b72c5f31191f9bb0da91f40c07efe9f77b0e5dad5999b491a71fc48`.
Evidence artifact 13969333849 has 47 JSON files; all 43 top-level executable
hashes match. The isolated executable directory contains only `nemoterm.exe`.
The earlier d124d87 pipelines were superseded by stronger tiny-window assertions,
not accepted as complete runs. Final 44ac455 pipelines passed on their first attempts.

The exact EXE passed nine sequential local groups: 100 application-resize checks,
GDI/hardware-GL geometry, rendering parity, startup sizing, font resize,
synchronized output, Sixel, queries and native mouse/ConPTY/manual-window resize.
The latter drives owned HWND handlers; it is not physical-device automation.
The final images and JSON are named `window-resize-local-*` / `window-resize-final-*`,
with the complete provenance index in `window-resize-checkpoint.json`.

Local GDI resize samples peak at 6,242,304 private WS, 25,698,304 total WS and
7,561,216 private-commit bytes. The local hardware-GL sample before injection
is 29,470,720 private WS / 59,400,192 total WS; post-injection samples include
test-only Frida and remain labelled. Cloud GL requests exercise GDI fallback.
Cloud real-Codex default and inline frontend peaks are respectively
5,074,944 / 5,099,520 private WS and 34,811,904 / 34,836,480 total WS bytes.
Host/client processes remain separate; sampled peaks do not prove every workload.
Local clipboard access was denied at the preceding checkpoint and no new local
real-Codex clipboard acceptance is claimed here.

REA import inspection covers all 79 descriptors, 605 regular and 11 delayed
imports without reported issues; dynamic loading is outside that inspection.
`dist/nemoterm.exe` is replaced with this accepted artifact; the preceding
9ccbad3 image is retained in `build/dist-before-window-resize-44ac455/`.

Physical DPI behavior, axis maximization/fullscreen controls, DirectX frontend,
four-sided tabs with hover previews, full grapheme behavior, live Claude Code
and the remaining protocol families remain open. The original goal is active.
