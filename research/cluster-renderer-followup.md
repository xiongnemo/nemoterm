# Native cluster renderer follow-up

This is development evidence, not promotion of a new single executable. The
accepted main artifact remains `8f7a9d2` / SHA-256 `a108894f50f7d797f7d2c01558a71f268a1c812fe365270e5a6a7fb7868ca4ed`.

## First CI attempt

At `b3022a8`, [core CI](https://github.com/xiongnemo/nemoterm/actions/runs/43328370274)
passed sanitizer/core tests but failed the native clipboard expectation.
The actual existing behavior of local selection is to end mode 2026, present
the pending frame, then select its cells. The new fixture had incorrectly
expected text from the preceding frozen frame. Its revised case uses distinct
cluster sequences in both frames, requires exact Unicode from the newly
presented frame, checks mode 2026 reset, and retains the no-forwarded-input
barrier. Native clipboard verification is still pending CI; local clipboard
access is unavailable.

[Single-EXE CI](https://github.com/xiongnemo/nemoterm/actions/runs/43328370282)
built a 4,391,936-byte executable but failed an earlier renderer pixel check.
The unverified artifact hash is `ec8d62a3f557bf3eb70d3f437901ff8bcb970d7f0e8b9788b47980b269f667c6`.
Both compared windows were GDI (the OpenGL request fell back on that runner).
Consolas images differed at (66,30) and (67,30), three channels with maximum
error 70. That same binary passed actual GDI/OpenGL/DirectX locally with
Consolas; the local result does not erase the CI failure.

The renderer now explicitly flushes queued GDI background writes before
DirectWrite touches its DIB, and finishes the destination copy before reusing
the tile. [CreateDIBSection's synchronization contract](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-createdibsection)
requires completion of GDI writes before direct access. Microsoft's
[DWriteCore overview](https://learn.microsoft.com/en-us/windows/win32/directwrite/dwritecore-overview)
describes DirectWrite's direct DIB drawing. This corrects the interop boundary;
it is not yet proof that it caused the CI pixel difference. Pixel tolerances
remain unchanged. An offscreen test compares many reused-tile copies against
individually flushed copies.

## Memory and compositor changes

The initial dense Sarasa 160x48 test reached 22,671,360 bytes private WS in
DirectX with two retained tabs and twelve create/close cycles. Its failed
record is `cluster-memory-before-observed.json`, frontend hash
`0329acc26b1cb0ab54d1b605c7b139cff5d11242be64fd7309aa5759ad5ac256`.
It was terminated through its owned job after the assertion, and is not an
accepted cleanup result.

The follow-up makes three changes:

- Undecorated run-cache keys share the same raster across columns. Patterned
  underlines retain absolute-x keys, because their phase can depend on position.
- GPU cursor lines/outlines/dots are drawn as clipped primitives. The text path
  already paints active block-cursor colors. Cursor drawing no longer requests
  GDI readback of the retained GPU frame; explicit captures and trust icons
  retain their existing readback path.
- Rows that need neither bidi reordering nor Arabic shaping do not retain two
  extra copies of every cell/cluster and two index maps. The existing `is_rtl`
  predicate includes shaping characters and directional controls. Trusted
  sigil rows retain the full transformation path. Tests cover LTR clusters,
  Hebrew visual order and cursor maps, then replacement by LTR clusters with
  the old mappings freed.

The final local frontend hash is
`0294da429f90d76976a1a91bf37304ee40ada8bff4961903f2c1a4762e241e53`.
All 35 core/native-offscreen executables passed, including all 853 official
segmentation vectors. Sarasa and Consolas renderer fixtures passed actual GDI,
OpenGL and DirectX, including repeated clusters, bidi, five underline styles,
cursor states, Sixel, synchronization and resizing. Ordinary and font-resize
grapheme fixtures passed locally with clipboard explicitly skipped.

| Dense tabs, actual 160x48 | Sampled private WS | Sampled total WS |
| --- | ---: | ---: |
| GDI, top | 9,011,200 | 29,294,592 |
| DirectX hardware, left | 19,320,832 | 54,161,408 |

`cluster-tabs-*-observed.json` retains the samples. They precede all capture or
input instrumentation and include live temporary third tabs, one warm-up and
twelve create/close cycles. Warm-up accounts for lazy window/IME/menu resources
before checking stable handle counts; its memory is still sampled. Each case
passed all nine native host groups, including preview refresh and keyboard
routing, then drained all 56 owned processes without forced cleanup. Preview
checks occur after instrumentation and are not uninstrumented preview-memory
acceptance. No working-set trimming is used. Child-process memory, arbitrary
tab counts, other fonts and long agent workloads are outside these samples.

`--dense-clusters` adds these cases to portable and single-EXE CI. The new
single-EXE suite has two additional cluster-width cases and two dense-tab cases
relative to the previously accepted 57-check suite. A fresh green run and
validation of its exact single-EXE artifact are still required.

## Subsequent CI and icon correction

At `18ddd24`, [core CI](https://github.com/xiongnemo/nemoterm/actions/runs/43331849023)
passed sanitizer tests and both native grapheme fixtures, including actual
clipboard assertions in all three requested modes (active GDI/GDI/DirectX).
The frontend hash in `cluster-ci-18d-grapheme*.json` is
`8788037259993d0f5ae297e4006369b724d5496a2264916e24e2c119c36ac384`.
The overall run later failed the embedded-icon variation-selector regression:
the new cluster path bypassed the GDI-only embedded font. Private-use icons
followed only by variation selectors now retain their existing GDI glyph;
selectors remain in stored/copied text. CJK variation sequences and real emoji
still use whole-cluster shaping. Local Consolas and Courier native tests passed
four distinct BMP/supplementary icons, exact selector pixel identity, 32 resizes,
6,144 distinct symbols and 5,000 RTL repaints. Their JSON explicitly records
clipboard skipped. CI rejects that local skip option.

[Single-EXE CI](https://github.com/xiongnemo/nemoterm/actions/runs/43331849044)
still failed the same GDI comparison after explicit GDI flushing. Repeated
accented text expanded the mismatch to 96 channels, with the same maximum
error 70. Therefore the flush boundary was not a sufficient fix and this build
is still unverified. No pixel tolerance was changed.

The next diagnostic run records selected clusters' font, exact floating-point
geometry, rendering parameters, normalized scalar, glyph IDs, resolved font
files and tile hashes through the opt-in `NEMOTERM_CLUSTER_TRACE` environment
variable. Normal runs create no trace file. Output is limited to 64 selected
clusters per window. Native parity is now also checked in the portable job,
and a separate MSVC frontend job obtains these observations without waiting
for the embedded OpenConsole build. The trace-enabled local three-renderer
check passed; the CI-only pixel difference remains unresolved.

## First-process raster difference

At `a9a000c`, all three CI builds (MinGW portable, standalone MSVC and the
single-image MSVC build) reproduced the same 96-channel, maximum-70 difference.
Tile traces show that it exists before the compositor or capture: Consolas
U+00C4 has hash `c665072c90a9e969` in the first GDI process and
`673635bb9d23f602` in the next process. U+00E9 is identical. Font file, glyph ID,
advance, baseline, transform, color and rendering parameters agree.

The `ed148a8` diagnostic deliberately requests GDI, GDI, OpenGL, GDI, DirectX.
Its first and second pure-GDI processes already differ. All subsequent initial
frames agree with each other, including actual DirectX. Only the initial text
and Sixel scenes differ from the first process; the later resized scenes agree.
Recommended rendering mode, actual target transform and font simulation flags
also agree. This rules out OpenGL fallback as the trigger, but does not yet
identify the internal cause. The same five-process sequence passes locally.

The next diagnostic matrix retains the unchanged shared-factory control and
tests an isolated factory and pixel-aligned centering on separate clean runners.
Each experimental job records its label, exact modified source, executable
hash, frames and traces. These are diagnostic builds only; the portable and
single-image acceptance jobs still build committed product source. This tests
cache isolation and fractional placement without silently promoting either
experiment or changing pixel tolerances.

At `69b3feb`, the isolated-factory diagnostic passed all five processes and
all scenes. Each initial U+00C4 tile was `c665072c90a9e969`; the shared-factory
control still failed. Pixel-aligned centering also failed (96 changed channels,
maximum 33), so it was discarded. `cluster-ci-isolated-diagnostic.json` and
`cluster-ci-aligned-diagnostic.json` retain the labelled results. Full traces
and exact experimental source are in [the CI artifacts](https://github.com/xiongnemo/nemoterm/actions/runs/43336395825).

The integrated fix uses one isolated DirectWrite factory shared only among
Nemoterm's live cluster renderers in the current UI thread. This preserves
cache reuse across tabs without using the cross-process shared-factory state
implicated by the controlled experiment. Per-window layouts, formats and
scratch targets remain independent; the final renderer releases the factory.
The native offscreen test now closes the original cache owner while a sibling
continues drawing, then recreates the factory after its last owner closes.
Microsoft documents [isolated versus shared factory state](https://learn.microsoft.com/en-us/windows/win32/api/dwrite/ne-dwrite-dwrite_factory_type);
the observed raster discrepancy's internal Windows implementation is not
otherwise established. Centering geometry and pixel tolerances are unchanged.

Local development frontend
`f9241a8737c9756514725de921882fd640e16090d4c2aa19c6476ac31d636a90`
passed the extended offscreen lifetime check, the five-process Consolas check,
and actual GDI/OpenGL/DirectX Sarasa pixel checks. Dense 160x48 GDI/top tabs
passed with a sampled private peak of 9,416,704 bytes (total 33,669,120).
The first DirectX/left attempt failed at cycle 9 on handle counts: 480 to 493
kernel handles and 43 to 46 USER objects, with GDI objects unchanged at 37.
Its failure JSON is retained. An unchanged fresh repeat passed all nine groups,
including all 12 create/close cycles and clean owned-process shutdown, at
19,640,320 private bytes (total 58,224,640). This single transient handle-count
failure is not explained by the repeat and must remain visible in acceptance
notes. Resource thresholds were not relaxed. All memory samples precede
instrumentation and exclude child processes and hover-preview peaks; this
development frontend is not the final embedded single-EXE artifact.

## Remaining failures after the isolated-factory fix

At `4c93714`, MSVC's repeated renderer diagnostic is green and the portable
job passes the cluster/clipboard, all tab sides, dense tabs and embedded-icon
checks. It later fails one synthetic Ctrl+click in the hyperlink fixture.
The single-image build passes that hyperlink test, the native cluster cases
and GDI/top, GDI/bottom and DirectX/left tab groups. It then reports an access
violation (`0xc0000005`) while closing the original tab in the OpenGL/right
case, which actually uses GDI on CI. Both failure JSON files are retained.
Neither workflow is green, and no artifact is promoted.

The unverified single image is 4,397,056 bytes, SHA-256
`551bae249c30584df644511224b89baed10507d13b4a4a33c4ccd65ba2e86b86`.
Locally it passes the actual OpenGL/right tab case and eight GDI/right repeats
at CI's 88x35 grid and Consolas font. The eight repeats used an external
ProcDump monitor, exited normally and produced no crash dump. These negative
reproductions do not dismiss the CI access violation. Disposable CI runners
now retain application-scoped Windows minidumps and Application Error events;
the fast MSVC job repeats the failing tab scenario eight times. The normal
executable does not acquire diagnostic code or an extra dependency.

A local observation-only hyperlink trace captured 255 queued mouse-leave
messages immediately after synthetic hover messages. This independently
confirms that mixing desktop tracking with SendMessage's synthetic modifier
state makes the old fixture unreliable; it does not establish the exact
message that cancelled the earlier CI click. The fixture now models pointer
tracking inside its owned HWND, drops queued desktop motion/leave messages,
and retains sent mouse gestures, button messages, focus and capture cancellation.
It no longer moves its window under the user's cursor. Local activation and
all four app-mouse modes pass. The explicit local activation-only option never
opens the clipboard, and is rejected in CI. Full CI still tests the real
clipboard and all link actions. Instrumented memory is labelled and retains
the existing 20,000,000-byte assertion.

Visual review also found absent Hebrew glyphs in the native parity scene.
An owned 40x8 GDI/Consolas comparison of the accepted `a108894f` executable
and development `f9241a87` produced identical pixels, so this is an existing
limitation, not a newly established cluster regression. GDI reports no Hebrew
glyphs in Consolas or Sarasa, while Segoe UI and Arial provide them. PuTTY's
`exact_textout` intentionally disables font linking for RTL runs. A separate
RTL fallback fix and glyph-presence assertions remain required; agreement
among compositors alone is not proof that every script rendered correctly.
