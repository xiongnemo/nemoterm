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

Static source checks passed before submission; behavioral and compilation
results are pending remote CI. Physical high-resolution wheels,
DPI transitions and local Sarasa rendering still require further verification.
The accepted executable remains unchanged, and the prior integrated DirectX
resource-cycle failure remains unresolved.
