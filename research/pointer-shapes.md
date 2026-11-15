# OSC 22 pointer-shape development

OSC 22 is currently missing from the Nemoterm parser and Windows frontend.
This branch first records an independent reference before implementing it.
The accepted distribution is unchanged; local native testing remains paused.

The [kitty protocol](https://sw.kovidgoyal.net/kitty/pointer-shapes/) defines
30 CSS shape names, set/push/pop operations, support/current/default/grabbed
queries, separate main/alternate stacks and reset behavior. Stack capacity must
be at least sixteen. Shapes apply independently of mouse reporting; local
selection and link hover may override them. The
[XTerm specification](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
defines the original unprefixed X11 name setter and a different unknown-name
fallback. Those are distinct behaviors to compare, not interchangeable names
for a completely verified protocol.

`tests/kitty_pointer_oracle.py` authors 117 input cases / 555 stages for the
existing pinned upstream `8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f`.
It uses the real native parser, upstream `Window.set_dynamic_color` dispatcher
and native shape stack. Three literal response controls check that the native
test callback has actually been connected. The fixture records raw replies,
current shapes, cursor positions and text rows; it does not calculate expected
stack results. Coverage includes all specified shapes, 41 alias candidates,
stack eviction and underflow, malformed/empty lists, alternate-screen modes,
hard/soft reset, selection-independent mouse modes, BEL/ST, cancellation and
bytewise input. Alias candidates are inputs, not claims of supported aliases.

The disposable Linux workflow runs this capture under the existing pinned REA
process recorder. Its result must preserve source/binary hashes, complete input
and output records, exit status and verified cleanup. This in-memory reference
does not observe an OS mouse cursor or establish Windows rendering.

Implementation still requires bounded per-terminal state, response framing,
all thirty Windows cursor presentations, legacy aliases, per-tab cursor
isolation and precedence with local selection, links and busy status. Native
cursor inspection, settings/permission behavior, resets, allocation/lifetime
checks and the original memory limits remain separate acceptance work. No
support row is promoted by adding this reference fixture.
