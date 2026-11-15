# ANSI character-set conformance reference

The development branch implements `ESC SP L/M/N` with one byte of per-terminal
ANSI conformance state. It changes future locking shifts without changing DEC
operating level, C1 framing, selected banks or a pending single shift. Local
desktop testing remains paused and the accepted executable is unchanged.

The [pinned XTerm specification](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.ms)
lists three ECMA-43 conformance levels. Its
[actual dispatcher](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/charproc.c)
stores ANSI conformance separately from DEC operating level and C1 reply
framing. Treating this command as an alias for DECSCL or S7C1T/S8C1T would change
unrelated terminal behavior.

[Reference run 43701953352](https://github.com/xiongnemo/nemoterm/actions/runs/43701953352)
at `3b49cd4` captures **243 input streams, 1,443 Unicode cell observations and
three literal controls** from XTerm(412), pinned to
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f`. Each case starts a fresh XTerm and
private Xvfb display. The fixture retains its complete input and raw wire
replies, including cursor/charset reports. It requests Unicode cell checksums
after a temporary DEC level increase, since lower levels cannot answer those
queries. These are stored-character observations, not screenshots or physical
display verification. Literal ASCII, DEC line-drawing and Finnish controls
check that checksum collection is observing the selected character sets.

The resulting matrix establishes these implementation requirements:

- DEC level 1 ignores ANSI setters and extended locking shifts. DEC level 2
  ignores ANSI setters but continues to support the extended shifts.
- At DEC levels 3–5, ANSI levels 1 and 2 block subsequent LS2/LS3 and
  LS1R/LS2R/LS3R operations; level 3 enables them.
- Changing ANSI level preserves already selected GL/GR banks and pending
  SS2/SS3. SI/SO and single shifts keep their independent behavior.
- ANSI level is not a cursor-save or alternate-screen property. Changes made
  after DECSC or inside the alternate screen remain in force on return.
- RIS and DECSTR preserve ANSI level. Reset defaults for G2/G3 differ at ANSI
  level 1, where the reference reports ASCII banks. Levels 2 and 3 restore
  their default supplemental banks in this byte-mode configuration.
- DECSCL establishes the operating level's default ANSI state. VT52 return
  behaves as DEC level 1, including suppressed higher-level state reports.

The first capture, `dd3dee2`, began its probe with ASCII `q`, which does not
distinguish either national bank for a single-character shift. `677d00b` fixes
that input by putting `[` first. `3b49cd4` adds reset defaults, already selected
banks, pending single shifts and VT52 return. All three original captures are
retained; only the last is the current reference. SUB cancellation records the
reference's stored U+0026 error character and shifted cursor/checksum positions. Those
bytes must not be silently replaced by Nemoterm's preferred cancellation policy.

`ansi-conformance-reference-validation.json` indexes 1,419 original records in
`ansi-conformance-reference.tar.gz`, including exact input-authoring revisions,
the unchanged upstream replies, source/build identities and the read-only
dispatcher source used for the audit.

## Terminal implementation and replay

The newer [CAN/SUB checkpoint](control-cancellation.md) at `d07f13d` matches
all 243 unchanged ANSI reference streams on GCC/Clang sanitizers and MSVC,
whole and bytewise. It removes the three SUB policy exceptions described in
the historical checkpoint below. A 177-stream native projection is now wired
into product CI, with 66 binary-only cases named as exclusions; its native
result is still pending.

[Run 43705674015](https://github.com/xiongnemo/nemoterm/actions/runs/43705674015)
at `889c941` passes GCC and Clang AddressSanitizer/UndefinedBehaviorSanitizer,
and MSVC. Each compiler replays every input against a fresh terminal, both as
one chunk and one byte at a time. **240 streams exactly match XTerm's complete
wire replies** in each mode, including Unicode checksums and charset/cursor
reports. At that historical revision, three named SUB cases assert the Nemoterm cancellation policy
against the corresponding independent CAN observation: no error glyph is
inserted. The original SUB replies remain unchanged in the generated header
and archive. The newer cancellation checkpoint closes those three differences.

The implementation preserves ANSI level through RIS, DECSTR, cursor saves and
alternate-screen changes. DECSCL resets character sets under the old ANSI state,
then establishes the new DEC level's ANSI default. VT52 return now selects
VT100 conformance. Unsupported escape intermediates in VT52 consume their final
byte instead of leaking an ANSI command letter onto the screen, matching the
[pinned XTerm parser tables](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/VTPrsTbl.c).
There is no per-cell allocation or new distributed dependency.

Existing query, state-control, keyboard and pointer suites pass on all three
compilers; Windows additionally passes the general terminal and mode suites.
The independent header generator checks the retained observation digest and
copies complete input/reply bytes without replacing expected values.

The first run at `2650746` fails Linux configuration because GTK-disabled builds
do not provide the general terminal/mode targets. Its Windows fixture initially
omits the checksum permission enabled in the XTerm collector, so all 243 cases
lack checksum replies. After fixing only these harness conditions, `7f449c0`
reproduces six differences on all three compilers: three VT52 leaked letters
and three existing SUB glyph-policy differences. The next run fixes VT52 and
asserts the explicitly retained SUB policy. No production checksum permission
or expected upstream observation was relaxed.

`ansi-conformance-component-validation.json` indexes the failed and successful
run artifacts and exact source blobs in `ansi-conformance-components.tar.gz`
(122 records, 589,115 bytes, 36 verified source hashes).
The ordinary and single-image workflows started solely while registering the
new focused workflow were intentionally cancelled; they are not regression
results. Complete product CI, native ConPTY integration and local 160×48 Sarasa
acceptance for this new parser change remain separate.

## Complete single-image checkpoint

[Run 43706001135](https://github.com/xiongnemo/nemoterm/actions/runs/43706001135)
at `5bc9608` passes all 154 existing single-image validation groups, twelve
uninjected memory workloads, 25,048 post-memory image-cell checks and natural
owned-job cleanup. Its 4,532,224-byte executable has SHA256
`40403ea7f4bb05c1cc411e09eb38cccb15390f27b1c5e1e2ab9ea687a6b91a4e`.
The [single-EXE artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43706001135/artifacts/14160240151)
is retained until 2026-12-15. It is a development build; the accepted local
executable remains unchanged.

This image contains the ANSI changes and predates CAN/SUB error-character
parity and the new 413-case native conformance fixture. It therefore establishes
existing product regression coverage, not native replay of that new matrix.
The vendor/native production and single-image build inputs match the `889c941`
compiler checkpoint. Dense remote GDI private/total working-set peaks are
14,016,512 / 46,305,280 bytes on a 109×34 Consolas grid; DX peaks are
17,596,416 / 55,173,120 bytes on an 88×35 grid. These are bounded remote
workloads, not local 160×48 Sarasa acceptance. Current DX memory is accepted.

The simultaneous ordinary run, 43705998603, failed the reference generator's
strict UTF-8 encoding check before the frontend build. `6d9d80d` fixes the
file-read encoding without changing production sources; its replacement
ordinary run subsequently reaches the outer job deadline, as described below.
The original failed ordinary evidence and
successful single-image evidence are preserved together in
`ansi-conformance-evidence/single-5bc9608.tar.gz` (4,620 records, 8,356,678 bytes),
indexed by `ansi-conformance-single-validation.json`.

The replacement ordinary run,
[43706562015](https://github.com/xiongnemo/nemoterm/actions/runs/43706562015),
passes its sanitizer, MSVC renderer and source-host jobs. Its Windows job is
cancelled exactly at the 40-minute outer deadline during the final dense DX
workload; the retained GitHub annotation explicitly confirms that limit.
Eleven uninjected workloads, including dense GDI, complete successfully, but
there is no completed dense DX result or successful portable artifact. This
is partial evidence, not a full ordinary pass. The original logs, annotations,
unverified image and artifacts are retained in
`ansi-conformance-evidence/ordinary-timeout-6d9d80d.tar.gz` (4,538 records,
9,099,528 bytes), indexed by `ansi-conformance-ordinary-timeout-validation.json`.
The current CI gives that outer job 50 minutes; individual test deadlines,
memory assertions and production code are unchanged by the budget adjustment.
