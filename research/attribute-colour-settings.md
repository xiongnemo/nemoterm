# Saved attribute colours: source and build checkpoint

`Window > Colours > Attributes` adds a native settings page with a selector for
bold, underline, blink, reverse and italic. Each attribute has an initial colour
mode, an optional custom RGB value, and a choice to keep its original text style
alongside that colour. A shared option controls whether attribute colours
override explicit application text colours. Everything defaults off, preserving
the prior rendering behaviour until the user or an application enables a mode.

Three decimal RGB fields and the native colour picker edit the selected colour.
A valid edit or accepted picker enables that custom value; it does not silently
enable the attribute's colour mode. Disabling a custom value retains its RGB for
later use and falls back to the configured text foreground. Switching the
selector or refreshing the dialog preserves each attribute's independent values.
Cancelling the picker leaves them untouched. Decimal input saturates at 255
without arithmetic overflow; empty/nondecimal edits do not modify configuration.
These are source behaviours awaiting UI execution and visual review.

## Persistence and live updates

Eight ordinary Conf entries use existing session storage. They are appended to
the list, preserving the previous 248 serialised key IDs.

| Storage key | Default | Contents |
| --- | --- | --- |
| `NemoAttributeCustomColours` | 0 | Custom-colour enable bits 0–4 |
| `NemoAttributeColourModes` | 0 | Initial mode bits 0–4; override bit 5 |
| `NemoAttributeKeepStyles` | 0 | Keep-style bits 0–4 |
| `NemoAttributeBoldColour` | `0xffffff` | Retained bold RGB |
| `NemoAttributeUnderlineColour` | `0xffffff` | Retained underline RGB |
| `NemoAttributeBlinkColour` | `0xffffff` | Retained blink RGB |
| `NemoAttributeReverseColour` | `0xffffff` | Retained reverse RGB |
| `NemoAttributeItalicColour` | `0xffffff` | Retained italic RGB |

All masks use OSC 5 order: bold, underline, blink, reverse, italic. Negative or
out-of-range masks resolve to zero. Invalid packed RGB resolves to the declared
white default. Startup uses the saved modes; later RIS/DECSTR preserves the
running mode state as in the preceding protocol implementation.

Application OSC 5/4 overrides take precedence over the saved custom colour.
OSC 105/104 reset removes the application override, revealing the saved custom
colour or configured foreground. OSC 10 does not alter this fallback. Changing
a local custom flag or RGB clears only that attribute's application override.
Changing a saved mode updates only the bits whose saved values changed,
preserving unrelated application mode changes. Other setting changes retain
both application colours and mode state. Keep-style changes repaint immediately
without clearing colour overrides.

The palette stack retains only application overrides and their unset state.
Restoring an unset slot therefore follows the current saved preference; it does
not roll back local preferences. The keep-style mask is a Nemoterm setting with
OSC 5 bit order, not the differently numbered XTerm `veryBoldColors` resource.
It preserves the existing style path, including the user's bold/blink policy;
keeping reverse allows inversion after the special background is resolved.
Exact XTerm resource equivalence is not claimed.

Cached defaults plus a style mask add 21 bytes of members per terminal before
padding, as well as eight configuration entries. No screen/scrollback cells or
palette snapshots grow in this settings patch. The paint path uses cached data
and does not look up these settings per cell. This is source-level accounting,
not a new working-set measurement.

## Prepared validation

The configuration suite adds defaults and save/load for all eight keys. The
colour suite adds startup defaults, application precedence, selective local
updates, mode-bit independence, all five retained styles, malformed settings,
resets and palette restoration after a preference change.

The existing native settings fixture now prepares all five selections, validates
independent controls and RGB retention, saves/reloads all eight entries, checks
live OSC replies and applies a new local colour. It retains
`attribute-colour-settings.png` for visual review and runs in ordinary and
tabbed settings paths. A configured GDI variant compares the saved startup
scene with explicit RGB rendering and checks reset to saved defaults. The core
and native suites are prepared only; none has been executed for this patch.

The [build manifest](attribute-settings-build-validation.json) binds the exact
source hashes, three raw build logs and the separately staged single EXE.
MSVC compiled the frontend, `test_conf` and `test_osc_colour`; Linux compiled
both suites with ASan/UBSan; the source-integrated host linked the final image.
Python syntax compilation, two PowerShell AST parses, Conf-key ordering and
whitespace checks passed. Existing C4319 warnings in the Windows link/window
code remain. The OpenConsole overlay was not regenerated.

Static review also found an existing fixture variable collision: script-level
UI-control loops overwrote `$control`, the mailbox path subsequently passed to
the child. The mailbox now uses `$controlFile` throughout, separate from UI
elements. This fixes the source-level collision; execution is still pending.

**No product/test executable, sanitizer suite, XTerm, settings dialog or desktop
fixture was run**, as requested by the user. Layout, picker acceptance/cancel,
visible saved styles, real persistence and full regression remain runtime gates.
The candidate is isolated under `build/local-attribute-settings-unverified`;
accepted main and the earlier candidates retain their recorded hashes. Resume
with core/configuration suites, then both settings paths and review their
screenshots/picker, all colour renderers and configured GDI, then uninstrumented
GDI memory acceptance. DirectX's existing memory gate is unchanged.
