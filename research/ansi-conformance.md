# ANSI character-set conformance reference

`ESC SP L/M/N` is still unimplemented in Nemoterm. This checkpoint records the
independent behavior needed to implement it; it does not promote protocol
support or replace the accepted executable. Local desktop testing remains paused.

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
reference's `&` error character and shifted cursor/checksum positions. Those
bytes must not be silently replaced by Nemoterm's preferred cancellation policy.

`ansi-conformance-reference-validation.json` indexes 1,419 original records in
`ansi-conformance-reference.tar.gz`, including exact input-authoring revisions,
the unchanged upstream replies, source/build identities and the read-only
dispatcher source used for the audit. The matrix has not yet been replayed
against an implementation in Nemoterm. Full terminal dispatch, fragmentation,
reset integration, bounded state and native ConPTY behavior remain required.
