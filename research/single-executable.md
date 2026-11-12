# Source-built console host in one executable

## Decision and verified source build

The user requested source reuse of OpenConsole/ConPTY and a final single
`nemoterm.exe` (2026-11-12). The implementation links the native
PuTTY-derived frontend, Microsoft's `conptylib`, and OpenConsole host into one PE.
It launches that same image with `--headless` for the console server. This is
one executable file, with separate frontend, host and shell processes. It does
not extract embedded executables, replace Windows system files, or register a
default console handler. The source build and initial native tests passed in
[CI run 43152218663](https://github.com/xiongnemo/nemoterm/actions/runs/43152218663).
The single-file artifact is now the primary deliverable; the MinGW sidecar bundle
remains a separate compiler/backend comparison build.

## Current delivered checkpoint (2026-11-12)

The installed `dist/nemoterm.exe` is built from source commit
`a6493606a92cd6994fcc805d1a51d8a957ef63a3`: 4,314,112 bytes, SHA-256
`bfe1523105d1ef10de53c51e9fab4abcee710e5e93f59d3475401cc8a148b86f`.
The directory contains only that executable. Both
[single-executable CI](https://github.com/xiongnemo/nemoterm/actions/runs/43192696557)
and [core CI](https://github.com/xiongnemo/nemoterm/actions/runs/43192696689)
passed: 29 native checks, 29 core suites and 12 terminal sanitizer suites.
The [download artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43192696557/artifacts/13931254248)
contains only `nemoterm.exe`; test logs and captures are a separate artifact.

REA's complete import inventory for this exact file has 79 descriptors,
598 ordinary imports and 11 delayed imports, with no parse issues. It has no
import-table dependency on conpty.dll, WebView2Loader.dll or external
MSVC redistributable DLLs. Windows system/API-set DLLs, UCRT and ConDrv are still
required. The isolated runtime test also confirms that the hidden console host
uses the same executable path, no OpenConsole.exe/conhost.exe child is used,
and the portable directory still contains only the EXE after shutdown.
Embedded licences and third-party notices total 79,365 bytes and are available
through `--licenses` and About / View Licence.

The [working-directory checkpoint](working-directory.md) and
[`cwd-checkpoint.json`](cwd-checkpoint.json) bind the current artifact to its
CI, local regression results and memory samples. The earlier measurements below
are historical checkpoints, not the identity or size of the current file.

## Source integration

Microsoft Terminal is a pinned Git submodule at
`f6de9e0618015def1c9dda5b82f9d3abf03eb799`. Both OpenConsole and the ConPTY
implementation are in that repository. Its MIT LICENSE and third-party NOTICE,
plus the Nemoterm and PuTTY licenses, are embedded as resource 40000, available
via About / View Licence and redirected `--licenses` output. The upstream
checkout is unmodified; `scripts/prepare-single-exe.py` applies reviewed changes
to a generated copy under `build/openconsole-single` and rejects changed anchors.

## Evidence

REA's native PE readers inspected the shipped pinned NuGet files. Full evidence
is in `conpty-rea-evidence.json` (two records, not a runtime trace):

* conpty.dll: SHA256 `feeef341d891643c62d30b6b07800bc70f0bc148f44cb8c3bee84aa557ae805a`,
  119608 bytes, 14 export entries including ConptyCreate/Resize/ClosePseudoConsole.
* OpenConsole.exe: SHA256 `3d66b23d0a71bb8eed2b77edc8b9df9bf54ce6c8fb74c863a30e760997f80586`,
  1089376 bytes, PE import/delay-import inventory retained. Import-table entries
  establish dependencies, not which calls execute in a particular scenario.

Source inspection establishes the implementation boundary:

* [winconpty.cpp](https://github.com/microsoft/terminal/blob/f6de9e0618015def1c9dda5b82f9d3abf03eb799/src/winconpty/winconpty.cpp)
  creates a ConDrv server/reference handle pair, creates the signal pipe, and
  launches a headless host with a restricted inherited handle list.
* [winconpty.h](https://github.com/microsoft/terminal/blob/f6de9e0618015def1c9dda5b82f9d3abf03eb799/src/winconpty/winconpty.h)
  documents the OS-shared HPCON layout and ConDrv reference lifetime. ConDrv is
  still an operating-system dependency; bundling user-mode sources does not
  replace the Windows kernel console driver.
* `src/winconpty/lib/winconptylib.vcxproj` already defines a static library.
* `src/host/exe/exemain.cpp` validates the console server handle and starts the
  console server threads. Its globals and lifetime assumptions favor retaining
  a distinct process, even when both modes share a single executable image.

The overlay changes host path selection to the current image, renames the host
entrypoint, dispatches only a leading `--headless`, disables incoming COM handoff
and omits the Windows Terminal UI dependency feature. Renderer build flags stay
at upstream defaults; headless operation does not construct the visible renderer.
The underlying console protocol/server implementation remains Microsoft's.
The frontend uses the four statically linked Conpty functions as one ABI unit,
including ReleasePseudoConsole for delegated process lifetime;
`NEMOTERM_CONPTY=system` remains an explicit diagnostic override.

## Downloaded artifact and isolation evidence

Commit `855dbd81b6c30d3476b70ecc963084741ff01326` produced a 1,633,792-byte EXE,
SHA256 `5eb5f9681eb997d95d7d97d4858044bf5a39fa49462b1965b6565c3c116b8c52`.
REA inspected all 79 import descriptors (597 ordinary and 11 delayed functions)
without parse issues. `single-exe-rea-evidence.json` retains the complete table:
Windows system/API-set DLLs, including system UCRT and delayed ICU; no conpty.dll,
OpenConsole sidecar or external MSVC redistributable DLL. Import inspection is
static evidence and does not claim every imported function executed.

The downloaded file ran alone from an otherwise empty directory containing
spaces and Chinese characters. The native fixture observed a second process
with the exact same executable path, tested a child surviving its initial
launcher, verified clean final shutdown, and checked the directory still
contained only the EXE. Embedded licence output was 27,091 bytes.
`single-exe-observed.json` records paths, executable digest and separate memory
samples: frontend private WS 3,788,800 / total WS 22,237,184 / private commit
4,894,720 bytes; hidden host 1,548,288 / 10,510,336 / 2,199,552 bytes. These are
point observations, not lifetime peaks, and the child workload is separate.

At this initial checkpoint, `scripts/test-single-exe.ps1` copied only the EXE
into its own dist directory and ran 20 native groups plus two additional
keyboard font/configuration cases.
The workflow retains all JSON, PrintWindow captures and logs separately from
the one-file download. Shell detection/default selection is implemented and
documented in [shell-selection.md](shell-selection.md).

All 20 groups and both additional keyboard cases passed locally for the artifact
above. `single-exe-validation.json` lists cases and hashes of the original JSON
observations. The mixed 6,000-link / 800-Sixel workload continuously sampled
frontend peaks of 9,314,304 bytes private WS, 35,516,416 total WS and 10,670,080
private commit. Reflow peaked at 7,020,544 / 24,580,096 / 8,400,896 respectively.
No working-set trimming was used. These workload-specific frontend peaks do
not include the host or shell, and do not establish bounds for every workload.
All six locally available shells, including WSL Debian Bash, ran an interactive
marker command and exited; temporary settings persisted Git Bash and the startup
chooser while leaving the user's Default Settings unchanged.

The first full local run stopped before modifying an existing bitmap clipboard,
because the test helper only understood HGLOBAL formats. The helper now uses
documented OleDuplicateData handling for bitmap/palette objects, releases private
copies, and leaves a newer external clipboard owner alone. The affected native
tests then passed with the image clipboard retained. Remaining terminal protocol,
physical IME, multi-monitor DPI and long-running real-agent acceptance are tracked
separately in the requirements ledger.


## Unicode input checkpoint

The later `badf932` source artifact is 4,307,968 bytes with SHA-256
`25d734ce58418509d423d7091f76c5efe23821759fbee929bc16176e8bf7a892`.
All 28 single-executable CI checks passed at that checkpoint.
It includes the embedded Nerd font and source-host Unicode stream corrections.
REA again parsed 79 descriptors, now 598 regular and 11 delayed imports, with
no issues. Runtime isolation still uses only the same EXE and Windows system
components. See [input-method validation](input-methods.md) for CI links,
local verification, memory samples and the remaining acceptance boundaries.
