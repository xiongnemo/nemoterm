# Parameterized underline discovery

Both full workflows pass at `37ef26d`, including all 93 single-image groups.
The earlier `6cbe05f` compiler comparison failed during hyperlink teardown;
the [fixture correction and retained failure evidence](hyperlink-shutdown.md)
remain separate from the later successful run. The accepted root executable
has not been replaced, and local DirectX acceptance still fails below.

Nemoterm can already render styled and coloured underlines. Programs using
XTGETTCAP could not discover the parameterized sequences, because `Smulx` and
`Setulc` were unknown. The current development source now returns these two
case-sensitive terminfo programs:

| Name | Parameter | Result after client-side expansion |
| --- | --- | --- |
| `Smulx` | 0 through 5 | SGR `4:0` through `4:5`: off, single, double, curly, dotted, dashed |
| `Setulc` | One packed `0xRRGGBB` integer | SGR `58:2::R:G:B` |

The returned values contain actual ESC bytes and literal terminfo `%` operators,
all hex-encoded inside the DCS reply. The client evaluates the program; the
terminal does not evaluate arbitrary input programs or load a terminfo database.
Queries do not change the cursor, current attributes or colour. `Setulc` is
reported as known but unavailable when either ANSI colour or true colour is
disabled in the local configuration. `Smulx` remains available in those modes.
Unknown names, including `Su` and `Setulc1`, remain unknown. SGR 24 and 59 clear
the underline style and colour respectively.

The style program follows the pinned ncurses
[terminfo source](https://github.com/ThomasDickey/ncurses-snapshots/blob/7404b376832583182c52722dc09d86b8675db375/misc/terminfo.src).
The packed-colour argument follows tmux's
[usstyle feature](https://github.com/tmux/tmux/blob/d56d72094d3ace7a25330bba8a8392ff66083a09/tty-features.c#L143).
Nemoterm's colour program uses an explicit empty colour-space field and omits
tmux's unnecessary trailing conditional terminator. This is an extension of the
XTGETTCAP name whitelist; xterm's documented key/identity whitelist is not an
independent oracle for these two names.

## Bounds and dependencies

The input limit remains 2,047 bytes. `Setulc` is now the largest response
expansion: 13 request bytes including the separator produce 134 response bytes.
157 repeated names produce 21,045 reply bytes. The implementation also enforces
an explicit 22 KiB response ceiling, returning a negative response rather than
allowing future table entries to silently increase allocation. The previous
less-than-14-KiB bound in the [literal rendition checkpoint](rendition-capabilities.md)
applies to that older source, not this extension.

Both programs fit in the existing 64-byte temporary capability buffer; the
copy now checks that bound. There is no added persistent terminal state,
thread, DLL, runtime library or service. ncurses is only an independent test
dependency on Linux/WSL, not a dependency of the single Windows executable.

## Local validation

The Windows capability, SGR and query suites pass. The capability suite checks
exact values and unchanged state, case-sensitive names, all four combinations
of ANSI/true-colour configuration, full response expansion, fragmented parser
input, oversized direct and parsed requests, and recovery to a subsequent DSR.
The new Linux `test_tcap` target passes under ASan and UBSan.

`tests/test_underline_terminfo.py` runs the actual parser's reply export through
ncurses `tparm`, checking **780 numeric cases** against independent style/RGB
arithmetic. This covers all six styles, all 256 values in each colour channel
with nonzero neighbouring channels, and packed-value boundaries. It does not
contain a custom terminfo evaluator. Local ncurses is 6.5, patch 20250216.

The native query fixture captures exact `Smulx` and `Setulc` replies through
the real ConPTY transport, replays 15 representative expanded sequences, and
checks their state using DECRQSS plus a final DSR ordering barrier. It also
checks the two resets together. On Windows these replay values are independent
numeric expectations, not a claim to run ncurses inside the terminal. The
captured Windows programs are then separately passed to the same ncurses
checker in WSL, and all **780 expansions pass again**. The fixture's five owned
processes drain naturally without forced termination.

A further native transport check receives the full **21,045-byte** maximum
repeated-name reply, followed by its separate four-byte DSR barrier. An
oversized request produces the expected negative response and another intact
barrier. This verifies the increased response bound across real ConPTY reads.
The same image passes the extended fixture with natural five-process cleanup;
its newly captured programs pass all 780 ncurses expansions as well. These two
transport cases are included in the permanent Windows fixture.

The local single image is **4,467,200 bytes**, SHA-256
`e06d094d785e2f79abe03fe3d429a83efad81f59244594253091fef0f368775d`.
The native cursor fixture instruments only its owned process; its memory sample
is not uninstrumented memory acceptance. The renderer and cell storage are
unchanged. This work is not a DirectX memory optimization and does not supersede
the existing failed local 25 MB DX result.

Two initial test integration failures are retained: Linux had no `test_tcap`
CMake target, and the new reply-export entry point initially omitted the mock
screen initialization. UBSan caught the latter during cleanup. The target and
entry point are fixed, and both sanitizer and independent expansion checks pass
afterward; neither fix changed product parser behavior.

The [manifest](underline-capabilities-validation.json) retains exact source and
executable hashes, every numeric expansion, native wire replies, successful
logs, failed attempts and cleanup. CI now includes the Linux capability suite
and independent ncurses check, and the existing Windows/MinGW native query
fixture includes the new discovery and state checks. The full terminal goal
remains open.

## Downloaded CI image and local follow-up

At `37ef26dae839319f7bf703bb648038c343c357f1`, the
[single-image workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43508892024)
passes 93 distinct groups and the
[compiler/sanitizer workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43508891431)
passes all four jobs. Both complete hyperlink records now include successful
natural shutdown, frontend/retained child exit codes zero, and live observer
detachment. The prior timeout remains a failed historical run.

The [single-image artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43508892024/artifacts/14079650407)
contains a 4,448,768-byte EXE, independently hashed as
`79845d77c08f2c32d2cffa4d85a5a7c6c7954efd948e8874956d20d281f8c5e2`.
It expires on 2026-12-13 at 21:34:39 UTC. Its isolated distribution directory
contains only `nemoterm.exe`. Local query replay uses that exact downloaded
image and completes with natural five-process cleanup. Actual programs from
the local image and both Windows CI variants each pass 780 ncurses expansions;
the Linux sanitizer job independently passes 780 expansions too.

The unchanged uninstrumented SarasaTermSC Nerd Font Light, actual 160x48,
two-tab workload produces:

| Renderer / run | Private WS peak | Total WS peak | Private commit peak | Outcome |
| --- | ---: | ---: | ---: | --- |
| GDI | 16,642,048 | 42,680,320 | 19,279,872 | 9 functional groups; memory pass |
| DirectX, unmodified follow-up | 30,474,240 | 71,577,600 | 100,126,720 | 9 functional groups; memory fail |

Both rows finish with 56 owned processes drained naturally. The DX 25,000,000
byte gate is unchanged. The smaller CI Consolas grids (GDI 109x34 and DX 88x35)
pass their gates but do not replace this larger local acceptance.

The first local DX attempt failed earlier at temporary-tab cycle 9: handles
rose from baseline 486 to 537, GDI objects from 37 to 39, and USER objects from
42 to 56. The full workload/memory gate was never reached. Its raw samples and
failed record remain retained, including the scoped forced cleanup of five
remaining job members. It must not be described as a successful functional run.

A bounded follow-up added external, owned-process window-class/module snapshots
without injection. It retained every original assertion and would have kept a
failed sample failed even if resources later settled. That run did not reproduce
the burst: its baseline and final counts were already 543 handles, 39 GDI and
56 USER objects, with no later module additions. It completed nine functional
groups and natural cleanup but failed memory at 30,466,048 bytes. It is retained
as diagnostic evidence, not acceptance. A fresh run of the unmodified fixture
then produced the DX table row above. These observations do not establish the
cause of the initial resource change or prove it fixed. Both that intermittent
failure and the reproducible DX memory excess remain open.
