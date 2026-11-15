# Cursor and function-key modifier negotiation

Applications can now negotiate xterm cursor-key (resource 1) and function-key
(resource 2) modifiers, independently of character-key resource 4. The modern
xterm keyboard profile supports levels 0–4, explicit disable, query, format
selection and DECRQSS. Level 0 preserves parameterized SS3; level 1 selects
CSI, level 2 adds the leading parameter, level 3 marks modified sequences
private, and level 4 uses xterm's extended key codes with either encoding.
Disabled function-key modifiers select the extra function-key numbers using
the default 12-key stride. Editing keys preserve xterm's distinct treatment.

The additional per-terminal state consists of two eight-byte records and a
negotiation flag. Encoding adds no allocation, library or renderer dependency;
Windows reuses its existing on-demand keyboard tracking table when an
application negotiates these resources, as it does for other keyboard modes.
RIS, DECSTR and DECSCL reset the resources; alternate screens, cursor saves,
resize and unchanged reconfiguration preserve them. Application negotiation
takes priority over optional Win32 input transport; Kitty input and configured
local bindings keep their existing priority. Numbered keys in older PuTTY
keyboard profiles and non-bitmap arrow configurations keep their encodings.

## Independent reference

The pinned, unmodified XTerm 412 source is
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f`; executable SHA256 is
`fabe97acf7dc1d7b5e4786d797f77be94edf11d43ccbd1322cbfad7e52120688`.
The [control specification](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
and retained `input.c`, `charproc.c`, `keysym2ucs.c`, manual and control-sequence
text describe the behavior. Expected key bytes come from XTest events on a
private Xvfb server. The Windows desktop and clipboard are not used.

The selected fourth capture has 81 cases and 395 steps. Three literal controls
verify ordinary input, Ctrl+Alt+F1 and Shift+Insert before the matrix runs.
Private-server virtual-console switching is disabled, and an explicit
`insert-seven-bit` translation prevents local XTerm shortcuts intercepting
the protocol samples. The first three setup observations remain in the archive:
default server/terminal bindings intercepted some events, and the third
capture used an incorrect Xrm newline that disabled key translations. They
are not product parity evidence.

`special-key-modifiers-reference.tar.gz` and its validation manifest retain
all four captures and their exact fixtures. The generator checks the archive
digest and projects **394 unchanged steps**. One reset-all observation is
retained separately: the selected XTerm leaves these two resources unchanged
for `CSI > m`/`CSI > f`, whereas Nemoterm retains the documented all-resource
reset contract. This difference has a separate policy test and is not counted
as a matching reference step. As with character modifiers, accepted numeric
levels are bounded; `65535` restores disabled state in Nemoterm. The first
capture records that XTerm instead treats an explicit `65535` setter as an
extended level; this is not the same as its `CSI > resource n` disable command.

## Validation and limits

MinGW and GCC/Clang with ASan, UBSan and leak checking pass the 394-step replay
both whole and bytewise. All three also pass the existing keyboard, UDK,
query, state-control and Win32-input suites. Windows checks verify optional
Win32 input yields to negotiation and resumes after reset.

Native replay uses owned HWND messages and ConPTY. The previous colour-fix
image fails at the first newly supported query, after its mechanism controls
pass. The fixed portable image passes **378 exact native streams** and all
three owned processes exit naturally. Sixteen local copy/paste or scrolling
combinations are intentionally excluded from HWND replay and covered by the
core reference; no clipboard is accessed. `special-key-modifiers-fix.tar.gz`
retains both images, source-built sidecars, fixtures, source hashes, raw replies,
core logs and cleanup records. The negative comparison's forced cleanup is
preserved and is not reported as a successful shutdown test.

This does not establish physical-keyboard or full-product acceptance. The
new core/native checks are included in ordinary and single-image CI; their
complete candidate results remain pending, with an unresolved MSVC native
tab-selection access violation in run 43768960240. Resources 3, 6 and 7 are
covered by the later [extended-key implementation](extended-key-resources.md).
Resource 0, remaining application/IME work, and the outstanding desktop tests
remain separate work.
No accepted distribution is replaced and no memory-limit waiver is introduced.
