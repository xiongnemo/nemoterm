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
XTerm discards the entire argument list when these identity requests contain
unexpected colon subparameters, then still dispatches the default query, even
for a nonzero first parameter. Nemoterm reproduces this observed behavior only
for these four queries; other non-SGR controls keep their existing validation. The
bounded parameter/subparameter count is unchanged. Without colon subparameters,
a saturated first number is nonzero and therefore gets no reply.

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
the Linux ASan/UBSan target list. This change does not complete the broader
query or modern terminal protocol ledger.

Revision `5c08944677594e985439c679884093d1390fac87` passed
[independent reference run 43242677840](https://github.com/xiongnemo/nemoterm/actions/runs/43242677840):
all 62 XTerm cases, with [raw bytes and reference EXE hash](identity-xterm.json).
The Linux sanitizer job also passed in core run 43242677806. The local MinGW
comparison build passed 65 identity checks through bundled ConPTY, plus the
existing cursor/status/keyboard tests. [Its exact evidence](identity-native-local.json)
records EXE SHA-256 `12b5f0ef016692e1d4a0c407f5d0ba388dca4e21a3e9850380a2cd259d9346b3`,
5,419,008 bytes sampled peak private WS and 26,251,264 total WS. This comparison
build uses runtime sidecars and is not the final single EXE. Full Windows core
run 43242677806 passed. Single-EXE run 43242677797 passed its native checks and
both real-client scenarios but failed while removing the temporary Codex home:
late Git subprocesses outlived the startup process snapshot. Its executable is
retained as unverified and is not promoted.

Revision f6b4409 bounds the complete fixture tree with a private Windows Job,
assigned before the root's initial thread resumes. Two native tests cover late
descendants, unrelated-process isolation and natural exit. Core run 43246777771
passed; [single-EXE run 43246777750](https://github.com/xiongnemo/nemoterm/actions/runs/43246777750)
also passed all 37 check groups, including default and inline real Codex UI.
`identity-single-ci.json` retains its executable hash and complete group list.
The downloaded EXE hash is
`d8bbb52a7712f912a2c57b0a0c74727359d01354cec650ee62fd8b049a47ad34`.
Both private jobs drained to zero active processes; their respective lifetime
totals were 67 and 68 processes. A local real-client retry reached
the window but was blocked by clipboard access-denied before preservation; it
is not counted as successful validation. The identity changes and native-window
shutdown repair subsequently passed combined core and single-EXE CI at 80c6cf2.
The exact single EXE passed the 65 identity cases locally; final artifact hashes
and acceptance evidence are recorded in `window-shutdown.md`.

The first independent run (43241329669, revision 7732557) disproved the initial
assumption that XTerm rejects colon subparameters: all four `0:0` requests got
their normal reply. The implementation and expanded oracle now follow that
observed behavior. Run 43242015937 further showed that a colon also discards a
nonzero first parameter. Inspection of the upstream pre-dispatch subparameter
guard confirmed its ResetState call clears the parameter list without changing
the pending dispatch case. The final oracle tests all 62 observed cases.
Both failed reference runs are retained as evidence of the corrections.

The existing cursor pixel fixture was also made deterministic about focus.
Local testing of the preceding single EXE observed desktop foreground changes
during cursor samples. `query_focus_probe.js` models active/inactive focus inside
the owned process only and records suppressed events; it never sets global
desktop focus. Both active blinking and inactive dashed pixels are required.
This verifies rendering under controlled focus, not real desktop focus routing.
