# XTSETTCAP reference and terminfo lifetime

XTSETTCAP is still missing from Nemoterm. This is reference research for its
implementation, not a declaration of support or product acceptance.

The pinned [XTerm 412 specification](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.txt)
defines `DCS + p hex-name ST` as selecting a terminal database entry. It affects
the tcap keyboard profile and capability queries. It is not a list of mutable
`name=value` capability assignments. The source accepts names shorter than
32 bytes, checks graphic characters and selected punctuation, and gates the
operation separately from termcap queries.

## Independent captures

An unmodified checkout at `5c75ead9a75d4b2e666ca06fa94503b5766ed93f` was built
with the tcap keyboard/query features enabled. Its executable SHA256 is
`5cf13eb0677c8f0a930ed80c7871c80edf50e19d0ec74106b391a3569b9fa15c`.
The Linux reference uses ncurses 6.5.20250216 and a private Xvfb server. XTest
events target only its owned XTerm windows; no Windows desktop or clipboard is
used. Query bytes and real key bytes are retained together with two barriers.

The first complete capture has 60 cases and 458 steps. The expanded capture has
**71 cases and 568 steps**, including eleven installed terminal types selected
at startup, default and tcap profiles, fourteen requested setter names, malformed
names/hex, reset and alternate-screen transitions, and four permission profiles.
All reference windows exit with status zero. Missing database entries (`vt525`,
`alacritty` and `xterm-kitty`) remain recorded as unavailable on this host; they
are not used as successful-selection controls.

The expanded capture starts malformed-name cases from the populated initial
tcap database. The first capture selected Linux before those inputs, which
could mask a rejected setter's state-preservation behavior. Both captures are
retained; their input streams are not rewritten. The initial build-stage gate
also failed before running any capture: it expected an explicit definition in
`xtermcfg.h`, whereas enabled-by-default features are defined in `ptyx.h`.
The corrected gate retains actual preprocessor definitions for both features.

## Observed mismatch in the terminfo build

Selecting Linux at startup with `-tn linux` produces Linux function-key bytes:
F1 is `ESC [ [ A`, and F5 is `ESC [ [ E`. Starting with the default database and
then sending XTSETTCAP for Linux instead produces the ordinary xterm fallback:
F1 is `ESC O P`; the queried cursor-up and real Up output change from the tcap
application form to the ordinary cursor form. This is not the documented
selection of the Linux key strings. It is observed for successful database
selection in this particular terminfo-linked build, not asserted for every
XTerm build or platform.

The [pinned source](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/xtermcap.c)
calls `setupterm` for the selected name, then `free_termcap`, whose terminfo
branch calls `del_curterm(cur_term)`. The next cache load obtains no strings and
input falls back to ordinary key formatting. A separate C control linked to
the same libtinfo verifies the library lifecycle for vt100, Linux,
xterm-256color, screen and tmux: strings exist immediately after setup, become
unavailable after deleting the current terminal, and return after setting up
the same name again. This supports the source explanation independently of
Nemoterm's code; it is not a modified XTerm oracle.

The default keyboard profile remains unchanged by these setter captures.
`TN` and `Co` replies retain the emulator's identity/colour count. With the
master permission off, GetTcap and SetTcap restrictions are independent; an
enabled master overrides the restriction list. A hex string decoding to
`vt100` followed by NUL and trailing bytes is accepted as its C-string prefix
in the reference. All these raw observations remain distinct from a future
implementation policy.

## Implementation direction

The implementation must preserve the documented successful-selection behavior,
using independently captured startup key strings and database values to check
it, while explicitly recording this reference setter difference. Merely clearing
the existing key table would copy the observed failure and would not implement
the requested operation.

A Windows single EXE needs an embedded, versioned database rather than relying
on a Unix installation. A compact read-only capability pool and per-terminal
entry index can keep unused entries off the private heap. The original reference
host had only 41 distinct installed database files (73,822 bytes); that was a
measurement of that minimal installation, not the full ncurses database.
The subsequent [complete pinned database export](terminfo-database.md) compiles
2,931 aliases and retains 2,854 entries accepted by upstream libtinfo, with all
77 rejected names recorded. Its 218 key capabilities occupy 192,401 bytes of
read-only C tables. Every compiled alias/key pair matches the original library
observation, including absent keys and present empty values. These are database
verification results, not a Nemoterm implementation or working-set measurement.
License embedding, complete input key-name mapping,
permission settings, lifecycle, malformed input, native key/query consistency
and GDI working-set verification remain implementation work. The feature must
remain absent from OSC 60/61/62 advertisements until it actually exists.
