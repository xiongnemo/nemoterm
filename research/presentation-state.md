# Presentation-state reports and replay

The development frontend now implements cursor and tab-stop reports
(`CSI 1/2 $w`, DECRQPSR), their corresponding restoration strings
(`DCS 1/2 $t ... ST`, DECRSPS), and displayed extent (`CSI "v`, DECRQDE).
They require VT300-level compatibility, as in the independent reference.
Complete terminal-state serialization (`CSI $u`) is a different feature
and remains absent.

## Reference and exact comparisons

The reference is [XTerm 412 at
5c75ead9a75d4b2e666ca06fa94503b5766ed93f](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f),
with executable SHA-256
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
The [control-sequence specification](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.txt),
`charproc.c`'s DECRQPSR/DECRQDE handlers, and `misc.c`'s
`restore_DECCIR`/`restore_DECTABSR` functions define the comparison.
The [DEC VT420 programmer reference](https://vt100.net/mirror/mds-199909/cd3/term/vt420rm2.pdf)
provides the underlying presentation-report format.

`tests/xterm_presentation_state_oracle.py` captured 148 cases on a private
Xvfb display. The raw replies are unchanged in
`presentation-state-xterm.json`. The generator includes 142 exact cases
and declares six differences explicitly:

* Four SCO `U` designations are supported by PuTTY/Nemoterm, while this
  XTerm ignores them. Nemoterm reports the actual selected SCO bank.
* One existing DECRQSS reply orders equivalent SGR fields differently.
* Existing SUB cancellation emits no replacement glyph; the reference
  advances the cursor by printing its error glyph.

Ten direct cases cover those differences, modern underline interaction,
a tab string longer than the bounded query buffer, and all visible stops.
Unlike the reference's fixed reply-parameter array, Nemoterm does not
truncate a dense tab report to its first 26 entries.

## State semantics and memory

Cursor reports use absolute viewport coordinates, including under DECOM.
They encode the four legacy rendition flags, protection family, origin,
pending wrap, single shift, GL/GR bank selectors and supported G0–G3
designators. Colors and modern rendition fields are not part of this DEC
report. Restoration retains those unrelated fields and applies valid
fields in order; an invalid later field leaves the valid prefix applied,
matching the reference. Unsupported/overlong cursor payloads do not cause
input-sized allocations; the existing 2,048-byte query buffer bounds them.

Tab restoration parses the stream into a temporary bitset, allocated only
when a valid restoration header is received. It is sized to the retained
tab table, not the incoming string. Numeric accumulation saturates and
out-of-range stops are ignored. ST commits the result; CAN/SUB, another
escape sequence, RIS and destruction release temporary storage. The
visible tab table remains unchanged before ST. As in XTerm, column one
is not an explicit restored/reported stop.

The table retains at least 1,024 columns so that shrinking and growing a
window does not lose offscreen stops. Larger grids extend it to their
widest size. This is approximately 1 KiB for ordinary windows, plus a
128-byte temporary restoration bitset; cell storage does not grow.
Tests also exercise a 4,096-column grid and stop 3,001.

G2/G3 now accept the same ASCII, British, DEC line-drawing and SCO
designations as G0/G1. SS2/SS3 are one-shot GL shifts, and LS2/LS3 select
the corresponding GL bank. Queries do not consume the one-shot shift.
Native pixel checks compare G2/G3 drawing with the established G0 path.

This is still not full ISO 2022: other national replacement and
96-character sets are absent; PuTTY's UTF-8 British mapping behavior is
unchanged. GR bank state and line/UK mappings are handled, but the default
right-half interpretation still follows the configured byte codepage.
Those gaps are recorded in the protocol coverage inventory rather than
describing the presentation feature as complete charset conformance.

## Protection-family correction

The reference distinguishes the selected protection family from a cell's
protected flag. In particular, DECSCA selects the DEC family even when
its parameter disables protection for subsequent characters. Soft reset
ends the family without erasing existing content. A later selective
erase then erases that content; restoring the DEC family makes protected
cells effective again. A full selective ED with no protected cells left
also ends the family.

The earlier frontend retained effective protection after soft reset.
Ten additional reference cases now compare the actual erased text via
rectangle checksums across DECSEL, DECSED, DECSERA and presentation-state
restoration. The core lifecycle test separately proves that soft reset
itself preserves the text, before checking the subsequent erase.
The owned native fixture also checks protected text and overlapping Sixel
pixels disappear on selective erase after soft reset.

## Validation boundaries

`presentation-state-validation.json` records final source hashes,
compiler/sanitizer results and the isolated single-image executable.
The initial image at `build/local-presentation-check` passed the earlier
132-reference/10-direct matrix; the final image is at
`build/local-presentation-protection-check` and includes the independently
discovered protection-family correction. These images are not substitutes
for the accepted main distribution.

Core tests cover fragmented input, valid-prefix restoration, cancellation,
5,000-digit saturation, long tab streams, sparse/offscreen stops, pending
wrap, selection, grapheme attachment, and destruction of unfinished DCS.
Native tests replay captured cursor/tab reports, compare rendition and
G2/G3 pixels, resize the owned window and repeat read-only reports 30 times.
Checksums are enabled only in a temporary test profile to verify the
protection cases; the application's default remains disabled.

Clipboard-dependent native tests and real-Codex acceptance are still
reserved for the existing CI gates. Physical IME, complete charset
mapping, real-agent workloads, long GPU runs and the previously recorded
CI tab-close crash remain outstanding. Local success does not imply that
hosted CI ran or that its artifacts exist.
