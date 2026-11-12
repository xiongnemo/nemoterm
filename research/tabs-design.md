# Native tab host plan

Requested: a tab bar on top, bottom, left or right, plus terminal previews on
hover. Default placement: top. A new session keeps the default 160x48 content
grid when it fits; the tab bar is added to the window chrome before applying
the work-area clamp. This is a design, not a claim that tabs are implemented.

## Layout and interaction

Use one top-level Win32 host and an owner-drawn tab strip. Horizontal placement
uses a single row with overflow scrolling; vertical placement uses a readable
list of horizontal titles, not rotated text. Each tab has its own title, close
button and shell/session identity. Add a new-tab button and shell chooser.
Store placement and bar size in settings; changing sides preserves running
shells and immediately recalculates the terminal viewport.

Hover for about 300 ms to show a small, non-activating preview popup next to the
tab. Fit the popup inside the monitor work area. Capture the hovered terminal
on demand, cap a preview at about 320x200 physical pixels before DPI policy is
finalized, and retain at most one thumbnail. A 32-bit thumbnail of this size is
256 KiB. Refresh at a bounded rate only while visible, cancel when the pointer
leaves, the tab closes, or the session switches. Never send input or steal
focus merely to obtain a preview. Frozen synchronized output must stay frozen
in previews as well. Large-font and Sixel content use the same renderer as the
terminal, then downsample; do not maintain a raw full-screen copy per tab.

Register new/close/next/previous/select-tab actions with the binding UI, retaining
the existing copy/paste and rectangle actions. Active application mouse and
keyboard protocols apply only to the content area, not the tab strip. Each
tab owns its selection, keyboard protocol state, IME preedit, scroll position,
title, cwd and session-specific settings.

## Existing code to separate

`WinGuiSeat` already groups Conf, Terminal, Backend, Ldisc, window, font and
input state; `wgslisthead` already tracks multiple seats. The hidden timer
window and handle-wait list can drive all sessions in one UI thread.

However, `windows/window.c::WinMain` currently creates exactly one seat and
polls only that seat's focus. `start_backend` exits the process on startup
failure. `exit_callback` and `WM_DESTROY` post WM_QUIT for one session.
`wgs_cleanup` relies on process exit for most terminal/backend allocations.
New/duplicate/saved-session menu actions create another process. These paths
must be made session-local before tabs are safe.

Extract application initialization and the message loop from session creation.
Add a host object with a list of seats and an active seat. A failed shell start
must close or mark only the affected tab. Closing a seat must cancel its
callbacks, IME, clipboard requests, backend I/O and timers, detach Backend from
Terminal, then release Ldisc, Backend, Terminal, Conf, logs, fonts, menus and
rendering resources. Only closing the last tab quits the process. Keep the
single-file frontend/hidden OpenConsole process model.

Use an active-tab renderer owned by the host for GPU mode so that every hidden
tab does not allocate its own GL context or retained full-size GPU frame.
Hidden PTYs continue to drain and parse output; suppress hidden repaint work.
They must receive consistent grid sizes after viewport/font changes, rather
than being resized only when activated. Share fonts/caches only where their
keys include font family, size, quality, fallback and DPI; terminal state stays
independent. Account separately for host memory, each tab's terminal/history,
and each hidden OpenConsole/shell process.

## Acceptance

Exercise all four sides, DPI transitions, work-area bounds, overflow, hover
cancel, previews of hidden text/Sixel/alternate screens/synchronized frames,
and switching while a command is writing. Verify exact input reaches only the
active child, background output is not lost, clipboard/IME focus does not leak,
and closing one tab leaves other shells alive. Repeat open/close and renderer
switches while measuring private WS, commit, GDI handles, handles and child
process lifetime. Preserve existing single-session native tests by targeting
the host's active content surface explicitly.
