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

This is an **unwired component**, not advertised terminal support. Framing,
shared image ownership, erasure/scrolling, fonts and native acceptance still
need integration. The hosted comparison currently retains a font mismatch as
a failure; see `research/regis-native-component.md`.
