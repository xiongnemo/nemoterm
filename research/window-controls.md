# Window and title controls: investigation and implementation boundary

This work covers the missing XTWINOPS operations, title stack and title modes.
It does not replace the broader modern/xterm protocol requirement. No new
application implementation is claimed by this initial reference checkpoint.

## Current source gaps

The inherited `terminal.c` window-control switch supports only part of the
family. Pixel resize (4) and screen size in characters (19) are empty branches.
Cell pixels (16), monitor pixels (15), full-screen controls (10), axis-specific
maximization (9;2/3), title push/pop (22/23), and title-mode set/reset are absent.
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
