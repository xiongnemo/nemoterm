# Files and image clipboard input

Dropping files or folders into a terminal view pastes their quoted paths, separated
by spaces, through the regular terminal paste path. It honors bracketed paste and
does not add Enter. Dropping on a tab label targets that session; dropping on other
parts of the host targets the active session. Existing mouse reporting remains
independent. Explorer's copied-file format (`CF_HDROP`) is accepted by the regular
Paste binding too, ahead of any accompanying text fallback.

Quoting uses the configured startup shell, or a recognized explicit/custom shell
command. PowerShell single quotes are doubled; ash/bash use POSIX single-quote
escaping. Git Bash and BusyBox receive forward-slash Windows paths. WSL drive
paths use the default `/mnt/<drive>/...` mapping. Cmd receives quoted Windows
arguments. Embedded controls, invalid UTF-16 and malformed or oversized DROPFILES
blocks are rejected as a whole. There are limits of 1024 paths, 32,767 UTF-16 units
per path, a 1 MiB source block and 65,536 UTF-8 bytes of resulting text.

Terminal applications receive the path paste and can interpret it themselves.
Standard VT input does not define a universal file-drop acceptance handshake.
Consequently this fallback does not infer application acceptance from mouse
reporting, upload file contents, or change quoting when a nested shell starts.
Custom WSL mount points/UNC mounts and Cmd variable expansion (`%...%`, or `!`
with delayed expansion) retain their shell-specific semantics. Review those
paths before executing a command in such environments.

When the clipboard contains only an image, the terminal's Paste binding forwards
Ctrl+V to the application after releasing the clipboard lock. The application
then reads the native image clipboard. This works for the tested Windows Codex
and OpenCode clients; image support still belongs to the receiving application.
Text plus image uses the existing text paste behavior. This feature does not
change Sixel output or add an image codec to the terminal executable.

## Validation

`tests/drop_window_smoke.py` exercises the posted Windows drop-message boundary,
tab host delivery, copied-file clipboard data, image-only delegation, ordinary
text and malformed data in owned real terminal/ConPTY sessions. It also lets
installed pwsh, Windows PowerShell, BusyBox ash and Git Bash parse the actual
delivered quoting. GDI and DirectX are supported test variants. This test does
not simulate a physical Explorer mouse drag or validate a WSL distribution's
custom mount layout.

`tests/agent_clipboard_smoke.py` tests Ctrl+V and Ctrl+Shift+V with actual clients:

```powershell
python -m pip install Pillow==13.0.0
python tests/agent_clipboard_smoke.py --client codex --client-exe C:\path\codex.exe --terminal C:\path\nemoterm.exe
python tests/agent_clipboard_smoke.py --client opencode --client-exe C:\path\opencode.exe --terminal C:\path\nemoterm.exe
```

The client fixture uses a fresh home, private Git workspace and loopback model
provider returning fixed text only. Codex shell, patch, multi-agent and web-search
features are disabled with read-only sandbox/never approval. OpenCode tools and
permissions are denied, with no configured MCP servers or plugins. The provider
never issues a tool call, uses no account credentials or live model, and records
only generated marker text and image metadata. Codex can still advertise built-in
non-shell tools; advertised tool counts/names are retained rather than described
as zero. OpenCode's tested requests advertise zero tools.

Each case observes the application consume its generated prompt before pasting,
checks the visible image attachment, submits to the loopback provider, and
compares all 32x16 generated pixels in the received PNG. The original clipboard
is restored before normal client shutdown, unless another application replaced
it in the meantime. Evidence includes executable hashes, tool metadata, exact
pixel comparison, screenshots and natural owned-job cleanup. The tested local
versions were Codex 0.167.0 and OpenCode 1.19.3. Pillow is a test-only dependency.

Windows references: [WM_DROPFILES](https://learn.microsoft.com/en-us/windows/win32/shell/wm-dropfiles)
and [DragQueryFileW](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-dragqueryfilew).

Exact executable identities, local/CI failures and follow-up results are retained
in the [input validation checkpoint](../research/automation-input.md).

The manual **Input compatibility for an existing image** workflow can replay
the drop and real Codex image checks without compiling a new executable. Supply
the source run, exact artifact name and expected image SHA-256. The workflow
verifies the downloaded bytes and retains their original run identity; it does
not turn a failed build into a successful full-suite distribution.
