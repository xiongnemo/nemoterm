# Relative cursor movement audit

This is the preserved pre-fix result. The [correction](relative-cursor.md) now
matches all 848 streams in both complete CI workflows and downloaded-image
checks under actual GDI, OpenGL and DirectX.

An independent 80x24 XTerm(412) comparison against the published `37ef26d`
single-image artifact found 47 different reply streams in 848 sequences.
These are repeated cases of related behavior, not 47 independent defects.
The first 568-case matrix found 20 differences; a separate 280-case boundary
matrix found 27 more. Every case was collected before the aggregate comparison
failed. Transport completed and all five owned processes in each run exited
naturally. Both comparisons retain their failing result.

Differences are confined to `CSI a` (HPR, 34 streams) and `CSI e` (VPR,
13 streams). With origin mode disabled, XTerm's relative-position commands
can cross the scrolling margins. Nemoterm currently shares the CUF/CUD
handlers, which stop at those margins. The boundary matrix demonstrates the
difference with ordinary counts, including omitted, zero, one, two and three;
it is not restricted to the first matrix's very large count.

For example, with margins at rows 4–17 and columns 8–67, origin disabled and
cursor at row 16, column 66, `CSI 2 a` moves XTerm to column 68 and Nemoterm to
67. `CSI 2 e` moves XTerm to row 18 and Nemoterm to 17. The matrix includes
origin enabled/disabled, positions before/at/beyond boundaries, defaults,
pending wrap, disabled wrap and subsequent printable text.

HPR also differs on double-width rows: XTerm allows reported positions beyond
the row's 40 visible character positions. This observation alone does not
justify copying an unsafe index or claiming visual correctness. The reference
uses `CursorSet` for HPR/VPR; CUF/CUD use distinct handlers. Any correction needs
bounded internal positions, full cell-lifetime assertions and native rendering
checks, especially for subsequent writes and wide/combining text.

CNL/CPL and the boundary matrix's CUF/CUD controls matched in these query
streams. The audit checks cursor reports before movement, after movement and
after a printable character. It does not establish complete pixel, scrolling,
resize or memory behavior. No implementation change is included here, and the
accepted executable remains unchanged.

The [manifest](cursor-movement-audit-validation.json) binds the exact artifact,
reference binary, authored inputs, raw replies, comparison fixtures, failures
and natural cleanup. XTerm source is pinned to
[`5c75ead9`](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f);
the tested product is the
[37ef26d artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43508892024/artifacts/14079650407).
