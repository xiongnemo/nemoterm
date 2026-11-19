# Files and image clipboard input

Dropping files or folders into a terminal view pastes their quoted paths, separated
by spaces, through the regular terminal paste path. It honors bracketed paste and
does not add Enter. Dropping on a tab label targets that session; dropping on other
parts of the host targets the active session. Existing mouse reporting remains
independent. Explorer's copied-file format (`CF_HDROP`) is accepted by the regular
Paste binding too, ahead of any accompanying text fallback.

Each running tab remembers the shell it started with, including recognized
explicit/custom commands. Changing the default shell in Profile Settings affects
new sessions; file drops into an existing session keep its original quoting.
PowerShell single quotes are doubled; ash/bash use POSIX single-quote escaping. Git Bash and BusyBox receive forward-slash Windows paths. WSL drive
paths use the default `/mnt/<drive>/...` mapping. When `wsl.exe` launches a
known distribution, dropping or pasting an Explorer path such as
`\\wsl.localhost\Ubuntu\home\me` yields `'/home/me'` in that distribution.
The `\\wsl$` alias and extended UNC spelling also work. If a WSL share belongs
to a different distribution, or the running distribution cannot be identified,
the whole drop is rejected instead of pasting paths to unrelated files.
Cmd receives quoted Windows arguments. Embedded controls, invalid UTF-16
and malformed or oversized DROPFILES
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
If both text and an image are offered, [nonempty text still wins](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/clipboard-empty-text.md), including
whitespace. An empty text alternative no longer discards an available image.
If the Unicode alternative is empty but the ANSI alternative has text, that text
is pasted. An empty clipboard text without an image still sends nothing. This feature does not
change Sixel output or add an image codec to the terminal executable.

## Validation

`tests/drop_window_smoke.py` exercises the posted Windows drop-message boundary,
tab host delivery, copied-file clipboard data, image-only delegation, ordinary
text and malformed data in owned real terminal/ConPTY sessions. It also lets
installed pwsh, Windows PowerShell, BusyBox ash and Git Bash parse the actual
delivered quoting. GDI and DirectX are supported test variants. This test does
not simulate a physical Explorer mouse drag or validate a WSL distribution's
custom mount layout. [The WSL share and shell profile replay](../research/drop-shell-paths.md)
also checks the actual file contents across Save and Apply and a new session.

The real-client tests run on GitHub-hosted Windows only. An exact-image replay
uses `font-zoom-replay.yml` with `suite=image-timing` for a copied bitmap,
`suite=image-files` for a copied PNG file, or `suite=interaction` and
`groups=["agents"]` for the Codex/OpenCode checks. Supply the branch, full
product commit and Actions run containing the single executable as described
in [the replay instructions](INTERACTION_ACCEPTANCE.md). The two clipboard
formats and the first visible prompt versus the settled editor are scored
separately. See [the file, bitmap and draft-order results](../research/codex-file-draft-order.md).

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
in the [input validation checkpoint](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/automation-input.md).

The manual **Input compatibility for an existing image** workflow can replay
the drop and real Codex image checks without compiling a new executable. Supply
the source run, exact artifact name and expected image SHA-256. The workflow
verifies the downloaded bytes and retains their original run identity; it does
not turn a failed build into a successful full-suite distribution.

For multiline text, Windows CRLF and standalone LF represent a logical line break. By default, Nemoterm sends CR for each break. An application can request literal LF with `CSI ? 2006 h` and restore the default with `CSI ? 2006 l`. This is independent of bracketed paste (`?2004`): enabling brackets alone does not change line endings. A standalone CR and the physical Enter key keep their usual meaning. See the [clipboard replay](INTERACTION_ACCEPTANCE.md#多行剪贴板换行与括号粘贴) for the verification scope.
