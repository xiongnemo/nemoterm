# Colour reset and screen reverse

An independent capture from pinned XTerm(412) source
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f` exposes two additional gaps:
RIS did not clear application ANSI palette overrides, and OSC 10/11 queries,
sets and resets did not follow the displayed foreground/background under
DECSCNM. The cursor also needs XTerm's stateful foreground-following behaviour.

The [reference run](https://github.com/xiongnemo/nemoterm/actions/runs/43459732585)
captures 25 cases before the implementation changes. Its artifact is
`14054743769`, fixture commit `3f34922b1b49121c3c444792152326c4a96d5b89`.
The [raw replies](protocol-reference-evidence/20261114-reset-palette-xterm.json)
have SHA256 `380e46e9e48dd2262fb0227efb87c0fde2b113cccfc503fce938308182ce5795`.
The reference binary SHA256 is
`9f440380b493c91dbd1fcb8a6277df1ca121390b23fe526baa24c15525f4df64`.
The successful capture job does not itself establish product compatibility.

The cases cover RIS, DECSTR, SGR and alternate-screen changes in normal,
alternate and reversed states; saved-palette restoration; reversed dynamic
colour sets/resets; and a cursor initially matching foreground, background or
neither. Both resets restore ANSI and five special colours while keeping
dynamic and selection colours. RIS clears screen reverse; DECSTR preserves it.
Saved palette slots survive both resets. OSC 10/11 operate on the displayed
colour roles under screen reverse; OSC 12 remains the cursor colour.

In XTerm's `ReverseOldColors`, a cursor equal to the current displayed
foreground moves to the next foreground. This is stateful: a cursor initially
equal to the normal background stays unchanged on entering reverse, but then
matches the reversed foreground and follows it on leaving reverse. A separate
cursor colour stays fixed. Nemoterm keeps normal foreground/background palette
slots and maps dynamic requests according to screen reverse instead of swapping
the underlying slots. The helper also runs when RIS clears screen reverse.
No new terminal fields or allocations are needed.

`generate_reset_palette_oracle.py` generates C and Python cases directly from
the retained replies, validating the recorded hexadecimal bytes. Both product
fixtures explicitly set the configured cursor default to `#bbbbbb` to match
the reference resources; PuTTY's usual cursor default is green. The core suite
feeds every sequence byte by byte. The native fixture runs all 25 exact cases
on GDI, OpenGL and DirectX, then checks repaint after DECSTR, redraw after RIS,
and automatic cursor changes against explicit colour scenes. Wrong-colour
control images must differ. These are product pixel regressions, not an
independent XTerm pixel comparison. GPU capture is instrumented; its memory
samples are not used for the uninstrumented DirectX acceptance threshold.

Local checks are limited to fixture generation, Python/PowerShell parsing,
compilation/linking and whitespace inspection. Product execution remains in
GitHub CI while local runtime testing is paused. Complete native acceptance
is pending for this patch.

The preceding `ea042bc` core workflow passed the sanitizer and MSVC renderer
jobs but failed the native guarded-area fixture again. Its downloaded evidence
must remain a failure; it does not establish complete core-CI success. That
sidecar-host response-ordering issue is separate from this palette patch.
