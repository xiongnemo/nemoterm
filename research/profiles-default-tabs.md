# Profiles and default tabs

Product source: `9be9bce2039b6e4383a90ec8d499e3c3fde67a28`.
Single executable: **4,553,216 bytes**; SHA-256:
`a77d7c38deb3885a4a8fe03a63da179379853d9cc5589f8b7a8f0a7e1affde4b`.

[Download the exact tested image](https://github.com/xiongnemo/nemoterm/actions/runs/43860864767/artifacts/14223332537).
The archive includes provenance JSON; only `nemoterm.exe` is needed to run.

## Behavior

- New configurations use tabs by default. Existing explicit preferences still load; `--no-tabs` selects a standalone window.
- The Profile page provides Add, Edit, Save and Delete. Default is created on first launch and cannot be deleted. Existing `Default Settings` storage and `-load` remain compatible; `--profile NAME` selects a profile explicitly.
- Save and Apply persists the current profile and applies it to the active terminal. Save and Open persists startup settings. Cancel discards unsaved edits; explicit Add, Save and Delete operations remain stored.
- Profile / Shell controls the shell and starting directory for new terminals. A running child is not restarted. Temporary `-e` commands are excluded from persistent settings.
- Discovery reports each terminal's `profile`. New and duplicated tabs retain their owning window type after editing a profile with a different saved launch preference.

## Verification

[Profiles job](https://github.com/xiongnemo/nemoterm/actions/runs/43860864767/job/133279142926) passed against the exact image above on a disposable Windows runner:

- Nine CLI cases: legacy profile loading, explicit option precedence, `--profile`, default tabs, Ctrl+Shift+T and explicit standalone mode.
- Default 160×48 character sizing and work-area clamping.
- Profile creation, selection and deletion through the real settings dialog.
- Both tabbed and standalone settings flows: live renderer/color/binding changes, active-profile persistence, restart/reload, and exclusion of temporary commands.
- Live profile changes with the opposite stored window mode: New/Duplicate actions keep the correct host and profile identity, without changing the stored launch preference.
- Native UI control bounds and captured Profile/Shell pages inspected.

Local non-GUI checks passed: frontend compilation, `test_conf` (including profile storage errors, default protection and duplicate names), Python/PowerShell syntax, and the 11 offline interaction-runner tests. MSVC renderer diagnostics and ASan/UBSan passed remotely.

The earlier `366551c` attempt failed because the settings button label was escaped twice. The labels were corrected; the final job uses a fresh evidence directory to exclude historical captures tracked in the repository.

Raw JSON, screenshots, source identity and job log: [profiles-ci-9be9bce.zip](profiles-ci-9be9bce.zip).
The complete [portable suite](https://github.com/xiongnemo/nemoterm/actions/runs/43860864767) and [single-image protocol suite](https://github.com/xiongnemo/nemoterm/actions/runs/43860864628) were still running when this preview was prepared. This is targeted feature acceptance, not a claim that all v0 interaction work is finished. No local desktop tests were run for this change.
