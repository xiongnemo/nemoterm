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
