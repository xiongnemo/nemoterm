# ECMA-48 ideogram decoration checkpoint

This branch adds SGR 60 through 65 on integration base `9e7549b`. The source
reference is [ECMA-48, fifth edition, section 8.3.117](https://www.ecma-international.org/wp-content/uploads/ECMA-48_5th_edition_june_1991.pdf),
printed pages 61-63 (PDF pages 75-77). The downloaded 1,607,865-byte PDF has
SHA-256 `9577ad2514c411584b274ef7a4b3238c80aa93defbb349b18b8c78f78873f450`.
The standard leaves usable combinations to the implementation.

## Behavior and representation

The five independent aspects are underline (60), double underline (61),
overline (62), double overline (63) and stress marking (64). SGR 65 clears all
five, preserving ordinary underline, enclosure, overline and colour settings.
SGR 0, DECSTR and RIS clear them. Saved cursor, alternate screen, compressed
history, resize/reflow and whole rendition-stack frames retain the same state.
Selective stack selectors 60-64, DECRQSS and common-rectangle reports include
these aspects as explicit Nemoterm extensions; this is not an XTerm parity claim.

This horizontal terminal draws strokes along the logical cell's bottom or top,
and a small square stress mark centered near its top. With thickness
`t = max(1, font_height / 16)`, double strokes occupy offsets 0 and 2t from the
corresponding edge. The stress square is 2t wide/high, bounded by the cell, with
its top at offset t. This geometry is project policy. It does not implement
vertical writing or script-specific emphasis positioning.

The renderer uses the text foreground (including inverse), skips concealed
decorations, and clips double-height halves from one logical decoration. Wide
cells and combining clusters share one stress mark. All three backends use
the existing raster path. Drawing uses stock GDI objects with no retained new
object or dependency. Bits 35-39 of the existing 64-bit decoration field hold
the state: `truecolour` stays 16 bytes and Windows `termchar` stays 32 bytes.

## Verification

Before implementation, the previous integrated image failed the new GDI bottom
stroke check and the old parser failed the new query cases. Those observations
and original fixtures are retained. One expected DECRQSS string initially used
colon notation for indexed underline colour; it was corrected to the existing
semicolon reply format. That fixture correction is distinct from the missing
ideogram implementation, and the original failed output remains available.

After implementation, six core suites (`test_sixel`, `test_sixel_terminal`,
`test_sgr`, `test_queries`, `test_state_control`, `test_rectangle`) pass Linux,
ASan/UBSan with leak detection, and MSVC. The generated SGR fixtures and resource
timing unit tests pass. The strict C99 Sixel decoder build/test also passes.

The locally linked single executable is 4,511,744 bytes, SHA-256
`7f3a9933200be5f50a25a7e8fe69683fb04db56621455ed5b57195308a6b06b8`.
It uses freshly built frontend libraries and the previously validated host
objects, not a new full-source CI build. Native checks use this exact image and
SarasaTermSC Nerd Font Light:

* Twenty scenes pass on each actual GDI, OpenGL and DirectX backend. The two new
  scenes check every pixel of individual/combined/cancelled/hidden/inverse
  decorations, wide cells and double-size rows. Combining text also participates
  in backend parity. New ideogram scenes have zero differing channels.
* All 283 protocol cases pass through real ConPTY: 193 unchanged XTerm references
  and 90 extension cases, including 44 new ideogram cases. The existing auxiliary
  exercise adds 44 scene/read-only/resize exchanges (327 recorded exchanges).
* Both full nine-group tab workloads pass at actual 160x48, including twelve
  create/close cycles, menu ownership, sibling lifetime and renderer transfer.

| Workload | Samples | Private WS peak | Total WS peak | Private commit peak |
| --- | ---: | ---: | ---: | ---: |
| GDI | 531 | 16,183,296 | 42,967,040 | 19,357,696 |
| DirectX | 515 | 23,834,624 | 63,328,256 | 87,130,112 |

Values are bytes. Private working sets satisfy the current limits; DirectX total
working set remains above the approximate 50 MB target. Startup and bounded
resource-wait samples are included, without working-set trimming. Memory
sampling precedes pixel-helper instrumentation. This is an observed workload,
not an attribution of run-to-run variation to this change.

Each full workload drains all 58 outer processes naturally; renderer and wire
controllers similarly drain all 11 and 5 processes. No owned process survives,
and no existing user terminal is controlled.

The [manifest](sgr-ideogram-validation.json) verifies 160 compressed records
(1,382,130 bytes), including compiler logs, original failures, exact pixels,
queries, memory samples, cleanup and link-input/source hashes. These are local
observations, not REA-server Evidence. Full branch CI and downloaded-artifact
verification subsequently passed in the [accepted artifact checkpoint](sgr-ideogram-ci.md).
The earlier local image above is not reassigned that artifact identity; the
broader terminal compatibility goal remains open.
