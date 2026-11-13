# Parameterized underline discovery

CI follow-up at `6cbe05f`: the single-image workflow passed all 93 groups, but
the compiler comparison failed during hyperlink teardown. The
[fixture correction and retained failure evidence](hyperlink-shutdown.md)
keep that failure separate from the successful underline checks. Full CI for
the correction is pending; this feature has not yet replaced the accepted build.

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
fixture includes the new discovery and state checks. Full remote CI and its
downloadable artifact remain pending at this local checkpoint. The accepted
root distribution has not been replaced, and the full terminal goal remains open.
