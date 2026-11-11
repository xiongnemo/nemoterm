# Nemoterm requirements and evidence ledger

The complete user goal remains active. This is a native terminal project based on the
MIT-licensed PuTTY 0.85 C sources, not a promise that upstream already implements all protocols.

## Acceptance

* Native C/Win32; no WebView/browser runtime.
* Per-window **private working set <20 MB**; total working set approximately 50 MB,
  clarified by user 2026-11-12. Record bytes, decimal MB and MiB; no forced working-set trimming.
  Child shell, ConPTY host and agent must be reported separately, not silently excluded from totals.
* Configurable font, colours, dimensions, history, shell and interaction.
* Default Ctrl+Shift+C/V system clipboard.
* Selection right-click: configurable copy-only (default) or copy-and-paste.
* Shift+left drag always selects renderer grid, even in application mouse/alternate screen modes.
* Complete mouse behaviour (user reiterated): legacy/X10/normal/button/any-event,
  SGR cell and pixel reporting, wheel/horizontal wheel, modifiers, focus, selection,
  release/capture transitions and drag outside the client area.
* Window resize (user reiterated): ConPTY notification, grid and alternate-screen
  integrity, wide/combining characters, history/reflow, rapid resize, maximize,
  DPI/font changes and retained graphics semantics.
* Test with installed SarasaTermSC Nerd Font Light, including Chinese, width and Nerd glyphs.
* Modern terminal semantics referenced against Windows Terminal, Alacritty and xterm;
  all requested escape/OSC families must remain tracked, including Sixel.

## Protocol scope (open until backed by tests)

Inventory official xterm ctlseqs and modern extensions. Record individual supported,
intentionally gated, unsupported and unverified sequences. There is no finite universal
registry of every private terminal extension; do not equate xterm-compatible with all.
Do not drop requirements merely because upstream lacks them.

Pending: CSI/ESC/C0/C1 conformance; SGR styles/true colour; scrolling/margins/alternate
screens; Unicode/graphemes/emoji/IME; keyboard modifier, kitty/CSI-u and Windows input;
mouse/focus/bracketed paste; OSC titles/palettes/links/clipboard/cwd/shell integration;
DCS queries; synchronized output; Sixel rendering/lifetime/scroll/erase; other modern
image protocols; resize and app compatibility with Claude Code/Codex.

## Current evidence

* Empty workspace at start; original local pterm and user settings are separate.
* Upstream tar SHA-256: 13fd4db2936d03b73812a7bcc2a658e4dd29cc776a56c3670a7fc6f1a0ee8af8.
* Source: https://the.earth.li/~sgtatham/putty/0.85/putty-0.85.tar.gz
* All checked-in vendor edits are Nemoterm changes; original archive retained locally.
* See research/ for REA binary identity/import evidence and baseline runtime measurements.

## 2026-11-12 implementation checkpoint

`scripts/test.ps1` passes configuration storage/defaults, terminal semantics,
streaming Sixel decoding and Sixel/core integration tests. Windows x64 executable
builds with GCC. Native screenshot via `tests/capture_window.py` succeeds.
The installed Sarasa font has a wrong-for-grid OS/2 average width (922/1000 em);
GDI reports 15px average vs 8px ASCII advances at 16px. Cell sizing now measures
actual digits; before/after screenshots are retained in research/.

Initial end-to-end Sixel **failed through this machine's Windows 10 19044 ConPTY**:
`research/nemoterm-sixel-conpty.png` shows DCS payload printed as characters.
This is not evidence of functioning graphics despite passing decoder/core tests.
Resolved for the colour-block fixture by the official pinned Microsoft ConPTY
1.25.260930003 package. `research/nemoterm-modern-conpty.png` proves the same DCS
fixture displays graphics through the bundled host. `nemoterm-modern-memory.json`
records private WS 2,961,408 bytes and total WS up to 13,565,952 bytes, with host
and Python child listed separately. Still not a stress or real-agent acceptance.

Image-core remaining defects: partial scrolling across image edges is not split;
top partial-scroll/history interaction was repaired with a regression; resize/font change currently
clears images; scaled pixels crossing erased cell edges need exact clipping;
palette changes do not recolour existing pixels. Other image protocols remain open.

Latest 80x24 text fixture measurement: private WS 4,218,880 bytes, total WS
20,123,648 bytes; this is **not** an image or agent workload acceptance result.
No user pterm process was modified or closed.

Resize suite now passes with Chinese/combining text, main/alternate screen isolation,
history restoration and clipboard retention after selection cancellation. Actual
window resize produced child-observed 80x24 -> 133x35 -> 64x17 sizes, recorded in
`research/resize-observed.json`. Alternate-screen contents/cursor now survive resize.
Text reflow and image preservation on resize remain open.


Mouse checkpoint: exact-byte tests now cover X10/1000/1002/1003, UTF-8/SGR/
urxvt/pixel encoding selection, Alt/Control, four wheel directions, focus,
alternate scrolling, Shift takeover, multiple held buttons and capture cancellation.
Win32 handlers now retain pixel coordinates, separate wheel-axis accumulators,
honor Windows local scroll-line settings, and release application buttons on
capture/focus loss. Blank double-width rows are normalized on reset.
`tests/mouse_window_smoke.py` launches only its own window and injects window
messages (not global physical input), checking bytes read by the real ConPTY child.
Results: `research/mouse-window-observed.json`; resize observed 80x24 -> 108x27 -> 58x12.
1001 highlight tracking, side buttons, real hardware/trackpad and multi-DPI acceptance
remain open. Ctrl+right-click remains the documented local-menu override.
