# Chained OSC colour error recovery

An invalid colour in OSC 4 or OSC 5 previously left the loop running: later
colour setters and queries in the same command still executed. The development
fix stops that command at the rejected specification, while retaining earlier
successful changes and replies. A following OSC command is processed normally.
The separate OSC 10–19 handler continues after an invalid component, as observed
in the independent reference. No storage, allocation, dependency, colour syntax
or memory-limit change is introduced.

The reference is unmodified XTerm(412), commit
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f`, on a private Xvfb display with TCP
disabled. No input or clipboard operation targets the Windows desktop. All
**72 original streams and binary replies** are retained in
`osc-colour-sequence-reference.tar.gz`, together with the capture scripts,
executable identity, X11 package versions and upstream source.

The [control-sequence specification](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
defines multiple indexed/special colour pairs and successive dynamic colour
parameters. The pinned
[`ChangeAnsiColorRequest` and `ChangeColorsRequest`](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/misc.c)
have distinct failure handling; the captured replies establish the behavior
used here rather than assuming that both handlers should stop.

**64 unchanged reference streams** cover indexed colours, attribute colours,
OSC 4 attribute aliases, dynamic colours, successful commands, seven rejected
specifications, and both BEL/ST termination. Earlier mutation/query effects and
subsequent-command recovery are observable in each invalid indexed/attribute
case. Eight further streams show that this Xlib accepts an extra component in
`rgb:1/2/3/4`; Nemoterm's existing exact-three-component syntax rejects it. Those
eight raw observations are retained separately and are not counted as matching
reference cases. This patch does not change that syntax policy or the separately
documented numeric-index/reset differences.

The old production parser produces **84 mismatches** when the 64-stream replay
runs whole and bytewise. The fixed parser passes both modes, plus the existing
colour, OSC colour, query, SGR and state-control suites, on local MinGW GCC and
WSL GCC/Clang with ASan/UBSan. The negative-control log, baseline source hash,
fixed source, compiler/build logs and original references are retained in
`osc-colour-sequence-fix.tar.gz` and its validation manifest. Archive members
are rehashed after compression.

The native ConPTY fixture and all three component compiler jobs are wired into
CI, and the single-image plan gains one group. **Native replay, MSVC and complete
product CI are not yet verified for this change.** The ongoing 49-group local
acceptance uses the previous exact `253855b` executable, so its results and
memory measurements do not certify this later parser patch. Neither the
accepted executable nor the main branch has been replaced.
