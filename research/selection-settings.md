# Saved selection colours: source and build checkpoint

`Window > Selection > Colours` now provides separate background and text
colour preferences. Each component has an enable checkbox, three decimal RGB
fields and the existing native colour picker. Both preferences default off,
retaining inverse-video selection. Changing RGB or accepting the picker enables
that component; turning it off retains the chosen RGB for later use. Cancelling
the picker leaves the setting unchanged. Dialog refreshes do not enable custom
colours as a side effect.

Four ordinary `Conf` settings persist through the existing session storage:

| Storage key | Default | Meaning |
| --- | --- | --- |
| `NemoSelectionBackgroundEnabled` | false | Use a configured selection background |
| `NemoSelectionBackground` | `0xffffff` | Background RGB |
| `NemoSelectionForegroundEnabled` | false | Use configured selected text colour |
| `NemoSelectionForeground` | `0x000000` | Text RGB |

They are appended to the configuration key list so existing serialised key
numbers do not move. No separate file or renderer dependency is added. RGB
fields accept decimal components and saturate large numeric values at 255
without integer overflow. Incomplete/invalid edits do not modify configuration.
Out-of-range persisted packed RGB values resolve to the declared white/black
defaults. These are source behaviours pending runtime verification.

## Interaction with applications

The existing OSC 17/19 application colours take precedence over configured
defaults. OSC 117/119 removes only the corresponding application override and
therefore returns to the configured colour, or inverse selection if disabled.
Changing a local selection preference immediately clears the application
override for that component. Changing an unrelated setting preserves it.

Palette stacks retain application overrides and their unset state. A saved
unset component therefore follows the current local preference after a local
configuration change. Local configuration is not rolled back by palette pop.
Exact comparison with XTerm's resource-specific selection heuristics remains
part of the pending [selection-colour validation](selection-colours.md).

Two cached default RGB values add eight bytes of fields per terminal, outside
screen and scrollback cells. Effective colours are selected once per paint;
the renderer does not look up configuration for every selected cell. Four
configuration entries also occupy memory in each configuration object. No new
memory-acceptance result is claimed from these source-level sizes.

## Prepared checks and build evidence

The configuration suite now checks defaults and persistence for all four keys.
The mock-renderer suite adds live configuration, query replies, component-wise
precedence, independent application resets, palette restoration after a local
change and malformed stored values. The existing settings fixture adds visible
controls, RGB edits, toggle retention, save/load, application override
retention through unrelated settings, and live application of a new colour.
It runs both ordinary and tabbed configurations in CI. A configured-default
GDI pixel variant supplements the existing three renderer fixtures.

The [build manifest](selection-settings-build-validation.json) binds the
source files, exact logs and the unverified image:

* MSVC compiled the frontend, `test_conf` and `test_osc_colour`.
* The source-integrated OpenConsole host linked the single EXE.
* Linux built both core test targets with ASan/UBSan enabled.
* Python syntax compilation, PowerShell AST parsing and whitespace checks passed.

Runtime testing remains paused at the user's request. **No new binary, unit
suite, sanitizer suite, settings dialog or desktop fixture was executed.** The
new UI's layout, picker interactions, persistence and live colour behaviour are
not yet accepted. Existing MSVC C4319 warnings in the link UI/window code remain.
Both accepted main and the previously tested palette-stack EXE are unchanged;
the new image is staged separately under `build/local-selection-settings-unverified`.

When testing resumes, run the extended core/configuration suites and independent
XTerm capture first, then the settings fixture in ordinary and tabbed modes,
all renderer colour checks and the configured GDI variant. Review the actual
settings screenshot and native picker, then repeat the uninstrumented GDI
memory workload for the new image. Previous runtime passes do not transfer.
