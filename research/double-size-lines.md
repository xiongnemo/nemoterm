# Double-size line output and wrapping

The three double-size tabulation failures found at `3aec08c` are fixed. Output
now uses each row's logical character width: 80 physical columns provide 40
positions on DECDWL and both DECDHL halves, while the following single-size
row uses all 80. The parser recalculates the destination limit after wrapping.

The same limits apply to late grapheme widening, saved pending wraps, forward
cursor movement and tabulation. A wide scalar or a cluster growing into a
one-position row becomes a single replacement character without overwriting
hidden cells. Combining marks attach to the last visible cell even when its
column index is zero. Changing the line size preserves the row's wrap flags.
Absolute positioning in the hidden half is retained, but subsequent graphic
output there is ignored, matching the captured xterm behavior.

## Reference and deliberate difference

`tests/xterm_double_size_oracle.py` records 48 cases from the pinned XTerm 412
binary under a private Xvfb display. `double-size-xterm.json` retains all input,
raw replies and 27 cell checks per case. `test_state_control` compares 45 of
them, including cursor reports and 1,215 cell values. Xterm's composed e-acute
is treated as equivalent to Nemoterm's retained e + combining acute sequence.

Three captures expose an xterm batching quirk rather than the target behavior:
after 40 characters on a double-size row, one continuous run of 80 characters
wraps the next single-size row after only 40. In the pinned `charproc.c:7041`,
`real_rmargin`/`last_col` are computed before `WrapLine`, then reused for that
output run on the next row. Nemoterm uses the destination row's actual size.
Direct grid assertions and a native ConPTY query verify the full 80 characters
fit on that next row. The raw xterm discrepancies are retained and explicitly
excluded from equality fixtures rather than silently rewriting the reference.

The old three tabulation exclusions are removed: 108 tabulation cases now
match the reference. Only the three documented malformed-colon policy cases
remain excluded from that suite.

## Verification and artifact

* All 35 MSVC core/offscreen suites passed, including the expanded state and
  grapheme suites and the existing renderer checks.
* MinGW state, grapheme and upstream terminal suites passed.
* Linux state, grapheme, margins and Sixel suites passed ASan/UBSan with leak
  detection; the compiler/linker cache contains both sanitizer flags.
* The exact local single image passed 108 tabulation comparisons, 45
  double-size comparisons, one destination-row-width assertion, and isolated
  single-EXE startup with the console host running from the same image.
* Owned native jobs drained naturally with zero active processes. The final
  GDI screenshot `double-size-window.png` was inspected: full double-height
  text, Chinese text and composed-looking accents are visible, and characters
  crossing the logical edge appear on the next normal row.

The first native attempt failed at a literal LF because the generic Python
fixture used Windows newline translation. The shared oracle driver now enables
its existing `NEMOTERM_TEST_EXACT_OUTPUT` option, which disables Python newline
translation and selects the corresponding console output mode. The unchanged
binary passed the replay. The initial failure is retained in the validation
record, separately from product failures.

Local test executable: `build/local-double-size-check/dist/nemoterm.exe`,
4,417,536 bytes, SHA256
`287ad39080163017e4afca8c433f709551b3b45fa2a4b80ace7ffd103cbf7204`.
`double-size-validation.json` records source hashes, test output and exact
native evidence. This does not replace the previously accepted main artifact
or close pending clipboard/real-agent CI gates. CI account billing remains an
external startup blocker. Row-size-specific editing and resize combinations
still need a broader matrix; this checkpoint proves output and cursor behavior.

References: [xterm control sequences](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html),
[pinned xterm source](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f).
