# Cursor charset save/restore: source and build checkpoint

## Current remote verification (2026-11-14 Sydney)

The 44 authored cases now match independent XTerm(412) replies in
[reference run 43454910323](https://github.com/xiongnemo/nemoterm/actions/runs/43454910323).
The [reference manifest](protocol-reference-validation.json) retains the raw
bytes. Core/sanitizer checks pass, and the
[ea042bc single-image run](https://github.com/xiongnemo/nemoterm/actions/runs/43458313477)
passes the presentation-state fixture with these 44 cases plus its existing
142 captures and ten other direct cases. The restored four-bank pixel scene
matches its explicit baseline; replay, resize, read-only checks and protected
text/Sixel checks also pass. The [raw native record](attribute-reset-evidence/presentation-state-observed.json.gz)
is linked to its EXE by the [manifest](attribute-reset-validation.json), with
natural process-group cleanup. This does not extend the implemented charset
repertoire or prove full ISO 2022 conformance. Local runtime testing remains
paused; the sections below preserve the initial compile-only checkpoint.

The inherited cursor cache saved only the designation of the currently selected
GL bank. For example, an application could designate line drawing in G2, save
the cursor while G0 was selected, change G2 to ASCII, and restore the cursor;
G2 would incorrectly remain ASCII. The GR selector was not saved either.

The development source now saves all four supported G0–G3 designations and both
GL/GR selectors. This applies to DECSC/DECRC, ANSI cursor aliases and private
mode 1048, including mode 1049's implicit main-screen save/restore. The main and
alternate screens retain separate saved caches. Power-on/RIS initializes both;
DECSTR initializes only the active cache through the existing save path.

The current local prohibition on remote character-set changes also applies to
cursor restoration. A previously saved designation, UTF mode or SCO ACS mode
cannot restore those settings while the prohibition is enabled. Saved entries
are retained, so explicitly re-enabling changes allows later restoration.

The extra fixed members total eight `int` values across both screen caches
(32 bytes with the current Windows/Linux compilers). There are no new heap
allocations, screen-cell fields or scrollback fields. This is source accounting,
not a working-set measurement. Pending SS2/SS3 remains live state and is not
added to the saved cache.

## Primary source basis

The reference is the previously pinned
[XTerm 412 source](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f):

* `cursor.c:398–415` (`CursorSave2`) copies `curgl`, `curgr` and all designations;
  `CursorRestoreFlags` at lines 467–480 restores them. `curss` is not copied.
  SHA-256: `3caf38bdfb855243a79ceabd0203be078e1eedacde37d29b646b20702eddfbb8`.
* `charproc.c:1221–1238` (`saveCharsets`/`restoreCharsets`) copies the designation
  table; the DEC and ANSI dispatch paths share the cursor functions.
  SHA-256: `c59a06ec6a3a243bfd1547e11dd0aa38e189e3256644ca6cfc43dc6810a4d325`.
* The [control-sequence reference](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
  identifies DECSC/DECRC, the ANSI aliases and modes 1048/1049.

This patch does not implement additional national/96-character sets, change
PuTTY's UTF-8/legacy codepage mappings, or establish full ISO 2022 conformance.
C0/C1 parsing, selectable eight-bit replies and other ledger gaps remain open.

## Prepared validation and current limits

`tests/cursor_charset_cases.py` contains 44 **authored, runtime-unverified**
wire expectations, not captured reference data. They cover four GL selectors,
three GR selectors, DEC/ANSI/1048 saves, first restore, RIS, DECSTR, single-shift
lifetime and main/alternate cache separation. `test_state_control` uses these
cases and adds direct cell checks for restored GL/GR line drawing, SCO banks
and local policy changes. The existing presentation-state native fixture adds
the wire cases and a comparison between four restored banks and a G0 baseline.

`tests/xterm_cursor_charset_oracle.py` is a prepared independent collector. When
runtime testing resumes, it must retain raw reference replies before comparing
the authored expectations. The existing 142 presentation-state captures remain
unchanged and do not validate these new cases.

The [build record](cursor-charset-build-validation.json) binds source hashes,
the raw MSVC/Linux/single-image link logs and the separately staged candidate.
Windows compiled the frontend and `test_state_control`/`test_queries`; Linux
compiled those tests with ASan/UBSan instrumentation. Both builds and the
single-EXE link completed successfully. Python syntax, generator freshness and
Git whitespace checks passed. The existing MSVC C4319 warnings remain.

**No executable test, sanitizer test, XTerm, terminal window, keyboard/mouse
automation, clipboard operation or screenshot ran for this patch.** Independent
wire comparison, actual cells/pixels, broad regression and memory acceptance
remain pending at the user's request. The accepted main executable is unchanged.
