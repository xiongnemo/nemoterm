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
