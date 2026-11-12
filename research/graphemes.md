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
context and the revised Indic linker rule across input batches. The 843
generated ranges occupy 10,116 bytes with the tested compiler. Hangul syllable
properties are computed rather than stored as hundreds of alternating ranges.
Invalid scalar values form isolated replacement clusters. This policy is
outside UAX #29's valid-scalar test corpus.

The generator is offline and verifies all pinned inputs against their SHA-256
manifest. The original Unicode license accompanies the data and is included
in portable packages and the single-EXE embedded notices. No ICU or other
runtime dependency is introduced. Existing PuTTY Unicode 16 wcwidth tables
remain separate until the terminal's width policy is implemented.

Local strict C11 compilation passed all 853 official `GraphemeBreakTest.txt`
vectors, stream splits, million-scalar combining/RI streams, invalid scalars
and explicit reset. Windows CI runs the same corpus; Linux CI adds ASan/UBSan.
Those CI results must be checked before claiming CI verification.

## Still required before enabling a terminal mode

- Attach complete clusters to screen cells, with bounded storage and defined
  over-budget replacement, including delayed extensions across output batches.
- Choose and expose legacy versus cluster width policy; implement late VS16
  widening and right-margin/wrap handling without corrupting neighbouring cells.
- Shape the complete cluster with installed system font fallback in GDI,
  OpenGL and DirectX paths, including emoji ZWJ, regional flags, Indic and Jamo.
- Preserve clusters through copying, rectangle selection, editing, reflow,
  scrollback, saved screens and synchronized updates; test erasure of either
  half of a wide cluster.
- Implement and test mode 2027 query/set/reset/save semantics only once the
  full terminal behavior exists. The segmenter is currently test-only and the
  frontend does not advertise mode 2027.

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
