# Hosted historical reference collectors

The remote-only policy includes regenerating upstream reference observations,
not only replaying the checked-in observations against Nemoterm. An entry-point
audit found 25 older XTerm collectors without a direct Actions entry. Native
tab overflow was already reached dynamically by `tabs_regression_suite.py`;
clipboard/CWD children and the GPU settings driver are also called by their
existing hosted parents. `etw_region_report.py` only reads retained trace files.
The old print-only `font_probe.c` is superseded by the hosted dependency
installer's checked actual-font selection; its machine-specific historical
family name is not used as a runner requirement. The independent
`tcap_library_probe.c` now runs in the upstream build job for five databases,
retaining JSONL and its own executable hash.

`protocol-reference.yml`, `family=historical-xterm`, now invokes
`xterm-historical.yml`. Its eleven groups execute 33 collector invocations,
including all four batches of the 320-case character mapping. Set
`historical_group` to a single group for a bounded replay. The controller
requires Linux, `GITHUB_ACTIONS=true` and `RUNNER_ENVIRONMENT=github-hosted`.
No local reference binary, terminal window or display is used.

The build uses unmodified XTerm commit
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f` on Ubuntu 24.04, explicitly enables
termcap keys/queries and verifies their effective preprocessor definitions.
One build is shared by all groups; each verifies its SHA-256 before execution.
Build/configuration/package records and the raw captures are retained as
separate artifacts. Each capture has a private Xvfb display, original input
streams, its own output directory and a ten-minute outer deadline. Failed
captures remain failed while other collectors continue.

These are fresh observations, not rewritten expected answers. No checked-in
reference is replaced, and successful upstream capture does not establish
Nemoterm support for a missing feature such as XTSETTCAP.

## Runs and observations

[Initial run 44064785066](https://github.com/xiongnemo/nemoterm/actions/runs/44064785066)
uses fixture `0308ef3`; its XTerm SHA-256 is
`b95532e0f3aa85b1c41cbb781a094240e68a0fa4392524118a454bf1f0463c1f`.
State, editing, all character mappings, character input, character-state/
lifetime and XTSETTCAP collectors pass. Extended and special-key collectors
also pass, but the legacy-key collector exceeds the new outer ten-minute
budget after 65 completed cases. Character checksums stop after 121 completed cases because
the next XTerm does not create its child readiness report within the existing
eight-second deadline. The old collector discarded native startup stderr;
the original failure artifact is retained rather than treated as success.

Fixture `860b02f` adds opt-in XTerm/Xvfb stderr and startup-process diagnostics,
without changing the input streams or readiness deadline. Its isolated
[checksum replay 44065504220](https://github.com/xiongnemo/nemoterm/actions/runs/44065504220)
passes all 172 cases on the same XTerm binary. Its 172 startup diagnostics
contain no error, and all 121 previously completed case records match exactly.
The intermittent first startup failure is not claimed fixed or overwritten.
A separate [key replay 44065103132](https://github.com/xiongnemo/nemoterm/actions/runs/44065103132)
at `5e1d44b` passes the older `xterm_mok_reference.py` collector's 312
observations, plus the extended/special-key collectors again. Its legacy-key
collector likewise reaches the outer limit after 63 complete cases. Both
timeouts and their partial streams remain failed and retained.

The legacy collector contains 2,895 steps. Its unchanged input transport
waits 40 ms for each real key event and another 60 ms after each reply, so
the newly imposed ten-minute whole-collector budget was inadequate. `e62d598`
partitions its independent, fresh-XTerm cases by default/legacy/VT220 profile.
Every partition retains all literal controls and all state cases; input,
barriers, assertions, per-step deadlines and the ten-minute per-invocation
limit remain unchanged. The three profiles run on separate hosted workers in
[run 44067625285](https://github.com/xiongnemo/nemoterm/actions/runs/44067625285).
All three pass: each records 42 cases and 983 steps in 266.524, 275.071 and
266.974 seconds respectively. Their union is exactly 98 cases / 2,895 steps.
Duplicate controls/state streams agree, and all 65 cases completed in the
first timed-out capture have identical input/actions/reply bytes in the
partitioned result. Every case reports completion and XTerm exit zero.

[Run 44066604048](https://github.com/xiongnemo/nemoterm/actions/runs/44066604048)
passes the added ncurses controls and repeats all 73 XTSETTCAP cases. For
vt100, Linux, xterm-256color, screen and tmux, the selected database contains
key strings after setup, has no current database/strings after deletion, and
returns the same strings after setup again. All twenty phase records are
retained, independently of Nemoterm.

The fresh XTSETTCAP capture has 73 cases because this runner's installed
terminfo entries differ from the earlier 71-case reference host. Availability,
package identity, startup key strings and requested names remain recorded;
the different case count is not silently substituted into the historical
[XTSETTCAP study](set-tcap-reference.md).

## Final scope and retained evidence

All **33 current invocations** across the **25 collector scripts** have a
successful hosted receipt across these five runs. This is a combined coverage
record, not a claim that the two original failed runs became green. The first
checksum startup failure remains unexplained; its full successful diagnostic
replay and all failed data are retained. No product build or protocol support
claim is inferred from reference capture alone.

[The evidence archive](remote-reference-migration-evidence.zip) contains 50
files plus its SHA-256 manifest: original capture artifact ZIPs, selected build
logs/configuration/library controls, final run/job/artifact metadata, and the
derived 98-case partition comparison. It is 4,437,295 bytes, SHA-256
`477959a603db8c22a523119cf28d82d922e2c5f8f81545fd361ec3441a6d1b96`.
Selected build archives omit duplicate binaries; their original artifact IDs,
ZIP digests and the actual reference executable hash remain recorded.
