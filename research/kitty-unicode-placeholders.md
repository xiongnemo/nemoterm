# Unicode image placeholders: independent reference and baseline

The complete [upstream run 43673330735](https://github.com/xiongnemo/nemoterm/actions/runs/43673330735)
captures **97 cases / 728 states**, including all **297 row/column diacritics**.
Nemoterm's new real-core replay currently fails **681 states across 97 cases**.
This is an implementation baseline, not product acceptance. The accepted
752f3be single executable remains unchanged.

## Reference identity and scope

Fixture source f536f4c58de4103ab5b45e6a3f445f5c1c1f8edb builds unmodified
Kitty 8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f using its upstream CI recipe.
REA 6.8.0 records the compiled parser and graphics manager, normal exit 0,
verified process cleanup and temporary-root removal. Eight upstream controls
pass, covering basic placeholders, image high bytes, multiple placements,
scrolling, reverse scrolling, history margins/fill and relative parents.

The successful observation has SHA256
feda36b2971fbc29059b4c80ddf989c228e8c4b5c18ffe07fb064b05bbd78a44.
The fixture records exact input/reply bytes, cursor, normal-screen text,
image counts before/after layer updates, viewport history offset, geometry,
raw layers, upstream source hashes and compiled-file hashes. Resize and
viewport-scroll calls are explicitly declared actions. Layer updates are
declared observation effects; they can recreate cell images or retire orphans.
This is headless model evidence, not native window/GPU pixels. REA's sampled
process tree and non-atomic prelaunch file-identity limitations remain retained.

The [Unicode-placeholder protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/#unicode-placeholders)
provides the input vocabulary. Cases cover indexed/RGB foreground IDs,
underline placement IDs, all diacritic mappings, inherited coordinates/high
bytes, extra/unrecognised marks, incremental combining input, aspect fitting,
edits, graphics deletion selectors, retransmission, relative descendants,
alternate screens, history and resizing/reflow. Expected geometry is observed
from the compiled upstream, not computed in the fixture.

The initial [run 43673001055](https://github.com/xiongnemo/nemoterm/actions/runs/43673001055)
completed all states and controls, but its 256 KiB rendered-terminal journal
budget omitted 44 frames. The complete observation file was hashed, and process
cleanup succeeded; nevertheless the no-truncation gate correctly failed.
The second run changes only that recorder budget to 2 MiB. The fixture and
assertions are identical. Both captures are retained separately, including the
initial truncation details; only the complete second capture generates tests.

## Strict real-core replay

The generator preserves every state, converts normalized layer coordinates
using each captured window size, and reproduces the declared resize/scroll
operations. Replies and normal-screen text compare directly. Error replies
require the captured ID/status prefix, nonempty detail and the exact terminator.
Text extraction omits blank tail cells like the upstream line representation;
the generator asserts that none of these captured lines ends in a literal space.
The replay also checks cursor, history offset, image count, source/destination
rectangles, z order and the shared image budget.

With production source unchanged from 656fed4, local GCC 16.2.0 builds and runs
the new suite. It exits 1 with 681 failed states, while the earlier relative
suite remains at 233/238. Its executable SHA256 is
a47dcfccc86aaee20e929964100f09bb2b3c45f057b8de043985bf2aa055d2da.
The log, exact fixtures, compiler identity, CMake configuration and source diff
are retained in the baseline archive.

Most failures expose the missing virtual-placement/cell-image path. Six text
assertions also differ in REP, alternate-screen entry and ED 3 scenarios; seven
cursor assertions differ in REP and alternate-screen scenarios. These need an
independent xterm comparison before choosing text-semantics changes. The replay
keeps those observations and does not silently exempt them or classify all
cross-terminal differences as graphics defects.

The implementation must preserve existing text storage and its bounded
combining-character chains, account for derived image metadata, distinguish
invisible templates from text-driven visible cells, and handle invalidation,
history, parent visibility and disposal. Native compositor/pixel, selection,
resize/lifecycle and uninjected single-image memory acceptance remain required.

[kitty-unicode-validation.json](kitty-unicode-validation.json) indexes both
upstream captures and the unchanged-production baseline with per-record hashes.

## Development implementation and independent text policy

The implementation stores invisible virtual templates alongside ordinary
placements and derives bounded one-row image runs from existing terminal text.
It adds no field to every terminal cell. The 297-entry protocol alphabet is
generated from the hash-pinned capture. Foreground colour supplies the image ID,
underline colour supplies placement ID, and positional combining marks supply
row, column and high image-ID byte; adjacent compatible cells form a run.
Templates fit the whole image with aspect-preserving letterboxing. Derived
runs share the existing image budget and have a separate cap of 8192; ordinary
placements/templates retain their cap of 512. The paint path renders placeholder
glyphs as spaces without changing stored or copied text.

Templates survive text clearing; derived runs disappear with text. A child of a
template without any cell anchor is hidden and retained. Template replacement,
explicit deletion, data retransmission, history scrolling, font changes and
destruction retain separate ownership rules. New component checks exercise
admission failure, both placement caps together, hidden children, named data
retention and anonymous image disposal. Local strict GCC compilation passes;
the placement suite now passes 12635 checks.

Iteration 01 matched 718/728 raw Kitty states. Iteration 02 fixed a real scalar
REP defect and matched 720/728. Both failures and source diffs remain retained.
REP now remembers the previous spacing character across combining marks; mode
2027 still repeats the complete bounded grapheme cluster. Ordinary terminal and
grapheme regression suites pass.

The remaining eight raw differences are text policies, independently tested in
source-built XTerm 412 at commit `5c75ead9a75d4b2e666ca06fa94503b5766ed93f`:

| Operation | Kitty capture | XTerm capture and Nemoterm policy |
| --- | --- | --- |
| Enter 1047/1049 alternate screen | Home cursor | Preserve cursor position |
| Leave 1047 alternate screen | Restore main cursor | Preserve current cursor position |
| ED 3 | Erase visible text too | Keep visible text; erase saved lines |

[Run 43675871329](https://github.com/xiongnemo/nemoterm/actions/runs/43675871329)
retains 18 streams. It exposed an observer effect: inserting CPR between text
and REP cancels XTerm's repeat state. The corrected
[run 43676070696](https://github.com/xiongnemo/nemoterm/actions/runs/43676070696)
retains 26 streams, separating eight uninterrupted REP cases from eight query
controls, plus ten alternate-screen/erase cases. Its observations SHA256 is
`ea49c2d8830394edd8f156c3159a7cbfc66d9761d28a161640930d84ec1db3f2`.
These captures establish the decisions above, not complete XTerm conformance;
the query-interrupted REP control is not an implemented compatibility claim.

The generator retains the original 728-state Kitty array byte-for-byte and
appends eight explicit alternative expectations. It validates the independent
XTerm cursor/checksum replies before deriving them. The expected image source
rectangles still come from Kitty; only the cursor-driven translation and
ED3 retention of previously captured cells differ. Every state's cursor, text,
image count, history, replies, image geometry and budget assertions still run.
The test log names every policy state. Iteration 03 passes all 728 checks as
720 raw matches plus eight explicit xterm-policy states; all 238 relative states
and earlier graphics/compression/query suites also pass.

This remains development evidence. No capability-advertisement or accepted
product change is implied by these local core results.

## Native repaint regression and correction

The source-built combined image from `3ee3235` has SHA256
`cd5a038a03eec1329b77062590fda15b1a3c5c995b55a84c369feef331b944b2`.
The new native fixture tests the entire 40x12 text grid, using the installed
SarasaTermSC Nerd Font Light. Its 30 stages cover text editing/scrolling,
template deletion/recreation, RIS/ED2/ED3, alternate screens, virtual-parent
visibility/movement, letterboxing, placement selection and high image-ID bytes.

The initial GDI API run passed all 30. OpenGL, DirectX and a direct GDI client-DC
capture each passed 22 stages and failed when erasing the last virtual-parent
anchor: the child was hidden in the placement model but its blue pixels remained
in the presented surface. GDI's API snapshot forced a redraw and masked this
defect. The three failures and all screenshots are retained, not reclassified
as instrumentation noise.

`do_paint` now notices placement-generation changes during text-cell refresh
and invalidates the displayed cells even if no current view remains visible.
It sets invalid attributes directly without scheduling another paint. After
this change, the same 30 stages pass in all four capture modes (120 pixel
states). Ordinary terminal, grapheme and complete image-core regressions also
pass. All eight native runs exit normally, remove their temporary profiles and
leave no owned child processes. The fixed local frontend SHA256 is
`c11361107a16632e5b66822f6ed26d5acae325be1d353c7cea2c675fe96415b9`.

The fixed native runs use a local MinGW frontend plus the unchanged source-built
headless host from `3ee3235`; they are not a fresh combined-single-file
acceptance. The fixture is added to Windows CI and the single-executable
verification script for all three renderers. `native-repaint.tar.gz` retains
489 inputs, logs, snapshots, source/runtime metadata and images with hashes.
Actual text selection, Unicode-image zoom/resize/history disposal, long-session
resource behavior and fresh uninjected single-image memory acceptance remain
pending. The broader project goal is still open.

## Transparent borders and font geometry

The pinned upstream `shaders.c` configures `REPEAT_CLAMP` with a transparent
border and `GL_CLAMP_TO_BORDER`. The earlier native painter repeated edge pixels
outside the raster, which filled the empty portion of a partially occupied
Unicode cell. A new partial-letterbox case fails on the repaint-only image:
320 extra green pixels appear in direct GDI capture. The corrected painter
leaves out-of-raster samples transparent. This retains Nemoterm's nearest-neighbour
sampling; it does not claim pixel identity with Kitty's GPU linear filtering.
The upstream file, including its licence, is retained as research evidence;
the production fix is an independent bounds check.

[Run 43679054777](https://github.com/xiongnemo/nemoterm/actions/runs/43679054777),
at fixture source `6520e3c`, independently captures 153 fresh cell geometries
(widths 4 through 12, heights 10 through 26) from the pinned compiled Kitty.
Three upstream controls pass. REA records normal exit 0, verified process
cleanup, temporary-root removal and no truncation. The observation SHA256 is
`c6a03613d5f5df5313ee7f07610bb4ac2b0615428a9ab5efd61f9fd06e59656a`.
`font-geometry-reference.tar.gz` retains the complete capture and CI provenance.
The generator validates these observations and exports their rectangles for
native checks. It removes only checked floating-point representation noise
when converting normalized coordinates back to integral destination pixels.

The first native replay rejected the two reference image APCs with `E2BIG`:
upstream accepted their 6144-character base64 payloads, while the protocol
chunk limit is 4096. The fixture now splits the same decoded bytes into legal
chunks and checks the graphics replies. The rejected input, replies and failed
screen are retained as a transport mismatch in the fixture, not a renderer bug.

Sarasa passed the new zoom/history sequence after the transparent-border fix.
Consolas then exposed another real border defect at 7x15 cells: double-precision
roundoff moved an exact bottom-edge sample slightly inside the image, painting
one extra row (28 pixels per image). The painter now canonicalizes only values
within 16 double-precision epsilons, scaled by raster extent, of either raster
border. Interior samples are unchanged. The independently captured expectations
and every pixel assertion remain unchanged.

The final local frontend SHA256 is
`0675072f4cb1c070a81d676211343ecdc14b5340b7b153a8d5b85ce7d812f474`.
It passes 603 native pixel stages in 25 owned runs:

- Sarasa and Consolas each pass 32 Unicode editing/letterboxing stages and
  19 geometry/history stages in GDI, actual OpenGL, actual DirectX and direct
  GDI client-DC capture: 408 stages together.
- Ordinary Kitty images, compressed images and placement zoom/resize pass
  24, 29 and 12 stages on each of the three renderers: 195 stages together.

The geometry sequence checks shrink/grow/reset, window resizing, synchronized
output ending on zoom, scrollback visibility, history erasure and template
retention after history erasure. Expected image rectangles come from the
independent fresh-size captures; the 153 reference sizes are not 153 native
font runs. Geometry checks compare complete red/blue pixel sets; the separate
32-stage fixture compares the whole text grid, including its background.
All owned process groups exit naturally. These tests use no global input or
clipboard access. The real-core Unicode replay still passes all 728 states,
including its eight explicit xterm text-policy alternatives; ordinary terminal
and grapheme suites also pass.

`native-border-geometry.tar.gz` retains 2089 records from 46 runs, including
the two production failures, the oversized-APC fixture failure, preliminary
passes and all final passes, plus source/runtime identities and controller logs.
A PowerShell argument-splatting mistake exited in argparse before launching a
terminal; its log is also retained. Older geometry reports omitted their output
folder: the retainer matches complete checks JSON and, where identical runs
exist, requires a unique controller-log/checks completion-time match within two
seconds. That mapping evidence is explicit in the manifest. Future reports
record the folder directly.

CI now regenerates the font reference and runs Unicode geometry/history tests
for each renderer, including isolated single-executable validation. The local
frontend still uses the unchanged source-built `3ee3235` headless host; these
results are not acceptance of a new combined single executable. Fresh CI,
selection, lifecycle and uninjected memory acceptance remain pending.

## Selection core and completed repaint CI

An additional 32 real-core copy checks preserve the literal U+10EEEE scalars
and their combining marks through ordinary and rectangular selection. They
cover main/alternate screens, application mouse on/off, mode 2027 on/off and a
repeat after image preparation. Shift keeps the gesture local even when mouse
reporting is enabled; releasing modifiers before the button produces no stray
mouse report. Expected newlines and supplementary-plane encoding follow the
platform. The local Windows GCC build passes these checks and the complete
graphics suite. This uses the mock clipboard sink, not the system clipboard or
native selection pixels.

The repaint checkpoint `191c641` has now completed
[core CI 43678325293](https://github.com/xiongnemo/nemoterm/actions/runs/43678325293),
[single-image CI 43678327425](https://github.com/xiongnemo/nemoterm/actions/runs/43678327425)
and [component CI 43678139051](https://github.com/xiongnemo/nemoterm/actions/runs/43678139051).
All four core jobs and all three component compilers pass; the single-image
manifest lists 146 passed groups. The downloaded 4,522,496-byte executable has
SHA256 `eadbb1d7280e764fe61460427399d3b2c86a9d158a4ae46e89ca7eff0a24d4c2`.
It predates the transparent-border/roundoff fixes and has not replaced `dist`.
The earlier `3ee3235` core and single workflows were automatically cancelled by
same-branch concurrency when the repaint-fix workflows were dispatched; their
component workflow passed. Those cancellations are neither test passes nor
diagnosed failures. `ci-repaint-and-selection.tar.gz` retains all six workflow
receipts, full logs, artifact metadata, the single-image validation manifest and
the exact new local selection source/build/test evidence.

## Native clipboard selections and combined-image precheck

The owned-window selection fixture now checks both Ctrl+Shift+C and default
right-click copy through the real Windows clipboard. Sixteen cases combine
main/alternate screens, application mouse on/off, normal/rectangular selection
and mode 2027 on/off. They release modifiers before the mouse button and drain
child input exactly, so a copied value alone cannot hide a forwarded mouse or
paste event. The copied text includes the original supplementary-plane PUA and
all positional combining marks. The fixture preserves supported clipboard
formats and restores them when its own window still owns the clipboard.
Its injected keyboard state and mouse messages are confined to the owned UI
thread; these are not physical-input or uninjected memory measurements.

The first fixture expectation omitted the leading space on the second line of
a cross-line selection. The second attempt clicked the same point rapidly
enough for the real frontend to classify the third click as line selection.
Both failed attempts, including exact copies and screenshots, are retained.
The corrected fixture includes the leading space and moves consecutive
independent selections outside the system double-click rectangle, rather than
altering terminal selection behavior or weakening byte comparisons.

The local MinGW frontend `0675072` passes 256 clipboard copies with Sarasa and
Consolas across actual GDI/OpenGL/DirectX and direct GDI client-DC capture.
All eight final runs close naturally, restore the clipboard, remove their
temporary profiles and leave no owned processes. `native-selection.tar.gz`
contains 324 records from all ten attempts, including both fixture failures.
The new fixture is wired into future ordinary and single-executable CI runs.

Before selection, the test asserts the complete opaque red image area. Selected
screenshots are retained diagnostics, not an assertion that image pixels change
colour. Inspection shows that opaque images cover the underlying selection
background, so an image-only rectangular selection has no separate visible tint.
Copying still works. The pinned Kitty `draw_cells_with_layers` also draws negative
images after cell backgrounds; this is source evidence, not a captured Kitty
selection-pixel comparison. A dedicated image-selection overlay remains absent.

The current source-host artifact `14148651177` from core run `43681119193` is
built at `4095697`. Its combined executable is 4,522,496 bytes, SHA256
`31850600b2a0a9d9a91ff9305ff449ae4febca6fc977c306a25bbff1aaee51ed`.
An isolated-directory check confirms that the child console host runs from the
same executable, no OpenConsole/conhost sidecar process is used, the console
survives delegated-launcher exit and the directory still contains only the EXE.
The same image then passes 204 Unicode/geometry pixel stages and 128 native
clipboard copies with Sarasa across the four capture modes.

One initial DirectX geometry run passed 16 stages, then received an extra
`DEL` byte after the otherwise correct geometry/status replies. The unchanged
input and executable pass all 19 stages on retry. The failed input/reply record
and screenshots remain in `combined-409-precheck.tar.gz` alongside the passes
(552 records). The user confirmed using the computer during testing, making
external input plausible, but no specific physical action is established as
the byte's source. This is not silently treated as a first-attempt pass.

Local interactive testing is now paused at the user's request. All fixture
processes had exited when the pause was checked. Remote CI and background source
work may continue. The combined-image precheck has not replaced `dist`, and its
incidental small-window memory samples do not replace the required uninjected
160x48 workload acceptance.

## Capability discovery after implementation

The development responder now advertises `U=1` and relative-placement keys
`P/Q/H/V` for transmit-and-place (`e=T`) and place (`e=p`) feature queries.
Signed parent offsets retain their signs, including the 32-bit limits. Queries
remain non-mutating and do not require the requested parent IDs to exist; this
reports individual supported fields, not validity or budget admission of every
combination. Unsupported Unicode flag values are still omitted, as in the
independent upstream capture.

The generator reuses the unchanged 84-case/176-state reference: exactly five
expected replies change, and all original input bytes and upstream replies are
preserved. Four cases no longer need capability omissions, reducing explicit
subset projections from 22 to 18. The existing 1,000-query allocation check now
also includes Unicode placement, maximum parent/placement IDs and signed offset
limits while the graphics cache and placement store remain absent.

This advertisement change is newer than `4095697` and the downloaded precheck
image. [Component CI 43682719696](https://github.com/xiongnemo/nemoterm/actions/runs/43682719696)
passes GCC/Clang with ASan/UBSan and MSVC at `3ac5a6b`: 176 feature states with
18 explicit capability subsets, 238 relative states, 728 Unicode states with
the same eight xterm-policy differences, and 32 exact core copies. Original
logs, artifact identities and hashes are retained in `kitty-unicode-validation.json`.
Native/full-product validation remains pending. Local desktop tests remain
paused; neither the accepted executable nor its documented scope changes yet.

## Dense cell-image memory workload

The next CI checkpoint adds `--kitty-images --kitty-unicode` to the existing
uninjected two-tab memory fixture. A shared 512x288 PNG is repeated with explicit
row/column zero in each visible interior cell. At 160x48 this is 7,268 independent
cell images per tab, rather than a few contiguous image runs. The workload keeps
the existing 2,000-line histories, 24 redraw/resize transitions, temporary-tab
cleanup and mandatory strict GDI 20 MB / inclusive DirectX 25 MB private-WS
thresholds. The Unicode text overwrites the previously emitted Sixel region,
exercising its disposal; the existing mixed-image memory groups remain separate.

Both tabs are reseeded at their final grid size before sampling stops. Only
afterward, bounded one-pixel-high screenshot strips check the centre of every
expected cell on active and inactive tabs. Missing late allocations therefore
cannot pass solely because the first image appeared. Screenshot requests and
the later input/hover probes remain outside memory acceptance sampling.
Input sizes/hashes, actual grids and process-tree samples are retained. The
fixture is added to both full workflows; it has not yet run on this paused
desktop or passed its new remote memory gate.

## Completed border-fix CI checkpoint

At `4095697`, [ordinary CI 43681119193](https://github.com/xiongnemo/nemoterm/actions/runs/43681119193)
passes all four jobs and [single-image CI 43681119198](https://github.com/xiongnemo/nemoterm/actions/runs/43681119198)
passes 149 isolated groups. Both exercise 153 Unicode cell/geometry stages with
GDI, OpenGL and DirectX requested, as well as ten uninjected two-tab memory
workloads each. The remote OpenGL requests fall back to actual GDI; these runs
prove GDI and DirectX pixels, not actual OpenGL execution. The earlier local
development observations identify actual OpenGL separately.
Those remote workloads used Consolas at the actual screen-clamped grids
109x34 (top tabs) and 88x35 (left tabs). They passed their existing private-WS
limits; they are not local 160x48 Sarasa or dense Unicode-cell memory acceptance.

The downloaded [single executable artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43681119198/artifacts/14149387899)
is 4,522,496 bytes, SHA256
`875c89cae3c17b33da93c157b5f7d95a6982a25c2bbb602397e034177d8168a9`.
Its digest and sole-file directory match the isolated validation manifest.
`full-ci-4095697.tar.gz` retains 66 original workflow, memory and native-result
records with per-file hashes. This checkpoint predates the newer capability
advertisement, native clipboard fixture and dense Unicode memory fixture.
It has not replaced the accepted `752f3be` executable. At `eae8968`, ordinary
CI fails `tabs_profiles_window_smoke.py` at the final zero-exit assertion:
all seven functional checks complete, then the frontend exits `0xC0000005`.
The graphics/memory gates later in that job were not reached. Its independent
single-image workflow is still running. Local desktop testing remains paused.
