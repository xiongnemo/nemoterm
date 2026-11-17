# Pinned ReGIS source

These original files come from XTerm commit
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f`:

| File | SHA-256 |
| --- | --- |
| graphics_regis.c | `a14512193dccdf25fb230da82698ceb7b522c45dc6fd892842dfcbb026af8109` |
| graphics.c | `e2c758da0d4b91463b1241575e6abf7f7c7792070d0f159824a6ae9b86dd8a7c` |

Their bytes match the original source files retained by hosted reference run
`44093439244`. Each file contains its copyright and permission notice.

`scripts/import-regis-parser.py` generates the native parser and colour
conversion includes in `vendor/putty-0.85/terminal`. The adapter removes X11
dependencies and global parser, spline and scratch state. It adds per-owner
accounting, sparse indexed pages, request limits and a native glyph callback.
Generated files preserve the upstream notices.

This is **development code, not advertised terminal support**. DCS framing,
shared image accounting and Windows glyph callbacks are now connected.
Image placement, rendering, erasure/scrolling and native acceptance remain
unfinished. The hosted component comparison passes its 70 original frames
with independent upstream Xft glyph inputs; native Windows font validation
is a separate gate. See `research/regis-native-component.md` and
`research/regis-terminal-input.md` for failures, current results and scope.
