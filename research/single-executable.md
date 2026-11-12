# Source-built console host in one executable

## Decision and current validation boundary

The user requested source reuse of OpenConsole/ConPTY and a final single
`nemoterm.exe` (2026-11-12). The implementation being validated links the native
PuTTY-derived frontend, Microsoft's `conptylib`, and OpenConsole host into one PE.
It launches that same image with `--headless` for the console server. This is
one executable file, with separate frontend, host and shell processes. It does
not extract embedded executables, replace Windows system files, or register a
default console handler. A source build and native runtime tests must succeed
before this becomes the default deliverable; the existing MinGW bundle remains
the tested baseline during integration.

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
and custom GPU shaders, and omits the Windows Terminal UI dependency feature.
The underlying console protocol/server implementation remains Microsoft's.
The frontend uses the three statically linked Conpty functions as one ABI unit;
`NEMOTERM_CONPTY=system` remains an explicit diagnostic override.

## Remaining acceptance

Build and download the CI artifact; inspect its dependencies; copy only its EXE
to an empty path containing spaces/Unicode and exercise console creation,
keyboard/mouse, resize, Sixel, clipboard and settings. Verify the hidden host is
the same image and no sidecar executable/DLL is created. Record private working
set, total working set and private commit separately for frontend and host.
Shell selection/detection (including Windows PowerShell, pwsh, BusyBox ash,
Git Bash, and installed WSL distributions) remains a separate active requirement.
