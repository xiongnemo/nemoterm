# Dialog modality, Bell layout and default font shortcuts

Product source: `1f4db229cd9bc5763dc880126ecc0ba3b7fb2a96`.
Single executable: **4,556,288 bytes**; SHA-256:
`7c5c8bb866cafa4506b97cc52214b9b90c7d8b50353e5ae6e9eef4a9be9fb4cb`.

[Download the tested image](https://github.com/xiongnemo/nemoterm/actions/runs/43872383575/artifacts/14228757239).
Only `nemoterm.exe` is needed at runtime; the artifact also carries build provenance.

## Behavior

- Bell's overload controls live on Terminal / Bell / Overload. Both pages fit above Save and Apply; no global dialog enlargement is required.
- Default zoom accepts Ctrl+=, Ctrl+Shift+=, Ctrl+keypad-plus, Ctrl+minus and Ctrl+keypad-minus. Existing wheel behavior stays available. Custom bindings use their configured key; aliases apply only to the defaults.
- Older saved zero zoom bindings migrate once to the new defaults. Custom nonzero bindings survive; a subsequently saved Disabled choice remains disabled. Zoom does not overwrite the configured base font.
- Settings, About, Licence, Event Log and message boxes disable terminal interaction in their UI thread. Native file/font/colour pickers inherit the outer dialog's modality. Nested close operations restore only windows they disabled.
- Terminal activation is redirected to the enabled modal popup after Windows finishes activation. Disabling a window alone did not prevent programmatic foreground activation.
- The opt-in debug interface permits discovery/capture during dialogs and returns status 4 for input, paste and key requests. Posted terminal commands and input messages are also rejected.

## Verification

The [single-image profile/dialog job](https://github.com/xiongnemo/nemoterm/actions/runs/43872383575/job/133319228542) passed against the hash above. Fresh evidence and its job log are archived in [dialogs-ci-1f4db22.zip](dialogs-ci-1f4db22.zip).

Both tabbed and standalone modes passed:

- Every default keyboard zoom spelling changes the grid size and reverses correctly. CSI-u receives no shortcut press/release bytes.
- Terminal foreground activation returns to an enabled owned dialog; direct terminal input, paste and new-tab commands are blocked.
- File picker and Licence nesting preserve outer-dialog modality. Closing all dialogs restores terminal input, and owned processes exit cleanly.
- Bell and Overload controls are visible and do not overlap the footer. The two captured pages were visually inspected.
- Old profile zoom defaults migrate and persist; existing profile CRUD, live Save and Apply, reload, window ownership, default tabs and work-area sizing checks also pass.

The [MSVC diagnostics job](https://github.com/xiongnemo/nemoterm/actions/runs/43872383575/job/133316708436) passed the same new dialog tests on the portable frontend, plus its renderer/lifetime checks. [ASan/UBSan](https://github.com/xiongnemo/nemoterm/actions/runs/43872383575/job/133316707886) passed. Local non-GUI compilation, configuration storage/migration tests, binding policy tests and Python/PowerShell syntax checks passed.

Earlier attempts exposed the owned-dialog UIA hierarchy, disabled-window foreground activation and missing registry parents on a pristine runner. The fixture discovery/setup and activation handling were corrected; the successful run above includes all those corrections.

The comprehensive [portable suite](https://github.com/xiongnemo/nemoterm/actions/runs/43872383575) and [single-image protocol suite](https://github.com/xiongnemo/nemoterm/actions/runs/43872385380) were still running when this preview was prepared. This is targeted feature acceptance, not a claim that all v0 interaction work is finished. No local desktop tests were run for this change.
