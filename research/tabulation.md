# Xterm horizontal tabulation

The parser previously ignored CHT (`CSI n I`), did not restore default stops
with DECST8C, and allowed Tab beyond the horizontal right margin. CBT also
crossed the left margin in origin mode. A one-column double-size line could
leave Tab's logical cursor at -1.

`nemo_tabulate` now serves HT, CHT and CBT, bounds work by the number of columns,
keeps pending autowrap, respects double-size row limits and origin/margin rules,
and schedules a display update for both directions. DECST8C restores stops at
columns 9, 17, etc. TBC follows xterm's first-parameter behavior even with extra
parameters. No new heap storage or runtime dependency is introduced.

`xterm_tabulation_oracle.py` ran 111 cases against the independently built,
pinned XTerm 412 under a private Xvfb display. `tabulation-xterm.json` retains
the executable hash and exact input/reply pairs. The generator emits matching
C and Python fixtures; `test_state_control` and `tabulation_window_smoke.py`
both compare 105 cases. The native test uses an owned process job and the real
single-image ConPTY path without desktop input or clipboard operations.

Six reference cases are explicitly excluded from equality assertions:

* Three malformed colon cases: Nemoterm rejects the unsupported parameter form
  without changing state. Xterm instead discards the parameters and executes
  the default. Direct C assertions preserve the documented rejection policy.
* Three double-size text autowrap cases: this is a real remaining discrepancy,
  not an intentional compatibility policy. Existing text output wraps at the
  physical width instead of the double-size row's logical width. Cursor-only
  tabulation on all three double-size line types does match the reference.
  The raw failing cases remain checked in for the next fix.

Additional assertions cover the actual origin-relative cursor (CPR clamping
alone can hide the error), text/attribute preservation, and a one-column line.
The initial failing regression output and post-fix evidence are retained in
`tabulation-validation.json`. All 35 MSVC core/offscreen tests passed; the state
and margin suites also passed Linux ASan/UBSan with leak detection. The exact
local single image passed the 105 native comparisons and isolated single-EXE
startup with a console host running from the same executable.

The local image is `build/local-tabulation-check/dist/nemoterm.exe`, 4,417,024
bytes, SHA256 `11d97279c9e836aad3492c54afac9ccf722390d6ca8350832ede41970a2f6337`.
The accepted main executable is unchanged. GitHub billing has prevented recent
CI jobs from starting; local results do not substitute for the remaining CI
clipboard/real-agent gates.

Protocol source: [xterm control sequences](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html),
CHT/CBT, HTS/TBC and DECST8C. For broader implementation status see
[the coverage inventory](../docs/PROTOCOL_COVERAGE.md).
