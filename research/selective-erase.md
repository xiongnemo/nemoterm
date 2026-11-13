# DEC protected text and selective erasure

This is the original checkpoint record, not the current protection-family
specification. The later [presentation-state checkpoint](presentation-state.md)
superseded its DECSTR choice below; [ISO guarded-area development](guarded-areas.md)
adds SPA/EPA and further shared-erase changes with build-only evidence.

Implemented DECSCA (`CSI Ps " q`), its DECRQSS query, DECSEL/DECSED
(`CSI ? Ps K/J`), DECERA (`CSI top;left;bottom;right $ z`) and DECSERA
(`CSI top;left;bottom;right $ {`). Protection uses bit 29 of the existing
decoration word: no added per-cell allocation. SGR reset preserves protection;
cursor save/restore, alternate screens, compressed history and reflow retain it.
Ordinary erasure still clears protected cells. Selective erasure skips complete
protected wide glyphs and only removes Sixel pixels beneath cells actually erased.

`test_selective_erase` covers fragmented and malformed sequences, all line/page
ranges, cursor/pending-wrap, rectangles/origin/margins, wide/combining text,
styles, links, selection, history compression/reflow, and Sixel retention.
All 23 core tests passed locally; the new test also passed ASan/UBSan/leak checks.
The owned-window ConPTY fixture passed clipboard, pixel comparison, resize,
alternate-screen/reset, synchronized painting and 3000-line history scenarios.
Observed peak frontend private WS / total WS / private commit:
5,672,960 / 21,803,008 / 7,319,552 bytes (no trimming; host/shell separate).
The JSON records the exact executable used; this is not a measurement of the
later single-executable integration.

An independent XTerm(412) oracle recorded 22 cases in `selective-erase-xterm.json`.
Its source was commit `5c75ead9a75d4b2e666ca06fa94503b5766ed93f`, executable SHA256
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
The fixture reads cell checksums and reported SGR over a private PTY/Xvfb.

Explicit semantic choices:

* DECSEL/DECSED use BCE for erased cells; DECSERA preserves their visual attributes.
* DECERA follows XTerm's current-SGR behavior and preserves an old foreground or
  background when the corresponding current color is default. This differs from
  the DEC manual/Windows Terminal erase-attribute behavior.
* At this original checkpoint, DECSTR retained effective per-cell protection.
  The later presentation-state checkpoint replaced that choice with XTerm's
  family semantics: DECSTR ends the family without clearing the stored cell
  bits, allowing subsequent selective erasure until DEC protection is selected.
* Omitted rectangle coordinates in origin mode mean the full origin region.
  The oracle exposed XTerm(412)'s extra top-margin offset for omitted coordinates;
  this implementation uses the DEC coordinate definition.

References: [xterm control sequences](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html),
[DEC DECSERA](https://vt100.net/docs/vt510-rm/DECSERA.html),
[Microsoft adapter](https://github.com/microsoft/terminal/blob/f6de9e0618015def1c9dda5b82f9d3abf03eb799/src/terminal/adapter/adaptDispatch.cpp).
ISO SPA/EPA, left/right margins and rectangle copy/fill/attribute operations
were open at this checkpoint; later work is tracked in the protocol inventory.
These original tests do not validate those subsequent implementations.
