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
