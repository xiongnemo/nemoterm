# ReGIS and Tektronix source review

This is a source-only investigation, not implemented protocol support or a
passing runtime check. The current production candidate remains `329019d`;
its ongoing full regression is not superseded by this review.

## Pinned upstream

Use XTerm commit `5c75ead9a75d4b2e666ca06fa94503b5766ed93f`, the same revision
as the existing hosted reference collectors. Relevant upstream files are
[graphics_regis.c](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/graphics_regis.c),
[graphics.c](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/graphics.c), and
[Tekproc.c](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/Tekproc.c).
Their file-specific copyright and permission notices must accompany any
adapted code; Tekproc also contains the original DEC notice.

The [control-sequence reference](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
describes ReGIS DCS entry and the separate Tektronix mode. These are separate
parser and display mechanisms, not additional Sixel encodings.

## Integration constraints found in source

* ReGIS uses process-global `persistent_context` and `persistent_state`.
  Nemoterm must give each terminal its own lazily allocated state: sharing
  these globals across profiles or tabs would mix independent sessions.
* `parse_regis` consumes a complete NUL-terminated string, allocates a scratch
  buffer of its length, and preserves state across requests. Modes 1 and 3
  reinitialize that state. The integration needs explicit input, work and
  memory bounds, including cancellation and split-transport tests.
* The ReGIS context includes eight alphabet slots and a 2,048-point fill
  buffer. Graphics pages, font rasterization and repaint scheduling depend
  on XTerm/Xlib. Importing the complete file would not supply a native Windows
  backend. Rendering adapters and page ownership must use the existing shared
  raster budget and terminal lifecycle.
* Upstream ReGIS emits replies through `unparse*` functions and periodically
  refreshes graphics while parsing. Both output transport and scheduling need
  native adapters; a decoder that only draws lines would leave these behaviors
  unimplemented.
* Tekproc has its own parser, X11 widget and input/display handling. Its status
  replies, graphics input, mode transitions and retained drawing operations
  need a separate implementation and reference matrix.

## Next evidence boundary

Before changing production, add a hosted collector that explicitly enables
ReGIS in the pinned XTerm build and retains its effective configuration,
binary identity, original input, replies and framebuffer captures. Begin with
mode/reset/resume behavior, position reports, drawing and page selection;
keep text/font and mouse-driven requests separately identified. Include
ordinary text controls and process cleanup. All reference execution remains
on GitHub-hosted Linux runners, followed by native Windows product checks
only after an implementation exists.

The coverage ledger continues to mark both families **Missing**. No new
capability is advertised and no memory result is inferred from this review.
