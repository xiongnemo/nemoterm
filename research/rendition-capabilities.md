# Parameter-free rendition discovery

XTGETTCAP now reports eight literal sequences for already implemented styles:

| Names | Enter / leave |
| --- | --- |
| `smul` / `rmul` (aliases `us` / `ue`) | SGR 4 / 24, underline |
| `sitm` / `ritm` (aliases `ZH` / `ZR`) | SGR 3 / 23, italic |
| `smxx` / `rmxx` | SGR 9 / 29, crossed out |
| `Smol` / `Rmol` | SGR 53 / 55, overline |

Values are hex-encoded actual escape bytes, not printable backslash escapes.
Names are case sensitive. The existing combined-reply and unknown-name stopping
rules are unchanged. Querying a style does not enable or disable it, move the
cursor, or depend on whether colour is enabled. These are static literal values;
there is no new persistent allocation, service, or runtime dependency. Existing
2047-byte request and less-than-14-KiB response bounds still hold: `TN` remains
the largest expansion relative to its input length.

The definitions and aliases follow ncurses revision
`7404b376832583182c52722dc09d86b8675db375`:
[terminfo source](https://github.com/ThomasDickey/ncurses-snapshots/blob/7404b376832583182c52722dc09d86b8675db375/misc/terminfo.src)
and [capability names](https://github.com/ThomasDickey/ncurses-snapshots/blob/7404b376832583182c52722dc09d86b8675db375/include/Caps).
This whitelist does not advertise arbitrary terminfo programs or the
parameterized `Smulx` / `Setulc` and boolean `Su` extensions. Support for those
query names remains open even though the renderer already handles styled and
coloured underlines.

## Validation

The core `tcap` suite checks all twelve names with fragmented input, exact
values, unchanged current styles/colour/cursor, uppercase hex spelling, mixed
known/unknown lists and disabled-colour configuration. Existing keyboard,
malformed-request and response-expansion checks also run. The native query
fixture checks exact responses through ConPTY, decodes and replays the returned
sequences, and independently asks DECRQSS to verify the enabled and cleared
styles. The test targets a freshly created process and does not send global
desktop input.

The first local core attempt inherited the preceding test's disabled-colour
configuration; the rendition test now explicitly configures its initial state.
The first native replay expected the DECRQSS fields in numeric order; the
existing encoder emits italic, crossed-out, underline, overline. The expected
reply now uses that existing order. Neither correction changed product code.

Local `tcap`, SGR and query core suites pass, as does the full native cursor,
query and keyboard fixture with the twelve new names and replay checks. The
single image is 4,467,200 bytes, SHA-256
`ac83f2e022b60068d39e0e00a51d175f1c4a5e3ddeb68229d524ce2661e20a20`.
All five owned job members drained naturally. The
[evidence manifest](rendition-capabilities-validation.json) retains exact source
hashes, replies, logs, cursor images and the two corrected fixture attempts.
The existing cursor fixture instruments focus inside the owned process; its
memory readings are diagnostic, not memory acceptance or physical-display
acceptance.

Remote CI is pending. This change is not a renderer memory optimization and
does not replace the accepted local distribution.
