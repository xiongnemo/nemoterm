# Installed shells and startup selection

`--shell`, `--shell-command`, `--choose-shell`, and `--list-shells` are implemented.
Session contains the persisted shell selector and optional startup chooser;
Session / Shell edits a custom command. CLI selection is applied after `-load`;
an explicit `-e` command takes precedence. Existing defaults are not rewritten.
The automatic order is pwsh, Windows PowerShell, cmd, then other installed shells.
An explicitly selected missing shell reports an error instead of substituting one.

Detection uses filesystem/registry reads, not shell execution:

* pwsh: Scoop's actual app (avoids its shim), PATH, Program Files, WindowsApps.
* Windows PowerShell: GetSystemDirectoryW plus `WindowsPowerShell/v1.0/powershell.exe`.
* BusyBox ash: Scoop actual binary or PATH, with `ash -i`.
* Git Bash: GitForWindows InstallPath, Scoop, Program Files, local Programs/Git,
  or a validated Git bin/cmd parent on PATH. An unrelated `bash.exe`, including
  System32's WSL legacy launcher, does not qualify. MSYSTEM and CHERE_INVOKING
  are overridden only in the sorted Unicode child environment block.
* WSL Bash: System32 wsl.exe and the registered default Lxss distribution.
  Mere presence of wsl.exe does not imply an installed distribution. Detection
  establishes registration, not that Bash is installed inside every distribution.
* cmd: the system directory, regardless of PATH contents.

All six launches on this machine executed a marker command through an owned
Nemoterm window and exited. `shell-window-observed.json` contains exact commands,
paths and executable digest, with a frontend memory sample for each launch.
These are sampled shell-startup observations, not long-session peak claims.
`test_shell` independently creates fake installations under a Unicode/space path
to check missing shells, empty PATH, Windows PowerShell fallback, Git-vs-WSL
classification, quoting and child-only environment overrides. `test_conf` checks
shell/default-chooser/custom-command persistence including UTF-8. The native
settings fixture saves Git Bash and the startup chooser to a temporary named
profile, verifies reload and automatic dialog opening, and verifies `-e` override.
User Default Settings are preserved.

The machine's older inbox WSL parser rejects **unnecessary** quotes around a
simple distribution name: the raw CreateProcess command `--distribution "Debian"`
returned 0xffffffff with “There is no distribution with the supplied name”, while
`--distribution Debian` ran `/bin/echo`. Commands now omit those unnecessary
quotes while retaining required Windows argument escaping for other names.

The backend also releases the ConPTY reference after child creation and waits
for console EOF, so descendants can outlive their initial launcher. A separate
native fixture proves that behavior and last-client shutdown; see
`delegated-console-observed.json`. Initial investigation associated this with
the WSL failure, but subsequent captured output identified the quoted-name
bug as that failure's direct cause. Lifetime behavior is independently tested.
Old explicit system ConPTY without ReleasePseudoConsole retains legacy launcher
lifetime; the default bundled and source-linked backends support the new path.
