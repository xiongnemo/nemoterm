# Window and title controls: investigation and implementation boundary

This work covers the missing XTWINOPS operations, title stack and title modes.
CSI 22/23 title stacks, [title encoding modes](title-modes.md), and
[geometry queries](window-geometry.md) are now implemented and have single-file
CI and local validation. Geometry mutation gaps and the broader modern/xterm
protocol requirement remain open.

## Initial source gaps before the following checkpoints

The inherited `terminal.c` window-control switch supports only part of the
family. Pixel resize (4) and screen size in characters (19) are empty branches.
Cell pixels (16), monitor pixels (15), full-screen controls (10), axis-specific
maximization (9;2/3), and title-mode set/reset are absent.
Requests 13/14 ignore their text-area versus outer-window selector. On Windows,
WM_MOVE reports the client origin while the default query wants the outer
window position; WM_SIZE reports client dimensions including padding rather
than the exact text area. DECSLPP always requests 24 rows instead of its argument.
Resize request 8 maps zero/omitted dimensions to saved configuration, which
needs comparison with the XTerm distinction between current and maximum size.

The two title strings already retain a codepage and are freed on terminal
destruction. OSC 0/1/2/21 updates are deferred through the normal presentation
path. They honor `no_remote_wintitle`; queries 20/21 honor the existing three-way
none/empty/real policy. Stack push/pop and encoding modes must retain these
policies, store the encoding alongside the string, and avoid unrelated settings
changes overwriting an application's title. The current shared OSC parser
truncates long titles and has family-specific cancellation handling; tests must
make rejection, truncation, UTF-8 boundaries and recovery explicit.

## Reference and observations to collect

The pinned upstream is
[XTerm 5c75ead9](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f).
`ctlseqs.txt` defines XTWINOPS and XTSMTITLE/XTRMTITLE; `charproc.c::window_ops`
dispatches selectors and stores icon/window fields independently. In
`misc.c::xtermPushTitle/xtermPopTitle`, ten ring slots serve both stack and
indexed requests. Missing fields are searched in preceding slots. The third
parameter may retrieve without popping, and the implementation wraps indexed
values modulo ten even beyond the documented 1-10 range. These details need
runtime evidence, not assumptions about two independent stacks.

`tests/xterm_window_oracle.py` captures 30 cases on a private Xvfb display with
title/window operations enabled. It covers separate labels, Unicode, partial
push/pop, invalid selectors, indexed slots, overflow, RIS/DECSTR, alternate
screen, title hex mode and geometry. Baseline semantic assertions prevent a
disabled XTerm feature from looking like a valid empty result. Raw replies
must be inspected before creating the Nemoterm fixture.

## Independent reference captured

[Run 43244992756](https://github.com/xiongnemo/nemoterm/actions/runs/43244992756)
passed all baseline assertions and captured 30 cases from XTerm 412. Exact
sequences and replies are retained in `window-xterm.json`, including the
reference executable hash. This verifies the reference behavior only.

Icon and window fields share ten slots. A pop can fill a missing field from an
older slot. Invalid selectors still consume a slot on push or pop; direct slot
reads do not pop, and slot 11 aliases slot 1. Stack and direct writes share
storage. After twelve pushes, only STACK11 through STACK2 can be recovered;
further pops leave the last restored title unchanged. RIS, DECSTR and alternate
screen changes preserve the stored titles in these cases.

Hex queries return uppercase encoded UTF-8. Odd or invalid hex updates preserve
the prior title; decoded NUL/control bytes truncate the observed title. A
4096-byte update is rejected. Geometry queries distinguish the text origin from
the outer origin, and text pixels from outer pixels; screen and cell reports
agree with the private 1024x768 display and 6x13 font cell.

The earlier run 43244575456 did not clear indexed slots between cases. It is
superseded: direct-slot-and-stack previously inherited BASE from another case.
The corrected fixture empties all ten indexed slots and observes SLOT for both
queries. Keep this isolation when adding more cases.

## Title stack implementation and current validation

CSI 22/23 shares ten lazily allocated slots. Each saved icon/window string keeps
its codepage and distinguishes empty strings from absent fields. Partial saves,
older-field fallback, indexed access, documented selector defaults, invalid
selectors and modulo-ten indices match the 22 relevant captured reference
cases. RIS, DECSTR and alternate screens preserve the stack. Local title-update
policy blocks both push and pop without consuming stored entries; title-query
none/empty/real policy still applies independently.

Depth saturates at ten instead of growing an unbounded counter. Once all ten
retained entries are consumed, stack pops do nothing and the next push starts
at slot zero. This deliberately defines bounded overflow behavior; it does not
copy XTerm's unbounded count or claim identical behavior for interleaved direct
writes after an overflow. Each string is limited to 4096 bytes; a push containing
an oversized local title is rejected atomically. The twenty strings therefore
use at most 81,940 bytes plus slot metadata. No stack allocation occurs on reads.

`test_titles` compares the 22 independent replies, checks encoding and policy
preservation, empty fields, oversized titles, cancellation, large indices and
20,000 pushes. Windows core CI and Linux ASan/UBSan include it. Frozen reference
vectors are in `test/title_cases.h` and `tests/title_stack_reference.json`, both
derived from the retained XTerm result. Title-mode and geometry cases are not
claimed by these stack tests.

`titles_window_smoke.py` verifies the 22 exact replies through ConPTY and the
actual Win32 title, plus 1,000 pushes/pops with long strings. It changes no
clipboard or global input. The local comparison build passed all 23 checks
with Chinese, combining characters and emoji; sampled peak private WS was
3,502,080 bytes, total WS 20,590,592, private commit 4,513,792. Exact frontend,
DLL and host hashes are in `titles-window-observed.json`.

The official sidecar OpenConsole initially converted the astral query character
to two U+FFFD characters in raw UTF-8 ReadFile. The existing single-EXE source
overlay already repairs this host surrogate-buffer bug. The passing local
comparison used the verified f6b4409 single EXE as its OpenConsole host, with
the new MinGW frontend and pinned DLL. It is not a single-file acceptance run.
The single-EXE workflow runs the same strict native test using the final image;
its result is recorded below. No emoji check was removed to accommodate the upstream
sidecar limitation.

## Accepted single executable (2026-11-13 Sydney)

Source `5a8b27feb6ab980cceaef87e592aaa0ebf900def` passed
[core and sanitizer CI](https://github.com/xiongnemo/nemoterm/actions/runs/43251676450)
and [single-executable CI](https://github.com/xiongnemo/nemoterm/actions/runs/43251676493).
All 39 native CI groups passed, including real Codex default/inline sessions,
settings, shutdown and the new title stack group. The EXE artifact is
`13960112313`; full evidence is artifact `13960791747` from the same run.

The exact 4,339,200-byte executable has SHA-256
`c5970125f2c171a86ff33a50d37357d03dfc3ecfe0bed7832b76bda642629995`.
Local testing of that downloaded file passed all 23 title checks, including
actual HWND Unicode titles and the 1,000-entry churn. Its directory contained
only `nemoterm.exe`, with no development runtime sidecars. Sampled frontend
peaks were 3,973,120 private WS / 23,314,432 total WS / 5,136,384 private commit
bytes. The equivalent CI samples were 4,116,480 / 31,571,968 / 5,173,248 bytes.
These are samples after phases, not a continuous peak measurement; console host
and client memory are separate from the frontend. Exact observations are in
`titles-single-local.json`, `titles-window-ci.json` and `titles-single-ci.json`.

This accepts bounded title stacks only. Title encoding modes and remaining
geometry controls continue in a separate branch. It does not close the broader
renderer, tab, physical-device or protocol requirements.

## Implementation constraints

Use lazy bounded storage, including metadata and title bytes. Preserve explicit
empty strings separately from absent fields, and never use an unbounded push
counter. Define overflow behavior without wraparound or resurrection of evicted
entries. Direct slot access must not change stack depth. Preserve per-string
encoding and validate decoded controls before setting a native title or
returning a query. A reply must not contain user-supplied escape delimiters.

Geometry queries must use physical pixel units consistent with Sixel and current
font/DPI. Obtain both client text geometry and outer-window/monitor geometry;
avoid reporting a full-window size as a text area. Apply local remote-resize
policy before mutations. Bound arithmetic before calling Win32 or allocating
terminal rows. Keep asynchronous resize/report ordering explicit: a DSR reply
proves parsing, not that the OS has committed a requested window size.

The pinned Microsoft host forwards output and suppresses its own replies in
ConPTY mode. Its internal window-title changes and partial WindowManipulation
support still need end-to-end verification, including effects on duplicated
sessions. No direct edits to the Microsoft submodule are planned.

## Required acceptance

Test byte fragmentation, cancellation, long and malformed title payloads,
invalid selectors, nesting/overflow/indexed access, encoding changes between
save/restore, main/alternate screens, resets, reconfiguration and permissions.
Use ASan/UBSan and repeated storage churn. Native tests must compare the actual
Win32 title, exact child replies and real font/grid/window dimensions, including
negative monitor coordinates, minimized/restored state and GDI/OpenGL switching.
Keep potentially disruptive window commands confined to owned test windows.
Measure per-window private working set and retain the single-EXE distribution.
