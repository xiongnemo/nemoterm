# Grapheme implementation and verification

`feature/graphemes` now shapes complete bounded clusters and supports
application-negotiated DEC mode 2027. The initial width policy remains the
legacy scalar policy for compatibility. This is development-branch evidence.
The accepted single-EXE artifact remains source `8f7a9d2`, SHA-256
`a108894f50f7d797f7d2c01558a71f268a1c812fe365270e5a6a7fb7868ca4ed`.
Do not replace it with the local MinGW frontend.

## Baseline and bounded terminal cells

`observe-graphemes.py` measured the earlier single-EXE build from `fffc8bb`,
hash `60f32c8bb844ba11e0493a81417cb6b7666e86c7191861fa2fb89d0300b01c1c`.
`grapheme-baseline.json` and `.png` retain its native ConPTY/Sarasa observations:
skin-tone and woman-technologist sequences occupied four columns, family eight.

`nemo_grapheme.c` implements allocation-free streaming extended grapheme
segmentation for [UAX #29 revision 49](https://www.unicode.org/reports/tr29/tr29-49.html)
using pinned Unicode 18.0.0 inputs. Six bytes of segmentation state retain RI
parity, emoji-ZWJ context and the revised Indic linker rule across input batches.
The 977 generated ranges also contain emoji and East Asian width properties;
Hangul syllable properties are computed. Invalid scalars are isolated replacement
clusters, outside the official valid-scalar corpus. The offline generator checks
all input SHA-256 hashes. Unicode's license is included in portable and embedded
single-EXE notices. No ICU dependency is introduced.

The existing PuTTY Unicode 16 wcwidth tables remain the legacy path. Cluster
width takes the widest member, uses pinned wide/fullwidth and emoji-presentation
properties, permits eligible VS16 widening, respects ambiguous-width settings,
and never retroactively shrinks a cell. Cells reuse PuTTY's extension chain:
one base plus at most 32 extensions, including positive-width members. Overflow
produces a fixed replacement. Movement, edits, screen switches, resizing and
trust changes terminate pending attachment; SGR and queries preserve the first
member's style. Late widening reserves a second cell or wraps the whole cluster;
when two cells cannot fit, it produces a bounded replacement.

REP retains a bounded copy independently of the source cell's later erasure.
Each repeat starts a new cluster; omitted and zero counts mean one in both width
policies. Storage and copying retain the original Unicode sequence.

## Windows drawing and negotiation

`windows/nemo_cluster.cpp` loads system DirectWrite/GDI interop lazily and draws
complete clusters into one bounded tile shared by GDI, OpenGL and DirectX.
Ordinary runs retain GDI drawing. An NFC rendering copy makes canonical forms
and Hangul Jamo shape consistently without changing stored or copied Unicode.
Emoji clusters select Segoe UI Emoji as a whole; other clusters use the chosen
font and system fallback. Natural advance is fitted into the allocated cells.
Caller clipping, viewport, colors, concealment, decorations, bold and DEC
width/height geometry remain in effect.

Input is bounded to 66 UTF-16 units and raster scratch to 65,536 pixels (256 KiB).
Old raster storage is released before resizing, layouts are transient, and the
renderer is freed with its window. This scratch cap excludes DirectWrite font
caches and other process allocations. Invalid input, oversize tiles or system
API failure uses a width-preserving replacement. No additional DLL/font ships.
The renderer uses the process heap and builds without exceptions or RTTI.
Import-table verification rejects compiler runtime DLLs in the portable build;
the MSVC single-image build already uses its static runtime.

Outlines are currently monochrome. The installed Segoe UI Emoji renders the
Australian regional-indicator pair as `AU`, not flag artwork. Correct two-cell
cursor advance does not prove every font supports every ZWJ sequence. Missing
sequence and color-font policy remain work.

Windows advertises mode 2027; other frontends do not. `CSI ? 2027 h/l` changes
the width policy, DECRQM reports set/reset/unsupported, and XTSAVE/XTRESTORE
saves/restores it. DECSTR and RIS reset the current state. As with the existing
saved slots, an explicit restore after RIS can restore an earlier saved state.
Already stored clusters still draw as whole cells after width mode is disabled.
The [terminal Unicode core draft](https://github.com/contour-terminal/terminal-unicode-core/blob/master/spec/terminal-unicode-core.tex)
is the protocol reference; this is not a claim of universal adoption.
A GUI choice for initial width policy is not yet implemented.

## Verification and limits

At `db133116bdaa4361e6daed58b88e8c69ff72e877`, before native drawing/mode
integration, [core CI](https://github.com/xiongnemo/nemoterm/actions/runs/43321902110)
and [single-EXE CI](https://github.com/xiongnemo/nemoterm/actions/runs/43321902294)
passed. Windows and Linux ASan/UBSan exercised cell integration. Those results
do not validate the subsequent native changes.

The native changes passed all 35 local MinGW Release test executables and the
pinned table check. Segmentation tests include 853 official vectors with every
input split, million-scalar streams and invalid scalars. Core tests cover 13
shapes, fragmented UTF-8, margins, insert/overwrite, half-wide erasure, exact
copy, alternate screens, 10,000-member overflow, history reflow, rectangle copy,
REP and mode query/set/reset/save/restore.

The offscreen native test checks fallback, NFC pixel equivalence, unchanged
input, exact clipping/viewport, double-height halves, double-width scaling,
shadow bold, invalid input, scratch bounds and stable GDI handles over 100 size
changes. It does not prove arbitrary-font visual correctness.

`grapheme-window-observed.json`, `grapheme-font-window-observed.json` and selected
PNGs record local frontend SHA-256
`0329acc26b1cb0ab54d1b605c7b139cff5d11242be64fd7309aa5759ad5ac256`.
Both native fixtures passed using SarasaTermSC Nerd Font Light with actual GDI,
OpenGL and DirectX required. Checks cover exact ConPTY cursor replies, late wrap,
REP, legacy widths, compositor pixel parity, synchronized saved frames, grid and
font resizing, and owned-job cleanup. The existing renderer regression passed
text, Sixel, palette, cursor states, synchronization and resize too. Tests use
owned HWNDs, with no foreground changes or global keyboard input.

Before capture instrumentation, sampled private working-set peaks across the
two 80x24 fixtures were 5,652,480 bytes (GDI), 32,038,912 (OpenGL) and 14,581,760
(DirectX). OpenGL has the user's memory exception. These are single-window
local development observations, not single-EXE/default-160x48/tab-preview/long
workload acceptance; child memory is excluded. JSON retains total working set
and private commit too.

Native clipboard checks were skipped locally because this desktop denies
OpenClipboard. CI requires exact original Unicode from Shift-Ctrl rectangle
selection and Ctrl-Shift-C in live and frozen synchronized frames, while app
mouse tracking is enabled. An input barrier checks that no mouse/copy key was
forwarded. Ordinary and font-resize fixtures are wired into both CI workflows;
results for the native change are pending. Core copy tests do not substitute
for this native clipboard check.

Remaining acceptance: new CI and actual single-EXE artifact, default-size/tabs
memory, initial-policy settings, wider missing-font/ZWJ/color behavior and real
agent workloads. This checkpoint is not complete Unicode/protocol coverage.

## Reproduction and original probe

Run `python scripts/generate-grapheme-tables.py --check`. Build CMake targets
`test_grapheme`, `test_grapheme_terminal` and `test_cluster_renderer`; pass
`tools/unicode/18.0.0/GraphemeBreakTest.txt` to `test_grapheme`.
Run `python tests/grapheme_window_smoke.py` and again with `--font-resize`, using
`NEMOTERM_TEST_EXE` for the intended binary.

The original standalone `probe-dwrite-clusters.cpp`, `dwrite-clusters.jsonl` and
PNG retain font-face/glyph observations. The probe is not product code; its
4,108,288-byte private working-set peak is not an additive terminal cost estimate.
Microsoft's [GDI surface guide](https://learn.microsoft.com/en-us/windows/win32/directwrite/render-to-a-gdi-surface)
and [bitmap glyph API](https://learn.microsoft.com/en-us/windows/win32/api/dwrite/nf-dwrite-idwritebitmaprendertarget-drawglyphrun)
describe the bridge used by the integrated renderer.
