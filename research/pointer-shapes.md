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

## Retained reference and component checkpoint

[Reference run 43692238900](https://github.com/xiongnemo/nemoterm/actions/runs/43692238900)
at `ed5beca` completes all 117 cases / 555 stages and three literal controls.
REA records normal exit and verified owned-process cleanup; its prelaunch-image
identity and sampling limitations remain in the manifest. Fifteen original
records are retained in `pointer-shape-evidence/kitty-reference-ed5beca.tar.gz`,
indexed by `pointer-shape-reference-validation.json`. The observation SHA256 is
`4060b1bc1cde1302da9874c804e4d83d66d95a0bfb47b5a1dbf8401a2081d81e`.

The upstream keeps the prior shape for an unknown setter, keeps separate stacks
across all three tested alternate-screen modes, and clears both on hard and soft
reset. Empty setters install an automatic-shape slot; empty push elements do
nothing. Three legacy spellings (`arrow`, `beam`, `hand`) return supported in
queries while other recognized aliases return zero. The raw capture also keeps
malformed-string/cancellation behavior; those observations are not silently
rewritten into Nemoterm expectations.

The standalone component uses 34 bytes for both sixteen-entry stacks and has
no allocator. Complete payloads are bounded to 2,048 bytes and query content to
4,096 bytes; query output is only emitted after successful completion. A future
terminal owner can allocate this state lazily. It is not linked into the
terminal yet and does not advertise runtime support.

`generate-pointer-reference.py` reproduces a 106-case / 504-stage component
projection from the unchanged capture. Its eleven omitted cases require actual
VT dispatch (screen switches, resets, mouse modes, cursor save/erase, cancellation
and NUL handling) and remain reserved for that integration. Bytewise input in
the source is replayed as complete payloads here; this does not verify parser
fragmentation. Additional component checks cover screen isolation, rejected
oversized input, exact reply capacity and read-only query state. Local checks
have only compiled the C sources and parsed/generated fixtures; runtime replay
uses the disposable GCC, Clang and MSVC CI jobs.

[Component run 43693144294](https://github.com/xiongnemo/nemoterm/actions/runs/43693144294)
at `51fe4b2` passes all three compiler jobs and both GCC/Clang ASan/UBSan runs.
Each execution reports 4,740 checks and all 504 unchanged upstream stages.
The four compiled source/header hashes in each compiler artifact match the
identified Git blobs (with any checkout line-ending conversion recorded).
`pointer-shape-component-validation.json` indexes 23 retained records in
`components-51fe4b2.tar.gz`. This still does not establish terminal integration,
Windows cursor pixels or a new accepted product.
