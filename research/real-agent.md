# Real Codex client interoperability

## Reproduction and scope

The installed Windows Codex CLI 0.167.0 was launched in a newly owned Nemoterm
window with SarasaTermSC Nerd Font Light, a temporary `CODEX_HOME`, an empty
working directory, and `--no-daemon`. The real client rendered the conversation;
a loopback-only fixture supplied deterministic streamed text. No online model,
existing conversation, user API credential, MCP server or generated tool call
was used. The client also requested a task title; the fixture serves that request
separately from the two tested conversation turns.

The first executable was the `a649360` single-file artifact, SHA-256
`bfe1523105d1ef10de53c51e9fab4abcee710e5e93f59d3475401cc8a148b86f`.
The local Codex image was SHA-256
`edfdd48f8b458af0906e507b4cb05217b326c3d6e515e9f024e05e3b8d650f70`.
Native `ReadConsoleInputW` traces from the owned Codex process distinguish
transported key records from the text eventually submitted by the application.
Frida traces are runtime observations, not facts inferred from import tables.

## Unicode text events

Typing `NEMOTERM_INPUT 中文 é 🙂` into the old artifact submitted only
`NEMOTERM_INPUT 中文 é`. At the Codex API boundary, the emoji arrived as four
records: high-surrogate down, high-surrogate up, low-surrogate down, low-surrogate
up. Codex 0.167.0's [Cargo.lock](https://github.com/openai/codex/blob/rust-v0.167.0/codex-rs/Cargo.lock)
pins crossterm 0.29.0 at `ed1cdab335221515706178d68495bba2aed1924f`.
That [Windows decoder](https://github.com/openai-oss-forks/crossterm/blob/ed1cdab335221515706178d68495bba2aed1924f/src/event/sys/windows/parse.rs)
uses one surrogate buffer for that event stream; those pairs do not form a
Unicode scalar. Temporarily suppressing the release characters at the owned
client's read boundary restored the exact emoji, confirming this hypothesis.
That experiment is explicitly diagnostic and is not product acceptance.

The source-host overlay now emits key-down-only text records for surrogate
units, covering both `InputStateMachineEngine::_GetSingleKeypress` and
`InteractDispatch::WriteString`. This follows the text-commit behavior of
[Windows Terminal's SendCharEvent](https://github.com/microsoft/terminal/blob/f6de9e0618015def1c9dda5b82f9d3abf03eb799/src/cascadia/TerminalCore/Terminal.cpp).
It does not add a pending-event buffer or change physical-key release handling.
The upstream submodule stays unchanged; the two changes are applied to the
generated build tree by `scripts/prepare-single-exe.py`.

`console_unicode_window_smoke.py` reads real console events in batches of 1, 3
and 128 records, using both burst and separated text input. It checks BMP text,
combining marks, emoji, supplementary CJK and a supplementary Nerd symbol,
followed by Enter. The old artifact fails on the invented surrogate releases.
The existing raw/VT/cooked byte-reader tests remain separate regression gates.

## Enter after a burst

The initial automation sent the whole prompt and Enter immediately together.
Codex's [PasteBurst implementation at 0.167.0](https://github.com/openai/codex/blob/rust-v0.167.0/codex-rs/tui/src/bottom_pane/paste_burst.rs)
intentionally treats Enter within a paste-like burst as an input newline. Its
Enter suppression interval is 120 ms and its Windows flush interval is 60 ms.
The trace contains the expected VK_RETURN/CR press and release. This observation
does not establish a dropped Return in Nemoterm. The application test first
observes the complete input in the client's rendered screen, then waits 200 ms
before submitting. A fixed sender-side delay is insufficient if a slow startup
queues both text and Enter before the input loop starts. No delay or Codex
configuration workaround is added to the terminal product.

## Independent mouse selections

The inherited click classifier checked only button and time. Two rapid drags
on different lines could therefore become word/line selections. A native test
reproduced this independently of Codex. `click` now also checks the system
double-click rectangle; timer subtraction uses unsigned wraparound arithmetic.
The per-window state gains two integers, with no allocation per click.

`selection_window_smoke.py` verifies four rapid independent ranges in both
ordinary mode and application mouse mode with Shift held. The right button
copies each exact range and sends no paste or application mouse bytes. The
old single EXE fails this test; the corrected source-built candidate passes.

## Real-client regression

`codex_window_smoke.py` exercises default and `--no-alt-screen` modes:

* Actual native Codex startup and exact Unicode text delivered to its provider.
* Streamed Markdown, a code block, table, Chinese, combining marks and 80 rows.
* Thirty-two live window size changes with the completed response retained.
* Shift grid selection and exact Ctrl+Shift+C, including both Nerd symbol planes.
* Ctrl+Shift+V reaching the real client and its next request with exact Unicode.
* Separate frontend, host and client process samples, and owned-process cleanup.

The model fixture uses the documented
[Responses streaming events](https://developers.openai.com/api/reference/resources/responses/streaming-events).
The CI client is pinned to 0.167.0 through a package lock with integrity hashes;
it is a test dependency, not part of the shipped terminal. The single-file test
runner accepts `-CodexExecutable` and CI uses it for both client modes.

To reproduce against an installed native client in a fresh isolated directory:

```powershell
./scripts/test-single-exe.ps1 -Executable ./dist/nemoterm.exe `
  -Destination ./build/agent-validation-new `
  -CodexExecutable (Get-Command codex.exe).Source
```

The two real-client groups default to SarasaTermSC Nerd Font Light locally;
CI selects Consolas. No private client home or conversation is copied into CI.

Frontend memory sampling finishes before Frida is attached to the terminal for
shortcut injection. The shortcut probe changes keyboard state only on the
owned terminal's UI thread and restores it; it sends no global keyboard input.
The first diagnostic runs also traced or modified the owned client and are
excluded from final product evidence. Input here uses native window messages
and a controlled keyboard-state fixture, not physical keyboard/IME operation.

## Artifact validation

An initial CI run at `73bce4e` compiled the single executable and passed the new
Unicode-event and independent-selection groups. Both workflows then failed an
old highlight test that treated a click at column 2 followed by column 5 as a
double-click. The fixture now performs its double/triple clicks at column 5;
the expected word/line selection and highlight protocol replies stay the same.
The downloaded candidate passes that corrected native highlight test.

At `4e2f17c`, core CI passed and the first 32 single-file checks passed. The
last, inline Codex check exposed the startup race described above: its captured
screen eventually contained the complete Unicode prompt, but the text and Enter
had been consumed as one paste burst and no request was submitted. The test now
waits for visible input consumption. Both modes pass locally on that unmodified
candidate, SHA-256
`d26760bc01775334a5bab73378b1db1fd1f1675f5bc70404804dab985949e21e`.

At `67cfc11`, core CI passed. The single-file job exposed a separate shell
fixture race before reaching Codex: CMD's redirection created the cwd report
before the command populated it. The reader now waits for a subsequent
completion marker, including the Git Bash/WSL duplication checks. All six local
shells pass. The delegated-child fixture now uses the existing atomic JSON
mailbox writer to eliminate the same incomplete-report window.

Source commit `2862f6768478c2933a8ae3f60640a7e34e3190ea` passed both
[single-file CI](https://github.com/xiongnemo/nemoterm/actions/runs/43206539384)
and [core CI](https://github.com/xiongnemo/nemoterm/actions/runs/43206539406):
33 single-file checks, 29 core suites and 12 terminal ASan/UBSan suites.
The [single EXE artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43206539384/artifacts/13938628132)
contains only `nemoterm.exe`; the
[build and native evidence](https://github.com/xiongnemo/nemoterm/actions/runs/43206539384/artifacts/13938688064)
is separate. Its 33 artifact-bound JSON records were checked against the
downloaded executable's SHA-256:

`955c4c7b66fdb98dce4edef2b7dc6645678b8fb582b67742d45732da15edda56`

The executable is 4,314,112 bytes. That exact file passed seven further local
groups: isolated single-file operation, native console Unicode events, rapid
independent selection, same-position highlight multi-clicks, all six shells,
and both real Codex modes with Sarasa. It is installed as `dist/nemoterm.exe`;
the directory contains no other file. The
[checkpoint](real-agent-checkpoint.json) binds CI and local evidence to this
artifact, and the [local manifest](real-agent-local-validation.json) lists the
completed groups.

Local frontend sampled peaks, before attaching the shortcut probe (bytes):

| Codex mode | Private working set | Total working set | Private commit |
| --- | ---: | ---: | ---: |
| Default | 7,008,256 | 32,604,160 | 9,015,296 |
| Inline | 7,213,056 | 32,882,688 | 8,900,608 |

The separate headless host's post-resize snapshots were 1,581,056–1,617,920
private WS, 10,575,872–10,588,160 total WS and 2,297,856–2,310,144 private
commit bytes. The separate Codex client's snapshots were 32,509,952–32,968,704
private WS and 155,627,520–156,041,216 total WS bytes. These snapshots are not
peaks; process working sets share pages and are not added as unique physical
memory. Both frontend peaks satisfy the requested private WS <20 MB and total
WS around 50 MB. No working-set trimming is used.

[REA import evidence](real-agent-pe-evidence.json) for the same SHA covers all
79 descriptors, 598 ordinary imports and 11 delayed imports without parse
issues. There is no import-table dependency on conpty.dll, WebView2Loader.dll
or an external MSVC redistributable DLL. Windows system/API-set DLLs, UCRT and
ConDrv remain required. The isolated runtime check separately confirms a
same-image hidden host and 79,365 bytes of embedded licences/notices.

Inspected captures: [streaming Markdown](codex-default-markdown.png),
[exact grid selection](codex-default-selection.png), and
[inline Unicode paste and response](codex-inline-paste.png). All owned process
handles reported termination: frontend/host exit 0 and Codex CTRL_C_EXIT when
the terminal closed. This is not a graceful client `/quit` test.

This closes only the tested real-client paths. Live-service sessions, Claude
Code, long-running agent workloads, physical IME/keyboards, multi-monitor DPI,
complete grapheme rendering and the remaining terminal protocol ledger stay open.
