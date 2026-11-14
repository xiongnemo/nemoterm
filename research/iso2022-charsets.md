# ISO 2022 mapping component

The new `nemo_charset.c` component supplies immutable designation descriptors
and Unicode mapping tables. **It is not yet connected to `terminal.c`: these
character sets are not new runtime capabilities of the current EXE.** Parser
state, input decoding, GL/GR/SS invocation, reset and cursor/presentation-state
round trips remain the next integration work. UPSS reassignment and legacy
non-Unicode Xlib glyph behavior are not implemented by this component.

The mapping repertoire includes the national sets and aliases, DEC supplemental
and technical sets, JIS Roman/Katakana, and the six ISO supplemental designators
listed in [XTerm's control reference](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html).
Descriptors retain alias spelling, 94/96 classification, NRC requirements and
terminal-level limits. Unknown or unavailable designations return no descriptor;
the parser must choose its recovery policy. The byte mapper does not parse
UTF-8 or control sequences and does not allocate memory.

Thirty 96-entry `uint16_t` mapping arrays use 5,760 bytes of static data before
descriptor/string/code storage. They are derived from the pinned XTerm 412
[mapping header](https://github.com/ThomasDickey/xterm-snapshots/blob/xterm-412/charsets.h),
whose complete license notice is retained beside the generated data. The
generator verifies SHA-256 for that header and the X11 keysym definitions.
Neither Python nor X11 becomes a terminal runtime dependency. The existing
PuTTY ASCII/UK/line/SCO byte-codepage behavior has not been changed.

## Reference capture and validation

All reference runs use a private Xvfb display and XTerm(412), EXE SHA-256
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
The byte-aware collector retains raw sent bytes and exact replies, with 96
one-cell Unicode checksum queries per stream. Four finite batches capture
320 designation/NRC/encoding/GL-or-GR combinations at level 5.

The first 80-stream attempt used the shared collector's `-u8` command-line
option, which locks UTF-8. It therefore does not validate switching via
`ESC % @/G`. A separate encoding probe demonstrates the problem: forced mode
decodes the same Chinese character both before and after `ESC % @`; the revised
unforced mode returns its three separate Latin-1 bytes after that switch.
The initial results remain retained as a fixture limitation, not passing data.

The revised collector permits runtime encoding changes and turns NRC off before
reset, then selects the base encoding before turning NRC back on. This avoids
carrying XTerm's temporary NRC/UTF-8 mode swap into the next case. The normal
legacy byte path and Unicode NRC path yield 160 mapping streams / **15,360
independently captured cells**, all matched by the component. Controls consumed
by the reference parser leave blank cells; those are distinguished from a mapped
character. The other 160 captured streams preserve encoding-mode behavior for
the forthcoming parser integration and are not claimed as mapper checks.

The level-5 captures do not exercise JIS rendering at its level-3-only setting
or the level-2-specific DEC supplemental designation. Boundary/unit assertions
check their availability, but their independent runtime mapping coverage remains
open. XTerm's NRC-disabled legacy glyph-index differences remain separate from
the Unicode mapping policy and must not be hidden when integrating the parser.

Validation completed:

- GCC strict C11 and separate ASan/UBSan/leak checks: 15,360 cells plus
  designation, alias, level and byte-boundary assertions pass.
- MSVC 14.44 `/W4 /WX /O1 /MT /std:c11`: the same checks pass.
- The new portable CMake `test_iso2022_charset` target configures, builds and
  passes under Linux.
- All 44 existing cursor/charset oracle streams exactly match the previously
  retained reference after extending the shared collector. Its default forced
  UTF-8 behavior remains unchanged for existing callers.

The [manifest](iso2022-charsets-validation.json) retains exact sources,
generator inputs, reference requests/replies, failed initial observations and
build/test logs. New MSVC, MinGW and sanitizer CI checks are registered; their
full branch run is pending. No terminal-memory acceptance or default-executable
promotion is claimed for this component checkpoint.
