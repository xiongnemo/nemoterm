# Relative cursor positioning

The [independent audit](cursor-movement-audit.md) found that HPR (`CSI a`)
and VPR (`CSI e`) incorrectly shared CUF/CUD's scrolling-boundary rules.
The correction gives them position-relative movement with CUP's
origin policy: origin disabled permits crossing scrolling margins; origin
enabled confines both coordinates to the origin region. CNL/CPL and CUF/CUD
retain their existing behavior.

HPR keeps its logical column within the allocated physical grid. On a
double-width row it can therefore report a column beyond the visible half-row,
matching XTerm. The existing writer ignores positive-width text there; it does
not receive an index beyond the allocated line. No allocation or runtime
dependency is added.

The generated oracle reproduces all 848 retained XTerm query streams, including
the 47 originally differing streams. It verifies each captured input/reply and
the compressed reference's decoded hash, with no excluded cases or substituted
expectations. Core assertions also check writes across scrolling margins,
origin clipping, preserved unrelated cells, no spurious scrollback, saturated
counts and tiny grids with UTF-8, combining text, hyperlinks and protection.

The margin, state-control and Sixel terminal suites pass locally in MinGW and
Linux ASan/UBSan with leak detection. Native tests replay all 848 streams and
compare eight pixel states: absolute versus relative placement outside margins,
origin-clipped placement, ignored writes beyond a double-width row, and the
same bounds after resizing. These initial development runs do not establish a
final single-image artifact or memory acceptance; the subsequent checkpoint below
validates the downloaded image separately.

All three native runs use the actual requested GDI/OpenGL/DirectX renderer,
resize from 80x24 to 93x24 and drain their five owned processes naturally.
The DirectX screenshot was visually inspected. GPU captures use the existing
owned-process observer and are excluded from memory acceptance.

The tested MinGW frontend is 3,873,566 bytes, SHA-256
`1c975954cb0e9ddcc754004aa79a40fe4126b4b7d26b605bfa25292f490ea291`.
It uses the unchanged source-built host from `37ef26d`, SHA-256
`d0a95950e45f77c541f7ae524d20003e56caf57fe7e9b3480d8102385dab9d6a`.
The [manifest](relative-cursor-validation.json) retains exact source/binary
identities, all replies, pixel hashes/screenshots, natural cleanup and sanitizer
logs. This is a development sidecar build; the accepted local EXE is unchanged.

The subsequent development merge includes the [DECALN correction](alignment-reset.md)
and its UTF-8 generator fix. The merged margin, state-control and Sixel suites
pass on MinGW and Linux ASan/UBSan. Those separate source hashes/build logs are
retained without relabeling the earlier native captures as a merged-image test.
The combined single-image workflow now exercises 99 functional groups.

## Complete CI and downloaded-image checkpoint

Commit `f079f80` passes all four jobs in
[Test and build](https://github.com/xiongnemo/nemoterm/actions/runs/43517911825)
and all **99 groups** in
[Single executable from source](https://github.com/xiongnemo/nemoterm/actions/runs/43517911793).
The [single-image artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43517911793/artifacts/14082763320)
contains only `nemoterm.exe`, **4,449,280 bytes**, SHA-256
`0db4c0d807e810a7d34c592c0920214d667bb45f8d5576d4fda9a42b38e566e5`.
Its reported expiry is 2026-12-13 22:44:04 UTC.

Both CI compiler paths pass all 848 cursor sequences and eight pixel checks
per requested renderer, plus the DECALN 13-reference/one-direct/12-pixel matrix.
Their OpenGL requests fall back to GDI. The exact downloaded image then passes
both complete matrices locally under **actual GDI, OpenGL and DirectX**. Each
of those six runs drains all five owned processes naturally. The final DirectX
cursor screenshot was visually inspected. GPU captures remain separate from
memory acceptance. Both CI hyperlink records also confirm live observer
detachment and natural zero-exit cleanup.

The uninstrumented local GDI workload uses SarasaTermSC Nerd Font Light at an
actual 160x48 with two tabs and passes all nine functional groups. Startup-inclusive
frontend peaks are **16,130,048 private-working-set bytes**, 43,020,288 total
working-set bytes and 18,976,768 private-commit bytes, across 454 samples over
49.067 seconds. All 56 inner-job and 58 outer-job members drain naturally.

The local DirectX run again fails the resource assertion on the ninth post-close
sample: 492 handles / 37 GDI / 43 USER become 549 / 39 / 56. It completes only
one functional group and does **not** reach the full memory workload or its gate.
Five remaining owned processes require the inner fixture's forced cleanup.
The old `37ef26d` full DX measurement remains 30,474,240 private-working-set bytes,
above 25 MB; that number is not assigned to this new image.

This local DX fixture has a documented failure-only extension: after the original
sample already exceeds a resource limit, but before the unchanged assertion and
cleanup, it captures external window/module metadata. No observer starts before
that failing sample, and no target code is injected. The original and modified
fixture hashes, observer source, failing sample and output are all retained.
The observer stops without errors or truncation. The captured windows include
the input-manager families previously seen in [bounded diagnostics](dx-window-resources.md),
with the three UIM class callbacks mapped into `msctfuimanager.dll`. The first
capture has no baseline window set, so this presence does not prove the cause.
The 4.995-second partial trace is not memory acceptance.

Two later GDI-to-DX sequence controls, including copying the DX fixture only
after GDI finishes, do not reproduce the resource jump. Their DX baselines
already include the larger resource set; see the [paired observations](dx-window-resources.md).
These bounded diagnostics do not replace the first failing sample or establish
its cause.

A separate **unmodified** full DX follow-up on this exact image passes all nine
functional groups, with 12 resource cycles and natural cleanup of all 56 inner
and 58 outer job members. Its baseline is already 543 handles / 39 GDI / 56 USER.
The full workload records 250 samples over 27.069 seconds without injection:
**30,629,888 private-working-set bytes**, 71,806,976 total-working-set bytes and
98,164,736 private-commit bytes. The unchanged 25,000,000-byte gate fails, so the
fixture and controller both exit 1. Pixel capture instrumentation starts only
after memory sampling. This fills the missing full-workload measurement; it
does not resolve the initial resource failure or turn the checkpoint into a
DirectX acceptance pass.

The manifest now retains 144 compressed records, preserving earlier development
evidence separately from these complete CI and exact-image results. The accepted
local distribution remains unchanged; full compatibility and DirectX acceptance
remain open.
