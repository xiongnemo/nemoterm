# XTerm bell modes

The development branch implements private modes 1042 (window attention) and
1043 (raise on bell), their DECRQM replies and independent private-mode
save/restore. Component and native Windows validation are pending. No local
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
and uses `SetWindowPos` with `SWP_NOACTIVATE` for raising. It does not select an
inactive tab or restore a minimised window. A focused host is not flashed for
an inactive tab's bell. On focus, all seats belonging to that host clear their
notification. This deliberately uses ordinary Windows notification clearing,
including after mode 1042 is disabled, rather than reproducing X11's sticky hint.

The component fixture projects all original replies and window-state records
without rewriting them. It models the X11 focus/stack adapter to test core
attention requests; that model does **not** certify Windows API effects or
visible taskbar behavior. Separate checks exercise overload, setting changes,
silent reset and OSC termination. Real Windows focus, stacking, taskbar effects,
background tabs and complete product CI remain pending.
