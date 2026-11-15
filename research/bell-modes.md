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
both fail before the first bell case: `SetForegroundWindow` refuses fixture
preparation after earlier physical-input tests. Both still pass the preceding
89 UDK cases / 232 exact streams. `bell-full-first.tar.gz` retains all 8,725
records / 16,535,421 bytes with original run metadata, logs and both unverified
images; neither full workflow is accepted. The currently accepted local image
is unchanged.

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
builds image SHA256
`bb407c52853e9e9003b9b853e418495940033182c15f714efabe31f9115b9955`.
Its separate window-state fixture passes all **30 GDI/DirectX checks**, including
two simultaneous owners and natural job cleanup. The overall job nevertheless
fails: the older protocol fixture records 139 exact reply streams before a
transient empty mailbox read raises `KeyError: hex`. The corrected observer waits
for a complete snapshot and still compares the exact phase and original bytes;
no expected reply or product behavior is relaxed. `bell-lifecycle-native.tar.gz`
retains all 40 records / 2,766,329 bytes, including both the passing state fixture
and the original overall failure. It does not promote the image.

The image-reuse job subsequently requires an explicit diagnostic-only flag to
use that completed failed run, and records the failure in its provenance.
[43724456785](https://github.com/xiongnemo/nemoterm/actions/runs/43724456785)
at `a87c01e` reaches another real GDI issue: closing the selected tab while the
host is unfocused selects its neighbour and incorrectly clears the neighbour's
notice. Actual foreground remains the other application. DirectX is not reached.
`bell-active-close.tar.gz` retains this observation, source and provenance.

The [SetFocus contract](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setfocus)
describes focus messages on the calling input queue; an internal tab selection
is therefore not sufficient evidence that the user brought the host forward.
`0284fcf` checks the actual foreground host before acknowledging notices or
reporting terminal focus. Its new fixture also checks that closing a background
host's selected tab emits no false focus report, and bringing the host forward
emits one real report. Native
[43724828019](https://github.com/xiongnemo/nemoterm/actions/runs/43724828019)
passes all 112 standalone cases / 192 exact replies. The state fixture reaches
19 GDI checks: background active-tab closure now retains the notice and emits
no false focus input, but real foreground activation fails to clear the notice.
DirectX is not reached. `bell-reactivation-first.tar.gz` retains all 41 records /
2,774,791 bytes and this original failure.

`5a1bcdb` acknowledges the host notification on actual `WM_ACTIVATE`, including
when its selected child already has focus in the application's input queue and
therefore receives no new `WM_SETFOCUS`. The same activation updates terminal
focus; the fixture requires exactly one real focus-in report. Foreground checks
still gate notification acknowledgement. No allocation or persistent state is
added.

The [Windows foreground rules](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow)
also allow denial of the controller's focus preparation. The fixture now checks
ownership and, when necessary, exposes and clicks only that owned host's caption
using real input. It verifies the actual foreground window and preserves the
topmost attribute. This occurs before observations; it does not alter bell API
results, replace focus messages, or relax reply/notification expectations.

Native [43725655349](https://github.com/xiongnemo/nemoterm/actions/runs/43725655349)
at `5a1bcdb` still fails on the nineteenth GDI check, although all 192 standalone
replies and sound/visual fixtures pass. `bell-activation-native.tar.gz` retains
44 records / 2,778,402 bytes. The single-image run at that source was deliberately
superseded early by [43725867215](https://github.com/xiongnemo/nemoterm/actions/runs/43725867215)
at production-equivalent `f9e6e82`, which budgets 60 minutes for the expanded
suite instead of 45. The earlier UDK-only suite reached that overall deadline
while dense Unicode frames were still progressing; per-fixture and shutdown
deadlines remain unchanged. Both full suites now include the 38-state fixture;
the complete single-image suite should contain 159 groups.

The image-identical diagnostic
[43726461817](https://github.com/xiongnemo/nemoterm/actions/runs/43726461817)
at `9dd2d92` observes the real host and child window procedures. Its trace shows
`WM_ACTIVATE` and `WM_SETFOCUS` during background tab selection with the other
process still foreground. Actual foreground restoration subsequently sends
`WM_NCACTIVATE` only. `bell-activation-trace.tar.gz` retains 21 records / 112,328
bytes, including this original failed assertion and exact image provenance.
The trace does not replace or synthesize any window message.

`4154bac` handles positive nonclient activation, checks that this host is truly
foreground, then acknowledges notices and reports focus. The foreground check
also distinguishes real activation from notification flashing. No allocation
or persistent state is added. The older full ordinary/single runs were
superseded because they contain the now-confirmed reactivation defect.
`bell-superseded-workflows.tar.gz` retains 582 records / 11,940,538 bytes from
those cancellations and the earlier budget replacement, including partial
outputs and unverified images. Their cancellations are not treated as passes.

Corrected native [43726648546](https://github.com/xiongnemo/nemoterm/actions/runs/43726648546)
at `4154bac` passes all **112 cases / 192 exact replies** and **38 GDI/DirectX
window-state checks**. Background selected-tab closure preserves the remaining
notice and emits no false focus bytes; actual reactivation clears it and emits
exactly one `ESC [ I`. Existing sound-policy/visual fixtures pass, and all six
owned-job groups exit naturally. The 300 focus preparations in this focused
run need no caption-click fallback; that fallback remains for the full-suite
foreground-denial case and is not certified by this narrow pass.

The image is 4,538,880 bytes, SHA256
`0936fe9e787c7e81b7486d8911859e5ef5eff4a1beebf936876f4b0ec11eaa17`.
`bell-lifecycle-final-native.tar.gz` retains 48 records / 2,912,342 bytes with
the executable, exact source, original replies, API calls, message traces and
cleanup. Its manifest independently checks the original XTerm byte streams,
window invariants and both renderers' closure/reactivation reports.

Full ordinary [43726676169](https://github.com/xiongnemo/nemoterm/actions/runs/43726676169)
at `4154bac` passes all four jobs. Its retained observations include all 192
bell replies, 38 GDI/DirectX window states, 232 UDK streams, 27 Locator checks,
413 earlier ANSI/cancellation streams and 12 memory workloads. The owned-window
caption fallback was used twice and achieved the verified foreground target.
All required cleanup checks pass. Remote Consolas peaks were 14,340,096 bytes
private / 43,311,104 total for GDI and 17,199,104 private / 51,761,152 total for
DirectX; these are not local Sarasa or single-image measurements.
`bell-modes-ordinary.tar.gz` retains 4,614 records (639,871,325 raw bytes;
9,559,674 compressed) with original images, replies, source host identity and
artifact receipts. Its manifest checks the complete recorded invariants.

Single-image
[43726676358](https://github.com/xiongnemo/nemoterm/actions/runs/43726676358)
failed in the shell-mark fixture after all 19 selection/reflow checks passed:
its final one-shot mailbox read returned an empty snapshot. The reader maps
transient file-read errors to an empty object; the precise caught exception was
not logged. The cleanup snapshot contains the expected unchanged
DSR bytes (`1b5b306e`) in the correct `clipped-history` phase. This is not a full
suite pass. `bell-single-mailbox-failure.tar.gz` retains a diagnostic subset of
11 records / 5,419,849 bytes: run metadata/log, shell-mark observations and
screenshots, and the unverified executable with its artifact receipt. The
original CI evidence artifact retains the other partial-suite results.

Both one-shot assertions now wait for a readable snapshot and assert on that
same value; a readable but incorrect reply still fails immediately. The fix
changes only the fixture. Replacement single-image
[43729769426](https://github.com/xiongnemo/nemoterm/actions/runs/43729769426)
at `9d636e9` passes all **159 groups** within the unchanged 60-minute total
budget. Production source is identical to `4154bac`; only the mailbox fixture
changed. The one-file image is 4,538,880 bytes, SHA256
`714c6af5cd66b3ef7eeb69b619850217ba9827d40e1fe2a31ea3f53ece700fea`.
Its retained observations independently verify all 192 bell replies, 38 window
states, 232 UDK streams, 27 Locator checks, 413 ANSI/cancellation streams and 12
memory workloads. Remote Consolas peaks are 14,196,736 private / 44,527,616 total
bytes for GDI and 17,272,832 private / 52,953,088 total for DirectX. These do not
certify local Sarasa memory.

`bell-modes-single.tar.gz` retains 4,590 records (637,266,503 raw bytes;
9,411,513 compressed), including the image, source, original observations and
artifact receipts. Its manifest links product artifact `14168664703` and
evidence artifact `14169591216`; the hosted evidence expires on 2026-12-15.
Local single-image Sarasa comparison is underway separately. No physical
taskbar/speaker acceptance or accepted-image promotion is inferred from CI.

## Topmost fixture precondition

Later full runs at `5f5e80c`, ordinary
[43750810064](https://github.com/xiongnemo/nemoterm/actions/runs/43750810064) and single
[43750809954](https://github.com/xiongnemo/nemoterm/actions/runs/43750809954), fail
the `already-topmost` bell scenario. They are retained failures, not full passes.
The original records already show `topmost: false` before the bell. The single
run passes the GDI instance of this scenario but fails its DirectX instance;
the ordinary run fails its GDI instance.

Diagnostic [43753878737](https://github.com/xiongnemo/nemoterm/actions/runs/43753878737)
reuses the exact failed single image, SHA256
`837c1ec9ac77c00e4088b5df2f4a2cce365134f433b68f5cf6d56fdc57d673ed`.
The controller's `SetWindowPos(HWND_TOPMOST)` returns success, but the target's
extended style remains `0x110`, without `WS_EX_TOPMOST`, both immediately and
through the existing wait deadline. The added precondition fails before the
bell. The unmodified window-message trace retains that failed preparation.
A separate local owned-window probe changes the styles successfully; it does
not explain the hosted desktop's differing behavior or certify its focus.

The fixture now creates both processes using the real `AlwaysOnTop` setting,
checks the resulting styles, and runs the lifecycle scenarios with both false
and true values. It requires topmost preservation, unchanged foreground and
active tab, natural shutdown, correct notification ownership, and exact
focus-in bytes. In the already-topmost case it also requires one `HWND_TOP`
call, rather than a temporary topmost/not-topmost round trip. Product bell code
is unchanged.

[43754133124](https://github.com/xiongnemo/nemoterm/actions/runs/43754133124) passes
all 74 states against the same failed image. Final diagnostic
[43754353621](https://github.com/xiongnemo/nemoterm/actions/runs/43754353621), fixture
`1950dce`, additionally asserts each tab's actual renderer property: GDI is 1
and DirectX is 3. All 74 states pass again; four owned jobs containing 48 total
processes exit naturally. The extra checks establish the requested setup;
they do not weaken the original bell assertions.

`bell-topmost-fixture.tar.gz` and its validation manifest retain the original
two failures, failed precondition trace, both successful diagnostics, exact
failed image and artifact receipts, four fixture versions, and the local
probe. These results cover hosted Windows state and API behavior, not physical
taskbar/speaker acceptance, local Sarasa memory, or a complete product release.
