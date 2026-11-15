# XTerm bell modes

The development branch implements private modes 1042 (window attention) and
1043 (raise on bell), their DECRQM replies and independent private-mode
save/restore. The complete component regression passes on three compilers,
and the focused native Windows checkpoint passes. Full product CI is running. No local
desktop test or executable promotion has been performed.

## Independent reference

[Run 43719391640](https://github.com/xiongnemo/nemoterm/actions/runs/43719391640)
at `fd5d1605ada039a1c64b66fab1bdd040b4d10a1f` observes unmodified XTerm(412),
pinned to `5c75ead9a75d4b2e666ca06fa94503b5766ed93f`, on a private Xvfb display.
All **112 fresh cases / 192 steps / three literal controls** complete, with
natural child exit and no stderr. Four explicit `bellIsUrgent` / `popOnBell`
resource combinations use 80x24 VT525 windows, measured 6x13 cells and disabled
bell suppression. The fixture reads actual X11 urgency flags, keyboard focus
and root stacking order, using its own second window as a cover/focus target.
Each byte stream ends in a DSR barrier and is checked for late replies.

`bell-modes-reference.tar.gz` retains 360 records / 339,272 bytes, including
original captures, child reports, workflow logs, exact fixture/shared harness
sources, executable identity, generated configuration and seven upstream source
files. `bell-modes-reference-validation.json` hashes every retained record.
The raw capture SHA256 is
`c5a87d9f9ee75d637293e3a6767d86102be622271720e8ee4b704e5727c9b6b4`.

Observed behavior includes independent defaults/toggles/saves/restores, an
unsaved restore clearing either mode, and preservation of both live and saved
values across RIS, DECSTR, DECSCL and alternate-screen transitions. Raising
does not move keyboard focus. Urgency is requested only when unfocused; focus
clears it while mode 1042 is enabled. Disabling 1042 after a bell leaves the
X11 urgency flag sticky even after focus. OSC BEL terminates the string without
ringing. BEL in the tested DECRQSS payload both rings and makes the query invalid.
RIS rings because upstream's `bellOnReset` resource defaults to true.

## Implementation and platform policy

The existing taskbar indication preference supplies mode 1042's startup
default. `NemoBellRaise` supplies mode 1043's default, initially false. A changed
local preference overrides the corresponding live mode; unrelated settings
changes preserve the application's modes. The new `NemoBellOnReset` preference
is initially false, preserving Nemoterm's prior silent-reset default. Both new
preferences appear in Terminal / Bell and persist in saved sessions.

The shared bell path keeps existing sound/visual and bounded overload behavior.
Urgency requests still occur under overload; raising and sound are suppressed.
The Windows backend uses the containing tab host for taskbar/caption indication
and uses `SetWindowPos` with `SWP_NOACTIVATE` for raising. These are the documented
[non-activating positioning](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos)
and [attention](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-flashwindowex)
APIs; an API success alone is not treated as proof of the visible effect.
It does not select an
inactive tab or restore a minimised window. A focused host is not flashed for
an inactive tab's bell. On focus, all seats belonging to that host clear their
notification. This deliberately uses ordinary Windows notification clearing,
including after mode 1042 is disabled, rather than reproducing X11's sticky hint.

The component fixture projects all original replies and window-state records
without rewriting them. It models the X11 focus/stack adapter to test core
attention requests; that model does **not** certify Windows API effects or
visible taskbar behavior. Separate checks exercise overload, setting changes,
silent reset and OSC termination. The focused native checkpoint below checks
Windows focus, stacking and attention API effects. Visible desktop taskbar
appearance, initially-topmost/minimized windows, background tabs and complete
product CI remain pending.

## First component checkpoint

[Run 43720699776](https://github.com/xiongnemo/nemoterm/actions/runs/43720699776)
at `b854196` passes all 192 bell reply/state records, in whole-buffer and bytewise
feeds, on GCC/Clang with ASan+UBSan and on MSVC. The complete workflow fails two
older authored assertions: a fixed 26-integer save-slot budget (now 28), and a
DECRQSS recovery test that incorrectly expected BEL to be removed from `m BEL`.
The latter is corrected to invalid-query status, consistent with the captured
`BEL m` query and the retained upstream `do_dcs` complete-string comparison.
No original oracle reply is rewritten. All three original failure artifacts are
retained in the component evidence bundle. Production code is unchanged
when correcting these two authored regression assertions.

The corrected [run 43721163137](https://github.com/xiongnemo/nemoterm/actions/runs/43721163137)
at `f93cb3d` passes all three compiler jobs, including every existing replay
in that workflow. `bell-modes-components.tar.gz` retains both original runs:
179 records / 816,297 bytes, with 126 source-hash matches. The companion manifest
keeps failures, passing logs and exact sources separate. This is a component
checkpoint, not full single-image acceptance.

## Native stacking failure and verified correction

The first [native run 43721167249](https://github.com/xiongnemo/nemoterm/actions/runs/43721167249)
at `f93cb3d` builds the single image but fails the first requested raise:
`SetWindowPos(HWND_TOP, SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE)` returns 1,
yet actual window enumeration still places the terminal below the foreground
cover window. Foreground focus remains unchanged and the real FlashWindowEx
request is observed. The fixture correctly rejects this API-success-only result.
Existing audible-policy and visual-bell fixtures pass in the same job.
`bell-modes-native-first.tar.gz` retains all 33 records / 2,747,094 bytes,
including the original image, API/focus/stacking observations, 16 preceding exact
reply streams, failure logs and exact fixture sources. Its validation manifest
does not promote the failed image.

`994bee4` uses a temporary topmost round trip for an ordinary window, preserving
the non-activating flags and restoring its original non-topmost class. A window
already marked topmost keeps that status. The native fixture additionally checks
that the final topmost attribute is unchanged, alongside actual stacking and
unchanged focus. Its [run 43721733820](https://github.com/xiongnemo/nemoterm/actions/runs/43721733820)
passes all **112 cases / 192 exact reply streams**, actual foreground and stacking
checks, and unchanged final topmost attributes. Four pairs of owned window/child
sessions exit naturally. Existing sound-policy and visual-bell fixtures also pass.

The 4,538,368-byte source single image has SHA256
`8cb4d404fa7c861e828b1b8af1151de7370fba85943c8b9b00d873de864e9ba9`.
`bell-modes-native.tar.gz` retains 33 records / 2,751,712 bytes; its manifest
compares all native sequences/replies/barriers with the unmodified original
capture and verifies API flags, actual Z order, foreground preservation, final
topmost state and cleanup. No API result or protocol expectation is substituted.
This does not certify desktop taskbar appearance, already-topmost/minimized
windows, background-tab bell behavior or local speaker output.

## Full workflow integration

`ea141fefc3e105aad6c1fcd49e0e0f161745ab53` adds generated-reference checking,
the new core replay and disposable native bell fixture to ordinary CI and the
isolated single-image workflow. Both required reference archives are copied
outside the executable directory; that directory still contains one executable.
The new single-image suite should have 158 groups. Ordinary
[43722555463](https://github.com/xiongnemo/nemoterm/actions/runs/43722555463) and
single-image [43722558224](https://github.com/xiongnemo/nemoterm/actions/runs/43722558224)
are running. The currently accepted local image is unchanged.

## Tab-host and window-state follow-up

The image-reuse job verifies a prior successful workflow's artifact ID, binary
source revision and SHA256 before running new fixtures. The first
[43723320663](https://github.com/xiongnemo/nemoterm/actions/runs/43723320663)
at `af5badf` stops before any bell assertion because its New Tab command launches
the configured shell instead of duplicating the fixture command. After using
Duplicate Session, [43723442007](https://github.com/xiongnemo/nemoterm/actions/runs/43723442007)
at `f654468` observes the unchanged `994bee4` image through ten passing GDI
window-state checks: focused/unfocused background bells, mode-disable/focus
clearing, an already-topmost host and a minimized host. It then finds a real
ownership bug: closing the sole notifying background tab produces no native
stop request, while the remaining tab and foreground window stay correct.
DirectX is not reached in that failing run.

`bell-window-state-failures.tar.gz` retains both original failures, 33 records /
55,246 bytes, with exact fixture sources, logs, binary provenance and observed
states. The tested executable remains in the earlier native archive.

`f25294c` clears a closing session's notification when it is the last owner for
that host, and preserves the host notification when another live session owns
one. It adds no allocation or persistent state. The new native build
[43723767151](https://github.com/xiongnemo/nemoterm/actions/runs/43723767151)
is pending and checks both GDI and DirectX, including two simultaneous owners.
A further fixture covers selecting a neighbour when an unfocused host's active
tab closes; its result is still pending. The earlier full workflows at `ea141fe`
predate this lifecycle correction and cannot certify it.
