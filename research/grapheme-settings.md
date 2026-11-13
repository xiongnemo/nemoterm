# Configurable startup grapheme widths

Window / Translation now provides **Use grapheme cluster widths at startup**.
The `NemoGraphemeWidths` Boolean is saved in the existing named-session settings,
defaults to false, and requires a frontend that implements whole-cluster drawing.
[Native settings capture](grapheme-settings.png).

Enabling the preference initializes a new terminal in mode 2027. A joined emoji
such as woman technologist then advances two columns rather than the legacy
four. Applications may still set or reset the mode. Applying a changed
preference changes the live mode for subsequent output; applying other settings
preserves the application's current mode. Stored text is not regrouped or erased.

This is specifically a startup preference. The
[terminal Unicode core draft](https://github.com/contour-terminal/terminal-unicode-core/blob/master/spec/terminal-unicode-core.tex)
requires both DECSTR and RIS to disable mode 2027. Those reset semantics are
unchanged even when the saved preference is enabled. The existing explicit
save/restore operations remain available. There is no new rendering dependency
or image allocation associated with this preference.

## Local evidence

The later [local MSVC single-image checkpoint](local-msvc-single-exe.md) builds
and exercises this setting in a combined executable. The MinGW evidence below
remains the record of the original implementation; full CI acceptance is still
outstanding.

Development frontend SHA-256:
`c6818d59accc482a70952e4e89643ce181548a257941a3dac1af3da894c6c7d7`.
This is the local MinGW frontend with the pinned ConPTY runtime and accepted
OpenConsole sidecar, not a newly accepted single-image release.

- All 35 Windows core/offscreen test executables passed. Configuration tests
  verify the false default and Boolean save/load. Terminal tests cover a fresh
  enabled session, two-column joined emoji, changed and unchanged live settings,
  retained stored text, both resets, and an unsupported frontend.
- All 16 terminal suites passed under Linux ASan/UBSan, including those startup
  and settings transitions. Leak detection and halt-on-undefined-behavior were
  enabled. [Results and source hashes](grapheme-settings-core-validation.json).
- The real [standalone settings dialog](grapheme-settings-window-observed.json)
  and [tab-host settings dialog](grapheme-tabs-settings-window-observed.json)
  passed visibility, false default, save/load, launch, and 11 exact ConPTY
  cursor/mode reply checks each. Rendering changes exercised actual GDI,
  OpenGL and DirectX. An application-disabled mode survived all four renderer
  changes; changed live preferences and soft/hard resets produced the expected
  two- or four-column cursor advance.
- Existing native grapheme grid and font-resize regressions passed on all three
  compositors: [ordinary](grapheme-settings-rendering-observed.json) and
  [font resizing](grapheme-settings-font-observed.json). Local clipboard
  assertions remain unavailable; CI still requires them.

The settings fixture now uses bounded atomic replacement for its JSON control
file, matching the existing Python fixtures. A real read handle held without
delete sharing exercises the retry before the UI test starts. This fixes an
observed `Move-Item -Force` replacement failure during the tab-host run.

One earlier standalone attempt timed out selecting the final GDI radio button
through UI Automation. Replaying the same radio actions passed; this does not
identify its cause. Failure diagnostics now retain the selected control name,
class and native check state. The retained fixture-failure summary distinguishes
that observation from the repaired mailbox race and development-only fixture
mistakes. [Failure record](grapheme-settings-fixture-failures.json).

The shared settings fixture is already part of both CI workflows and the exact
single-executable suite; Windows CI now also retains the new settings capture.
GitHub's account billing/spending restriction still needs to be resolved before
new MSVC and single-image acceptance can run. This setting does not close the
broader missing-glyph, color-font, physical IME, real-agent, or protocol inventory
work listed in the project requirements.
