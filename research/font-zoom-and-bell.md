# Session font zoom and bell validation

Development work based on `5b2e6f1263ba5b63ea861ea34ec78eb97b243e4a`.
The user has not resumed local native testing. This change is submitted to
remote CI; no new local runtime or memory result is claimed.

## Interaction

[Windows Terminal](https://learn.microsoft.com/en-us/windows/terminal/tips-and-tricks)
uses Ctrl+wheel for session zoom. The documented
[Alacritty Windows/Linux bindings](https://alacritty.org/config-alacritty-bindings.html)
use Ctrl with plus, minus and zero. Nemoterm adopts mouse zoom with explicit
application precedence:

* Ctrl+vertical wheel changes the current terminal's font by one point per notch.
* When the application captures the mouse, Ctrl+wheel stays application input.
  Adding Shift forces local zoom, consistent with existing local selection.
* Ordinary scrolling, unrelated modifiers and horizontal scrolling retain their
  existing path. Fractional wheel deltas accumulate separately for zoom and
  scrolling; switching between them discards the previous partial gesture.
* Increase, decrease and reset are available in the terminal menu. Keyboard
  bindings start disabled and are configurable at Window/Bindings/Font, with
  the existing duplicate-binding check. The wheel modifier can also be changed
  or disabled. AltGr retains the existing keyboard text-entry path.

Zoom keeps the window's outer rectangle and changes the child application's
rows/columns to fit. It is transient and belongs to the current terminal;
the configured FontSpec is not overwritten or propagated to sibling tabs.
Reset restores the configured font. Choosing a different configured face/size
clears the transient override. DPI changes rebuild from the selected point size.
Interactive zoom is bounded to 4–72 points; reset may restore a configured size
outside that range. Font resources, GPU caches, input-method font and the system
caret are updated through existing frontend paths. No external library is added.

## Bell

The Windows frontend already dispatches BEL to the configured system sound,
visual flash, custom WAV or PC speaker mode; Terminal/Bell exposes the settings.
This checkpoint retains that real implementation and adds verification instead
of treating a mock callback as proof of audible output.

The overload-accounting queue previously allocated a record on every BEL even
when overload suppression was disabled. It now allocates only while accounting
is enabled, and discards old records when the setting is disabled. Elapsed-time
comparison also avoids subtracting the timeout from a small tick count.

Core fixtures cover sound/disabled/visual policy, OSC BEL terminators versus
ordinary bells, visual state, overload suppression and 10,000 bells with no
retained accounting nodes when accounting is disabled. A remote native fixture
observes actual MessageBeep calls without replacing the function or its return
value; disabled and visual modes must not call it. This establishes API dispatch,
not audible speaker output. Visual pixels, custom WAV/PC-speaker operation and
local audible acceptance remain open.

## Verification

The first full core CI on `555934a` passes sanitizer and MSVC renderer jobs but
fails the new MinGW/native zoom fixture. Its GDI cell grows from 9x19 to 9x20
while the bright-pixel bounding box of M remains 7x7. That is not sufficient
to distinguish raster hinting from a stale glyph. The initial assertion that
every one-point increase must enlarge that bounding box is replaced by an
exact normalized glyph-cell comparison with a separate terminal started at
13 points, which never invokes zoom. A separate four-point zoom must visibly
enlarge the glyph. Cell-size, fixed-window, resized-grid, resource and input
assertions remain mandatory. The original failure is retained; it is not a
passing native run. The new reference comparison passed in the remote artifact
replay described below.

The native zoom fixture covers partial-wheel accumulation, application Ctrl
wheel reports, forced Shift zoom, menu reset, custom bindings including key-up
suppression in kitty event mode, current cell/glyph pixels, fixed outer bounds,
child grid notifications and six repeated zoom/reset GDI-resource cycles.
It records actual renderer selection (CI OpenGL may fall back), runs both a
standalone terminal and tabbed terminals, and owns each process tree. Input is
scoped to the test terminal's UI thread; no global keyboard/mouse input is used.
These instrumented functional checks do not establish the memory target.
The mixed-profile tab fixture additionally checks active-tab-only zoom, ignored
zoom commands to inactive terminals, persistence across three renderer switches,
unchanged sibling cell geometry and pixels, unchanged saved FontHeight values,
and restoration of the original active-tab frame after reset.
A separate profile disables wheel zoom and verifies both unchanged font size
and the application's Ctrl-wheel report.

The [focused replay](https://github.com/xiongnemo/nemoterm/actions/runs/43607132722)
at fixture commit `ea91559e4a5de5538d5234eed1ef762bf0677c55` passed all three
fixtures. It first checks that production source and build recipes are unchanged
from `555934a`, then isolates that commit's source-built single executable:
4,486,144 bytes, SHA-256
`84d51046b7a4a77f33f571de910d4733e5e5d6dda172b23e8f74b77c1951864f`.
The artifact was downloaded and its source manifest, size and hash independently
verified without executing it locally. Full observations and run logs are retained
with hashes in [the validation record](font-zoom-validation.json).

With CI Consolas at 96 DPI, the actual GDI and DirectX paths both match the
separate 13-point startup reference exactly. The one-point cell changes from
9x19 to 9x20 while the bright M bounding box stays 7x7; four points produce a
12x24 cell and a 10x13 glyph box. The independent pixel comparison supports
font rasterization quantization in this case, rather than a stale glyph.
The requested OpenGL path fell back to GDI and does not establish OpenGL zoom.
Six repeated zoom/reset cycles retain the same GDI object counts (22, 27 and
28 for the three enabled profiles). The disabled-wheel profile passes too.

The three-profile tab fixture passes active-tab isolation, unchanged saved
FontHeight values, frame restoration and 36 subsequent switches. The bell
fixture observes one real `MessageBeep(MB_OK)` call returning success for sound
mode, and zero calls for disabled and visual modes. All owned process trees
exit naturally. These are instrumented functional results, not memory or
audible-output acceptance.

The fresh [single-executable workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43606924121)
passes all 122 checks at `04d31a7292788460990c8463685c30be2fc16393`, including
font zoom, bell and the mixed-tab checks. Product artifact `14119299452` contains
the 4,486,144-byte executable with SHA-256
`bfc0278320055794f89f9f8d0f1d4cabb494ee3e1e8ba0b7a5b5a0026563cc34`.
The downloaded file matches the validation manifest, which lists only
`nemoterm.exe` in the test execution directory. It was not run locally.
Its independent startup-font comparison passes on actual GDI and DirectX;
the OpenGL request again falls back to GDI.

All six mandatory memory workloads finish nine functional/resource groups and
exit naturally. Their complete, uninstrumented frontend samples were independently
recomputed without dropping peaks. CI uses Consolas and grids of 109x34 for GDI
and 88x35 for DirectX; these do not establish the local Sarasa 160x48 target.

| CI workload | Private working set peak, bytes | Total working set peak, bytes |
| --- | ---: | ---: |
| GDI baseline | 11,632,640 | 43,102,208 |
| GDI inline PNG | 12,627,968 | 44,896,256 |
| GDI GIF | 12,992,512 | 45,232,128 |
| DirectX baseline | 15,421,440 | 51,978,240 |
| DirectX inline PNG | 17,006,592 | 53,936,128 |
| DirectX GIF | 16,928,768 | 54,140,928 |

These are ordinary default-font workloads, not a dedicated memory stress test
while zooming. Raw samples, private commit peaks, exact font/bell observations,
source/artifact identities and the complete workflow log are retained in the
validation record. The [complete MinGW/core workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43606924130)
also passes, including sanitizer, MSVC diagnostics, and the corrected native
font/bell and profile-isolation checks. Both full workflows for this checkpoint
are now green. Physical high-resolution wheels,
DPI transitions and local Sarasa rendering still require further verification.
The accepted executable remains unchanged, and the prior integrated DirectX
resource-cycle failure remains unresolved.
