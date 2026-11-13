# Sixel capability queries and color register count

XTSMGRAPHICS now answers `CSI ? Pi ; Pa ; Pv S` with the implemented
capabilities. Item 1 reads, resets, sets or reports the maximum Sixel register
count. The default and maximum are 256; valid settings are 2 through 256.
Color register selection and definition wrap modulo that setting, as in the
pinned xterm decoder. A change applies to subsequent images and leaves existing
rasters unchanged. RIS, DECSTR and alternate-screen transitions preserve the
setting; XTSMGRAPHICS action 2 explicitly resets it.

Item 2 reads the current pixel viewport or the maximum per-axis dimension,
8192. Current geometry follows the live grid and cell metrics, clamped to that
limit. Products use 64-bit arithmetic before clamping. Setting or resetting
the fixed geometry limits returns failure. The 4 MiB shared image allocation
budget remains enforced: a per-axis limit is not a promise to allocate an
8192 by 8192 raster. ReGIS and unknown items return invalid-item status;
unknown actions return invalid-action status. As in the reference, only an
exact item/action/value triple is dispatched.

## Independent reference

`graphics-query-xterm.json` records 41 cases from XTerm 412 under private Xvfb,
using upstream source `5c75ead9a75d4b2e666ca06fa94503b5766ed93f`. The reference
executable SHA256 is
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
Thirty-four cases compare exact replies in both the core and native tests.

Seven cases are deliberately separate: register maximum/default and values
257/1024 depend on the implementation (the reference permits 1024); current
and maximum geometry depend on resources/window metrics; an omitted item is
reported as zero by Nemoterm, while this xterm emits its sentinel as 65535.
The raw reference is retained unchanged. Direct assertions cover Nemoterm's
own limits, error replies and live geometry. Invalid and incomplete requests,
colon syntax, cancellation and reset/alternate-screen persistence are covered.

Reference behavior is documented in the official
[xterm control sequences](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
and implemented in pinned
[charproc.c](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/charproc.c)
and [graphics_sixel.c](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/graphics_sixel.c).

## Validation and artifact

All 35 MSVC core/offscreen suites passed. The focused query, Sixel decoder and
Sixel terminal integration suites also passed MinGW and Linux ASan/UBSan with
leak detection. Decoder tests include 20,000 bounded fuzz cases, palette index
wrapping, reset/default behavior and invalid setter arguments. Integration
checks confirm that existing rasters retain their data after a count change.

The local single image passed 34 native reference cases, three direct cases,
live geometry queries before/after owned-window resize, and exact palette
pixel checks. The 80x24 grid at 8x20 pixels reported 640x480; the resized
83x22 grid reported 664x440. A 32x12 raster contained 384 red pixels with two
registers, stayed byte-identical after switching to 256 registers, and contained
192 red pixels when redrawn under the new setting. The final capture was
visually inspected. The owned job drained naturally with zero active processes.

The existing native Sixel scroll/resize/erase/history/alternate-screen suite
and isolated single-EXE/same-image-host checks also passed. This finite Sixel
fixture sampled peak frontend private WS 2,785,280 bytes, total WS 15,040,512
bytes and private commit 3,596,288 bytes, without trimming. These are fixture
measurements, not full-workload or process-tree acceptance.

Test image: `build/local-graphics-query-check/dist/nemoterm.exe`, 4,418,048 bytes,
SHA256 `502d09b073d58cf49abe1801a2c5bbeab26f072f6ec09de56898241f92c9d9b7`.
`graphics-query-validation.json` records source hashes, the initial failing
query regression, suite output and exact native evidence. CI includes the new
generator check and native fixture in both relevant Windows paths; required
clipboard and real-agent tests remain enabled. GitHub account billing has
prevented recent jobs from starting. This local image has not replaced the
accepted main distribution or closed those outstanding acceptance gates.
