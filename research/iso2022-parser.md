# ISO 2022 parser integration checkpoint

This development branch now connects the immutable mapping component to the
real terminal parser. **It has not been merged to main or promoted to the
accepted executable.** Native glyph/pixel acceptance, input encoding and the
remaining protocol differences below must be resolved before promotion.

## Implementation

G0–G3 accept the supported one- and two-byte 94-set designations; G1–G3 also
accept 96-set introducers. Bounded integer handles refer to immutable tables
and retain the introducer size separately from the descriptor's reported size.
Mapped extended characters use existing Unicode cells: no per-cell charset
allocation or added cell fields. The four-bank cursor cache also retains these
handles. Presentation reports include aliases and the 94/96 size mask.

DECNRCM (42), its status query and saved-mode slot are implemented. NRC mode
temporarily enables byte parsing. DOCS uses a three-state override so an
explicit `ESC % @` can disable a configured UTF-8 decoder. `ESC % G` caches
the byte designations, resets them for UTF-8, and switching back restores that
cache. Encoding now remains global across cursor save/restore and alternate
screens, matching the isolated reference captures; the previous PuTTY cursor
UTF-8 cache is removed. A pre-existing local-policy test now selects UTF-8
before designating its saved banks, and checks that restoring a cursor does
not undo an encoding reset by local configuration.

The byte path now consumes GL DEL for 94 sets instead of PuTTY's destructive
backspace. British and DEC-line GR mapping follow the captured byte semantics.
Unknown registered designations reset the bank to ASCII; unregistered finals
after `%`, `&`, or `"` cancel without replacing the prior designation.

XTerm 412's `restore_DECCIR` consumes but ignores the size field and calls
`xtermDecodeSCS` with group zero. This branch follows its ambiguous-designator
behavior: restoring `%6F&4H` with size mask `J` reports mask `B`, because `H`
selects Swedish NRC rather than ISO Hebrew. This is an observed reference
limitation, not a claim that every 96-set presentation report round-trips.
The normal DECSC/DECRC four-bank cache does preserve the descriptor.

## Validation

- The 160 previously captured level-5 mapping streams run through the real
  parser both in one block and byte-by-byte. All 15,360 distinct reference cell
  values, final cursor positions, presentation replies and mode replies match
  in both transport shapes.
- Another 25 state-transition streams use a fresh private XTerm/Xvfb process
  for each case. Both transport shapes match all replies, covering extended
  banks, cursor/alternate caches, NRC modes, DOCS, cancellation and single shifts.
- A mock-clipboard test copies displayed German NRC Unicode and checks rectangle
  fill. It does not write the system clipboard.
- Eight Linux targets pass normally and under ASan/UBSan with leak detection:
  mapping, state control, queries, rectangles, Sixel terminal, reflow, keyboard
  and grapheme terminal. The modified mapping/state tests also pass after the
  additional handle and clipboard checks.
- MSVC builds the Windows frontend and eight test targets. Mapping, terminal,
  state, query, rectangle, reflow, Sixel and grapheme suites all pass.

Initial failures are retained. The first parser fixture omitted the existing
checksum-permission setting; the first Windows configuration incorrectly kept
`NDEBUG`, which this source rejects. A mock-only crash on BEL had a null bell
callback (ASan stack retained); supplying the mock callback resolves it.
This is unrelated to the unresolved native tab-close crash. Initial reference
state streams shared one process; DOCS' separate charset cache leaked prior
state across RIS, so acceptance uses fresh processes instead. Both captures
remain in the [evidence manifest](iso2022-parser-validation.json).

## Still open

- Native frontend rendering/copy under the actual Sarasa font and all three
  renderers; ConPTY transport; before/after memory and handle measurements.
- Reverse mapping for typed or pasted Unicode in NRC/byte modes. This checkpoint
  tests terminal output parsing, not complete bidirectional encoding.
- UPSS reassignment; the level-2 DEC supplemental and level-3 JIS runtime matrix;
  the remaining UTF-8/NRC combinations and more malformed/mode-policy cases.
- Xlib's legacy non-Unicode NRC glyph indices remain intentionally outside the
  Unicode mapping component. No complete ISO 2022 conformance is claimed.
- Legacy DEC checksums for extended sets require retained original byte/set
  information or an independently validated equivalent. Only the Unicode
  checksum mode is used for the new mapping acceptance.

Full CI for parser commit `9abf339` has since passed:
[core](https://github.com/xiongnemo/nemoterm/actions/runs/43588399701) and
[single image](https://github.com/xiongnemo/nemoterm/actions/runs/43588399714).
Subsequent input, native rendering and memory work is recorded separately in the
[input checkpoint](iso2022-input.md); the original archive above is unchanged.
The accepted root `dist/nemoterm.exe` remains source `8ff214f`, SHA-256
`c110843b1fd5a551d654df094fa716c1ea1c48383d90e642b964d7dfb3d15e26`.
