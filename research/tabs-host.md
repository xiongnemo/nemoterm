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
  native overflow navigation and physical multi-monitor DPI/IME testing still
  need coverage. Mixed renderer profiles, long-running agent workloads, tabbed
  clipboard/selection stress, and all existing native suites in tab mode remain
  before making the host the default or promoting a new accepted binary.
- No new dependency, webview, helper executable or per-tab GPU device was added.
