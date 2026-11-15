# CAN/SUB cancellation and error-character display

The development terminal now cancels unfinished controls with CAN (`0x18`),
and cancels with an error character for SUB (`0x1a`). This follows the pinned
XTerm(412) VT525 identity, including its byte/UTF-8 distinction. The change
adds no per-cell state, allocation or distributed dependency. Local desktop
testing remains paused, and the accepted executable is unchanged.

## Independent reference

[Run 43706391889](https://github.com/xiongnemo/nemoterm/actions/runs/43706391889)
captures 254 streams and 1,960 single-cell Unicode checksums from
XTerm revision `5c75ead9a75d4b2e666ca06fa94503b5766ed93f`. Each input runs in a
fresh XTerm on a private Xvfb display. Four literal controls establish the
ASCII/error-character observations. Complete inputs and replies are retained
unchanged in `control-cancellation-reference.tar.gz` (522 records, 54,787 bytes),
indexed by `control-cancellation-reference-validation.json`. The merged capture
SHA256 is `d69f11e6a36383d0cd8e08c4555bc6decb67f063c751992cd640f77acc9c0fa1`.

The matrix covers 23 parser prefixes, DEC levels 1–4 under the VT525 identity,
byte and UTF-8 coding, selected G0–G3 banks, pending SS2/SS3, insert mode, pending
wrap, disabled wrap, bottom scrolling, VT52, partial UTF-8 and raw C1 strings.
It observes these distinctions:

- CAN cancels without printing. SUB prints U+2426 in UTF-8/VT52, or byte `&`
  through the selected GL bank in byte mode. Pending single shifts survive the
  error character and apply to the next ordinary printable character.
- SUB uses ordinary insertion, wrapping, scrolling and image-overwrite rules.
  Text written over an existing image can therefore erase that image area.
- Partial UTF-8 emits U+FFFD before processing CAN/SUB. Its Unicode checksum is
  zero: the pinned [checksum implementation](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/screen.c)
  excludes Unicode special values. This is not evidence of a stored NUL.
- Writing the rightmost column records the pending-edge report flag even when
  DECAWM is disabled; the next character still overwrites that column.

The pinned [dispatcher](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/charproc.c)
has separate older VT100-family identity behavior. This capture does not claim
to cover all emulated hardware identities, all encodings, or every parser state.

## Implementation and compiler evidence

Cancellation releases active DCS tab restoration, Sixel decoding, OSC 52,
iTerm OSC and Kitty APC input as applicable. It preserves completed clipboard
cache entries and unrelated image transfers. SUB rendering uses the normal
terminal write path and preserves pending SS2/SS3. Truncated/invalid UTF-8 now
uses U+FFFD, and right-edge report state follows the independently observed rule.

[Run 43708274560](https://github.com/xiongnemo/nemoterm/actions/runs/43708274560)
at `d07f13d` passes GCC and Clang ASan/UBSan and MSVC. Every compiler matches
all **254 cancellation streams and 243 ANSI streams**, both whole and bytewise,
with no replaced replies or policy exceptions. The earlier three ANSI SUB
exceptions are removed. Each compiler also passes 64 payload lifetime cycles,
query/state/keyboard/pointer/OSC 52/Sixel regressions; MSVC additionally passes
the general terminal and mode tests.

The retained failures explain the fixes rather than disappearing from the record:

- `4de5494`, run 43707395096: right-edge metadata, partial UTF-8 graphics and
  raw C1 fixture setup differed. Existing query and Sixel tests also assumed
  SUB never prints. The latter now separates pending-image cancellation from
  ordinary text overwriting an installed image.
- `476d06f`, run 43708056696: MSVC passes the entire matrix; Linux retains 12
  raw C1 differences. The fixture's locale UTF-8 override superseded its
  requested ISO-8859-1 code page. `d07f13d` disables that fixture override and
  asserts the actual code page; it makes no further production change.

`control-cancellation-components.tar.gz` retains all three runs, their original
logs and exact source blobs: 190 records, 725,352 bytes and 63 verified compiler
source hashes. `control-cancellation-component-validation.json` indexes them.

The first full ordinary workflow at `73ed664`,
[run 43709232412](https://github.com/xiongnemo/nemoterm/actions/runs/43709232412),
then exposes old no-glyph assumptions in selective-erasure and SGR tests.
Their original failures and completed renderer/host jobs are retained in
`control-cancellation-ordinary-failure.tar.gz` (85 records, 337,448 bytes),
indexed by `control-cancellation-ordinary-failure-validation.json`.

`069d220` updates those assertions and the corresponding XTGETTCAP recovery
assertion without changing production code. Invalid erase requests still
preserve all cells; CAN resumes at the same cell, while SUB inserts the
independently observed error character before subsequent text. The SGR test
also checks that both the error character and following text retain default
attributes. [Run 43709798590](https://github.com/xiongnemo/nemoterm/actions/runs/43709798590)
passes the expanded regression set on GCC/Clang ASan/UBSan and MSVC, alongside
the unchanged 497-stream reference matrix and payload lifetime checks.
`control-cancellation-regressions.tar.gz` retains this and the earlier passing
`73ed664` component run (142 records, 497,415 bytes, 42 verified source hashes),
indexed by `control-cancellation-regression-validation.json`. Replacement
ordinary run 43710069426 was explicitly cancelled and superseded by
[run 43710486453](https://github.com/xiongnemo/nemoterm/actions/runs/43710486453)
at `7c40765`: the earlier ANSI run demonstrated that the 40-minute outer job
budget interrupted the final memory workload. The replacement allows 50 minutes
without changing individual test deadlines or memory limits. It remains in
progress at this checkpoint; the cancellation is not a product failure.

## Native integration boundary

The ordinary and single-image suites now include
`control_cancellation_window_smoke.py`: 177 ANSI and 236 cancellation streams
whose input bytes round-trip through the existing UTF-8 console fixture and
whose replies use seven-bit framing. The generators retain a named exclusion
list for 84 binary-only cases; those remain covered by the complete core
replay, not by this native fixture. It also compares SUB/CAN output pixels with
literal byte/Unicode text in an owned window. Expected wire bytes are copied
directly from the independent captures.

These checks now pass the complete single-image workflow below. Ordinary
workflow completion and local 160×48 Sarasa testing remain separate. The memory
target applies to GDI; current DX memory is accepted and this work does not
introduce further DX memory optimization.

## Complete single-image checkpoint

[Run 43709232409](https://github.com/xiongnemo/nemoterm/actions/runs/43709232409)
at `73ed664` passes all **155 validation groups**, including the 413 native
reference streams and three literal GDI pixel comparisons. Offline validation
compares every captured reply with the unchanged generated reference, checks
both hashes of each pixel pair and confirms natural process cleanup. The 84
binary-only streams retain their separately passing core coverage.

The single executable is 4,532,224 bytes with SHA256
`c5a359282e012a5cbd3b27b74543a5c74e9e5e43687cd1cd8d0d01e687890a71`.
The [verified CI artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43709232409/artifacts/14161561224)
expires on 2026-12-15. It has the same production and single-image build inputs
as the corrected `069d220` component checkpoint; the old test assertions are
not production code, and these are separately linked binaries.

All twelve uninjected memory workloads pass their existing private-working-set
limits, with natural cleanup and 25,048 post-sampling Unicode image cell checks.
Dense GDI uses a remote Consolas 109×34 grid and peaks at 14,213,120 bytes private
working set, 46,645,248 bytes total and 16,801,792 bytes private commit. DirectX
uses an 88×35 grid and peaks at 18,112,512 / 55,152,640 / 21,135,360 bytes. Its total
working set is recorded under the user's accepted DX scope, not the GDI target.

`control-cancellation-single.tar.gz` preserves 4,560 records (8,330,025 bytes),
including the executable, full CI evidence, original ordinary failure log and
exact source blobs. `control-cancellation-single-validation.json` indexes and
hashes those records. No local GUI was launched and `dist/nemoterm.exe` remains
the previously accepted image; this cloud checkpoint does not renew local
Sarasa or hardware OpenGL acceptance.
