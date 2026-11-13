# Local automation, file drops and image clipboard validation

Recorded 2026-11-14 Sydney. The user resumed local runtime testing. Earlier
records saying testing was paused describe their own checkpoints. The
[manifest](automation-input-validation.json) retains raw JSON, screenshots,
source hashes, CI identities and failed attempts without replacing their results.

## Local implementation checks

Product source `fa35542` adds opt-in local discovery, session-addressed text/key
input, visible text and BMP/PNG snapshots, shell-quoted file paths and native
image clipboard delegation. See [the protocol](../docs/AUTOMATION.md) and
[input behavior](../docs/INPUT_TRANSFERS.md).

The follow-up source `abafbbf` corrects the Unicode conversion and temporary
buffer lifetime described below. Its locally linked candidate is 4,466,176 bytes,
SHA-256 `9e79a655adbd20429d9f31caf037fb77c66a7da8e6028d3258a7908e6e23fbb1`.
It was linked before that commit from a checkout based on `4ab6939`; recorded
product source hashes match `abafbbf`. The reused CMake directory still embeds
the older PuTTY source marker `a3cce3a48d4ab12e0fccb32998b9042d4f7c3ff1`.
This is not an exact clean-commit CI build; use the image hash and recorded sources.
The manifest also retains the earlier `680bc6...` candidate and its successful
local checks. The accepted main-worktree executable was not overwritten.

| Scope | Observed result |
| --- | --- |
| Automation, GDI and actual DirectX | Nine groups each; discovery, Unicode, exact native screenshot pixels, input, bracketed paste, keys, malformed/stalled clients, tab isolation, opt-in and natural shutdown |
| File input, GDI and DirectX | 50 groups each; Unicode input/paste, file/folder paths, tab host and inactive tab targeting, ANSI and Unicode file clipboard formats, image-only delegation, normal text and malformed data |
| Shell argument interpretation | Actual pwsh, Windows PowerShell, BusyBox ash and Git Bash parse the delivered paths exactly; cmd and WSL are wire-format coverage only |
| Existing interaction regressions | Keyboard protocols, OSC 52 and GDI top-tab checks pass on the earlier `680bc6...` candidate |
| Codex 0.167.0 and OpenCode 1.19.3 | Ctrl+V and Ctrl+Shift+V each attach the generated 32x16 PNG with every RGB pixel matching; original clipboard restored and owned processes exit naturally |

The real-client tests use SarasaTermSC Nerd Font Light. Fresh private homes and
workspaces, disabled agent features and a text-only loopback provider prevent
model-driven tool execution. No live model or account credentials are used.
Codex still advertises nine built-in non-shell tools, recorded by name;
OpenCode advertises zero. No tool call is returned or executed.

The first automated image-first startup attempt did not attach an image and
required private-job cleanup. Its screen and record are retained. The successful
fixture first observes the application consume its generated prompt, then pastes
the bitmap. A startup frame alone was not a sufficient readiness check. This
does not claim that all startup timing problems have been identified.

Automation screenshots use transient buffers. DirectX's independent reference
capture is instrumented and later memory samples are marked accordingly.
These short clipboard/snapshot checks are not a new long-lived real-agent
memory acceptance. Physical Explorer gestures, custom WSL mounts, IME and
multi-monitor behavior remain outside this checkpoint.

## Complete CI baselines

Both full workflows pass at `34e60c1`: [single image, 88 groups](https://github.com/xiongnemo/nemoterm/actions/runs/43467627718)
and [compiler comparison/core/sanitizers](https://github.com/xiongnemo/nemoterm/actions/runs/43467627737).
The single image is 4,438,016 bytes, SHA-256
`4da276f0a46863bb7c0cb19e8a91240dc5beb42a3006a66d5c525d309a875b45`.
The source-built host fixes therefore have complete CI coverage in both compiler
paths; historical upstream-host failures remain retained separately.

The first automation CI at `826d98d` failed the UTF-8 fixture because it inherited
the runner's OEM console code page. `2cdde9c` explicitly selects UTF-8 in that
child. Its [single-image run passes 90 groups](https://github.com/xiongnemo/nemoterm/actions/runs/43475227426),
and its [complete core workflow passes](https://github.com/xiongnemo/nemoterm/actions/runs/43475227225).
The image is 4,444,672 bytes, SHA-256
`7cc4a722dac5e00b443ef559094664121822a64656c7c239997ddf2f90aaad7a`.

## Unicode failure and follow-up

Both `fa35542` native workflows fail their first file-drop check after passing
automation. Replaying the exact failed CI image in
[run 43481046410](https://github.com/xiongnemo/nemoterm/actions/runs/43481046410)
retains the expected and actual bytes: ordinary Unicode input and paste preserve
Chinese, while path conversion removes it. The first diagnostic rebuild at
`31c4e00` did not reach input tests because the MSYS2 dependency mirror refused
connections. Replaying the existing artifact avoids conflating that network
failure with native behavior.

`init_ucs` registered a 256-entry reverse mapping for UTF-8 when the font and
line codepages differed. Generic wide-to-UTF-8 conversion then used this display
table instead of the actual encoding, dropping CJK/surrogates and producing
single Latin-1 bytes. The local UTF-8 system locale had masked this case. A new
native regression explicitly initializes a Windows-1252 font with a UTF-8 line
codepage and round-trips accented, Chinese and supplementary characters. It
fails before `4ab6939` and passes after UTF-8 is excluded from single-byte maps.

The same conversion helpers cleared but never freed heap-backed temporary
buffers. `abafbbf` releases them in both directions. After allocator warm-up,
1,000 round trips of 4,096 Chinese characters increased private commitment from
1,466,368 to 25,714,688 bytes before the fix. Afterward it stays at 983,040 bytes.
The regression retains an 8 MiB allocator-growth allowance and never trims the
working set. This test covers conversion lifetime, not overall terminal memory.
The final MinGW/core CI independently repeats it at 1,306,624 -> 1,306,624 bytes.

A separate fixture problem was also reproduced locally: directory enumeration
could select the closed sibling's receipt after creating a second tab. Receipts
now use the PID announced by the selected child. Exact bytes, image pixels,
shell argument checks and natural cleanup assertions remain enforced.

All local automation, drop and four real-client image cases pass again on the
`9e79a655...` candidate. The complete `abafbbf` workflows are
[single image](https://github.com/xiongnemo/nemoterm/actions/runs/43482108697) and
[core/compiler comparison](https://github.com/xiongnemo/nemoterm/actions/runs/43482108469).
Both pass, with **93 single-image groups** including two real Codex image-paste
cases. The [downloaded image](https://github.com/xiongnemo/nemoterm/actions/runs/43482108697/artifacts/14066408513)
is 4,447,744 bytes, SHA-256
`d2cb59e3c50ba0e47afb7a19bbdd3b4bc8d6d9c98fca6d0e78ef1fcc0dcc74c8`.
Its nine automation groups also pass locally on Windows 10 with natural cleanup.
The earlier `4ab6939` full workflows also pass 93 groups, retained separately.

The final hosted single-image workload uses Consolas and actual grids of 109x34
(GDI) and 88x35 (DirectX). Frontend private-WS peaks are 11,177,984 and 21,876,736
bytes, respectively. Those passes do not replace the larger local Sarasa
workload observations below.

## Local Sarasa memory workload remains open

The exact earlier `fa35542` CI image (`ebe0bbd...`) was also tested locally with
SarasaTermSC Nerd Font Light, an actual 160x48 grid and two tabs. The uninstrumented
workload sampler records frontend peaks separately from hosts and clients:

| Renderer | Private WS peak | Total WS peak | Gate |
| --- | ---: | ---: | --- |
| GDI | 15,437,824 bytes | 41,578,496 bytes | Pass: below 20,000,000 |
| DirectX | 29,696,000 bytes | 70,004,736 bytes | Fail: exceeds 25,000,000 |

Both finish their functional groups and natural process cleanup. Repeating
DirectX after the conversion fixes on the `9e79a655...` candidate records
30,547,968 private / 70,971,392 total working-set bytes (100,216,832 private
commit bytes), again with all nine functional groups and natural cleanup.
The DirectX memory gate still fails. Smaller hosted-runner grids do not
supersede these observations. The current work does not complete the terminal goal.
