# Working directories and duplicated sessions

Nemoterm now stores the shell's reported working directory separately from text,
scrollback and the frontend process's cwd. Duplicate Session copies configuration
and uses this metadata when it names a local path. Copy Working Directory URI
copies a percent-escaped file URI. Neither action changes the original shell's
cwd or saved profile. The Session/Shell option can disable directory inheritance.

`--directory` overrides the saved starting directory; an empty value inherits the
launcher directory. Native Windows paths are passed as CreateProcessW's cwd.
Builtin WSL Bash uses `wsl --distribution <default> --cd <directory> --exec bash
--login -i`. Git Bash resolves POSIX paths against its actual MSYS mount table,
including `/tmp`, using fixed startup code and a separately quoted argument.
Directory text is never interpolated into that code. Custom shell commands and
`-e` use Windows native startup directories; automatic POSIX mapping is restricted
to the builtin Git Bash and WSL selections.

The starting-directory edit control uses UTF-8/UTF-16. A hexadecimal UTF-8
companion registry value preserves Unicode through PuTTY's legacy native-codepage
settings storage. The new controls and the existing Custom command control use
the current PuTTY edit-handler API; opening Session/Shell no longer dereferences
an obsolete integer context argument. Saved Unicode settings are tested through
UI Automation, registry readback and a second settings process.

## Protocol scope

| Sequence | Interpretation |
| --- | --- |
| OSC 7 `file://host/absolute-path` | Decode percent-escaped UTF-8 once; replace directory and host. |
| OSC 9 `9;directory` | Raw UTF-8 Windows path, optionally enclosed in double quotes; host becomes local. |
| OSC 633 `P;Cwd=directory[;nonce]` | Decode `\\` and `\xHH` once (case-insensitive hex); host becomes local. Nonce is retained only as an ignored delimiter, not authenticated. |
| OSC 1337 `CurrentDir=directory` | Raw UTF-8 path; retain independently reported host. |
| OSC 1337 `RemoteHost=[user@]host` | Replace host without changing the directory; user portion is not stored. |

BEL and ESC-backslash terminate OSC; CAN/SUB cancel it. Invalid, incomplete or
overlong updates leave the last valid metadata intact. Empty CurrentDir/Cwd
clears the active directory. RIS, DECSTR, alternate-screen changes, history clear
and resize preserve it; starting/restarting a backend clears it.

The decoded path is limited to 4096 UTF-8 bytes, host to 255 ASCII bytes, and these
OSC payloads to 16384 bytes. Persistent strings use at most 4353 bytes plus two
pointers. The shared OSC scratch buffer grows by 12 KiB; other OSC families retain
their existing individual limits. The directory decoder allocates at most 16385
scratch bytes per update. URI clipboard conversion has a separate bounded copy.
There is no directory history or per-cell metadata allocation.

Local hosts are empty, localhost, loopback literals, the Windows hostname or its
FQDN, compared without DNS/network queries. A remote host remains copyable but
cannot supply a local startup directory. Windows drive paths (including `/C:/`)
are accepted; UNC/device/network paths do not become local cwd. A WSL distribution
with a distinct hostname must report localhost/a recognized local hostname for
inheritance. This is metadata from terminal output, not an authenticated identity.
Unknown 633/1337 subcommands remain unsupported. OSC 133 command marks/navigation,
iTerm File images and user variables are not implemented by this change.

## Shell cooperation

A shell must report its directory. No user profiles are edited or automatically
injected. PowerShell can emit one update with:

```powershell
[Console]::Write("$([char]27)]9;9;`"$((Get-Location).ProviderPath)`"$([char]7)")
```

A Bash shell can emit raw UTF-8 CurrentDir (ordinary directory names without
control characters), preceded by the intended host:

```bash
printf '\033]1337;RemoteHost=localhost\007\033]1337;CurrentDir=%s\007' "$PWD"
```

These examples update once. Continuous tracking requires adding equivalent output
to a prompt function; existing prompt customization should be preserved.

## Verification

`test_cwd` covers each parser, Unicode/escapes, host provenance, malformed UTF-8,
limits, cancellation, fragmentation, reset/resize and 10000 replacements. Local
Windows core suites and Linux ASan/UBSan passed. `cwd_window_smoke.py` sends the
sequences through real ConPTY, then starts duplicates and checks the child OS cwd;
it also checks clipboard URI, Unicode executable location, malformed/overflow
recovery, reset/resize, disabled inheritance, bounded memory and owned cleanup.

`shell_window_smoke.py` launches all detected shells in a Unicode directory. On
this machine pwsh, Windows PowerShell, BusyBox ash, Git Bash, WSL Debian and cmd
passed. Git Bash's `/tmp` mapping and WSL's POSIX directory inheritance are checked
with actual duplicated shells, including spaces, Unicode, semicolons and `$()`.
CI checks only shells installed on its runner; it does not claim a WSL launch
when no distribution is installed. `settings_window_smoke.ps1` checks Unicode
save/reload and native control visibility. Final artifact hashes and measurements
are recorded separately in `cwd-checkpoint.json` after single-executable CI passes.

Sources: [Windows Terminal shell integration](https://learn.microsoft.com/en-us/windows/terminal/tutorials/shell-integration),
[VS Code protocol](https://code.visualstudio.com/docs/terminal/shell-integration),
[VS Code parser/escaping implementation](https://github.com/microsoft/vscode/blob/main/src/vs/platform/terminal/common/xterm/shellIntegrationAddon.ts),
[iTerm2 proprietary sequences](https://iterm2.com/documentation-escape-codes.html).
No claim of XTerm's OSC 7 support is made: these are cross-terminal extensions.
