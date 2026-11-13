# Selection-colour development checkpoint

The development branch implements OSC 17/19 (selection background/foreground)
and OSC 117/119 (restore the corresponding default). Runtime validation is
paused at the user's request. This checkpoint is source and build progress;
it is **not** a tested protocol or renderer acceptance result.

## Implementation

Two optional RGB overrides live in `Terminal`, outside screen and scrollback
cells. Unset components keep the existing inverse-video selection. Explicit
components override the displayed selection colour, including rectangular
and application-highlight selections. Rendering changes the temporary display
record; text, stored SGR and copied content are not rewritten. The frontend's
existing true-colour path handles GDI, DirectX and OpenGL.

Colour changes invalidate the terminal display and defer painting during mode
2026. Palette snapshots retain both the colours and their unset state, so
restoring an ordinary selection does not turn a per-cell inverse into a fixed
RGB colour. Nominal added storage is eight bytes per terminal and eight bytes
per allocated palette snapshot; no per-cell field or new external dependency
is introduced. Allocator and structure padding are not runtime measurements.

Queries use the existing bounded RGB parser and BEL/ST replies. The dynamic
list now advances through commands 10–19, preserving unsupported pointer and
Tektronix parameter positions. Those operations themselves remain missing.
Empty colour values are ignored. Truncated/binary payloads are rejected by the
existing OSC guard. Resetting a selection component does not reset indexed or
default text colours. Configuration refresh preserves application overrides;
the Linux full-palette reset clears them.

The source reference is [XTerm's pinned control-sequence
specification](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.txt)
and `misc.c::ChangeColorsRequest`, `ReportColorRequest`, `ResetColorsRequest`,
`xtermPushColors` and `xtermPopColors` at that same revision. In particular,
DECSCNM addresses the opposite selection component while preserving the
requested OSC number in the reply. Selection resets ignore their payload,
as the reference reset dispatcher does.

XTerm also has selection-resource heuristics (`highlightColorMode` and
`highlightReverse`). Nemoterm's current explicit-colour display policy is
described above. Exact rendering equivalence, default/reset behaviour and
interactions with these XTerm resources remain to be compared; implementing
the OSC numbers does not establish complete XTerm selection compatibility.

## Prepared verification

* Thirty authored protocol cases cover chaining, unsupported intermediate
  positions, BEL/ST, cancellation, invalid colours, reverse video, resets,
  alternate screens and palette stacks. They are labelled as authored
  expectations, not fabricated reference captures.
* `test_osc_colour` includes additional mock-renderer checks for displayed vs
  stored attributes, default queries, independent resets, unset-state stack
  restoration, synchronized presentation, rectangular/application highlights,
  resize, overflow and 1,000 restoration iterations. It never uses a system
  clipboard.
* `selection_colour_window_smoke.py` prepares all three native renderer modes,
  pixel restoration, background pixels, synchronized frames and rectangle
  resizing. Its temporary profile disables automatic copying and it has no
  clipboard imports or copy/paste actions. GPU capture is instrumented and
  cannot serve as an uninstrumented memory result.
* `xterm_selection_colour_oracle.py` prepares an independent capture, including
  resource-dependent resets. It retains raw results and fails when they differ
  from the authored expectations. It has **not** been executed.
* Both CI workflows include the native fixture. Existing core and sanitizer
  jobs include the extended OSC colour suite. Remote execution and artifacts
  must be verified separately.

## Evidence and next gate

MSVC compiled the frontend and extended colour test, and linked the single
source-integrated executable. Linux compiled and linked the extended colour
test with ASan/UBSan enabled. Python syntax/generation checks and PowerShell
script parsing passed. **No test executable, reference terminal, native
fixture or sanitizer suite was run for this change.** Existing unrelated
MSVC C4319 warnings remain in the link UI and window sources.

The [build manifest](selection-colour-build-validation.json) records exact
source hashes, logs and the unverified image. The accepted main executable
and previously tested palette-stack image remain intact. Prior runtime or
memory passes do not transfer to this new image.

When runtime testing is authorized again, first run the independent XTerm
capture and extended core suite, resolve any differences, then run the three
native renderer fixtures and the uninstrumented GDI memory workload. Review
cursor, wide/combining characters, dim/conceal/bold, selection resource policy
and configured defaults before changing the coverage status to tested.
