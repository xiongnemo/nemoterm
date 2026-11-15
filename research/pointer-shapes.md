# OSC 22 pointer-shape development

OSC 22 now has bounded parser state and a tested optional presentation callback.
The Windows frontend now connects the callback and presents all thirty shapes.
Native resource and real-window checks pass at the checkpoints below; the
latest source still needs full product regression and memory acceptance.
The accepted distribution is unchanged; local native testing remains paused.

The [kitty protocol](https://sw.kovidgoyal.net/kitty/pointer-shapes/) defines
30 CSS shape names, set/push/pop operations, support/current/default/grabbed
queries, separate main/alternate stacks and reset behavior. Stack capacity must
be at least sixteen. Shapes apply independently of mouse reporting; local
selection and link hover may override them. The
[XTerm specification](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
defines the original unprefixed X11 name setter and a different unknown-name
fallback. Those are distinct behaviors to compare, not interchangeable names
for a completely verified protocol.

`tests/kitty_pointer_oracle.py` authors 117 input cases / 555 stages for the
existing pinned upstream `8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f`.
It uses the real native parser, upstream `Window.set_dynamic_color` dispatcher
and native shape stack. Three literal response controls check that the native
test callback has actually been connected. The fixture records raw replies,
current shapes, cursor positions and text rows; it does not calculate expected
stack results. Coverage includes all specified shapes, 41 alias candidates,
stack eviction and underflow, malformed/empty lists, alternate-screen modes,
hard/soft reset, selection-independent mouse modes, BEL/ST, cancellation and
bytewise input. Alias candidates are inputs, not claims of supported aliases.

The disposable Linux workflow runs this capture under the existing pinned REA
process recorder. Its result must preserve source/binary hashes, complete input
and output records, exit status and verified cleanup. This in-memory reference
does not observe an OS mouse cursor or establish Windows rendering.

The reference alone does not establish Windows cursor presentation, per-tab
isolation, selection/link/busy precedence or resource lifetime. Those require
the separate native checks below. Product memory and local physical-device/DPI
acceptance remain open.

## Retained reference and component checkpoint

[Reference run 43692238900](https://github.com/xiongnemo/nemoterm/actions/runs/43692238900)
at `ed5beca` completes all 117 cases / 555 stages and three literal controls.
REA records normal exit and verified owned-process cleanup; its prelaunch-image
identity and sampling limitations remain in the manifest. Fifteen original
records are retained in `pointer-shape-evidence/kitty-reference-ed5beca.tar.gz`,
indexed by `pointer-shape-reference-validation.json`. The observation SHA256 is
`4060b1bc1cde1302da9874c804e4d83d66d95a0bfb47b5a1dbf8401a2081d81e`.

The upstream keeps the prior shape for an unknown setter, keeps separate stacks
across all three tested alternate-screen modes, and clears both on hard and soft
reset. Empty setters install an automatic-shape slot; empty push elements do
nothing. Three legacy spellings (`arrow`, `beam`, `hand`) return supported in
queries while other recognized aliases return zero. The raw capture also keeps
malformed-string/cancellation behavior; those observations are not silently
rewritten into Nemoterm expectations.

The standalone component uses 34 bytes for both sixteen-entry stacks and has
no allocator. Complete payloads are bounded to 2,048 bytes and query content to
4,096 bytes; query output is only emitted after successful completion. A terminal
owner allocates this state lazily. The component checkpoint below predates
terminal integration and does not establish native cursor support.

`generate-pointer-reference.py` reproduces a 106-case / 504-stage component
projection from the unchanged capture. Its eleven omitted cases require actual
VT dispatch (screen switches, resets, mouse modes, cursor save/erase, cancellation
and NUL handling) and remain reserved for that integration. Bytewise input in
the source is replayed as complete payloads here; this does not verify parser
fragmentation. Additional component checks cover screen isolation, rejected
oversized input, exact reply capacity and read-only query state. Local checks
have only compiled the C sources and parsed/generated fixtures; runtime replay
uses the disposable GCC, Clang and MSVC CI jobs.

[Component run 43693144294](https://github.com/xiongnemo/nemoterm/actions/runs/43693144294)
at `51fe4b2` passes all three compiler jobs and both GCC/Clang ASan/UBSan runs.
Each execution reports 4,740 checks and all 504 unchanged upstream stages.
The four compiled source/header hashes in each compiler artifact match the
identified Git blobs (with any checkout line-ending conversion recorded).
`pointer-shape-component-validation.json` indexes 23 retained records in
`components-51fe4b2.tar.gz`. This still does not establish terminal integration,
Windows cursor pixels or a new accepted product.

## Terminal dispatch and lifecycle checkpoint

The terminal now links the component, allocates its 34-byte state only after
an effective setter, and frees it when both stacks empty or on RIS/DECSTR or
destruction. There is one owner pointer and a deferred presentation flag per
terminal, with no per-cell storage. Screen changes schedule presentation of
that screen's current shape. Queries use the existing seven/eight-bit reply
framing. An absent frontend callback disables both setters and replies, so an
unimplemented frontend cannot claim support.

The first [terminal run at `98116eb`](https://github.com/xiongnemo/nemoterm/actions/runs/43694691231)
retains two distinct failures. GCC/Clang match all pointer states but differ
from three upstream cancellation replies in each fragmentation mode. The
existing Nemoterm parser cancels an unfinished OSC on CAN/SUB or an interrupting
escape and accepts the following valid query; the pinned Kitty parser leaves
that query unanswered. The replay explicitly names these three policy
differences and preserves the original reference bytes. No production parser
change was made to hide the discrepancy. MSVC's first terminal fixture instead
fails during compilation because its new VS-generator configuration defines
`NDEBUG`; the fixture now uses the project's existing Ninja/MSVC flags.

The [corrected run at `fe4b9a9`](https://github.com/xiongnemo/nemoterm/actions/runs/43694995351)
passes GCC, Clang and MSVC, including GCC/Clang ASan/UBSan. For each compiler,
all **555 stages** pass with original chunks and again bytewise: each mode has
552 exact upstream replies, three explicit cancellation-policy replies and
555 matching pointer states. Both the terminal state and the deferred frontend
callback model are checked. Supplemental tests cover lazy allocation, release,
two-screen reset, oversized setter rejection, parser recovery, C1 framing and
the absent-callback gate. The existing terminal query suite also passes.

`pointer-shape-terminal-validation.json` indexes 91 records in
`pointer-shape-evidence/terminal-fe4b9a9.tar.gz`, retaining both failed and passed
runs, exact source blobs and 54 matching source hashes. The generated full-VT
projection preserves every input chunk from the independent capture. This is
parser/callback-model validation: Windows pointer pixels, actual tab isolation,
native resources, DPI/selection/busy priorities and product memory remain
unverified. No local GUI or native runtime test was run.

## Windows presentation under validation

The frontend selects shared Windows cursors for standard shapes and eight
small monochrome glyphs for alias, cell, copy, grab, grabbing, vertical text
and zoom. Custom resources are lazy, shared across tabs, and bounded to 104
handles (eight shapes in thirteen 8-pixel size buckets, 32 through 128 pixels).
No custom resource is created on a default terminal. Shutdown destroys only
owned cursors after terminal windows close. No new library or distribution
file is required.

Application shape is per terminal. Busy status retains its existing priority;
Shift/local selection and allowed link hover override the application's shape.
Updates check the active visible window under the pointer or its mouse capture,
without changing the shared class cursor. Tab activation, pointer movement,
Shift transitions and DPI changes refresh presentation. System resize aliases
share the corresponding Windows axis/diagonal cursors. Cursor sizes above 128
pixels are clamped; physical multi-monitor/accessibility behavior remains to
be tested.

The native resource fixture checks all thirty shapes and thirteen sizes using
actual Win32 cursor objects, stable cache handles, teardown and three BMP
contact sheets. Source compilation alone does not establish these runtime
checks or actual frontend pointer/selection behavior.

## Native diagnostics and corrected observation

The first four remote attempts are preserved in
`pointer-shape-native-initial-validation.json` and
`pointer-shape-evidence/native-initial-failures.tar.gz` (415 records).
The first fixture used the wrong frontend output filename. Subsequent resource
checks found three additional GDI objects after drawing the first colour atlas.
A cursor-free control that performs the same colour drawing establishes a
0 → 3 → 3 baseline; monochrome drawing alone had not exercised that path.
The atlas itself returns to its pre-drawing count each time. The corrected
fixture retains strict final resource equality; it does not subtract a guessed
cursor leak. The first system-ConPTY window attempt timed out on its first
query without retaining enough wire evidence to locate the missing reply.

[Run 43697828780](https://github.com/xiongnemo/nemoterm/actions/runs/43697828780)
at `49e13b1` passes **141,028 native resource checks**, including 30 shapes,
13 sizes, 104 custom cursor objects, 39,000 cached reads and a second lifetime.
After all cursor destruction, USER/GDI counts return to the measured 1/3
baseline. Three raw BMP atlases and all 104 native masks are retained.
The same run builds a 4,532,224-byte single image with SHA256
`2627957c29e54cc6a79bcf61e61eac06381563be4fd070b95c04c2f8271bde1b`.
Its first OSC 22 query completes through the bundled console host, but the
first cursor observation fails. This run also exposes a real glyph defect:
floor rounding can place a scaled hotspot on a transparent pixel.

The hotspot now uses the first destination pixel that samples its opaque source
pixel. [Linux replay at `bbdd37f`](https://github.com/xiongnemo/nemoterm/actions/runs/43698295314)
passes **5,580,341 checks / 776 shape-size cases** under both GCC and Clang
ASan/UBSan, including canaries, exact mask capacity, opaque hotspots and rejection
of invalid sizes. Component and full-terminal replay also pass. MSVC was
intentionally skipped for that diagnostic; the older `49e13b1` executable does
not contain this hotspot correction.

Exact-image replays keep that older single executable and its original masks
fixed while changing only the observer. The first replay records Windows
`CURSOR_SUPPRESSED` and a null cursor despite successful query replies.
`SetCursorPos` alone leaves that runner state intact; real mouse-class
`SendInput` movement clears it. The next replay passes 51 checks, then samples
the old terminal cursor immediately after moving onto the tab strip. Hit testing
already identifies the host, but its queued cursor update has not completed.
The fixture now waits for the independently expected host arrow before testing
whether terminal output changes it.

[Replay 43699397756](https://github.com/xiongnemo/nemoterm/actions/runs/43699397756)
with fixture `7e12e03` passes **53 actual OS cursor checks and 44 exact OSC 22
round trips**. It covers every canonical shape, push/pop, alternate-screen
isolation, soft reset, mouse-reporting independence, real Shift transitions and
selection dragging, allowed link hover, two-tab isolation and activation,
tab-strip isolation and client re-entry. Hidden-tab and tab-strip guards each
retain 30 stable observations. All five owned processes exit naturally with
exit code zero. `GetCursorInfo`/`GetIconInfo` observe selected Windows objects;
the PNGs draw those objects with `DrawIconEx`, not desktop framebuffer captures.
The fixture refuses to send input outside disposable CI.

These five runs, exact source blobs, single image, raw cursor masks, logs and
observations are retained in `pointer-shape-native-diagnostic-validation.json`
and `pointer-shape-evidence/native-diagnostics-7e12e03.tar.gz` (541 records,
77 matching source hashes). The successful replay is at the runner's default
DPI against the older image. Current-source Windows validation, full ordinary
and single-image regressions, product memory, physical multi-monitor input,
busy-status transitions and optional user controls remain separate checks.
The accepted local executable and local-test pause are unchanged.

## Corrected-source Windows checkpoint and full-regression failure

[Run 43699492458](https://github.com/xiongnemo/nemoterm/actions/runs/43699492458)
at `7e12e03` passes all three compiler jobs with the hotspot fix included.
Both Linux sanitizers repeat the 776 glyph cases and full terminal replay;
MSVC repeats 141,028 resource checks, then builds the current source console
host and passes all 53 native cursor checks / 44 exact query round trips.
All five window-fixture processes exit naturally. Its 4,532,224-byte focused
single image has SHA256
`d02c4e4bf154236366dfef57594a7d20d7592500712d3fbc5a998ed91fa39cb8`.

The separately built [full single-image run 43699496703](https://github.com/xiongnemo/nemoterm/actions/runs/43699496703)
at the same source fails early in GDI file-drop validation. Thirteen checks
complete, including correct Windows PowerShell path bytes delivered by the
terminal. The independent `powershell.exe -NoProfile -NonInteractive -Command`
process that then parses those quoted arguments exceeds its existing 20-second
deadline. This is not evidence of a cursor failure, and the incomplete run does
not establish product regression or memory acceptance. Its separately linked
image is also 4,532,224 bytes, with SHA256
`862216d30cb5f5a27d9507c4e6ddfe7170de32f5871433c3af14f8f666b8cc6a`.
Both exact binaries and their distinct build/test records are retained in
`pointer-shape-windows-validation.json` and
`pointer-shape-evidence/windows-7e12e03.tar.gz` (333 records, 42 source matches).

The unchanged failed image subsequently passes three GDI drop replays in
[run 43700206613](https://github.com/xiongnemo/nemoterm/actions/runs/43700206613),
using fixture `068f87e`. Only external-shell timing/output recording was added;
the process invocation and 20-second limit are unchanged. Each replay completes
all 50 drop/clipboard checks and all six owned terminal lifetimes close without
forced termination. Actual pwsh, Windows PowerShell and Git Bash argument parsing
passes; other shells retain their existing wire-only scope on this runner.
Windows PowerShell takes 2.875, 0.219 and 0.219 seconds. These successes leave
the initial timeout unexplained; no production fix is claimed. The 32 original
records and 18 verified fixture-source hashes are indexed by
`pointer-drop-replay-validation.json` in
`pointer-shape-evidence/drop-replay-068f87e.tar.gz`.

The complete single-image regression is being repeated with the additional
timing evidence. Product sources remain identical between `7e12e03` and
`068f87e`; only documentation, CI triggers and diagnostic fixtures changed.
Local desktop tests and accepted distribution promotion remain pending.

## Complete ordinary CI checkpoint

[Ordinary run 43699494654](https://github.com/xiongnemo/nemoterm/actions/runs/43699494654)
at `7e12e03` passes all four jobs: source console-host build, terminal sanitizers,
MSVC native renderer diagnostics and the complete Windows portable build/tests.
All twelve uninstrumented history/image workload gates pass. The dense Unicode
image cases also verify 25,048 cells after memory sampling and close their
owned process trees naturally.

These are frontend peak bytes for the two dense workloads, using remote
Consolas windows; the private, total and committed peaks need not coincide:

| Renderer and actual grid | Private working set | Total working set | Private commit |
| --- | ---: | ---: | ---: |
| GDI, 109×34 | 14,008,320 | 44,912,640 | 16,969,728 |
| DirectX, 88×35 | 17,793,024 | 54,263,808 | 20,652,032 |

The private peaks satisfy the existing `<20,000,000` GDI and `≤25,000,000`
DirectX limits. DirectX total working set remains above the roughly 50 MB goal.
These workloads use the ordinary MinGW frontend and separate source host;
they do not establish single-image memory or local 160×48 Sarasa acceptance.

The portable frontend is 3,944,197 bytes, SHA256
`bac628dee463caf12b3c36cf8526b86546a6c1a6d2c55fc450e39ce26b6c1cd3`.
Its identified source host is 4,532,224 bytes, SHA256
`21c669e9e6634a2d56795fb1ec4d98022d046e00fda34c406d80723398e351e4`.
`pointer-shape-ordinary-validation.json` indexes 4,558 records in
`pointer-shape-evidence/full-ordinary-7e12e03.tar.gz`, including every ordinary
test artifact, portable runtime, exact source-host identity and workload
observations. The MSVC diagnostic artifact was downloaded into a fresh separate
directory before retention, avoiding a shared local download-directory collision
with the earlier pointer-only workflow. The full single-image retry remains a
separate gate.
