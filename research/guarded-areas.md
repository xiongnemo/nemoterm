# ISO guarded areas: source and build checkpoint

The development source adds SPA (`ESC V`) and EPA (`ESC W`). SPA selects the ISO
protection family and marks subsequently written cells protected. EPA ends
protected writes without removing protection from existing cells or changing
the selected family. The existing legacy C1 decoder can dispatch bytes 0x96/97
when the configured byte codepage recognizes them as controls. UTF-8-encoded C1
text is not reinterpreted as an SPA/EPA control; this patch does not redesign
the existing codepage-sensitive C1 decoder.

Ordinary ED/EL/ECH now preserve protected cells while ISO protection is selected.
For example, `A SPA BC EPA DEF` followed by a full EL retains `BC`. A later
DECSCA selects DEC protection, after which ordinary EL clears those same cells;
DECSEL/DECSED still preserve them. The most recently selected family applies to
all protected cells, matching the pinned XTerm implementation's shared cell bit.

| Operation | DEC family | ISO family |
| --- | --- | --- |
| Ordinary ED / EL / ECH | Clears protected cells | Preserves protected cells |
| DECSED / DECSEL | Preserves protected cells | Preserves protected cells |
| DECSERA rectangle | Preserves protected cells | Clears characters, retains attributes |
| DECERA rectangle | Clears protection and characters | Clears protection and characters |
| Ordinary text overwrite | Replaces the cell | Replaces the cell |

The shared erase helper retains whole protected wide glyphs and their combining
chains, hyperlinks, selections and overlapping Sixel pixels. Only actually
erased spans lose those objects. Interior erased spans are marked drawn while
trailing spans remain undrawn. EL0/ECH cancel pending wrap; other protected
erase ranges do so when a span is erased. Full-display protected erasure retires
an empty protection family, including ED0 at home and ED1 at the last cell.
DEC rectangle operations continue to leave cursor, wrap and line size alone.

The family is global operating state, not a cursor-save attribute or a per-screen
setting. The existing saved write-protection bit remains part of cursor rendition.
RIS/DECSTR end the family; SGR reset preserves the write-protection bit. DECRQSS
for DECSCA reports one only when the family is exactly DEC and protected writes
are enabled. DECRQPSR reports the DEC family bit. DECRSPS changes that bit without
clearing ISO state, so the reference's combined DEC/ISO state is retained too:
ordinary erases remain guarded, while DECSERA does not treat it as pure DEC.

One existing `bool` becomes one `unsigned char` containing the family bits. No
per-cell, per-line, history or palette storage grows, and no new allocation path
is introduced. This is source accounting, not new memory acceptance.

## Primary-source basis

The reference is pinned
[XTerm 412](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f),
with the [control-sequence reference](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
identifying the SPA/EPA forms. Inspected source functions:

* `charproc.c`: SPA/EPA dispatch, DECSCA and presentation-state reporting.
* `util.c`: `do_erase_char`, `do_erase_line`, `do_erase_display`, `ClearInLine2`,
  `ClearRight`, `ClearLeft` and `ClearLine`.
* `screen.c`: `ScrnWipeRectangle` uses the exact DEC family for DECSERA.
* `misc.c`: DECCIR restoration and DECRQSS for DECSCA.
* `ptyx.h`: `OFF_PROTECT`, `DEC_PROTECT`, `ISO_PROTECT` and the shared-bit policy.

Their exact SHA-256 values are retained in the build manifest. This is a source
comparison; it is not an independent runtime-oracle result.

## Prepared checks and build evidence

`tests/guarded_area_cases.py` contains 63 authored wire expectations. Individual
cell checksums include the protection bit, so the matrix checks both position
and attributes. Cases cover ordinary/selective erase ranges across the three
families, rectangles, family changes, queries, saved write flags, resets,
presentation restoration and pending wrap. A prepared collector retains raw
XTerm replies before comparison; it has not run.

`test_selective_erase` includes these cases plus wide/combining cells, Sixel,
hyperlinks, protected selections, shared alternate-screen state, history/reflow,
mocked legacy C1 control-table entries and UTF-8 C1 text. The owned native GDI
fixture compares protected text/Sixel with an explicit visual baseline, checks
rectangles, synchronized output and reset, and prepares 1,000 state transitions.
It has no clipboard or global input operations. Both CI paths include it.

MSVC compiled the frontend and five core test targets. Linux compiled four
ASan/UBSan-instrumented test targets. The single-image OpenConsole/frontend link
completed successfully. Python syntax/generator freshness, PowerShell AST and
Git whitespace checks passed. The initial Linux command included `test_terminal`,
which is not a target in the existing sanitizer configuration; that rejected
command is retained separately, followed by the successful available-target build.
The existing two MSVC C4319 warnings remain.

The [build manifest](guarded-area-build-validation.json) records the source and
log hashes and the separately staged candidate. **No product/test executable,
sanitizer run, XTerm/Xvfb, native window, screenshot, keyboard/mouse automation
or clipboard access ran for this checkpoint.** New and affected erasure paths
need independent wire, core, pixel, regression and memory validation after the
user resumes runtime testing. The accepted main executable remains unchanged.
