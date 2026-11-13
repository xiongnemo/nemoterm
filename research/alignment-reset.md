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
it changes neither generated expectations nor product code. Full remote CI
for this correction is pending. The accepted local executable remains unchanged, and
the larger DirectX memory limit and intermittent resource-count issue remain
open as recorded in the [preceding checkpoint](underline-capabilities.md).
