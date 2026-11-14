# ISO 2022 source codes and rectangle checksums

The legacy DECRQCRA sum must use a character's original graphic byte and
designated character set. Reconstructing it from the displayed Unicode glyph
was wrong for national, DEC supplemental/technical and ISO supplemental sets.
The [official XTerm control reference](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
defines the query and checksum-extension flags; pinned XTerm 412 source and
independent runtime replies supply the detailed character mappings.

Nemoterm now calculates the legacy code at character write time. It retains an
override only when the Unicode/tagged-cell fallback would produce another code.
The override occupies spare bits in the existing 64-bit cell metadata; neither
`termchar` nor `truecolour` grows. A separate bit preserves XTerm's byte-NRC
pound/font-slot checksum while rendering and copying Unicode U+00A3. One
`uint64_t` value accompanies the existing last-character state for REP.
The renderer strips checksum bits before grouping/drawing text. Current SGR
state, queries, selection and ordinary Unicode output do not acquire them.

The generator also imports the pinned upstream legacy-code tables with the
existing license notice. These are immutable data, without allocation or a new
runtime dependency. NRC output now distinguishes byte-mode MAP entries from
Unicode-only mappings. DOCS, NRC and UPSS resolution still determine the mapping
at write time; later redesignation does not change stored glyphs or checksums.

## Independent reference

Reference image SHA-256:
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
Each final case runs in a fresh XTerm on a private Xvfb display. Startup encoding
and DOCS cache are explicitly normalized by the recorded input stream.

All 172 mapping streams match 33,024 independently captured legacy/Unicode
cell sums, both as complete input and split into individual bytes. They cover
GL/GR, NRC on/off, the supported 94/96 designators, JIS at level 3 and DEC
supplemental at level 2. This is not an all-level/all-encoding proof.

Twelve of sixteen additional lifecycle streams match exactly. Four captured
differences are retained as explicit, authored expectations in the test:

| Operation | Observed XTerm 412 | Nemoterm behavior |
| --- | --- | --- |
| ICH/DCH | Unicode moves, but legacy source metadata stays at the old columns | Metadata moves with its character |
| ASCII overwrite of byte-NRC pound | Display becomes `#`, legacy sum still uses the previous British set | New character replaces the old metadata |
| REP after redesignation and CUP | Does not overwrite the original three cells in this stream | Existing Nemoterm last-glyph/cluster behavior repeats the last glyph and its metadata |

The raw XTerm replies are never rewritten to look like Nemoterm. These four
cases are not counted as exact matches. XTerm `screen.c`/`charproc.c` show its
separate source-code arrays and the relevant copy/write paths. Earlier batched
captures also exposed dependence on leftover reference cell metadata; both
those captures and their failing comparisons are retained separately from the
final isolated capture.

Authored checks verify compressed history and reflow retain all three German
source codes, and the existing selection test still copies Unicode text.
Nine Linux suites pass normally and under ASan/UBSan/leak checks; nine MSVC
suites pass. Existing charset output, state, paste, rectangle, query, SGR,
reflow, grapheme, keyboard and Sixel coverage remains in those suites.

## Native executable

The local single executable is 4,530,176 bytes, SHA-256
`9f224f62babece3cbaf225d9a9bbce38c15256a2c4a1385846e7b6479fd5aa90`.
Its cached source-host link inputs are recorded. It is not a CI artifact or a
replacement for the accepted executable.

Actual GDI, OpenGL and DirectX each pass nine text/pixel scenes at 160x48 using
SarasaTermSC Nerd Font Light. New scenes cover byte-NRC Greek and pound.
The public automation endpoint verifies legacy/Unicode replies, rectangle-copy
preservation and the pound checksum through real ConPTY. Existing paste/typing
checks pass. The outer job naturally drains eleven processes in 24.139 seconds.

## Memory and resource acceptance

The unchanged `6ab186d` fixture exercises actual 160x48 Sarasa windows with
history, images, resizing and temporary tabs. No concurrent compilation,
capture requests or injection ran during memory sampling; existing limits and
all failed samples are retained.

GDI completes all nine groups, with 556 samples: peak private working set
16,044,032 bytes, total working set 42,749,952 and private commit 18,796,544.
All 58 outer-job processes drain naturally.

DirectX fails the ninth resource-return cycle, before its full history/image
workload. The two-tab baseline is 547 handles / 39 GDI / 50 USER objects; eight
cycles return at 547 / 39 / 52, but the ninth ends at 549 / 39 / 53 after the
unchanged two-second deadline. This exceeds the USER allowance of two. The
frontend was still running; the inner job forcibly closed its five remaining
processes. Natural outer-job drain does not make that cleanup a pass.

The 212 early DX samples peak at 20,176,896 private working-set bytes,
59,379,712 total and 74,178,560 committed. These are incomplete diagnostic
observations, not a passed 25 MB workload acceptance. Failure-time window
metadata contains IME-related windows but has no matching baseline window
inventory, so it cannot establish their origin or a cause. This failure differs
from the older +40-handle / +12-USER failure and from the historic close crash.
There was no retry to replace the failed result and no threshold change.

This checkpoint's full CI is pending; the current accepted EXE remains unchanged.
The [validation manifest](iso2022-checksum-validation.json) retains sources,
reference captures, failed/passed comparisons, native pixels and resource samples.
The historical tab-close access violation, broader protocol and real-agent
coverage, and DirectX's total working-set target remain open.
