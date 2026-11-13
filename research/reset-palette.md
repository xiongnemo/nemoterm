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
GitHub CI while local runtime testing is paused. The completed remote scope
is recorded below; native OpenGL coverage remains unproven on these runners.

Source `d2aa14aaf1b70323cc742d31995f5024722ddbc9` passes the ASan/UBSan
and MSVC renderer jobs in
[core run 43461348513](https://github.com/xiongnemo/nemoterm/actions/runs/43461348513).
The sanitizer OSC-colour suite includes all 25 captured cases. The Windows
native job also passes all 25 replies and 23 pixel checkpoints with actual
GDI and DirectX. Its requested OpenGL profile falls back to GDI, so it does
not establish OpenGL pixel acceptance. That job then fails the pre-existing
guarded-area reply-ordering assertion. The
[single-image run 43461348325](https://github.com/xiongnemo/nemoterm/actions/runs/43461348325)
passes all **88** groups, including all three requested colour-reset renderer
profiles, broader protocol/input/settings checks, real Codex variants and
uninjected tab workloads. GDI and DirectX are actual renderers; OpenGL again
falls back to GDI. The single 4,438,016-byte EXE has SHA256
`e055646edb544b3d53dde1edf28fa0200b9fe65cf785329d9475e6b69650ea4d` and
[artifact 14058011250](https://github.com/xiongnemo/nemoterm/actions/runs/43461348325/artifacts/14058011250).
Frontend private-WS peaks are 11,145,216 bytes for GDI and 21,622,784 for DirectX;
total-WS peaks are 40,390,656 and 59,797,504. Both private-WS gates pass and both
owned jobs drain naturally; DirectX total WS remains above the approximate
50 MB target. The
[manifest](reset-palette-validation.json) retains the three native reports and
their actual renderer IDs, full single-image validation and raw memory samples.
The accepted local executable is unchanged.

The preceding `ea042bc` core workflow passed the sanitizer and MSVC renderer
jobs but failed the native guarded-area fixture again. Its downloaded evidence
must remain a failure; it does not establish complete core-CI success. That
sidecar-host response-ordering issue is separate from this palette patch.
