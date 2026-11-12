# Terminal identity queries

The modern default now treats `CSI = c` as DA3 rather than the colliding SCO
cursor-hide control. DA3 reports `DCS !|00000000 ST` without changing the cursor,
cells or current screen. Explicit PuTTY SCO mode (`CSI 42 " p`) retains its
legacy 0/1/2 cursor controls. DA3 requires the existing VT420 compatibility bit;
lower DEC modes do not answer it.

`CSI > q` returns `DCS >|Nemoterm(PuTTY 0.85) ST`. This identifies the fork and
source baseline, not a released Nemoterm version. DA2 retains PuTTY's historic
`CSI >0;136;0c` compatibility reply; it does not claim current XTerm conformance.
DA1 retains the configured terminal identity. All four requests use the first
parameter: zero or omitted requests a reply; positive parameters are ignored.
Extra ordinary parameters are ignored, including a saturated trailing number.
Colon subparameters and parameter-count overflow are rejected by the existing
CSI parser. A saturated first number is nonzero and therefore gets no reply.

## Independent sources and host boundary

The reference is Thomas Dickey's pinned
[control sequence specification](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.txt)
and [charproc.c](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/charproc.c)
(`CASE_DA2`, `CASE_DECRPTUI`, `CASE_REPORT_VERSION`). The independent reference
workflow builds that commit and runs `tests/xterm_identity_oracle.py` on its own
Xvfb display with terminal ID 420. Product-specific DA identities intentionally
differ; the comparable checks cover argument handling, DA3 bytes and visibility.

The pinned Microsoft console host already suppresses its own replies in
ConPTY mode (`ConhostInternalGetSet::ReturnResponse` in `src/host/outputStream.cpp`).
The frontend owns these replies; no Microsoft source overlay is needed.
The native test appends a DSR barrier and compares the whole input byte stream,
so duplicate host/frontend responses cannot pass a substring-only assertion.

## Validation status

The expanded local `test_queries` suite passes: fragmented requests, omitted and
extra arguments, malformed input, cursor/cell preservation, alternate screen,
explicit SCO mode, DEC compatibility levels and cancellation/recovery. It joins
the Linux ASan/UBSan target list. Native/independent reference and exact single
EXE acceptance are pending; this change does not complete the broader query or
modern terminal protocol ledger.

The existing cursor pixel fixture was also made deterministic about focus.
Local testing of the preceding single EXE observed desktop foreground changes
during cursor samples. `query_focus_probe.js` models active/inactive focus inside
the owned process only and records suppressed events; it never sets global
desktop focus. Both active blinking and inactive dashed pixels are required.
This verifies rendering under controlled focus, not real desktop focus routing.
