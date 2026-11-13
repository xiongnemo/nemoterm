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
This branch applies the hyperlink fix to the current main baseline separately.
Local validation is static only; native tests remain paused on the user's
computer. Remote CI must establish runtime acceptance before promotion.
