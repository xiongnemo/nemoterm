# Nemoterm requirements and evidence ledger

## Current source and accepted executable (2026-11-14 Sydney)

Main source is `8a41ad7`; the accepted local single EXE remains source `8ff214f`,
SHA-256 `c110843b1fd5a551d654df094fa716c1ea1c48383d90e642b964d7dfb3d15e26`,
4,452,864 bytes. The intervening changes update observation fixtures and records,
not product sources. See [the accepted artifact](../research/sgr-ideogram-ci.md).

The opt-in [automation interface](AUTOMATION.md) is implemented on main and in
that accepted EXE: local discovery, stable session IDs, directed text/paste/key
input and text/renderer snapshots. Tests now use it for several GPU observations.
It does not provide an output subscription or enable itself in existing windows.

Both full branch workflows passed at `8a41ad7`. Its subsequent main run passes
[single-file CI](https://github.com/xiongnemo/nemoterm/actions/runs/43581417881),
but [core CI](https://github.com/xiongnemo/nemoterm/actions/runs/43581417880)
fails the fifth MSVC tab-lifetime repetition: the sibling window disappears and
cleanup records frontend exit 0xC0000005. The exact MSVC image was not retained
by that workflow. Passing earlier runs do not resolve this failure.

Static inline PNG/JPEG/BMP/GIF and animated GIF development remains off main.
Complete experimental CI can pass while exact-artifact local memory acceptance
fails: the `a3eb24e` image reaches 25,202,688 private-working-set bytes in DirectX.
No experimental image replaces the accepted local binary. GDI's strict
20,000,000-byte and DX's inclusive 25,000,000-byte gates remain unchanged.
DX total working set still exceeds the approximate 50 MB target in recorded runs.

Full protocol coverage, sustained real-agent memory, physical IME and
multi-monitor acceptance remain open. Local runtime tests are authorized again;
older pause statements below describe their historical checkpoints only.

## Earlier integration checkpoint (2026-11-14 Sydney)

Main includes bounded Direct3D 11 composition, I/O worker cleanup, initial
visibility preservation, input-pipe-close/output-drain handling and Sixel
register identity/shared palette lifetime. Source `e436ecd` passes both complete
CI workflows, including 105 single-file checks. Its exact downloaded EXE is the
local distribution and passes all 16 palette phases for actual local GDI,
OpenGL and DirectX. CI's OpenGL palette request falls back to GDI; only the
separate actual local OpenGL run establishes that backend's coverage.

Fresh actual 160x48 Sarasa workloads pass nine groups per mode. GDI peaks at
16,568,320 private-working-set bytes and DX at 22,818,816. Total working set is
respectively 43,401,216 and 58,470,400 bytes; DX remains above the approximate
50 MB total target. Both jobs close all 56 inner / 58 outer processes naturally.
See [the exact-image checkpoint](../research/sixel-palette-ci.md).

The predecessor `9c22311` downloaded image also passed 16 local startup/visibility
groups and ten DX automation groups with zero screenshot channel differences;
those exact bytes remain identified in [their checkpoint](../research/d3d11-ci.md).
Earlier failed CI runs remain failed. The separate
[delay-load experiment](../research/delay-load.md) is not adopted and preserves
unresolved late-initialization and USER-object resource failures. Successful
downloaded-image runs do not prove those intermittent observations resolved.

The original complete-protocol, real application, physical input and long-session
requirements remain open. This checkpoint does not replace those requirements
with its narrower test scope. The sections below retain earlier checkpoints at
their named source versions.

## Rendition discovery and current artifact (2026-11-14 Sydney)

Eight parameter-free rendition sequences and four termcap aliases now have
XTGETTCAP replies. Both complete workflows pass at `4ed7e08`, including all
93 single-image groups and actual replay of the returned values through ConPTY.
The exact downloaded EXE passes that query fixture locally. Its uninstrumented
Sarasa 160x48 two-tab workload passes GDI at 15,626,240 private-working-set bytes
but fails DirectX at 29,569,024 against 25,000,000; all nine functional groups
and natural cleanup complete in both modes. No renderer optimization is claimed
from differences between runs. See the [artifact and raw evidence](../research/rendition-capabilities.md).
The accepted local distribution and remaining full-goal requirements are unchanged.

## Initial graphics allocations (2026-11-14 Sydney)

A first-switch diagnostic now captures graphics initialization previously
missed by the later heap observer. Both owned captures are valid and detach
cleanly, but remain instrumented diagnostics with explicit non-success exit 2.
A separate minimal Direct3D 9Ex feasibility probe uses about 1.01 MB less private
WS than its Direct2D arm in one observation; neither probe implements the full
terminal renderer or proves the 25 MB target. No product change is retained.
See [sources, raw samples and limitations](../research/graphics-initialization.md).

## Overline CI and downloaded-image checkpoint (2026-11-14 Sydney)

SGR 53/55, reset/query/stack and history/reflow coverage pass both complete
workflows at `9370c1f`, including 93 single-image groups. The downloaded EXE
also passes local Sarasa GDI/OpenGL/DirectX scenes and all 193 XTerm plus 29
direct rendition-stack cases. Its uninstrumented actual 160x48 two-tab workload
passes GDI at 16,445,440 private-working-set bytes and fails DirectX at
30,433,280 against 25,000,000. All nine functional groups and natural cleanup
complete in both modes. CI's smaller Consolas grids are recorded separately.
The [artifact and evidence](../research/overline.md) do not establish full
protocol coverage, physical input acceptance or a DirectX memory fix; the
accepted local distribution is unchanged.

## Local DirectX allocation follow-up (2026-11-14 Sydney)

An explicit owned-process all-heap diagnostic now complements the earlier
reservation census. It is instrumented, exits 2 on successful collection and
cannot count as memory acceptance. Local GDI/DirectX captures complete with
natural cleanup; 27 native collector checks and five page-accounting tests pass.
Two renderer experiments still exceed 25 MB (30.60 MB bounded readback,
30.37 MB frame reuse) and are reverted. Product source and the accepted local
distribution remain unchanged. See the [records and limits](../research/local-directx-heap.md).

## Automation and input-transfer checkpoint (2026-11-14 Sydney)

Local runtime tests resumed with user authorization. Opt-in named-pipe discovery,
explicit session targeting, text/key input and text/pixel snapshots are implemented.
The `2cdde9c` full core workflow and all 90 single-image groups pass. File/folder
path drops and image-only clipboard delegation are implemented at `fa35542`;
owned local GDI/DirectX checks and four real Codex/OpenCode image cases pass.
The first remote file-drop failure exposed a UTF-8 reverse-map bug, fixed at
`4ab6939`; `abafbbf` also releases conversion scratch buffers. Local regression
passes again, and both complete `abafbbf` workflows pass, including 93 single-image
groups. The downloaded CI image also passes the nine local automation groups.
A separate local Sarasa
160x48 two-tab workload passes GDI (15.44 MB private WS) but fails DirectX
(29.70 MB before the conversion fixes, 30.55 MB in the follow-up, against 25 MB),
so local DX memory acceptance remains open. The
[checkpoint and retained evidence](../research/automation-input.md) distinguish
these source/image identities and failures. No physical Explorer gesture,
custom WSL mount, long-lived agent memory or full protocol acceptance is implied.

Both complete workflows also pass at integration `34e60c1`, superseding the
older pending compiler-comparison status below. Historical pause statements
and failures remain attached to their original checkpoints.

## Current development checkpoint (2026-11-14 Sydney)

User-approved memory acceptance is now strict **20,000,000 private-working-set
bytes for GDI** and inclusive **25,000,000 for DirectX**, with the existing optional
OpenGL exception. Private commitment and roughly 50 MB total WS remain separate
measurements. Earlier failures keep their original thresholds and results.

Development source `ea042bc` passes all 85 single-image groups, including
attribute-colour reset/settings, cursor character sets, ISO guarded areas,
real Codex default/inline and tab variants, and uninjected two-tab workloads.
Its frontend peaks are 11,206,656 private / 40,538,112 total bytes for GDI and
21,819,392 private / 60,420,096 total bytes for DirectX. Both private-WS gates
pass; DirectX total WS remains above the approximate target. The
[exact artifact and retained results](../research/attribute-reset-validation.json)
also identify natural process cleanup. This is a development snapshot, not a
replacement of the accepted local executable or proof of all-load memory bounds.

The separate MinGW workflow still fails guarded-area cursor-reply ordering with
the upstream sidecar host. The [following colour-reset patch](../research/reset-palette.md)
has passed core sanitizer, MSVC renderer jobs and all 25 new native colour
replies plus 23 pixel checkpoints under actual GDI/DirectX. Requested OpenGL
falls back to GDI. Its complete single-image run at `d2aa14a` now passes 88
groups, with 11,145,216 GDI / 21,622,784 DirectX frontend private-WS peaks.
The compiler comparison is being rerun with the same source-built host fixes.
Independent XTerm
captures now verify the recorded identity, guard,
selection and cursor-charset families, while two attribute-colour divergences
remain explicit. Full protocol coverage, physical IME/multi-monitor behaviour,
the final local Sarasa workload and long-lived real-agent acceptance remain open.
Local runtime testing is still paused. Older dated sections below are historical
checkpoints, superseded only within the verification scopes stated here.

## Public CI recovery (2026-11-13; local runtime testing still paused)

[Recovery evidence](../research/ci-public-recovery.md) supersedes the earlier
compile-only status for the recorded Linux core suites: the complete ASan/UBSan
job at `ed78f2b` passes, including selection/attribute colours, cursor charsets
and ISO guarded areas. Generated-data portability and colour-painting fixture
errors were corrected without relaxing assertions. The mocked OpenGL cleanup
test also passes in MSVC CI at `ed78f2b`; eight tab-close repetitions use actual
GDI. Windows MinGW core checks pass at the same commit; that job later times out
in native shutdown. The diagnostic repeat at `41a6cc5` passes all six shutdown
cases but exposes a real duplicate Alt+A in the attribute settings page. The
selector and custom-URI option now avoid the global About/Apply accelerator;
the native MinGW settings fixture passes at `82f4d59`, including save/load and
live application. Its subsequent workload exposed a sampler classification bug
for the sidecar OpenConsole processes. That classifier is corrected for remote
revalidation without changing ownership checks or the memory threshold.
Main `992faa3` has a successful 57-group single-image artifact, while its
separate MinGW profile-close timeout remains unresolved. Development single-image
colour/charset/guarded-area checks pass at `ed78f2b`; its two-tab workload passes
with GDI (11,227,136 private bytes) but fails with actual DirectX (23,994,368).
The development single-image workflow therefore fails before its later settings
and Codex tests. Hardware memory gates and full-goal acceptance remain open.

## OpenGL context cleanup (2026-11-13; local runtime testing paused)

[Context-failure cleanup](../research/opengl-context-lifetime.md) releases CPU
cache keys even when WGL cannot bind, avoids GL deletion/readback without a
current context, and reports failed tab attachment. A mocked lifecycle target
is prepared for MSVC/MinGW CI. Local compilation and single-image linking pass;
the new checks have not been run locally. This is not an explanation or closure
of the historical GDI tab-close crash, nor a new memory acceptance result.

## ISO guarded areas (2026-11-13; runtime testing paused)

[SPA/EPA and protection-family handling](../research/guarded-areas.md) now
cover ordinary/DEC erasure, queries, reset and presentation restoration in
source, using the existing per-cell protection bit. Sixty-three authored wire
cases and core/native fixtures are prepared. Windows/Linux compilation and
single-image linking pass; runtime behaviour and memory acceptance remain
unverified. The accepted main executable is unchanged.

## Saved cursor character sets (2026-11-13; runtime testing paused)

[Cursor charset restoration](../research/cursor-charset-save.md) now retains
all four supported designations and the GL/GR selectors in each screen's saved
cache. Current local charset restrictions are respected on restore. Forty-four
authored wire cases plus core/native checks are prepared; Windows/Linux builds
and single-EXE linking pass. None of the new runtime checks has executed, and
the accepted main executable remains unchanged.

## Saved attribute colours (2026-11-13; runtime testing paused)

[The native attribute-colour settings page](../research/attribute-colour-settings.md)
adds independent saved colours/modes/style choices and live component-wise
updates. Previous Conf IDs are unchanged. Configuration/mock/native fixtures
are prepared; Windows/Linux compilation and single-EXE linking pass. UI,
runtime compatibility and memory acceptance are still pending.

## Attribute-colour development (2026-11-13; runtime testing paused)

[OSC 5/6/105/106 and indexed aliases](../research/attribute-colours.md) now have
source implementations for five special colours, enable/override modes, display
overlays and palette retention. Authored wire/mock/native checks are prepared.
Only compilation/linking and static checks have run; compatibility, renderer
pixels and the unchanged memory gates remain unverified for this candidate.

## X11 named colours (2026-11-13; runtime testing paused)

[The pinned 782-name Xorg table](../research/x11-colours.md) replaces the shared
OSC parser's eight-name whitelist. It uses read-only data and no per-terminal
allocation or new runtime library. Source-derived parser/protocol checks and an
independent XTerm collector are prepared. Windows/Linux builds and single-EXE
linking pass; runtime behaviour and memory acceptance remain unverified.

## Saved selection colours (2026-11-13; runtime testing paused)

[Selection colour preferences](../research/selection-settings.md) add a native
settings panel, independent foreground/background defaults, existing-session
storage and live changes. Core/configuration, ordinary/tabbed settings and
configured-default GDI checks are prepared. Windows and Linux test targets
compile and the single EXE links, but none of the new runtime checks have run.
The accepted main executable and all memory gates remain unchanged.

## Selection-colour development (2026-11-13; runtime testing paused)

[OSC 17/19 and 117/119](../research/selection-colours.md) now have source
implementations, authored protocol cases and mock/native rendering fixtures.
MSVC frontend/core-test builds, single-image linking and a Linux sanitizer
test build pass; the new executables and fixtures have not run. Independent
XTerm capture, pixel behaviour, full regression and memory acceptance remain
pending. The prior palette-stack results below apply only to their recorded
image, not to this newer unverified build.

## Palette/title-stack checkpoint (2026-11-13)

[Palette stacks and title positions](../research/palette-stacks.md) add four
xterm controls and correct title overflow/indexed interleaving without growing
the ten-slot storage. 101 exact XTerm cases pass in core and native GDI,
DirectX and OpenGL; all three renderers also pass palette invalidation,
synchronized-frame and resize checks. The new candidate passes 35 MSVC,
six MinGW and five ASan/UBSan suites, plus the existing title tests. Its longer
uninstrumented GDI workload peaks at 14,815,232 private WS bytes and 36,917,248
total WS bytes, with child processes separately recorded. This does not fix
the DirectX memory failure, promote the main executable or close the full goal.

## Latest memory checkpoint (2026-11-13)

The [two-tab workload record](../research/tab-workload-memory.md) adds continuous
frontend/host/client sampling during history, links, dense text, images and
resize. GDI passes that bounded workload at 14,778,368 private working-set bytes;
actual DirectX fails at 29,532,160 bytes. Both complete the tab functional checks
and natural owned-job cleanup. No product optimization is claimed: two attempted
DirectX changes were reverted after failing the same threshold. CI now retains
this longer workload gate. Sustained hover memory, real-agent/clipboard and
full-goal acceptance remain open.

The complete user goal remains active. This is a native terminal project based on the
MIT-licensed PuTTY 0.85 C sources, not a promise that upstream already implements all protocols.

## Acceptance

* Native C/Win32; no WebView/browser runtime.
* One final executable file. Reuse pinned open-source OpenConsole/ConPTY sources;
  a second process of the same image is allowed by the implementation design,
  with its memory reported separately. Do not call a sidecar bundle a single EXE.
* Startup shell choice and persisted default: detect pwsh, Windows PowerShell,
  BusyBox ash, Git Bash and WSL Bash with installed distributions, retaining cmd
  as a fallback. Implemented: all six local shells passed real interactive launch
  and exit, with native settings save/reload; see `research/shell-selection.md`.
* Per-window frontend private working set: **GDI <20 MB**, **DirectX <=25 MB**.
  The user approved the DirectX allowance on 2026-11-14, with further optimization deferred.
  Optional OpenGL retains its explicit exception. Total working set remains approximately 50 MB.
  Record bytes, decimal MB and MiB; no forced working-set trimming.
  Apply limits to the actual renderer, so fallback to GDI does not inherit the DirectX allowance.
  Historical evidence keeps its original limits; a new evaluation must identify the new policy.
  Child shell, ConPTY host and agent must be reported separately, not silently excluded from totals.
* Configurable font, colours, dimensions, history, shell and interaction.
* Default 160x48 character grid, reduced to the monitor work area when it does
  not fit. The user selected this rule explicitly.
* Ctrl+left drag rectangular selection, with configurable action bindings and
  rectangle modifiers. Shift continues to override application mouse tracking.
* Switchable GDI/OpenGL rendering. GDI retains the memory limits above; the
  user explicitly allows optional OpenGL mode to exceed them.
* Investigate a DirectX renderer without extra distributed dependencies.
* Native tabs with the strip on top, bottom, left or right, and a terminal
  preview on hover. Implemented with owned-window tests; see
  `research/tabs-host.md` and `research/rtl-font-fallback.md` for the measured
  workload scope and remaining lifetime/memory acceptance.
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

The first source-and-test audit is in [PROTOCOL_COVERAGE.md](PROTOCOL_COVERAGE.md).
It distinguishes tested subsets, configuration gates, missing handlers and
unverified behavior. [Tabulation](../research/tabulation.md) now has 108 exact
independent xterm comparisons through both the core and native ConPTY path.
The three double-size text-wrapping failures are fixed; see
[double-size lines](../research/double-size-lines.md) for 45 further reference
comparisons, cell checks, grapheme boundaries and remaining scope.
Sixel capability queries now report the actual register and dimension limits,
with configurable 2–256 color registers and native resize/pixel verification;
see [graphics queries](../research/graphics-query.md). This does not imply
ReGIS support or remove the shared image memory budget.
[DEC status reports](../research/dec-status.md) add extended cursor/device
queries and fix a native ConPTY race that consumed an application's cursor
reply. The source-built same-image host now tags its own synchronization
requests separately; full clipboard/real-agent CI acceptance remains pending.

Pending: CSI/ESC/C0/C1 conformance; SGR styles/true colour; scrolling/margins/alternate
screens; Unicode/graphemes/emoji/IME; keyboard modifier, kitty/CSI-u and Windows input;
mouse/focus/bracketed paste; OSC titles/palettes/links/clipboard/cwd/shell integration;
DCS queries; synchronized output; Sixel rendering/lifetime/scroll/erase; other modern
image protocols; resize and app compatibility with Claude Code/Codex.

## Current evidence

The development branches now include whole-cluster widths and shaping, missing
RTL glyph fallback, bounded bidi/layout caches, and a persisted startup width
preference. These are not yet part of a newly accepted single-image artifact.
See `research/graphemes.md`, `research/rtl-font-fallback.md`, and
`research/grapheme-settings.md` for exact source/artifact identities, native
results and outstanding acceptance. A newer local MSVC single image now covers
those changes, and selected Windows PowerShell launches also correct inherited
PowerShell 7 module paths. See `research/local-msvc-single-exe.md` for the two
exact artifact identities, compiler/native checks and remaining CI requirements.
New GitHub jobs are currently prevented
from starting by account billing/spending limits. Historical checkpoints below
describe their own commits, not a current declaration that all listed work is
finished or still missing.

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
1001 highlight tracking, real hardware/trackpad and multi-DPI acceptance
remain open. Ctrl+right-click remains the documented local-menu override.


OSC colour checkpoint: allocation-free Xlib rgb:/# parsing, eight explicit names,
OSC4 multi-set/query and104 selective/all reset, OSC10/11/12 sequential set/query,
and110/111/112 restore. Queries preserve BEL vs ST. Overlong colour payloads are
rejected as a whole with a fixed2048-byte buffer. Pure parser precision tests and
fragmented terminal-state tests pass; real ConPTY OSC4/10 round trips also pass.
Full X11 names and Xcms rgbi remain unsupported; no new full-surface framebuffer.


2026/DECRQM checkpoint: implemented synchronized presentation with lossless
32-row XPRESS_HUFF snapshots, an 8MiB module allocation limit, fixed one-second
recovery, and lifecycle cleanup. No full-window raw framebuffer is retained.
Snapshot errors are logged and the batch remains unfrozen (mode2); unsupported
frontends report mode0. Windows Compression API is a system dependency (cabinet).
All11 local suites pass; native tests cover frozen text/Sixel/background pixels,
queries, input, timeout and resize. `research/sync-window-observed.json` records
actual viewport size and private/total WS samples without trimming. Full4K is
verified in the separate offscreen module test, not this monitor-limited window.

Real Claude Code2.1.322 startup/idle check: `--bare --tools "" --permission-mode plan
--setting-sources ""`, isolated temporary directory; Sarasa100x30. Native captures
`claude-interactive.png` and `claude-resized.png` show the interactive UI and
unsubmitted Chinese/combining-text input after resize. Private WS4,333,568 bytes,
total20,484,096 bytes across5 samples; record `claude-interactive-memory.json`.
`claude-child-memory.json` lists the separate Claude process; ConPTY and fixture
Python are also separate. No inference was submitted. This is startup/idle/input
and resize evidence, not full-agent streaming/long-history or all-feature acceptance.

Side-button and resize checkpoint: XBUTTON1/2 map to xterm buttons 8/9, with
exact-byte tests for all encodings, modifiers, drag/release, cancellation and
Shift isolation. The native test reproduces and fixes a multiple-button defect:
SetCapture on a window that already owns capture sends WM_CAPTURECHANGED with
the same owner; this must not synthesize releases. Left-button release now
retains capture while a side button remains held. The own-window ConPTY test
also verifies 25 consecutive resizes and maximize/restore size notifications.
No global pointer input is injected; physical mouse and multi-DPI checks remain open.

CI checkpoint: commit 681317f passed all 11 Windows suites, both native window
tests, and Linux Sixel/colour ASan+UBSan. Downloaded portable EXE and bundled
ConPTY files matched their SHA-256 records. CI's sync fixture used an actual
1011x749 viewport, peak private WS 3,067,904 bytes, total WS 20,381,696 bytes;
these are hosted-runner fixture measurements, not full-agent acceptance.

SGR checkpoint: colon and semicolon RGB/indexed colours, italic3/23,
conceal8/28, underline4:0..5 and21, independent underline colour58/59.
Decorations add four bytes per live cell and are RLE encoded in compressed
history only when present. GDI draws directly into the existing target DC;
italic font variants are created lazily. No new persistent surface buffer.
CSI is bounded to32 main arguments and8 subarguments per group; overflow
rejects the complete sequence. Invalid colon groups cannot become separate
SGRs. CAN/SUB now cancel unfinished control sequences without consuming the
following character. Model, compressed history, alternate screen, resizing,
erase defaults and plain-text copying pass `test_sgr`; extended RTF export,
other SGR families and full conformance remain open.

`tests/sgr_window_smoke.py` verifies five distinct underline pixel patterns,
21 double underline,4:0 reset, reverse/explicit underline colour independence,
palette updates, conceal hiding glyphs/decorations, italic/reset, equivalent
RGB syntax, and styled pixels in synchronized snapshots through real ConPTY.
Screenshot: `research/sgr-styles.png`; measurements and hashes:
`research/sgr-window-observed.json`. Local sampled peak private WS4,505,600
bytes; total20,652,032 bytes. This is a style fixture, not complete agent acceptance.

Style fonts now retain the normal font's GDI average width separately from
the measured terminal grid advance. Passing Sarasa's 8px grid width as the
CreateFont average compressed italic CJK ink from14px to9px. The native
pixel regression reproduces that failure; the fix restores normal/italic
widths to14/14px for Chinese and8/8px for Latin M on this machine. Bold and
wide/narrow font variants use the same corrected average-width basis.
See the [CreateFont parameter definition](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-createfontw).
Font-resizing windows now translate their requested cell advance using a
measurement of the natural font at the requested height, avoiding the same
average-width mistake for normal text. `font_resize_window_smoke.py` uses an
isolated temporary profile and checks horizontal/vertical/both-axis enlargement
and restoration while keeping40x12 cells. On this machine Chinese normal/italic
ink grows from14/14px to27/27px with a twofold horizontal stretch, and returns
to14/14px. GDI resources stay at23; sampled private WS peaks at4,149,248 bytes.
The JSON and before/wide screenshots are in `research/font-resize-*` and CI.
The fixture probes the selected font and its native CJK coverage. Latin M is
always tested; Chinese is additionally tested when the font contains that
glyph (as the installed Sarasa does). Each style is compared with its own
baseline, allowing GDI hinting/overhang variation during scaling and requiring
exact restoration. Local Courier New also passes the Latin checks. Its missing
Chinese glyph uses independent system fallback, whose non-linear scaling is
not covered by this native-glyph check; font fallback remains an open item.
Physical dragging and multi-monitor DPI conformance remain open.

Cursor/query checkpoint: DECSCUSR0..7 selects blinking/steady block, underline
or bar, or restores the configured default; DEC12 toggles blinking independently
of cursor visibility. The Windows renderer uses the core's current style.
Unrelated configuration changes preserve application style; explicit cursor
configuration changes and RIS restore defaults. Local reset also cancels an
unfinished parser sequence rather than consuming subsequent text as its tail.

DECRQSS supports `m`, `r`, `SP q`, `$|` and `*|` for existing SGR state, scroll
margins, cursor style and current columns/rows. SGR readback can be replayed,
including true colour, indexed colours and independent underline style/colour.
Other requests return `DCS 0 $ r ST` with no reflected payload. DECRQSS queries are limited to
63 bytes in the shared DCS query buffer; overlong input is rejected until termination. Sixel remains
streamed. `test_queries` covers byte fragmentation, cancellation, bounds,
readback round trips, configuration/reset and Sixel coexistence. This does not
complete the remaining DECRQSS strings or DECSTR; XTGETTCAP is covered below.

The fifth native suite, `query_window_smoke.py`, verifies actual block8x20,
underline8x1 and bar1x20 pixels on the local Sarasa setup, visible/hidden blink
phases, steady output after disabling blink, resized dimensions and queries
during a frozen presentation. It records when foreground/system settings
prevent a blink pixel check. Local peak sampled private WS3,485,696 bytes,
total19,312,640 bytes; see `research/query-window-observed.json` and the cursor
PNGs. These fixture measurements do not establish complete agent acceptance.
Protocol reference: [xterm ctlseqs](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.txt).


XTGETTCAP checkpoint: DCS + q now accepts bounded hexadecimal capability
names, with one response for multiple names. TN/name shares the actual child
TERM constant; Co/colors and RGB reflect configured colour support. Logical
key capabilities use the same encoders as Win32 input, including function
keys1..63 and termcap aliases, navigation, extended modifiers, keypad and
backspace. Unknown names terminate the list; known unavailable keys are
returned without a value. Arbitrary terminfo programs (e.g. cup) are not part
of xterm's XTGETTCAP special-key query. Requests are bounded to2047 bytes,
responses below14KiB; DECRQSS retains its63-byte limit. Sixel stays streamed.

Defaults now select modern xterm function keys and modifier bitmaps. Home/End
follow normal/application cursor modes; modified cursor keys keep modifiers
in application mode. Ctrl edit/Page keys reach applications in modern mode;
Shift Page keys and copy/paste shortcuts remain local. Saved legacy profiles
remain selectable and no longer have their arrow setting overwritten at load.
Win32 now routes F21..F24, Help/Select and keypad Separator through the encoders.
The14th core suite checks exact bytes, all63 function names/aliases, modifier
combinations, mode/configuration changes, bounded parsing and Sixel coexistence.
The native query suite checks15 key messages against queried values in both
cursor modes through the bundled ConPTY. Local sampled peak private WS3,395,584
bytes, total19,238,912 bytes. These are fixture measurements, not complete agent
acceptance. XTGETTCAP describes logical encoders; local shortcuts, OS bindings,
IME/layout translation and physical-device validation remain separate. Numeric
keypad modifier semantics and remaining special-key names still need completion.
Primary references: [xterm control sequences](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.txt),
[xterm capability mapping](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/xtermcap.c).

The first XTGETTCAP CI run found a test mailbox race: a fresh read after a
successful wait could encounter a Windows sharing violation and return an
empty snapshot. The query fixture now uses the exact snapshot that satisfied
each condition for both assertions and evidence. A local fault-injection run
returned an empty snapshot on every third read (40 injected misses); all
native cursor, geometry, capability and keyboard checks still passed. No
terminal assertions were removed or relaxed.


1001 highlight checkpoint: a left press reports normally, then accepts the
application's five-parameter CSI T handshake. First/last rows constrain the
endpoint, with lastrow exclusive; character selection uses half-open viewport
boundaries. Forward unchanged boundaries use the short t reply; reversed or
expanded word/line selection uses the six-coordinate T reply. Legacy,1005,
1006,1015 and1016 completion formats are tested. As in xterm's implementation,
1016 press reports pixels but highlight completion describes character cells.
Unencodable legacy/UTF8 coordinates are rejected rather than truncated.

The highlight is separate from local clipboard selection: fixed terminal
state and existing text rendering, no per-cell or image allocation. Rendered
wide glyphs and double-width lines are snapped to whole glyph boundaries.
Double/triple clicks expand to words/lines; word selection follows wrapped
rows. Shift cancels the application gesture and starts local selection;
explicit copying still uses the existing Ctrl+Shift+C path. Active highlighting
does not suppress terminal output. Local motion/cancellation releases a 2026
presentation freeze so the displayed selection follows the mouse.

The handshake has a one-second recovery deadline; this is Nemoterm policy,
not a claim that the xterm specification requires that timeout. Late replies
are ignored after timeout/release. Host abort retains the eventual physical
release. Capture/focus loss, resize, cell-size changes, history scrolling,
alternate screen and configuration/encoding changes finish and clear the
highlight; mode replacement and RIS discard it. Old timer callbacks cannot
expire a newer handshake or an active selection. Other buttons retain normal
press/release behavior. The UI and parser never wait synchronously for a host.

`test_highlight` is the15th core suite; timer helpers are shared with
`test_sync`. The sixth native suite `highlight_window_smoke.py` verifies a
cooperating ConPTY child, exact6-cell-by1-row changed pixel bounds, forward/
reverse and multi-click replies, pixel restoration on release/capture cancel,
Shift takeover, F1 input during the handshake wait, timeout and resize. The
local Sarasa capture is `research/highlight-selection.png`; measured values
and executable hash are in `research/highlight-window-observed.json`. This
fixture is not full mouse-device, bidi, multi-DPI or long-running-agent
acceptance; those broader checks remain on the protocol ledger.
Primary references: [xterm highlight tracking](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.txt)
and [xterm TrackMouse/EndExtend](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/button.c).

Latest local highlight fixture peak private WS 3,448,832 bytes, total
WS 19,263,488 bytes, with no working-set trimming.

The first1001 CI run passed all15 core suites and the mouse/sync/SGR native
checks, then exposed the same mailbox race in the older font-resize fixture.
A shared wait_snapshot helper now reads once per poll and returns the exact
validated snapshot. Font, mouse, sync and SGR callers no longer reopen the
mailbox to fetch fields after checking a condition. Fault injection returned
an empty read every third poll:50 font,22 mouse,22 sync and47 SGR misses; all
four full native suites passed without relaxing their existing assertions.

Sixel images now retain one destination row per original cell-height strip.
Partial scrolling moves or discards only intersecting strips; it does not
duplicate decoder tiles or grow a fragment list. The row map and erase mask
are included in the existing shared 4 MiB budget. Grid resize follows actual
main-screen row moves into/out of temporary history, deletes alternate-screen
bottom rows, and preserves horizontally clipped pixels until erased. Clearing
history preserves the visible portion of an image that crosses row zero.
Raster reads expand aspect ratios into one bounded scanline before applying
cell erasure, including source pixels straddling a cell boundary.

`test_sixel_terminal` checks 100 shrink/restore cycles, 100 partial-scroll
round trips, bitmap identity and unchanged allocation, moved-cell erasure,
history truncation, independent screens and 3:2 aspect expansion. The seventh
native suite, `sixel_window_smoke.py`, compares exact red-pixel sets through
ConPTY across 44 checkpoints, including 12 repeated shrink/grow cycles. It
also exposed stale pixels in a new window border after shrinking; border
repainting now happens even when its width remains unchanged.
Local executable SHA-256 is recorded in `research/sixel-window-observed.json`:
peak private WS 1,961,984 bytes, total WS 12,345,344 bytes, private commit
2,576,384 bytes, without trimming. The preceding build's same fixture peaked
at 3,375,104 / 19,247,104 bytes private / total WS; neither sample is a
universal application limit. Captures are
`research/sixel-partial-scroll.png` and `research/sixel-resize-retained.png`.
This is finite fixture evidence, not long-running agent acceptance. At that
checkpoint font/DPI cell-size changes still cleared images; the following
change supersedes that limitation. Palette recolouring and remaining graphics
protocols remain open in `PROTOCOLS.md`.

Font-size changes now retain the original Sixel raster and its pixel erasures.
Each output scanline records its character-row anchor; its original pixel
offset stays fixed. This follows xterm's unfragmented-image geometry: the
origin follows the font grid, while raster dimensions do not scale with the
font ([graphics.c, refresh_graphic](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/graphics.c)).
For partial scrolling, each affected scanline carries an independent
character-unit translation. Font changes can therefore make fragments overlap,
as independently anchored fixed-size images can; restoring the font without
further edits restores the same pixels. No resampling or cumulative rounding
occurs. This fragmentation policy is local behavior, not an assertion that
xterm's partial-scroll implementation is identical.

Erasure uses the current font grid and records exact raster-pixel bits, including
cells cutting through old cell boundaries. Masks are allocated in 32-row bands,
not one tiny heap block per row. Bands with no remaining erased live pixels are
freed. Decoder storage, scanline metadata, band pointers and masks share the
4 MiB budget. Admission evicts oldest images before traversing the list to
allocate masks, avoiding iterator invalidation; fully erased rows allocate no
mask. Font changes allocate no new image storage and cancel only an incomplete
incoming image. The platform's existing DPI path uses the same cell-size API;
real multi-monitor DPI transitions remain unverified.

Core tests cover 200 font round trips, exact old/new pixel holes, non-aligned
scroll margins, history trimming after font changes, in-flight cancellation,
band reclamation and near-budget eviction with 1,600 image submissions, plus
2,000 deterministic mixed operations checking allocations, mask contents and
live-row counts. A headless Unix target runs the same terminal integration
suite under ASan/UBSan; it also passed locally in WSL Debian with leak detection.
The eighth native suite, `sixel_font_window_smoke.py`, compares exact pixel sets
at 37 checkpoints. A green steady cursor measures actual font cells and padding;
the red raster is checked independently. It covers width-only, height-only and
combined font changes, erasure before/after scaling, eight split-image font
round trips, history and distinct main/alternate images. A final burst of 800
images exercises the shared budget through actual Win32/ConPTY allocations,
followed by mask allocation, font resize and release. Local Sarasa cells were
8x20, 16x20, 8x40, 12x30 and 16x40 pixels; GDI objects rose from 22 to 23 during
the burst and returned to 22. Latest local fixture peak private WS was
8,089,600 bytes, total WS 24,031,232 bytes and private commit 9,351,168 bytes
without trimming. The exact executable hash is in
`research/sixel-font-observed.json`; screenshots are `research/sixel-font-*.png`.

OSC 8 core checkpoint: character cells now carry an opaque 32-bit hyperlink
handle, independently of SGR. The same handle survives wide/combining glyphs,
insert/delete operations, cursor save/restore, 1049 screen switching, compressed
history, clipping/restoration and font-size changes. Erasure and replacement
clear links; a split wide glyph cannot leave an invisible clickable space.
The existing optional-colour RLE flags also encode nonzero link handles, so
unlinked history uses the same compressed representation as before.

A lazily allocated registry accounts for at most 256 KiB and 1024 entries,
including its fixed pointer ring. URI/id limits are 2083/250 bytes, with a
4096-byte OSC 8 payload limit; other OSC payload limits stay at 2048 bytes.
URI syntax is ASCII and percent-encoded, with an absolute scheme. Unknown
parameters are ignored; duplicate id parameters, malformed URIs, embedded
controls/NULs and oversized completed commands clear the active attribute.
Cancelled commands leave the previous attribute unchanged. Nonempty id plus
identical URI shares a handle; missing/empty id starts a new run. FIFO eviction
invalidates old handles. Handles are monotonically allocated and never reused,
including after RIS; the UINT32_MAX guard fails closed instead of wrapping.
The NoRemoteHyperlinks setting disables parsing and address lookup.

The hit-test API reads the last painted visual grid, including bidi and
wide/double-width lines. Identical text with a different URI must update this
metadata on redraw. During synchronized output, the old displayed address
remains the target until presentation resumes (or becomes inactive if evicted).
The API returns borrowed registry pointers: a frontend must copy a URI before
processing nested messages or further terminal output. The native activation
UI and its subsequent verification are recorded below.

The sixteenth core suite covers these paths, invalid/fragmented framing,
6000 short/long registry admissions, 100 resize/font cycles, synchronized
presentation timeout and Shift selection in mouse modes 1000/1001/1002/1003.
Selected text contains the visible label, without OSC markup or the URI.
The headless suite passes ASan/UBSan in WSL with leak detection. This exposed
an existing teardown leak of the last selection's text/attribute/colour
buffers; term_free now releases all three. It did not accumulate on each
selection because replacement already freed the previous buffers.

The current local native rerun passed mouse/ConPTY/resize, synchronized
presentation and the 37-checkpoint Sixel/font suite. In the latter, peak private
WS was 8,007,680 bytes, total WS 23,941,120 bytes and private commit 9,236,480
bytes, without trimming. Executable SHA-256:
`b95449523cdf18865ac2f741705f3d7a732e5df6ceaa2354bbddbf81ef3a1871`.
This checks the larger cell layout against existing workloads.

OSC 8 native UI checkpoint: hovering displays a hard-wrapped, complete address
in a lazy Win32 STATIC popup and underlines every visible cell in the same
id/URI group without changing the model's SGR attributes. Ctrl+left-click
opens the target with ShellExecuteW's explicit open verb and no command-line
parameters. Ctrl+right-click offers Open Link and Copy Link Address. Ordinary
right-click retains the selected-label copy policy. Copying an address does
not discard the existing label selection. Shift always selects labels;
Ctrl-drag hands off to local selection instead of opening a link. Capture
loss, resize, font changes, focus loss and another pressed mouse button cancel
pending activation. WM_CANCELMODE now also reaches DefWindowProc to dismiss
the native popup menu.

Terminal/Hyperlinks exposes NoRemoteHyperlinks and NemoCustomURLSchemes.
The latter defaults to false: HTTP/HTTPS/FTP/mailto and local Windows file
targets may open; other registered schemes require explicit opt-in. File
authority must be empty, localhost or match the machine's short/FQDN name.
UNC/device/Unix paths, encoded separators/control bytes and file query/fragment
suffixes are rejected for activation; foreign hosts remain copy-only even
with custom protocols enabled. Single-letter schemes cannot masquerade as
Windows drive paths. There is no file-line/fragment navigation integration.

The ninth native suite uses temporary, UUID-named registry profiles and a URI
handler that records arguments into its temporary directory; it never opens
a browser or sends a request. It checks exact percent-encoded arguments,
group underline pixels, 2083-byte address wrapping, both preference switches,
live hover changes, menu open/copy/cancel, clipboard text, four application
mouse modes, Shift takeover, Ctrl-drag, mixed left/side buttons, capture and
resize cancellation, synchronized old/new displayed targets and foreign-file
policy. Clipboard formats are saved and restored, with unsupported handle
formats rejected before modification. Helpers send only to owned HWNDs; they
align their own window under the existing pointer without moving the cursor.

A final 6000-long-URI burst evicts an old main-screen link while retaining its
label, then admits 800 Sixel images. The stale label cannot open any new URI.
Local peak private WS was 8,634,368 bytes, total WS 31,535,104 bytes and private
commit 9,940,992 bytes, without trimming; child/ConPTY processes are separate.
Executable SHA-256: `f5a3fc1164e60615681a24fa04dba9600516dae2f3a87287084596196e57283c`.
Evidence: `research/hyperlink-window-observed.json`, `hyperlink-hover.png`,
`hyperlink-address.png` and `hyperlink-long-address.png`. All sixteen core
suites and Linux hyperlink/image lifecycle ASan/UBSan passed locally.
All nine native suites passed for this executable, including the existing
37-checkpoint Sixel/font fixture (8,155,136 bytes peak private WS) and font-resize
GDI resource checks. Workflow validation with actionlint
1.7.12 passed. Remote CI for the preceding core commit remained
queued/failed before job creation during GitHub's reported Actions incident;
these local results do not claim that the new UI has passed remote CI.

Native clipboard reads/writes now retry short lock contention for a maximum
100 ms retry window (plus scheduler/API latency). Copy remains synchronous.
The link fixture holds the clipboard for 50 ms and verifies that the selected
label is copied after release; a 400 ms hold verifies bounded failure without
overwriting the old address, followed by a successful explicit retry. A longer
external lock can still make an individual copy or paste fail; this is not an
indefinitely queued clipboard operation.
Copy and Paste uses the local selection buffer for its paste component, so a
failed system copy cannot paste stale clipboard text. The native menu test
holds the clipboard with a link address in it and verifies that the child
receives only the selected label instead.
The configured ordinary-right-click copy/paste path passes the same busy-lock
test in a separate profile; default right-click remains copy-only.

### Kitty keyboard checkpoint

The Windows input path now implements the five progressive enhancements from
https://sw.kovidgoyal.net/kitty/keyboard-protocol/. Query/set/push/pop have
independent 32-entry main/alternate stacks (66 bytes total), bounded eviction,
explicit-zero handling, fragmented input and cancellation/overflow tests.
RIS resets both; cursor save/restore and resize preserve modes. The portable
encoder bounds associated text to 16 Unicode scalars and output to 256 bytes,
rejecting invalid scalars and incomplete output without heap allocation.

The Win32 adapter originally allocated about 12 KiB after enhancement was used;
the later optional 9001 checkpoint extends this lazy allocation to about 24 KiB. It
tracks physical scan positions so a layout change cannot orphan a held key.
Press/repeat/release, lock state, left/right modifiers, navigation, keypad,
F1..F24 and media keys are mapped; the portable encoder covers F1..F35.
Physical PC101 alternatives and OS text are separate. ToUnicodeEx tests use
explicit US, US International, German and Russian layouts without activating
them, including dead-key composition and AltGr. No global input is injected.
Unknown-key text commits use key 0 when associated-text reporting is enabled.
Report-all without associated-text intentionally omits pure text, as specified.
Focus loss sends releases for reportable held keys, then clears local state.
Ctrl+Shift+C/V and local scrolling retain priority; their key releases do not
leak into the application. Paste remains a text/bracketed-paste operation.

`test_keyboard` passes on Windows and Linux ASan/UBSan. The tenth native suite
verifies exact child bytes across the bundled ConPTY, repeat counts, modifiers,
UTF-16 surrogate and IME-character messages, independent screen stacks,
synchronized output, focus loss, resize, selected-label copy and bracketed
paste. These synthetic messages do not verify real IME candidate windows,
physical devices, every locale, Alt-number entry or sustained agent behavior.
Windows input mode 9001 and modifyOtherKeys were outstanding at this checkpoint;
the later sections record their implementations and remaining limitations.

All 17 core and 10 native suites passed locally for executable SHA-256
`27a3e0e2658cfd237a0fa5d112dca84b011ca6328c40982b4a15dd26c2c57a89`.
The keyboard fixture's phase samples reached 3,670,016 bytes private WS,
19,542,016 total WS and 4,939,776 private commit. Continuous sampling during
the hyperlink/Sixel pressure fixture reached 8,454,144 private WS,
31,358,976 total WS and 9,654,272 private commit. No trimming was performed;
ConPTY and child processes are separate. Evidence lives in the corresponding
`research/*-observed.json` files, with `research/keyboard-window.png` captured
using PrintWindow. CI builds/runs the new core and native suites, includes the
keyboard core in ASan/UBSan, and uploads the native JSON/log/screenshot.

The earlier Actions outage is resolved for the previous UI checkpoint:
commit e9ef53886cf982e67d97e1d56bacbc1771291e12 passed remote run 43104641238
(16 core suites, 9 native suites and sanitizer job), and its downloaded
artifact manifest and executable hashes were verified. This historical run
does not claim remote verification of the new keyboard code.

Follow-up keyboard cases preserve legacy Ctrl/Alt text when only event types
are requested, ignoring Caps/Num Lock for that legacy byte mapping. Ctrl+Shift
chords use canonical CSI-u, and the alternate-key flag alone does not promote
a legacy text chord to CSI-u. Portable and native tests cover these combinations;
the native copy/paste phase now enables SGR application mouse tracking as well,
verifying that Shift selection stays local while enhanced keyboard input is on.
The refreshed `keyboard-window-observed.json` identifies the follow-up binary;
other local JSON files above remain evidence for their explicitly recorded hash.

The keyboard selection fixture uses initial font cell metrics plus the grid's
centered margin after resize, rather than assuming a one-pixel border. This
keeps the drag on the final letter with fallback fonts. Local runs with Sarasa
and explicit Courier New both copy the exact label without padding or a newline;
CI runs both its default fallback and Courier New and uploads separate evidence.

### OSC 52 clipboard checkpoint

The preceding keyboard checkpoint, commit cc0517683cca90ab684df35c900bbb44c76a6b48,
passed remote [run 43112134986](https://github.com/xiongnemo/nemoterm/actions/runs/43112134986).
Its downloaded executable manifest, commit, pinned ConPTY hashes, 17 core logs,
11 native JSON files (10 suites, keyboard with two fonts) and sanitizer logs
were verified. The following OSC 52 work has its own evidence and CI run.

OSC 52 uses a streaming Base64 decoder with at most 256 KiB of decoded UTF-8
text per request; it never buffers the encoded payload. Terminal/Clipboard
offers separate application read/write switches, saved as NemoOSC52Read and
NemoOSC52Write. Writes default on and reads off. Reads expose text to the
running session, including a remote host. Local copy/paste shortcuts remain
independent of these permissions.

The Windows mapping is c=system clipboard, s=alias of c, p=the terminal's last
local selection, and q/0..7=internal secondary/cut buffers. Empty Pc selects
s0. Multiple write targets share storage where possible; queries try targets
in order and return the first available target (s replies as c). The internal
buffers share a 1 MiB FIFO budget including metadata. Eviction clears old
references; there is no claim of X11 selection ownership on Windows. Remote
system writes preserve the local selection and its pixels; explicit p writes
replace it. Clipboard and retained buffers survive RIS and screen switches.

Empty or malformed Base64 clears the requested targets. Invalid UTF-8,
embedded NUL, oversized payloads and invalid target headers leave them
unchanged. Cancelled sequences cannot commit partial text. Replies preserve
BEL versus ST; the inherited PuTTY parser also accepts UTF-8 encoded ST.
Authorized queries with no available bounded text reply with an empty value;
disabled reads send no reply. One query may be pending per terminal. Requests
and completed replies are dropped when queued terminal/backend input exceeds
512 KiB, limiting additional clipboard reply backlog. These bounds and empty
fallback behavior are explicit Nemoterm policies.

System reads run on one refcounted worker per window, with a bounded UTF-16
scan and UTF-8 conversion. UI completion uses a request identifier and a
message cookie; reset/reconfiguration invalidates outstanding replies, and
window destruction detaches the worker. A 100 ms timer handles failed message
delivery. An OS delayed-render operation can outlive cancellation until the
OS returns, but cannot return text to the reset/revoked terminal. Writes use
the existing synchronous 100 ms clipboard-open retry. This is not a hard
deadline on all Windows API calls.

The eighteenth core suite checks fragmented framing, permissions, strict
Base64/Unicode boundaries, exact/oversized data, target order, cache sharing
and eviction, stale completions, reset/revocation and outgoing backlog. It
passes Windows tests and Linux ASan/UBSan with leak detection. The eleventh
native suite checks real CF_UNICODETEXT under four policy combinations,
Chinese/emoji, local-primary preservation, synchronized presentation, bounded
reads/writes, contention with responsive resize, and delayed-render reads
with responsive UI and suppressed replies after RIS. Windows normalized the
fixture's unterminated text publication; the test checks the format actually
returned by Windows, rather than claiming it exercised an unterminated buffer.
Helpers address owned windows and preserve/restore supported clipboard formats.

Protocol reference: [xterm OSC 52](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html).
The hidden delayed-render fixture follows Microsoft's
[clipboard ownership and rendering rules](https://learn.microsoft.com/en-us/windows/win32/dataxchg/clipboard-operations).
Real SSH/tmux/application flows and the remaining protocol ledger are still
outstanding; this checkpoint does not complete overall terminal acceptance.

All 18 core and 11 native suites passed locally for executable SHA-256
`358b5e01676886f73cf02e0342041a1002a675fe00a033fec2d4dd4e01e1b65e`.
Keyboard checks passed with both default Sarasa and Courier New; the current
local keyboard JSON/screenshot is the Courier run. OSC 52 continuous sampling
peaked at 5,804,032 bytes private WS, 21,749,760 total WS and 7,417,856 private
commit. The mixed hyperlink/Sixel stress fixture peaked at 9,510,912 private
WS, 36,589,568 total WS and 11,182,080 private commit. No working-set trimming
was performed; these are terminal-process measurements with ConPTY/child
processes separate. `research/osc52-window-observed.json` records exact reply
hashes and policies; `research/osc52-window.png` is a PrintWindow capture.
Actionlint 1.7.12 passed. CI now runs all 18 core and 11 native suites (plus
the second keyboard font), uploads the new evidence and runs the OSC 52 core
under ASan/UBSan before publishing the portable build.

The first OSC 52 CI run passed the other native suites and sanitizers, then
found a font-dependent assertion in the clipboard-contention resize fixture.
The fixture now reduces the measured window width by 12 actual character
cells and waits for the child to report the new dimensions as well as the
clipboard reply. Both local Sarasa and Courier New runs report 80 to 68
columns. This replaces an arbitrary fixed pixel width and a possible stale
dimension snapshot; it does not relax the required resize notification.

The corrected OSC 52 checkpoint, commit
`458b8fe0271f19ca3fd7e10a60363306bc25b9d2`, passed remote
[run 43118513619](https://github.com/xiongnemo/nemoterm/actions/runs/43118513619).
Its downloaded package commit, executable SHA-256, pinned ConPTY files,
18 core logs, 12 native JSON files and four terminal sanitizer logs were
verified before this next checkpoint.

### xterm modified keys and native settings checkpoint

`modifyOtherKeys` now has levels 0–3, disable/reset/query, both encoding
formats, modifier factoring and DECRQSS. The main and alternate screens
share the eight-byte state; kitty enhancements take input priority without
overwriting it. Initial settings are saved as NemoModifyOtherKeys and
NemoFormatOtherKeys, both zero by default, under Terminal/Keyboard/Extended.
The Windows adapter previews character lookup without consuming a pending
dead key, commits only handled events, and keeps local commands ahead of
protocol encoding. Exact syntax, independently reproduced XTerm(412) bytes,
Windows/XKB differences and remaining resource families are documented in
[modify-other-keys.md](../research/modify-other-keys.md).

The nineteenth core suite covers parser recovery, queries, reset/reconfigure,
bounded encoding, global screen state and kitty coexistence. Windows layout
cases cover US, US International dead keys, German AltGr and Russian without
changing the user's active layout. The new native input suite checks real
ConPTY bytes, repeats, Unicode/IME character messages, focus cleanup,
synchronized output, resize, Shift selection under application mouse mode
and Ctrl+Shift+C/V. A second run uses Courier New and saved level-3/CSI-u
defaults, including RIS restoration.

Opening the real settings dialog exposed additional defects missed by the
terminal fixtures: startup configuration assumed a network backend and
created orphan proxy controls, local launch validation required a host,
and the right-click radio options omitted required variadic shortcut fields.
The new modified-key radio controls also needed correct shortcut arguments.
These are corrected. The thirteenth native suite uses UI Automation scoped
to its own process to select visible options, check mutually exclusive
radio state, verify the default copy-only policy, save a temporary profile,
cancel, reload it and launch a local session with exact keyboard query replies.
It deletes its temporary profile and captures only the owned settings window.

The hyperlink fixture now waits until all three test labels have painted
before taking its baseline. A parser query reply can precede deferred drawing;
the original one-row, exact-group underline pixel assertion remains unchanged.
It first renders plain labels away from the real pointer, then adds OSC 8
metadata and waits for identical pixels before triggering hover. This prevents
a synthetic mouse-leave event from capturing an already-underlined baseline.

CI runs 19 core and 13 native suites, with extra font/configuration runs for
both keyboard protocols (15 native JSON files), plus five terminal ASan/UBSan
logs and the standalone Sixel/colour sanitizer checks. Physical devices,
real IME candidate UI, long agent sessions, history reflow and the remaining
protocol ledger remain outstanding.

All 19 core suites and 13 native suites passed locally, including the two
extra keyboard font/configuration runs, for executable SHA-256
`9ff8674c4c42801987d1b7bd3caae6a51d3a66d26902d9382fde4af031362fc1`.
The new and existing keyboard cores also passed Linux ASan/UBSan with leak
detection; actionlint 1.7.12 passed. Current native evidence carries this
executable hash (the older mouse fixture does not record a hash).

The default modifyOtherKeys run peaked at private WS 4,333,568 bytes
(4.334 MB / 4.133 MiB), total WS 25,587,712 bytes (25.588 MB / 24.402 MiB),
and private commit 5,918,720 bytes (5.919 MB / 5.645 MiB). The mixed
6,000-link/800-Sixel fixture's final baseline-fix run peaked at private WS
10,067,968 bytes (10.068 MB / 9.602 MiB), total WS 38,830,080 bytes
(38.830 MB / 37.031 MiB), and private commit 11,833,344 bytes
(11.833 MB / 11.285 MiB).
These are continuously sampled terminal-process peaks, without trimming;
ConPTY and child processes are separate. They do not establish the same
bounds for every future workload.


## Main-screen and history reflow checkpoint (2026-11-12)

This supersedes the earlier open text-reflow status. Column changes now reflow
main-screen and compressed history text by default. Soft wraps, hard breaks,
wide/combining characters, decoration colours and hyperlink handles survive.
Current/saved cursors, pending wrap and a scrolled viewport are mapped. The
native Window setting can disable reflow and persists across profile reloads.
Alternate screens, DEC double-size/trusted lines and Sixel-covered rows retain
fixed grids; surrounding text can move raster rows vertically without copying
or splitting pixels. History limits and cursor-visible bottom cropping remain
explicit bounds, not an unlimited preservation claim.

The implementation streams compressed rows and limits retained output to the
configured history plus screen. A 10,000-row uninterrupted logical paragraph
is tested through repeated narrowing, widening and bounded eviction. Real
ConPTY tests additionally verify exact whole-buffer copies, rendered Shift
selection while mouse reporting is enabled, alternate-screen restoration and
5,000 output lines during width/height changes. See research/reflow.md for
policy, fixed-grid exceptions and measured memory. The existing resize,
hyperlink and Sixel regressions remain enabled; test reset explicitly clears
history so independent fixtures cannot restore a previous fixture's output.

CI now includes 20 core suites, 14 native groups (16 JSON runs with additional
keyboard font/configuration runs), six terminal ASan/UBSan suites and standalone
Sixel/colour sanitizer checks. Physical devices, multi-monitor DPI, real IME,
full grapheme handling, extended agent sessions and the protocol ledger remain
open. This checkpoint does not complete the overall terminal goal.

All 20 core suites and 14 native groups passed locally for executable SHA-256
`9d7a47eeb829b1584fa5308f17165ddcfa315ea3cb42555f366752eb593111ab`,
including the additional keyboard font/configuration runs. Reflow, Sixel and
hyperlink cores passed ASan/UBSan; actionlint passed. Pixel fixtures now wait
for the actual final cursor geometry, and the hyperlink baseline stays on
screen away from the pointer and verifies that the hidden startup cursor is
also erased. The exact underline-group assertion remains unchanged.

## Optional Win32 input checkpoint (2026-11-12)

DEC 9001 negotiation and bounded KEY_EVENT_RECORD encoding are implemented,
with UTF-16, scan/virtual keys, left/right modifiers, lock flags, repeat counts,
press/release, focus cleanup and policy epochs. The profile option under
Terminal/Keyboard/Extended defaults off. Enabling it supports native Windows
console key identity; kitty and active modifyOtherKeys retain priority.
The pinned ConPTY preserves native F24 but drops it when re-encoding ordinary
VT input, and this path bypasses traditional custom key mappings. Keeping it
optional preserves the existing direct-VT F21-F24 capability/input regression.
See [win32-input.md](../research/win32-input.md) for upstream references and
the measured limitation; this does not complete keyboard acceptance.

The new native fixture reads real ReadConsoleInputW records, console control
signals, mouse events and resize records, then separately checks VT input,
application 9001, kitty/modifyOtherKeys coexistence and local Shift selection
with Ctrl+Shift+C/V paste. The settings fixture checks the visible option's
default, saved value and reload. The reflow fixture now waits for a complete
JSON snapshot when Windows temporarily denies access during atomic replacement;
its exact text, selection and dimension assertions are unchanged.

All 21 core suites and 15 native groups passed locally, including the two
additional keyboard font/configuration runs, for executable SHA-256
`f96bcb1d963015408ad79c8924c8dab0ad7ca964208d1994f06d1a35dc1af15d`.
Win32 input, kitty and modified-key cores passed ASan/UBSan with leak detection;
actionlint 1.7.12 passed. PrintWindow captures show the owned terminal and
settings controls. CI includes 17 native JSON runs, seven terminal sanitizer
logs and the separate Sixel/colour sanitizer checks.

The optional Win32 fixture sampled 4,399,104 bytes private WS, 25,538,560 total
WS and 5,812,224 private commit. The mixed 6,000-link/800-Sixel stress fixture
continuously sampled peaks of 8,876,032 private WS, 33,669,120 total WS and
10,190,848 private commit. Reflow peaked at 6,299,648 / 22,478,848 / 7,741,440
bytes respectively. No working-set trimming was used; ConPTY and children are
separate processes. Physical keyboard/IME, DPI, long-running real agents and
the remaining protocol families remain open.

## 2026-11-12: soft reset and saved private modes

Added DECSTR, XTSAVE/XTRESTORE for the existing mode families, DECNKM 66,
DECOM homing/relative CPR and saved-origin cursor restoration. The mode cache
is fixed at 84 bytes and preserves enum-valued mouse modes and screen aliases.
Twenty independent XTerm 412 cases and source comparison informed the behavior;
intentional differences and the exact lifecycle are recorded in
`research/state-control.md`. This does not fill unsupported mode families.

All 22 core suites passed locally. The new state suite passed Linux ASan/UBSan
with leak detection. Six native groups passed for executable SHA-256
`f99285d0af0dbee1083152fe0b0990a73d1fa56f8c640ee6d2b9c3a292a40687`:
mouse, query/cursor, keyboard, reflow, hyperlink/stress and state control.
The last verifies unchanged text/Sixel pixels through soft reset, real child
mouse bytes, restored 1016 coordinates after resize, exact Shift clipboard
selection, synchronized presentation and main/alternate cursor state.
Actionlint 1.7.12 passed. CI now includes 22 core suites, 16 native groups with
two additional font/configuration runs, and eight terminal sanitizer logs,
plus the separate Sixel and colour sanitizer checks.

State-control peaks were 4,653,056 bytes private WS, 20,660,224 total WS and
6,131,712 private commit. The 6,000-link/800-Sixel mixed workload peaked at
8,818,688 / 33,562,624 / 10,104,832 bytes respectively; reflow peaked at
6,541,312 / 22,700,032 / 7,888,896. No working-set trimming was used; ConPTY and
children remain separate measurements. Physical devices/IME, multiple DPI,
long-running agents and the other protocol families remain unaccepted.

The first CI run of this checkpoint passed all core and preceding native groups,
but the new Shift-selection fixture rejected an unmodified button-free motion
report at (463, 310), outside its injected selection path. The copied text was
correct. The fixture now distinguishes normal all-motion reports (SGR code 35)
from forbidden Shift/button/drag/release leakage and retains their exact bytes;
it still requires the exact clipboard text. The terminal implementation is
unchanged by this fixture correction.


## Embedded Nerd symbols and RTL memory checkpoint (2026-11-12)

The single EXE now embeds the unmodified Nerd Fonts Symbols Mono v3.5.1 asset.
Missing BMP and supplementary icons use a private, lazy-loaded font with eight
cached HFONTs; primary Sarasa glyphs remain unchanged. Surrogate/variation
sequences retain one terminal cell and exact original Unicode on Shift-copy.
Thirty-two font resize cycles and primary pixel restoration are tested.
The resource and complete notices remain inside the single executable; no font
is installed globally or extracted. See `research/font-fallback.md`.

Two temporary RTL draw buffers were leaking on each exact glyph paint. An old
artifact grew 8,368,128 bytes in private commit over 5,000 repaints; the fixed
artifact grew 12,288 bytes under the same fixture. This is a regression gate,
not a bound on all possible sessions. Windows now has 26 core suites; the new
native group and standalone cmap ASan/UBSan are included in CI. Generic emoji/
grapheme fallback, real IME/DPI, application sessions and remaining protocols
remain open. Intermittent local hyperlink fixture timeouts remain recorded and
are not claimed fixed by this renderer change.

## DEC rectangle editing checkpoint

DECFRA, DECCRA, DECCARA, DECRARA, DECSACE and its DECRQSS query are implemented
with an independent XTerm(412) oracle, 27 passing core suites and native pixel,
Unicode clipboard, Sixel, resize and 3,000-copy checks. Temporary copy storage
is one row; undrawn-cell metadata uses a spare existing bit. Local frontend
peaks were 5,079,040 / 26,595,328 / 6,615,040 bytes (private WS / total WS /
private commit). See `research/rectangle-editing.md` for the exact executable,
reference source, semantics and limits. The single-file CI has 25 checks.

DECLRMM/DECSLRM remain open: Sixel's current whole-row anchor representation
needs column splitting at horizontal margins. The remaining full protocol,
physical device/IME/DPI and real-agent requirements are unchanged.


## Horizontal margins checkpoint

DECLRMM/DECSLRM, mode/query/save/reset integration and origin-relative horizontal
coordinates now have 114 independent XTerm comparisons plus direct regression
cases. Partial-column scrolling preserves outside text/pixels, combining chains,
protection and hyperlinks. Sixel views share immutable raster storage and split
row anchors/masks within the existing 4 MiB budget. Full-width history scrolling
retains the line-rotation path; partial columns do not create whole history lines.
Saved DEC state now has 22 slots (88 bytes), including mode 69.

All 28 core suites passed locally. ASan/UBSan with leak detection passed margin,
image, rectangle, reflow and state-control suites. The native fixture verifies
exact text/Sixel pixels, Shift-copy under application mouse/keyboard protocols,
grid and font resizing, and 300 repeated image splits per resize policy. See
[horizontal margins](../research/horizontal-margins.md) for reference anomalies,
explicit differences, memory samples and reproducible tests. CI now includes
11 terminal sanitizer suites and 26 single-executable checks.

The broader full-protocol, Unicode/grapheme, real IME/DPI and real-agent workload
acceptance remains open. This checkpoint does not close those requirements.


## IMM / Unicode / DPI checkpoint (2026-11-12)

Source commit `badf932e75e083a072fb232b44debcc6dc108263` has green core and
single-executable CI: 28 core suites, 11 terminal sanitizer suites and 28 native
single-file checks. The installed artifact is 4,307,968 bytes, SHA-256
`25d734ce58418509d423d7091f76c5efe23821759fbee929bc16176e8bf7a892`.
IMM short-read boundaries, WM_UNICHAR, active composition font scaling and
OpenConsole UTF-16/UTF-8 byte boundaries are fixed. The source overlay retains
one pending UTF-16 unit and preserves string decoder state during internal
stream reads. Raw/VT/cooked reads have 24 buffer/mode combinations; actual IMM
API submission and synthetic DPI pixel checks pass locally with Sarasa.

The final artifact passed six local groups, including mouse/resize and all six
shells. Uninstrumented frontend margin stress peaked at 10,006,528 private WS,
32,813,056 total WS and 11,771,904 private commit bytes. Host and shell samples
remain separate. An earlier local full run's delayed clipboard fixture was
preempted by an external read and is explicitly not claimed passed; final CI
passed that group. Full details and the exact artifact-bound evidence are in
[the input-method record](../research/input-methods.md).

Physical IME candidate selection, genuine multi-monitor transitions, real agent
workloads and complete modern/xterm protocol coverage remain unaccepted. This
checkpoint does not close the broader goal.


## Working-directory checkpoint (2026-11-12)

OSC 7, OSC 9;9, OSC 633 P;Cwd and OSC 1337 CurrentDir/RemoteHost now provide
bounded directory metadata, URI copy and configurable Duplicate Session cwd
inheritance. Startup `--directory` and saved Unicode directories work with native
Windows shells, Git Bash mounts and WSL --cd. No shell profiles are changed.

Source `a6493606a92cd6994fcc805d1a51d8a957ef63a3` has green core and single-file CI:
29 core suites, 12 terminal sanitizer suites and 29 native checks. The installed
single EXE is 4,314,112 bytes, SHA-256
`bfe1523105d1ef10de53c51e9fab4abcee710e5e93f59d3475401cc8a148b86f`.
Seven local groups passed on that exact artifact, including all six shells.
Local frontend stress peaks were 10,420,224 private WS / 40,390,656 total WS bytes;
the host and Python fixture have separate idle samples. See the
[working-directory record](../research/working-directory.md) for limits, failure
history, screenshots, PE evidence and CI artifact links.

Remaining OSC 133/633/1337 commands, image protocols, complete modern/xterm
coverage, physical IME/DPI/device behavior and real-agent acceptance remain open.

## Real Codex input and selection checkpoint (2026-11-12)

The source-built host now preserves supplementary Unicode text in native
ReadConsoleInputW consumers by omitting synthetic surrogate text releases.
Rapid selections at different positions no longer become double/triple clicks;
same-position word/line selection and the highlight handshake remain tested.
The actual Codex 0.167.0 client passes exact Unicode input, streamed Markdown,
long responses, 32 live resizes, Shift grid selection and Ctrl+Shift+C/V in both
default and inline modes, using deterministic local responses.

Source `2862f6768478c2933a8ae3f60640a7e34e3190ea` has green core and single-file
CI: 29 core suites, 12 terminal sanitizer suites and 33 native checks. The final
EXE is 4,314,112 bytes, SHA-256
`955c4c7b66fdb98dce4edef2b7dc6645678b8fb582b67742d45732da15edda56`.
Seven local groups passed against that exact file, including all six shells
and Sarasa rendering in both Codex modes. Frontend private WS sampled peaks
were 7,008,256 / 7,213,056 bytes; total WS peaks were 32,604,160 / 32,882,688.
Headless host and client memory are recorded separately. Details, CI artifacts,
failure history and captures are in [the real-client record](../research/real-agent.md).

This finite client regression does not close live-service/long-term agent use,
Claude Code, physical IME/DPI/device behavior, complete grapheme rendering or
the remaining protocol ledger.

## Rendering, bindings and startup checkpoint (2026-11-13)

Source `8fb697a933ee56f3b5cb49b1bf4199d3a3dd278e` has green core and single-file
CI: 29 C core suites, 12 terminal sanitizer suites, four process-identity cases
and 36 native checks. The single artifact is 4,329,472 bytes, SHA-256
`6dd61201097f31083d9339ebfa809628857fb3ed7634b3d499fa5a29986d8684`.
It includes configurable copy/paste/rectangle bindings, Ctrl rectangles, the
160x48/work-area startup rule and optional OpenGL composition with bounded text
cache. Oversized startup grids are clamped before screen allocation.

Actual hardware OpenGL, Sarasa pixel parity and real Codex OpenGL modes passed
on earlier artifacts. Final cloud checks use GDI fallback when hardware GL is
unavailable; they do not certify this final artifact on the local NVIDIA driver.
At that historical checkpoint, local testing was paused and `dist` retained the
previously accepted `2862f67` artifact. The resumed shell-integration checkpoint
below supersedes that pending local acceptance status. [Evidence and failure history](../research/rendering.md).

DirectX remains a measured feasibility prototype and integration design. Tabs
with four-sided placement and hover previews remain designed, not implemented.
Shell command marks, the remaining protocol ledger and other original goal
requirements stay open. This checkpoint does not narrow or complete the goal.

## Shell integration and resumed local validation (2026-11-13 Sydney)

OSC 133/633 command marks and OSC 1337 SetMark now support bounded history
navigation, command/output selection and four configurable shortcuts. Core and
sanitizer coverage includes reflow, clipping, alternate screens and metadata
churn. Exact source `ff693f8` has green core and single EXE CI, and the downloaded
4,338,176-byte artifact passes 37 local check groups in documented sequential
segments, plus both real Codex modes with hardware OpenGL. SHA-256:
`453db4ea641cedf56a8a80b843dc51c2bf5690a5190ad7b22aa0df15a9583571`.

GDI real-Codex frontend private WS sampled peaks are 6.1-7.1 MB, with total WS
27.9-32.9 MB. Optional OpenGL sampled private WS is 44.1-50.1 MB under the user's
explicit exception. Shell-mark stress peaks at 7.8 MB private WS. All figures
exclude the separately recorded console host and client. Test focus isolation
and working-set sampler fixes, exact hashes, artifacts and captures are in
[the checkpoint record](../research/shell-marks-design.md).

These finite tests do not close extended/live-service agent use, Claude Code,
physical IME/DPI/device behavior, complete grapheme rendering or the remaining
protocol families. DirectX frontend rendering and four-sided tabs with hover
previews are still planned, not implemented. Identity queries were not part of
that artifact; the following checkpoint supersedes that distribution.

## Identity queries and native shutdown (2026-11-13 Sydney)

DA3 and truthful XTVERSION now match 62 independently captured XTerm query
cases, including parameter reset on colon subparameters. The same implementation
passes 65 native identity checks. The natural child-exit path also now destroys
its HWND before freeing callback state, which removes a reproduced stale-window
lifetime defect. A private Windows Job bounds late real-client test subprocesses.

Source 80c6cf2 has green core, sanitizer, independent-reference and single-EXE CI.
The exact 4,338,176-byte artifact passed 38 CI groups and local GDI/OpenGL shutdown
and query checks. `dist/nemoterm.exe` now contains that accepted artifact, SHA-256
`50b58e1f5f07901bfa3bc496a6e2d5e4b1eaa8397bb4152de29a0fa8c3024822`.
The previous ff693f8 artifact is backed up under
`build/dist-before-window-shutdown-80c6cf2/`.

CI's default and inline real Codex GDI frontend peaks are 5.07 and 5.24 MB private
WS, 34.85 and 35.01 MB total WS; host and client are recorded separately. The
local query peak is 4.68 MB private WS. The local real-Codex retry hit Windows
clipboard access-denied and is not counted as passed. Exact provenance and
observations are in [window-shutdown.md](../research/window-shutdown.md).

Title stacks were not part of that artifact; the following checkpoint supersedes
that distribution. Title encoding modes, geometry gaps, DirectX frontend rendering,
four-sided tabs/previews, physical input/IME/DPI and the wider protocol ledger
remain open. The original goal is still active.

## Bounded title stacks (2026-11-13 Sydney)

CSI 22/23 now saves and restores icon/window titles in ten bounded, lazy slots,
including indexed access and per-title encoding. Source `5a8b27f` passed core,
sanitizer and single-file CI; all 39 native CI groups passed. The exact final
artifact also passed 23 local title checks, including real HWND titles, Chinese,
emoji and 1,000 pushes/pops. Its GDI frontend samples peaked at 3.97 MB private
WS and 23.31 MB total WS. These are samples after phases, not continuous maxima.

`dist/nemoterm.exe` now contains the accepted 4,339,200-byte single executable,
SHA-256 `c5970125f2c171a86ff33a50d37357d03dfc3ecfe0bed7832b76bda642629995`.
The previous artifact is retained in `build/dist-before-titles-5a8b27f/`.
PE inspection found 605 regular and 11 delayed imports across 79 descriptors,
with complete table coverage and no reported issues. See
[the title-stack record](../research/window-controls.md) for artifacts, exact
responses, limits and the earlier development-host failure.

Title encoding modes continue on `feature/title-modes`. Geometry gaps, DirectX
frontend rendering, four-sided tabs/previews, physical input/IME/DPI, full
grapheme support and the wider protocol ledger remain open.

## Title modes, geometry queries and minimized rendering (2026-11-13 Sydney)

The preceding title-stack distribution is superseded by source `9ccbad3`.
It includes the bounded title encoding modes, live text/window/monitor/cell
queries, and a fix that preserves OpenGL and newly received output across
minimize/restore. Core, ASan/UBSan and all 41 single-file native CI groups passed.
The exact EXE passed nine local groups, including hardware GL pixel comparison,
both geometry renderers, 23 stack and 87 title-mode checks, startup sizing,
font resize, Sixel, queries and synchronized output.

`dist/nemoterm.exe` is now the accepted 4,342,272-byte single executable,
SHA-256 `9d8133f2cf4bbaa709d0e6b98014359c485125364d06a2c47cb91f1f55c5f909`.
The prior executable is backed up under `build/dist-before-geometry-9ccbad3/`.
Local GDI geometry peaks at 4.17 MB private WS and 23.55 MB total WS; the largest
private-WS peak across these nine groups is 6.16 MB. Cloud real-Codex default and
inline peaks are 5.35 and 5.51 MB private WS. These finite measurements exclude
host/client processes and do not establish all-workload limits. GL samples
after screenshot instrumentation are explicitly labelled.

The first MinGW native CI attempt had a hyperlink hover capture assertion; the
unchanged source passed on attempt three after an intervening mirror-download
failure. Its cause remains unconfirmed, with the first capture retained. Local
clipboard access remains denied, so local real-Codex copy/paste was not accepted
again. Exact provenance and boundaries are in
[the checkpoint record](../research/window-geometry.md).

At that checkpoint geometry mutations had 31 independent XTerm reference cases
but were not yet implemented. The following resize checkpoint supersedes it. DirectX frontend
rendering, four-sided tabs/previews, physical input/IME/DPI, full grapheme
support, live Claude Code and the remaining protocol ledger remain open.

## Application-requested window resize (2026-11-13 Sydney)

XTWINOPS character/pixel resize and DECSLPP now handle missing, empty, zero,
large and malformed parameters with ordered completion. Rejected requests
reassert the actual grid to ConPTY, fixing an independently reproduced child
console/frontend mismatch. Minimized requests and subsequent output survive
restore, and remote-resize, locked-window and font-resize policies are honored.
The 39-case independent XTerm reference has 36 exact model replies and three
documented differences for sub-cell minima and current rather than stale pixels.

Source `44ac455` passed core/ASan/UBSan CI and all 42 native single-file groups.
The exact artifact passed nine local groups, including 100 application-resize
checks, native mouse input/window resizing and hardware OpenGL pixel parity.
`dist/nemoterm.exe` is the accepted 4,343,808-byte single executable, SHA-256
`9e9e9d663b72c5f31191f9bb0da91f40c07efe9f77b0e5dad5999b491a71fc48`.
The prior image is backed up under `build/dist-before-window-resize-44ac455/`.

Local GDI resize sampled peaks are 6.24 MB private WS / 25.70 MB total WS.
Cloud real-Codex default/inline frontend private-WS peaks are 5.07 / 5.10 MB;
host/client memory remains separate. Local clipboard acceptance is not renewed.
The [resize checkpoint](../research/window-resize.md) links exact CI artifacts,
per-phase evidence, screenshots and measurement boundaries. DirectX frontend,
four-sided tabs/previews, physical input/IME/DPI, full graphemes, axis window
controls, live Claude Code and the remaining protocol ledger are still open.
