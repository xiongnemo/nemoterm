# Grapheme implementation checkpoint

The shipped frontend advances by scalar width and draws combining members
separately. `observe-graphemes.py` measured the actual single-EXE build from
tabs commit fffc8bb, hash
`60f32c8bb844ba11e0493a81417cb6b7666e86c7191861fa2fb89d0300b01c1c`, using native
ConPTY cursor-position replies and SarasaTermSC Nerd Font Light.
`grapheme-baseline.json` and `.png` preserve the result: a skin-tone sequence
and woman-technologist sequence each occupy four columns; the family sequence
occupies eight. Flags, keycaps and variation-selected symbols also need width
and shaping work. This is not complete grapheme support.

`nemo_grapheme.c` is an allocation-free streaming extended-grapheme segmenter
for [UAX #29 revision 49](https://www.unicode.org/reports/tr29/tr29-49.html),
using Unicode 18.0.0 data. The six-byte state preserves RI parity, emoji-ZWJ
context and the revised Indic linker rule across input batches. The 977
generated ranges include emoji and East Asian width properties. Hangul syllable
properties are computed rather than stored as hundreds of alternating ranges.
Invalid scalar values form isolated replacement clusters. This policy is
outside UAX #29's valid-scalar test corpus.

The generator is offline and verifies all pinned inputs against their SHA-256
manifest. The original Unicode license accompanies the data and is included
in portable packages and the single-EXE embedded notices. No ICU or other
runtime dependency is introduced. Existing PuTTY Unicode 16 wcwidth tables
remain the legacy path. The staged cluster policy takes the widest member,
uses the pinned wide/fullwidth and emoji-presentation properties, and permits
an eligible VS16 to widen a cluster. It preserves the caller's ambiguous-width
choice and never retroactively shrinks an already occupied cell.

Local strict C11 compilation passed all 853 official `GraphemeBreakTest.txt`
vectors, stream splits, million-scalar combining/RI streams, invalid scalars
and explicit reset. Windows CI runs the same corpus; Linux CI adds ASan/UBSan.
At source commit `ca1c2805441b8942fb49009899810f467bc5fa1f`,
[Windows and sanitizer CI](https://github.com/xiongnemo/nemoterm/actions/runs/43315470393)
passed, with both jobs recording all 853 vectors and bounded-stream checks.
[Single-EXE CI](https://github.com/xiongnemo/nemoterm/actions/runs/43315470225)
also passed. Those runs validate the standalone segmenter and unchanged
frontend regressions, before cell integration. Later commits add the offscreen
shaping probe, local test-command wiring and the accepted tab baseline; their
CI is separate. At `b421983`, Single-EXE CI passed (43318199242), while the
portable Windows run (43318199252) timed out resolving the newly opened tab
content HWND in the settings fixture, after the child's exact query replies
had already passed. That run is not a full green baseline.

## Staged terminal cells

`term_set_grapheme_clustering` enables the core only from the unit harness.
The frontend still defaults to legacy behavior, exposes no setting for this
work, and does not advertise mode 2027. Complete-cluster shaping is not yet
connected to the frontend, so this checkpoint is not a user-visible emoji fix.

Cells reuse PuTTY's bounded extension chain for all cluster members, including
positive-width members. A cell stores one base plus at most 32 extensions;
excess input becomes a fixed replacement cell. Transport batches preserve the
finite segmentation state. Cursor moves, editing, screen switches, resizing
and trust changes terminate pending attachment. SGR and status queries retain
the first member's cell style. Late widening reserves the second cell or
wraps the whole cluster, with a bounded replacement when two cells cannot fit.

REP retains a bounded copy of the last displayed cluster, independent of the
source cell's later erasure. Each repeat starts a new cluster; default/zero
counts repeat once in both width policies. The original raw input remains the
source for stored text and copy; normalization is a future rendering-only step.

Local MinGW Release verification passed all 34 test executables, including the
853 official segmentation vectors and `test_grapheme_terminal`. The latter
checks 13 shapes, fragmented UTF-8, late width changes at right/bottom/margins,
insert/overwrite, half-wide erasure, exact Unicode copy, alternate screens,
10,000-member bounded replacement, 40 retained clusters over repeated history
reflow, independent rectangle copies and REP after erasure/cursor movement.
The new core suite is wired into Windows CI and Linux ASan/UBSan; these local
results do not substitute for its subsequent CI run or native rendering tests.

## Still required before enabling a terminal mode

- Expose legacy versus cluster width policy only after complete native rendering
  and protocol semantics are verified, including visible behavior at margins.
- Shape the complete cluster with installed system font fallback in GDI,
  OpenGL and DirectX paths, including emoji ZWJ, regional flags, Indic and Jamo.
- Verify native rectangle selection, saved frames and synchronized updates with
  whole-cluster pixels, complementing the core copy/edit/reflow checks.
- Implement and test mode 2027 query/set/reset/save semantics only once the
  full terminal behavior exists. The frontend does not advertise mode 2027.

Run the table check with `python scripts/generate-grapheme-tables.py --check`.
Build `test_grapheme` through the existing CMake project and pass
`tools/unicode/18.0.0/GraphemeBreakTest.txt` as its sole argument.

## System shaping probe

`probe-dwrite-clusters.cpp` draws into an offscreen bitmap with Windows'
DirectWrite/GDI interop; it is not linked into Nemoterm. Its usage/build line
is in the source header. `dwrite-clusters.jsonl` records its executable hash,
Windows version, actual font faces, glyph IDs/advances and resident memory.
The PNG has automatic fallback in the left content column; the right column
uses an NFC rendering copy and selects Segoe UI Emoji for entire emoji cases.
The original Unicode strings must remain unchanged in terminal storage/copy.

The observed faces were SarasaTermSC Nerd Font Light, Segoe UI Emoji, Segoe UI
Symbol and Nirmala UI Semilight. DirectWrite formed whole skin-tone and
woman-technologist glyphs, plus a family composed of positioned glyphs.
Automatic fallback split the keycap between faces. Whole-sequence emoji face
selection fixed the keycap; NFC rendering composed the Hangul Jamo syllable.
The installed emoji font rendered the Australian flag as `AU` in both cases,
so automatic platform shaping alone does not supply flag artwork. This probe
uses monochrome outlines, not color-font layers. Natural glyph advance also
differs from a two-cell terminal width and needs bounded fitting.

The standalone probe's sampled peak was 4,108,288 bytes private working set
and 11,923,456 bytes total working set. These are not terminal memory results
or an additive cost estimate; integration still needs measurement in GDI and
the two GPU paths. The probe uses system DLLs and adds no shipped runtime.
Microsoft's [GDI surface guide](https://learn.microsoft.com/en-us/windows/win32/directwrite/render-to-a-gdi-surface)
and [bitmap glyph API](https://learn.microsoft.com/en-us/windows/win32/api/dwrite/nf-dwrite-idwritebitmaprendertarget-drawglyphrun)
describe this bridge. Bounded per-cluster shaping, fallback choice, optional
color layers, missing-sequence policy and glyph caching remain product work.
