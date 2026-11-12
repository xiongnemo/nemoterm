# Native tab host checkpoint

The feature/tabs branch now contains an opt-in, native Win32 tab host. Launch
with `nemoterm.exe --tabs --tab-side left` (also top, bottom, right), or enable
**Window > Tabs > Open sessions in tabs** in startup settings and save the
profile. Standalone windows remain the default during the migration. This
checkpoint is not a replacement for the accepted executable in the main checkout.

## Implemented

- One `NemotermHost` top-level HWND, separate `Nemoterm` child views and independent
  terminal/backend/input/scrollback state. Only the active child is visible.
- Four-sided tab strip, close buttons, middle-click close, new-tab button and
  overflow arrows/wheel; active tabs are brought into the visible strip.
- Ctrl+Shift+T / Ctrl+Shift+W / Ctrl+Tab / Ctrl+Shift+Tab defaults, with saved
  binding controls and collision checking shared with the other actions.
- Window > Tabs saves position, side-bar width, hover-preview preference and
  shortcuts. Settings round-trip checks also switch the active tab between GDI,
  OpenGL and DirectX while running.
- New tabs use the configured shell; Duplicate Session preserves the explicit
  command and the existing validated directory-inheritance policy.
- A single GPU surface/device is reparented to the active content window. GPU
  caches are cleared when changing seats; background seats have no GPU object.
  Different per-session renderer choices cause an explicit device change.
- One nonactivating preview popup and at most one 320x200 thumbnail. A temporary
  source band is limited to 256 KiB. Halftone downsampling preserves thin text.
  Only a visible preview refreshes, every 250 ms after a 400 ms hover delay.
- A frozen GPU presentation is compressed before transferring the device. The
  inactive tab retains its bounded snapshot until synchronized output ends.
  A snapshot allocation failure is logged and ends that freeze explicitly.
- Outer-window operations target the host; text, mouse and IME coordinates stay
  local to the child viewport. Background remote window operations cannot move
  or resize the shared host. Fullscreen restores the original host rectangle.
- Menus borrow the active seat's submenus, detaching them before resetting the
  system menu or freeing the seat. Last-session cleanup destroys the host.

## Evidence

`tabs-{renderer}-{side}-observed.json` contains final local native runs with
160x48 requested cells and SarasaTermSC Nerd Font Light. GDI top/bottom, actual
hardware DirectX left, and actual OpenGL right each passed nine groups:

1. Native tab hits and independent session input/output in one host.
2. Twelve create/close cycles retaining the same GPU surface HWND and stable
   handles, with samples taken before injection.
3. New, close, next and previous shortcuts on the owned UI thread.
4. Failed CreateProcessW/CreateWindowExW recovery preserving the active tab.
5. A bounded hidden-tab preview that updates to a specified new Sixel colour
   without selecting the tab.
6. Synchronized pixel equality across two switches and a GPU-device transfer.
7. Fullscreen restoration.
8. Host resizing and terminal grid reports for both sessions.
9. Original-tab close, sibling survival and natural process/job cleanup.

The pure layout test also passes 72,000 small-window, DPI and overflow cases.
`tabs-settings-window-observed.json` and `tabs-settings.png` cover the real native
settings dialog, unclipped controls, saving, reloading, changed bindings and
four live renderer changes. The settings binary differs from the final tab-test
binary only by the subsequent renderer-help wording change; each evidence file
records its own executable hash.

Local development builds use isolated ConPTY/OpenConsole sidecars. They are not
the single-executable delivery. Both GitHub workflows now run the new tab tests;
the single-executable verifier adds four tab cases and the tab-settings variant
to the previous 49 groups (54 with the real Codex cases enabled).

Eight standalone regression groups (startup caret, SGR, IME fixture, shutdown,
mouse, renderers, window resizing and session restart) passed on the preceding
host binary. Those exact records remain under `build/tabs-host-local-check` and
are distinguished from the final executable in `tabs-host-local-checkpoint.json`.

## Limits of this checkpoint

- The memory samples cover this two-session fixture and twelve temporary tabs,
  before injected capture/hover/key helpers. They exclude shell/console child
  processes and do not certify preview-time or arbitrary-session memory usage.
  OpenGL remains under the user's explicit memory exception. DirectX is checked
  against 20,000,000 private working-set bytes when hardware is required locally.
- Preview and key tests inject only fixture-owned HWND input. No global mouse
  movements or keyboard input are used. Preview leave tracking is simulated
  inside that PID; physical desktop hover is still a separate check.
- The geometry helper covers overflow and monitor-edge placement exhaustively;
  physical multi-monitor DPI/IME testing still needs coverage. Long-running
  agent workloads, tabbed clipboard/selection stress,
  and all existing native suites in tab mode remain
  before making the host the default or promoting a new accepted binary.
- No new dependency, webview, helper executable or per-tab GPU device was added.

## Overflow and protocol regression checkpoint

Closing a background tab before the selected tab could shift the selected tab
outside the visible strip. Removal now reveals its new index, while excluding
closing seats during host teardown. `tabs_overflow_window_smoke.py` reproduces
the original failure and passes five native checks for each of the four sides:
ten-tab creation, keyboard wrap, background close, wheel scrolling and middle
click close. These are real HWND/pixel checks with input confined to the fixture.

`tabs-regression-local-checkpoint.json` identifies the development executable.
GDI, actual OpenGL and actual DirectX each passed seven geometry phases and 42
application resize checks inside the host. Denied remote resizing, fixed window
size and font resizing also passed. The IME record covers injected fault cases,
an installed IMM submission and synthetic DPI changes, not physical composition
or moving between monitors. Local clipboard access was unavailable before the
selection assertions; that attempt is recorded separately and is not a pass.

Both workflows now run `tabs_regression_suite.py`, including four overflow sides,
geometry and resizing in all three renderer modes, IME/DPI, and three selection
variants. Core CI preserves these records even on failure. Single-EXE CI runs
the same tests from its isolated copy without console sidecars.

The prior revision's CI was not accepted:
[Core 43303590174](https://github.com/xiongnemo/nemoterm/actions/runs/43303590174)
left two owned descendants after host exit;
[Single EXE 43303590094](https://github.com/xiongnemo/nemoterm/actions/runs/43303590094)
observed the previous font geometry after a Sixel resize. The latter check now
waits for both the requested geometry and matching image pixels, because an
output query reply alone does not acknowledge native painting. Its exact binary
passed locally with the strengthened check. The process-cleanup failure has not
been reproduced in 16 local runs (192 immediate default-shell tab closes) on
that same CI executable. Each host test now repeats those closes and requires
the owned job to return to its original membership; failure records include
remaining process image names and PIDs. No termination assertion was relaxed,
and no speculative console-lifetime change was made. New CI results are still
required before accepting a single executable or enabling tabs by default.

## Rapid shell cancellation and mixed profiles

[Core 43306482281](https://github.com/xiongnemo/nemoterm/actions/runs/43306482281)
reproduced the cleanup failure on the second immediate default-shell close.
The new diagnostics identify the extra processes as PowerShell 7 and its
OpenConsole host. Closing the ConPTY alone was insufficient during that startup
race. Explicit session disposal now retains the original process handle through
ConPTY closure, gives it 100 ms to exit, and terminates it if still running.
This applies only to the owned initial process on explicit disposal; natural
EOF and already-exited launchers retain their previous behavior, and detached
descendants are not killed by a process-tree sweep. Delegated-client lifetime
and all six GDI/OpenGL/DirectX shutdown cases pass locally with this change.
The CI rapid-close test remains mandatory to validate the reproduced case.

`tabs_profiles_window_smoke.py` loads three saved sessions through the native
menu into one host. It checks distinct font sizes and rendering modes, isolated
input, an active profile's custom tab binding, rejected background window
requests, 36 switches with exact retained frames and stable handles, and a
frozen frame across destruction/recreation of the shared GPU renderer. It runs
in both CI variants through the shared tab regression suite. Its local record
uses actual GDI, OpenGL and DirectX; capture instrumentation means that record
is not a memory acceptance measurement.

## Input runtime distinction

Core run 43308880738 passed the four host cases (including all rapid closes),
native settings, four overflow sides, mixed profiles, geometry and resizing.
Its added IME check exposed the known upstream OpenConsole `ReadFile` surrogate
conversion bug: U+1F642 became two U+FFFD characters. The same failure reproduces
locally without tabs when using the pinned NuGet host, so it is not a host-window
input regression. Our source-built OpenConsole overlay already repairs this
byte-input path (`scripts/prepare-single-exe.py`).

Core CI now checks the exact complete Unicode strings through `ReadConsoleW`,
whose UTF-16 units the fixture incrementally decodes. Single-EXE CI continues to
use `ReadFile` and additionally runs the existing small-read Unicode suite.
Neither path accepts replacement characters or omits the emoji assertions.
`tabs-input-runtime-checkpoint.json` records the local three-way comparison and
the two different runtime hashes. The single-EXE verifier also adds real Codex
tab-host cases for both alternate-screen and inline modes; local real-clipboard
access remains unavailable, so these new Codex cases require CI verification.

Single-EXE run 43308880805 also passed all four rapid-close host cases with
the cancellation fix. It stopped later because the mixed-profile fixture read
an empty transient mailbox snapshot and indexed `hex` immediately. That check
now waits for a valid snapshot, retaining the input-isolation assertion. The
same CI binary (`60f32c8bb844ba11e0493a81417cb6b7666e86c7191861fa2fb89d0300b01c1c`)
passes all six mixed-profile checks locally with this correction. This is a
test transport correction, not a change to terminal input handling.

## 0044bd0 CI checkpoint

Core run 43311619116 passed both Windows tests/build and ASan/UBSan, including
the complete native tab regression suite. Single-EXE run 43311619227 stopped
earlier, at the existing hyperlink activation test, before reaching tab or
real-Codex checks. Its binary hash is
`5a0c8a9ef6e88465df06baaf4f78cf028cfd305de113d1da33a81f5e95ada8c8`.

The exact binary passed 48 local consecutive Ctrl-click activations across
mouse modes 1000/1001/1002/1003. The CI failure has not been reproduced locally.
The URI fixture writes its mailbox before Python exits; the activation helper
now waits for the owned handler to exit before starting another click, and
retains phase, capture, tooltip, child input and a screenshot on an activation
failure. No retry clicks or omitted launch/input assertions are used. Another
48 local activations passed using that exact helper, including the absence of
unwanted application mouse reports; see `hyperlink-activation-observed.json`.
This is a fixture synchronization/diagnostics change, not a proven fix for a
terminal defect. Local clipboard tests remain unavailable, and the complete
single-EXE suite still requires a passing CI run.
