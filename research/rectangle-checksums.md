# Rectangle checksum queries

This development change adds DECRQCRA and XTCHECKSUM to the single-executable
frontend. It is not a claim of complete xterm or DEC hardware emulation.
The accepted executable on `main` remains separate.

## Behavior and settings

`Terminal / Screen queries / Allow applications to query screen checksums`
persists as `NemoAllowChecksum`, default false. Both mode selection and replies
are disabled until enabled. Revoking the setting stops replies immediately.
The checksum request additionally needs VT420-or-newer operating compatibility.
It returns `DCS Pi !~ hhhh ST`, with four uppercase hex digits, modulo 65536.
Identifiers saturate at 65535; an omitted numeric identifier is zero. A wholly
parameterless request is ignored. Colon subparameters are rejected.

Coordinates use the shared bounded rectangle parser, relative to both margins
under DECOM. Inverted rectangles return zero. Page arguments select the sole
addressable page, the current active buffer. The short one/two-argument form
matches xterm's unusual use of the identifier/page as top/left coordinates.
Hidden retained columns, inactive buffers and scrollback are not queried.
Sixel pixels do not contribute to the character sum. No query allocates or
extends a retained line. Four bytes of mode state are added per terminal;
the cell structure is unchanged.

Mode bits match the pinned executable's observed implementation:

| Bit value | Effect |
| --- | --- |
| 1 | Return the positive sum rather than its negation. |
| 2 | Omit protected/concealed/underlined/inverse/blinking/bold attribute weights. |
| 4 | Include all positions instead of trimming undrawn blanks. |
| 8 | Include undrawn cells in the trimming path. |
| 16 | Use Unicode base values instead of legacy DEC/ASCII checksum codes. |

RIS and DECSTR reset this mode; alternate-buffer switching retains it.
As in the reference implementation, combining marks contribute only with bit 4
set and bit 16 clear. This is different from what one might infer from the
control-sequence document alone. DEC graphics checksum mappings are fixed
protocol tables, independent of Windows font fallback and GDI font indices.

## Independent reference and explicit differences

Reference: XTerm(412), built from
[`5c75ead9a75d4b2e666ca06fa94503b5766ed93f`](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f),
executable SHA-256 `089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
The primary sources are `ctlseqs.txt`, `screen.c:xtermCheckRect`,
`charsets.c:xtermCharSetDec`, and the DEC graphics mappings. It runs on a private
WSL Xvfb display with `-ti vt520 -u8 -xrm '*allowWindowOps: true'`. VT520 avoids
the VT525-specific color contribution.

`tests/xterm_checksum_oracle.py` records 429 cases in `checksum-xterm.json`.
`generate_checksum_oracle.py` retains exact bytes for 364 generated C/Python
cases. Its 65 exclusions are named, reasoned and never rewritten to pass:

* 32 combining scenes: Nemoterm retains input base/mark sequences; xterm composes
  some of them. A decomposed e plus acute has base value 101 here, not 233.
* 16 Unicode legacy scenes: xterm's stored `charSeen` values depend on preceding
  writes. The separately reproducible `--ordering-probe` capture shows the same
  mode-1 Unicode sequence returning `014B` after a Unicode scene, versus `00F7`
  in the full scene matrix. Both raw captures are retained. Nemoterm derives a
  deterministic legacy value from the retained character, without another cell
  cache. Its single-scalar legacy comparisons remain in the exact oracle set.
* 16 British-charset legacy scenes: the inherited PuTTY UTF-8 model ignores that
  national charset. It retains ASCII `#`; xterm's legacy checksum can use pound
  even when its Unicode checksum uses `#`.
* One explicitly empty identifier: Nemoterm uses zero, not xterm's 65535 missing
  parameter sentinel. This is consistent with its other numeric queries.

Eight direct cases assert these retained-cell policies and colon-mode handling.
DEC graphics comparisons explicitly enable the existing `UTF8linedraw` setting.
Unimplemented national/ISO sets, SCO font modes, full Unicode normalization and
VT525 color checksums are not claimed compatible.

## Selection regression and validation

The new nonmutation test exposed a pre-existing selection bug: `term_out`
checked the cursor's intersection with a selection after every received byte,
including each byte of a query. A selection covering a stationary cursor was
therefore removed. The extra point check now runs only when the cursor moves;
cell writers and erasers retain their own overlap checks. Tests verify both
query preservation and cancellation when a selected cell is actually replaced.
Checksum queries also preserve pending grapheme attachment and pending wrap.

Core checks cover the exact oracle, direct policies, disabled/revoked access,
selection, both buffers, sparse lines and oversize coordinates. Native checks
run the same cases through the bundled host, check the default-denied profile,
resize the actual window, query the origin-relative corner, and repeat a full
screen query 40 times while asserting identical captured text/Sixel pixels.
Settings checks cover the visible control, default, saved value and reload.
The final image passed 35 MSVC core/offscreen suites, three MinGW suites,
four Linux ASan/UBSan suites and 16 native groups. The image is 4,421,120 bytes,
SHA-256 `219dec1279798188ef60fb522fe63a566026d60c2cbdb8fb444331fad95e96bb`.
It is staged at `build/local-checksum-check/dist/nemoterm.exe`, with no sidecars.

The first permissive settings run recorded GDI for its OpenGL transition.
That early reading is preserved in `checksum-settings-initial-observed.json`.
An independent fresh OpenGL window reported renderer 2. The settings fixture
now records its final renderer after a terminal query/reply barrier, because
destroying the modal settings window can precede the caller's reconfiguration.
A strict rerun with both `NEMOTERM_REQUIRE_OPENGL=1` and
`NEMOTERM_REQUIRE_DIRECTX=1` passed: GDI/OpenGL/DirectX/GDI used 1/2/3/1.
This verifies actual GPU switching on this run; it does not establish the cause
of the first early GDI reading. Both observations are retained.

One graphics regression run initially encountered a transient empty mailbox
read during resize (`KeyError: columns`). The shared fixture now waits for a
complete snapshot while still checking process exit and child errors. The
original failure is retained in `checksum-graphics-fixture-failure.json` and
the affected protocol groups were rerun; it was not discarded as a product pass.

Artifact hashes, compiler/sanitizer results and native regression results are
in `checksum-validation.json`; actual replies are in `checksum-observed.json`
and `checksum-disabled-observed.json`. `checksum-window.png` is an owned-window
capture. Local clipboard-dependent tests were not run; the mandatory CI
clipboard and real-Codex gates remain in place. GitHub Actions startup must be
checked separately from local passes; no new hosted artifact is implied.

Reproduction: `python tests/generate_checksum_oracle.py --check`, build/run
`test_queries` and `test_conf`, then point `NEMOTERM_TEST_EXE` at the staged
single executable and run `tests/checksum_window_smoke.py`. The native test is
required by `scripts/test-single-exe.ps1`; the core workflow verifies generated
fixtures. The legacy portable workflow's unpatched sidecar host is not used
as evidence for this tagged-cursor-sync integration.
