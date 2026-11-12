# Embedded symbol fallback and RTL paint allocation lifetime

The installed SarasaTermSC Nerd Font Light has native U+E0B0 but no U+F120,
U+F07B, U+F0001 or U+F0002 in its Unicode cmap. The implementation now uses
the unmodified Symbols Nerd Font Mono v3.5.1 only for a character absent from
the selected primary font and present in the symbol font. It preserves primary
text, GDI system linking for other scripts, terminal cell advances and original
Unicode clipboard text. This does not claim complete emoji/grapheme or generic
font-fallback coverage.

The font is pinned at Nerd Fonts commit
`b894ea7803af6aade63d60a4381e006098ec9c4d`, SHA256
`fe471e538392f51910faab985fa8e192a39dd3426125edd15b71b3680df0e749`, 2,610,012
bytes. [Upstream Symbols Only](https://github.com/ryanoasis/nerd-fonts/tree/b894ea7803af6aade63d60a4381e006098ec9c4d/patched-fonts/NerdFontsSymbolsOnly)
supplies the font and MIT licence; its icon-source attribution and additional
component notices are retained under `vendor/nerd-fonts` and embedded in the
single executable's licence resource. The MinGW comparison bundle carries
the notices as separate text files.

The EXE resource is mapped directly. Registration through
[AddFontMemResourceEx](https://learn.microsoft.com/windows/win32/api/wingdi/nf-wingdi-addfontmemresourceex)
occurs only on the first required fallback and is private to that process.
No system font installation or extracted sidecar is needed. The headless host
does not register the font. Each GUI font lifecycle holds at most eight fallback
HFONTs and one primary supplementary-plane cmap, capped at 1 MiB. Font reset
and window destruction release fonts, registration and cmap storage.

BMP coverage uses the selected GDI font's glyph lookup. Supplementary-plane
coverage uses its actual OpenType cmap rather than treating UTF-16 surrogate
halves as glyphs. The allocation-free parser supports Unicode formats 4, 12
and 13, prefers the full-repertoire table, and bounds every offset/length.
Unknown vector/device-font supplementary coverage conservatively keeps the existing font.
Legacy bitmap faces have no supplementary-plane glyphs and use the symbol
fallback even though `GetFontData` cannot return a cmap. The first CI run
exposed this distinction: absent Sarasa resolved to raster Courier and both
supplementary icons initially rendered as the same missing-glyph box. A local
explicit Courier regression reproduced the failure before the fix. The native
core suite now exercises Consolas, raster Courier, requested Sarasa and an
intentionally absent family, records the actual face and checks its coverage.
Surrogate pairs and variation selectors stay together during run splitting;
fallback icons use verified glyph indices, are clipped to their own cells and
inherit colour/style. Windows does not re-map supplementary icon text a second time.

The portable cmap suite checks known upstream glyph indices, BMP range/delta
forms, supplementary mappings, absent characters, every truncated prefix and
malformed offsets. The native GDI suite checks primary-glyph preservation,
the actual selected fallback face, supplementary lookup and cache handle release.
The ConPTY window fixture checks four distinct rendered icons, unchanged adjacent
text, BMP/supplementary variation selectors, exact Shift-copy Unicode under
application mouse tracking, 32 resize cycles, restoration of primary pixels and 6,144 separately painted
distinct supplementary symbols.

Source inspection also found two unfreed temporary buffers in `exact_textout`,
the path used for already-reordered RTL text. Both now release after the GDI
draw. With the same 5,000 forced full RTL repaints, the previous single EXE
`66665c6df4140dac9f52488c79435376a3d0434bebf12ddbb7328d7db018bd12` grew from
6,778,880 to 15,147,008 bytes private commit. The fixed MinGW executable
`b8169ee7655b118143db53817043fcb5f11237c5f4295e02cf4639c6b1b43353` grew only
from 6,422,528 to 6,434,816 bytes after the same warm-up and repaint count.
The regression rejects growth of 2,000,000 bytes or more. Run it independently
with `python tests/font_fallback_window_smoke.py --rtl-only` and an explicit
`NEMOTERM_TEST_EXE` when comparing artifacts.
Use `--font Courier` to exercise bitmap-primary fallback independently of which
fonts the machine happens to have installed.

All 26 core suites passed locally. The complete new window fixture passed on
the fixed executable above: peak private WS 4,907,008 bytes (4.907 MB /
4.680 MiB), total WS 31,219,712 bytes (31.220 MB / 29.773 MiB), private commit
6,443,008 bytes (6.443 MB / 6.145 MiB). These are sampled frontend peaks for
this workload, with no working-set trimming; host and child are separate.
Single-executable CI recompiles the embedded font and runs the new window
fixture alongside the existing native groups. Its exact artifact/evidence
digest is recorded in the CI validation manifest.

After the raster-font correction, local executable
`5ae1e95a6f610e8cb2e60a02d0e979a28f6d5303ae3b65833b0132f5ce70f5ae`
passed the complete fixture with both Courier and Sarasa. Courier peaks were
4,182,016 / 30,339,072 / 5,816,320 bytes (private WS / total WS / private commit);
Sarasa peaks were 4,939,776 / 29,147,136 / 6,471,680 bytes. Both completed the
same 32 resize cycles, 6,144 symbols and 5,000 RTL repaints. Each CI pipeline now
also runs an explicit Courier variant; the single-file validation has 24 checks
(21 native groups and three font/keyboard variants).

The previously observed intermittent local hyperlink fixture timeouts remain
unresolved: no source or timing change here is claimed to fix them. They occurred
at different hover/open waits, with a subsequent instrumented run passing.
