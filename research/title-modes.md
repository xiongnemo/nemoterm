# Title encoding modes

## Independent reference

[XTerm 412 run 43254032458](https://github.com/xiongnemo/nemoterm/actions/runs/43254032458)
captures 86 cases from pinned upstream commit
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f` on a private Xvfb display.
`title-modes-xterm.json` preserves exact reply bytes, including replies that are
not valid UTF-8. The earlier run 43253161033 stopped on a strict Python decoding
error; it is superseded, not counted as passing. No terminal implementation
under test supplies the reference replies.

The cases cover all sixteen encoding masks, omitted/invalid/colon parameters,
DECRQSS forms, RIS/DECSTR/alternate screens, malformed hex and Unicode, raw
controls, title length boundaries and title-stack interaction. They supplement
the [pinned control sequence specification](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.txt)
and upstream `charproc.c` / `misc.c`; observed behavior takes precedence over
assumptions about omitted parameters.

## Implementation

CSI `> Pm t` sets and `> Pm T` clears bits 0 (hex input), 1 (hex queries),
2 (UTF-8 input) and 3 (UTF-8 queries). Omitted parameters do nothing; unsupported
numeric values are ignored. Unexpected colon subparameters clear the parameter
list and restore the compiled zero mask, matching the captured reference.
DECRQSS `>t` reports all four bits; a supplied first parameter selects one bit.
The state is shared across screens, survives DECSTR/reconfiguration and resets
to zero on RIS. No new setting or dependency is required.

OSC 0/1/2/21 applies the input mode. Remote titles longer than 1,000 wire bytes
are rejected, including the hex text before decoding. Invalid/odd hex leaves
the title unchanged. Decoded C0 bytes truncate hex titles. Raw NUL truncates;
CAN/SUB cancels the update. TAB and LF are retained, other C0 and DEL/C1 controls
are normalized to `?`. UTF-8 encoded U+009C is title content, not a terminator.
Query output is encoded for the active query mode, with uppercase hex when
requested. Query none/empty/real and remote title-update policy still apply.
Locally configured titles are normalized on query too, preventing an embedded
ESC from becoming a reply delimiter. Query reads are bounded to 4,096 bytes.

Saved titles retain their codepage; restoring applies the active title modes,
as in the reference. In particular, restoring a non-hex title while hex input
is enabled fails that update and consumes the stack entry. Storage remains ten
bounded slots. Title modes add one unsigned field and bounded temporary buffers.

Three reference cases deliberately differ: overlong UTF-8, encoded surrogates
and codepoints above U+10FFFF become `?`. XTerm's captured replies either decode
the overlong form or contain invalid UTF-8. Nemoterm does not reproduce those
invalid Unicode results. The three overrides are explicitly named in
`tests/title_modes_reference.json`; the original byte evidence is retained.
The remaining 83 cases have exact matching replies.

## Validation and failures

`test_titles` compares all 86 frozen vectors one byte at a time, including raw
NUL. It also retains 22 independent stack cases, 20,000-entry churn and bounds,
and adds legacy-codepage/UTF-8 queries, input mode overrides, reconfiguration,
query permissions, delimiter filtering and cancellation after a UTF-8 lead.
The existing Windows font reverse map for CP_UTF8 is not a UTF-8 encoder;
an initial implementation produced `caf?` when round-tripping a saved Latin-1
title. The implementation now encodes Unicode scalars explicitly and the test
checks both the initial title and restore. Local title, terminal and query
core suites pass. Linux ASan/UBSan and Windows CI include the title suite.

`titles_window_smoke.py --modes` compares all 86 exact ConPTY replies and actual
HWND titles where available, then churns 1,000 titles. The native fixture enables
VT output and DISABLE_NEWLINE_AUTO_RETURN for exact protocol output, and disables
Python newline translation. Without the console mode, LF inside OSC was expanded
to CR LF by the host; the initial native comparison correctly failed that case.
Both original stack tests and mode tests now use exact output. The churn payload
is below the newly enforced 1,000-byte remote-title limit.

The local development comparison passed 87 mode checks and 23 stack checks.
Its frontend is the new MinGW build; its OpenConsole host is the previously
accepted 5a8b27f single executable, with the pinned ConPTY DLL. Exact hashes and
sampled memory are in `title-modes-window-observed.json` and
`title-modes-stack-local.json`. This comparison is not a final single-file run.
The single-executable workflow adds the strict native mode group.

Source `3a97358ddd0be96b348b3d846df82194bc6666cb` passed core CI
[43256696505](https://github.com/xiongnemo/nemoterm/actions/runs/43256696505) and
single-file CI [43256696406](https://github.com/xiongnemo/nemoterm/actions/runs/43256696406),
including all 40 native groups. Artifact 13961763752 is 4,341,248 bytes, SHA-256
`9d9b1cab1186af8933152b8451532184a7933033e9ecb04ed71aaf04cac16ae5`.
The exact download passed 87 local mode checks and 23 stack checks; the local
mode private-WS sample peaked at 3,928,064 bytes. Evidence is retained as
`title-modes-single-local.json`, `title-modes-single-stack-local.json`,
`title-modes-single-ci.json` and `title-modes-single-validation.json`.

That candidate did not replace `dist/nemoterm.exe` directly: the subsequent
geometry work identified and fixed an existing minimize-to-GDI defect. The
combined source `9ccbad3` has now passed final validation and supersedes it;
see [the geometry checkpoint](window-geometry.md). Geometry mutations, remaining
protocol families, DirectX frontend rendering and tabs/previews remain open.
