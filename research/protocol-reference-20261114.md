# Independent protocol reference capture

[Run 43454910323](https://github.com/xiongnemo/nemoterm/actions/runs/43454910323)
builds pinned upstream XTerm(412), commit
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f`, on an isolated Ubuntu runner.
Each collector uses its own Xvfb display. No local terminal or desktop tests
were run. The [manifest](protocol-reference-validation.json) records the exact
fixture and executable identities and hashes of all retained raw captures.

Identity, guarded-area, selection-colour and cursor/charset comparison steps
pass. Their captures contain 62, 63, 41 and 44 cases respectively; the selection
capture includes 11 resource-dependent observations in addition to its 30
authored comparisons. This supplies independent wire evidence, not Nemoterm
pixel, performance or lifetime acceptance.

The attribute-colour step retains all 39 replies but fails on four authored
expectations: `reset-one-special`, `overflow-index`, `retain-ris` and
`retain-decstr`. The overall workflow therefore fails. In this pinned reference,
`OSC 105;2` resets both underline and blink colours, the overflowing index in
the fixture selects colour zero, and RIS/DECSTR restore the special colours to
the configured defaults. These differences require source review; do not change
an expected reply merely to claim parity. Nemoterm's documented rejection of
overflowing colour indices remains intentional, and the original observations
are preserved separately from any future implementation or fixture changes.
