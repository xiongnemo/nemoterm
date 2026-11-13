# Screen-alignment reset and image retirement

The [initial audit](alignment-audit.md) found that DECALN (`ESC # 8`) filled
cells but retained cursor position, margins, origin mode, pending wrap and
rendition. The development fix now resets those states, clears visible Sixel
pixels on the active screen, and fills every physical cell with an unprotected,
default-colour `E`. Double-size line attributes, combining payloads and old
hyperlink IDs are removed from replacement cells. Existing selection
invalidation remains in effect.

Current foreground/background colours and character-protection state survive
for subsequent text. Styles and underline colour clear; indexed bold/bright
foreground resolution follows the user's bold-colour setting. Saved cursor
state, current hyperlink, tab stops, insert/wrap/application-key modes, mode 69,
scrollback and the other screen remain independent. Erasure targets visible
image rows on the active screen, retaining image rows in scrollback and images
on the other screen. This adds no persistent allocation or runtime dependency.

## Validation

Thirteen complete query streams match the retained independent XTerm(412)
capture exactly in both the core parser and native ConPTY tests. The original
RGB case remains an explicit difference: XTerm clears its RGB flags while
retaining packed colour values, then reports those integers as indexed colours.
Nemoterm keeps valid RGB storage and reporting. A separate direct assertion
verifies that policy, rather than pretending the reference streams match.

Core tests additionally cover all filled cell payloads, selection invalidation,
retained current RGB/protection/hyperlink state, history, unrelated input modes,
one-cell geometry, 1,000 repeated replacements, active/alternate-screen Sixel
retirement and partially visible history images. The state-control, Sixel
terminal and hyperlink suites pass on Windows MinGW and Linux ASan/UBSan with
leak checking. Generated expectations are checked against the retained capture's
hash; they do not come from Nemoterm's output.

The native fixture passes on actual GDI, OpenGL and DirectX. Each run compares
13 reference cases and one direct RGB case, then performs 12 pixel checks:
explicit full-grid text versus DECALN output, visible Sixel replacement, retained
other-screen content, synchronized output before/after release, and resizing
from 80x24 to 93x24. The GPU cases capture the owned renderer through the existing
observer. All five processes in each controller job drain naturally.

The local frontend is a **3,878,174-byte MinGW sidecar development image**, SHA-256
`19846c394bcd1fc6d1e6b7c064a913c7543a31088fa55c8449c92dde9cd034fa`.
It uses the verified source-built host from base `37ef26d`, SHA-256
`d0a95950e45f77c541f7ae524d20003e56caf57fe7e9b3480d8102385dab9d6a`.
The fix changes the frontend terminal parser; the host overlay is unchanged.
These local runs do not establish the final single-image artifact or memory
acceptance. The [manifest](alignment-reset-validation.json) retains source and
binary identities, raw replies, pixel hashes/screenshots, natural cleanup and
sanitizer logs. The screenshot was also visually inspected.

CI adds all three native variants to the compiler comparison and single-image
workflow, bringing the latter from 93 to 96 functional groups. The first core
run at `f72272f` failed generated-data preflight: the new generator omitted an
explicit encoding when reading its JSON manifest, and CI promotes
`EncodingWarning` to an error. This stopped the Windows job before its build
and native assertions. The sanitizer, source-host and MSVC diagnostic jobs
passed. The original failed run and log are retained in the manifest.

The follow-up specifies UTF-8 and passes the same strict Python options locally;
it changes neither generated expectations nor product code. The corrective
push cancelled the first single-image run; that incomplete run is retained and
is not counted as a pass.

## Complete CI checkpoint and downloaded image

Commit `18e912d` passes all four jobs in
[Test and build](https://github.com/xiongnemo/nemoterm/actions/runs/43515344353)
and all **96 groups** in
[Single executable from source](https://github.com/xiongnemo/nemoterm/actions/runs/43515344377).
The [single-image artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43515344377/artifacts/14082226682)
contains only `nemoterm.exe`, **4,449,280 bytes**, SHA-256
`4591e312142a74efedb2f14588c9d3999cd3165a5fc9a193326f3ebd2d454ca3`.
Its reported expiry is 2026-12-13 22:22:04 UTC.

Both CI compiler paths pass 13 exact XTerm replies, the direct RGB policy and
12 pixel comparisons per requested renderer. Their OpenGL requests fall back
to GDI. The exact downloaded image then passes all those checks locally under
**actual GDI, OpenGL and DirectX**, with five owned processes per local run
draining naturally. Its DirectX screenshot was visually inspected. The GPU
observers remain excluded from memory acceptance. Both complete CI hyperlink
records also confirm observer detachment while live and natural zero-exit cleanup.

The uninstrumented local SarasaTermSC Nerd Font Light, actual 160x48, two-tab
GDI workload passes all nine functional groups. Its startup-inclusive frontend
peaks are **16,211,968 private-working-set bytes**, 43,122,688 total-working-set
bytes and 18,829,312 private-commit bytes, across 443 samples over 48.046 seconds.
All 56 inner-job members and 58 outer-job members drain naturally.

The new local DirectX run **fails before the full workload/memory gate**.
On the ninth post-close sample, handles increase from 492 to 549, GDI objects
from 37 to 39 and USER objects from 43 to 56. The first handle assertion fails
after one functional group; five remaining owned processes require the fixture's
forced cleanup. The outer controller subsequently has no active members, which
does not make the inner cleanup natural. All samples, the original failure and
both cleanup records are retained; no passing repeat replaces this result.

This recurrence is consistent with the earlier `37ef26d` resource-count failure,
but it does not establish a leak or the cause. The 4.948-second partial memory
trace is not a full-load budget result. The preceding checkpoint's unmodified
complete DirectX run remains 30,474,240 private-working-set bytes, above 25 MB;
that older measurement is not assigned to this new image. CI's smaller Consolas
grids pass their budgets (GDI 109x34, 11,452,416 bytes; DirectX 88x35,
21,938,176 bytes), and do not replace local 160x48 acceptance.

The manifest retains the original preflight failure plus 57 new compressed
records, including workflow/artifact metadata, replies, screenshots, core and
sanitizer logs, all memory samples and the new local failure. The accepted local
distribution remains unchanged. Full compatibility and DirectX acceptance remain open.
