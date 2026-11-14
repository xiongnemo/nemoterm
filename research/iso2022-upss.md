# User-preferred supplemental character sets

Development follow-up to `90370d65abfce374a237916788c065b028226e8d`.
The [evidence manifest](iso2022-upss-validation.json) retains independent
captures, initial failures, test sources, native pixels and executable hashes.
The accepted root executable has not been replaced.

## Behavior

DECAUPSS (`DCS Ps ! u Pt ST`) assigns the user-preferred supplemental set;
DECRQUPSS (`CSI & u`) reports it. A designated `<` bank resolves that preference
when printing or converting selection input. Changing UPSS affects subsequent
characters, while already rendered cells retain their Unicode values.

The implementation uses immutable existing mapping tables and four small state
slots for the active value, DOCS cache and main/alternate saved cursors. Assignment
uses the existing DCS buffer with a two-character limit; it adds no heap allocation.
Local character-set policy blocks assignment. UTF-8 mode ignores assignment,
while NRC mode permits it. Reports use the current 7-/8-bit reply framing.

The [official XTerm controls](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
describe the operation. The pinned XTerm 412 runtime additionally accepts short
suffix aliases and `0!uA` for ASCII, although the document lists `0!uB`.
Its assignment decoder accepts the extended choices at level 3; its level-3/4
UPSS invocation resolves most choices to Latin-1. The implementation follows the
observed reference, rather than claiming stricter DEC hardware behavior.

UPSS participates in DECSC/DECRC and alternate-screen saved state, unlike the
global encoding selection. DOCS caches/restores it with the other byte sets.
Soft reset selects the normal byte or Unicode defaults. RIS now retains the
encoding selection and DOCS cache, matching XTerm; a local power-on reset still
restores the configured encoding. Byte-mode reset also restores the G2/G3
Latin-1 defaults instead of reporting ASCII unconditionally.

## Reference and parser verification

Each reference case runs in a fresh private Xvfb/XTerm process. The reference
executable SHA-256 is
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.

- 112 independent streams cover assignment/query, invalid parameters, suffix
  aliases, UTF-8/NRC, reset, cursor/alternate saves, cancellation and selected
  control-byte boundaries. Whole-stream and single-byte parsing match exactly.
- 56 mapping streams compare 5,376 independently captured cells: fourteen
  preferred sets, level 3 and level 5, and both GL and GR. Level-3 state is queried
  before changing level to request checksums without erasing the cells.
- 28 independent selection captures cover all fourteen sets at levels 3 and 5,
  using the existing 586-codepoint input. The real long-paste callback path
  matches their exact bytes; the earlier 53 selection cases still pass.
- Authored regressions verify that a preceding DCS cannot supply an omitted
  UPSS parameter and that local character-set policy prevents reassignment.
- Eight Linux suites pass normally and under ASan/UBSan/leak checks. Eight final MSVC suites
  pass. The standalone mapper passes `/W4 /WX` and its 15,360 reference cells.

The first capture could not get checksums at level 3; it is retained separately
from the corrected capture. Initial parser failures exposed acceptance of a
leading-space parameter, ignored C0 payload bytes, and missing GR normalization
in the UPSS designator. Both failed logs and subsequent passing runs are retained.

## Actual native windows

The integrated local executable is 4,526,592 bytes, SHA-256
`5e5a76d851be6e96d1dd89e06ba8e09fd8b654836356fdf56904c84db9b86e17`.
Its exact cached source-host link inputs are recorded; it is not claimed to be
identical to a future CI build.

Actual GDI, OpenGL and DirectX each pass seven logical-text/pixel scenes at
160 x 48 with SarasaTermSC Nerd Font Light. The new scenes cover Greek UPSS,
reassignment and saved-cursor restoration. Each matches direct Unicode rendering
and differs from the blank baseline. The public local API verifies the UPSS
report and sends Greek selection text through ConPTY as `414243`. Existing
German paste and Unicode typing checks also pass. All owned processes exit
naturally; capture uses the public API without focus changes or injected code.

The fixture remains registered in core and single-executable CI. CI's smaller
Consolas grid and explicit hardware-fallback reporting remain separate from
the local actual-hardware acceptance above.

## Memory

The candidate uses unchanged fixtures from `6ab186d`, actual 160 x 48 Sarasa
windows and the existing tab/history/Sixel workload. No compilation, screenshot
requests or injected code run during sampling. All nine existing check groups,
resource limits and natural cleanup pass in both runs. Figures are frontend
peak bytes, not aggregate shell/host memory.

| Actual renderer | Samples | Private working set | Total working set | Private commit |
| --- | ---: | ---: | ---: | ---: |
| GDI | 525 | 16,654,336 | 43,372,544 | 19,550,208 |
| DirectX | 517 | 24,182,784 | 63,537,152 | 86,700,032 |

Both private-working-set limits pass (GDI below 20,000,000; DirectX at most
25,000,000). These are candidate acceptance runs, not a claim of improvement
over the previous image. The accepted executable's hash is unchanged.

## Remaining scope

Full CI for this checkpoint is pending. These finite synthetic workloads do not establish
every real-agent workload or complete ISO 2022 conformance. The broader
lower-level output matrix, extended legacy DEC checksums, all encoding and
malformed-input combinations, the prior native tab-close crash and DirectX's
approximately 50 MB total-working-set target remain open.
