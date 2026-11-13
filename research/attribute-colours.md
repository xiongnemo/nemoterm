# Attribute colours: source and build checkpoint

The development branch implements the five xterm special colours independently
of PuTTY's default/cursor palette slots. `OSC 5 ; index ; spec` sets or queries
bold, underline, blink, reverse and italic colours (indices 0–4). Their `OSC 4`
aliases are 256–260. Replies retain the caller's opcode/index and BEL or ST
terminator. Number 261 remains outside this namespace: none of these operations
can overwrite PuTTY's internal default foreground/background/cursor entries.

`OSC 105` resets all or selected special colours. `OSC 104` accepts the same
256–260 aliases, and its empty form now resets both ANSI and special colours,
matching the reference source's `MAXCOLORS` loop. It still does not reset the
separate OSC 10/11/12 dynamic colours. An unset special colour follows the
configured/platform default foreground, independently of application OSC 10.
Palette pushes retain the five overrides and their unset state. Pops restore
colours without restoring enable switches; SGR, RIS, DECSTR and alternate-screen
changes likewise preserve the switches. No new per-cell or scrollback fields
are introduced. Five `optionalrgb` fields plus a one-byte mode mask add 21 bytes
of members per terminal before padding, and 20 bytes per allocated palette
snapshot. The existing ten-slot lazy allocation bound is unchanged.

`OSC 6` and `OSC 106` share enable/disable handling: zero disables a mode and
nonzero enables it. Modes 0–4 default off. Mode 5 implements the documented
override of explicit ANSI/truecolour choices. Without mode 5, foreground
attribute colours apply only to the default foreground and reverse colour
applies only to the default background. Enabled foreground modes use the source
priority blink, bold, underline, italic; reverse supplies the background.
The display policy follows the default `veryBoldColors=0`: enabled bold,
underline and italic modes suppress their corresponding font styles, while
preserving ANSI bold brightening. Replaced blinking text does not blink; reverse
mode suppresses SGR inversion. Screen reverse and selection then apply, with
explicit selection colours taking precedence. Stored SGR/cell data is untouched.

## Source basis and boundaries

The audit used the pinned XTerm(412) source already retained locally, upstream
commit `5c75ead9a75d4b2e666ca06fa94503b5766ed93f`. The input-file hashes are in the
[build manifest](attribute-colours-build-validation.json). Relevant entry points:

* `misc.c`: `ReportAnsiColorRequest`, `ChangeAnsiColorRequest`,
  `ResetAnsiColorRequest`, `do_osc`, and palette push/pop.
* `ptyx.h`: `COLOR_BD` through `COLOR_IT`, `ReverseOrHilite`.
* `xterm.h`: `MapToColorMode`, `checkVeryBoldColors`.
* `charproc.c` and `util.c`: default resources, extended colours and drawing.
* `ctlseqs.txt` and `xterm.man`: OSC 5/6/105/106, `colorAttrMode`,
  `colorXXMode`, and `veryBoldColors`.

The official [control-sequence specification](https://invisible-island.net/xterm/ctlseqs/ctlseqs.pdf)
documents mode 5, but the inspected `do_osc` switch handles only 0–4. Nemoterm
implements the documented mode 5 rather than copying that omission. No runtime
comparison has yet determined the observable reference result. XTerm also
caches extended colour indices while writing cells; Nemoterm resolves its
overlays at paint time so a mode change updates existing visible text. Exact
timing and mixed-attribute parity require independent pixel evidence.

Existing strict decimal parsing is retained: signed, junk-suffixed and
overflowing values are rejected, rather than emulating XTerm's permissive
`atoi` cases. Empty mode fields surrounded by separators represent zero;
missing final values do nothing. Unknown numeric mode pairs are skipped.
Oversized/binary OSC strings and cancelled operations do not partially apply.
Malformed pair recovery is not claimed identical to XTerm. The subsequent
[settings implementation](attribute-colour-settings.md) adds saved custom
defaults, initial modes and style retention. Its reset path reveals the saved
custom colour before falling back to the configured foreground. The style
mask is a Nemoterm setting, not an identical `veryBoldColors` resource mapping.
Pointer/Tektronix colours remain separate, unimplemented protocol work.

## Prepared validation, not runtime acceptance

The subsequent [independent capture](protocol-reference-20261114.md) found
that both RIS and DECSTR reset the five special colours to their configured
defaults. This agrees with `ReallyReset` calling `ResetAnsiColorRequest` for
both hard and soft reset in the pinned `charproc.c`. The implementation now
clears application overrides in both paths, retaining saved defaults and mode
switches. Wire cases and configured-colour paint checks cover the correction;
the local test target is compiled and linked only, with runtime checks in CI.

Two reference differences remain separate from that fix: overflowing indices
remain rejected, and `OSC 105;2` unexpectedly resets an additional slot in the
pinned capture. Its `ResetAnsiColorRequest` source advances `next` after testing
`strchr(";", *next)` even when `*next` is NUL. That permits scanning beyond the
logical string terminator; the exact extra slot still needs a runtime causal
check. The collector now retains short/long prior-query and trailing-separator
variants. Nemoterm retains the documented selective-reset semantics while this
reference behaviour is investigated.

[Follow-up 43456769586](https://github.com/xiongnemo/nemoterm/actions/runs/43456769586)
repeats both corrected reset replies and retains eight selective-reset variants.
Adding a trailing separator to `OSC 105;2`, or preceding it with an `OSC 4`
alias query, prevents the extra underline reset. This supports the parser-tail
explanation; Nemoterm keeps the documented single-index behaviour. The reference
collector now checks exact upstream bytes for both known differences, reports
them separately from matching product cases, and still fails on any unexpected
reply. This does not claim full parity or change either product assertion.

39 authored wire cases cover aliases, BEL/ST, selective/full resets, malformed
inputs, stack retention and screen/reset interactions. The mock-renderer suite
adds each mode, priority combinations, preserved stored attributes, explicit
ANSI/truecolour, override mode, screen reverse, selection precedence, ANSI
colour policy, synchronized painting, parser boundaries and cancellation.
The independent XTerm collector retains actual raw replies before comparing;
it has not run and authored cases are not labelled captured reference data.

The native GDI/OpenGL/DirectX fixture compares a coloured-attribute scene with
an explicit-RGB scene including Chinese and a combining character. It also
checks mode updates, palette restoration, synchronized output, resize and
1,000 bounded save/restore cycles. It uses a private saved profile with explicit
white/black defaults, owned windows/processes, and no clipboard access.
GPU measurements are labelled instrumented; the GDI sample gate remains
20,000,000 private-working-set bytes. These fixtures are wired into CI and the
single-file validation script but have not been executed.

MSVC frontend/core compilation, Linux ASan/UBSan compilation and single-EXE
host linking passed. Python syntax compilation, generated-fixture freshness,
PowerShell AST parsing and whitespace checks passed. The host overlay was not
regenerated. Existing unrelated C4319 warnings were seen in the initial Windows
build. **No new executable, unit suite, sanitizer suite, XTerm or desktop
fixture was run**, in accordance with the user's testing pause.

The candidate is isolated under `build/local-attribute-colours-unverified`.
Accepted main and the last native-tested palette candidate remain unchanged.
This patch does not establish runtime compatibility, working-set compliance,
DirectX memory acceptance or completion of the terminal goal. Resume with core
checks and independent wire/pixel comparison, then all native colour/selection
regressions and uninstrumented GDI memory sampling. Inspect mismatches rather
than regenerating expected data to match the implementation.
