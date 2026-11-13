# Settings accelerator collision

The custom-URI option in Terminal / Hyperlinks used Alt+A. On Windows this
conflicts with the global About button at startup and Apply during live
reconfiguration. `winctrl_add_shortcuts` requires each visible shortcut to be
unique and asserts on a duplicate; the shortcut also needs a unique destination
when assertions are disabled.

The option now uses Alt+R in "registered". No preference values, defaults or
link-opening behavior change. The existing owned-window settings fixture now
opens the hyperlink page at startup and during live reconfiguration, checking
both options remain visible and retain their defaults. It still exercises
save/load, bindings, shell launch, renderer changes and normal shutdown.

The same class of conflict was observed in the development attribute-colour
page in [Windows CI](https://github.com/xiongnemo/nemoterm/actions/runs/43422849774/job/131876855657).
The hyperlink fix was applied to the main baseline separately at `108af0c`.
Its [Windows/core workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43425076349)
and [single-image workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43425076239)
both passed. The startup and live hyperlink-page checks pass in standalone and
tab-host settings; the full single-image manifest records 57 successful groups,
including settings, tab regressions and the four Codex fixture modes.

The [single-EXE artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43425076239/artifacts/14038426448)
contains only `nemoterm.exe`, 4,371,456 bytes, SHA-256
`0a5115bbb0cce074256c0b3726afeb72421e18943689066756dc79fca4fd17c9`.
The downloaded file matches the native test manifest. The retained
[validation record](settings-shortcuts-validation.json) binds the settings
results and artifact to the tested commit. The main source branch now contains
this fix; the accepted local EXE was not replaced.

The MinGW mixed-renderer tab profile also closed successfully in this run. One
successful repeat does not explain its earlier timeout. This limited fix does
not establish the development branch's longer DirectX memory requirement or
complete the broader protocol/hardware acceptance. Native tests remain paused
on the user's computer; these runtime checks ran on GitHub-hosted machines.
