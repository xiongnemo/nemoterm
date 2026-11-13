# Local MSVC single-image checkpoint

This checkpoint builds the newer grapheme, RTL and startup-setting changes into
one executable on Windows 10 19044. It does not promote the accepted `dist` image
or replace the still-required GitHub clipboard and real-Codex gates.

## Artifact and toolchain

Source `800be22e8f80aca17d9b0d4c0bc066773c747485` produced a 4,416,000-byte image:
`cd654873bf56be28e65e5d357065b2d0941fb7ef5d673007f6a9c57f36a8b511`.
The local copy is `build/local-msvc-check-800be/dist/nemoterm.exe`.
Its isolated-directory test passed with exactly one file, an embedded license,
and a hidden console host using the same executable. No runtime extraction or
OpenConsole/ConPTY sidecar was required.

The build uses MSVC 19.44.35230, MSBuild 17.14.60.43110, the Windows SDK NuGet
packages 10.0.26100.6584 targeting 10.0.26100.0, and a static CRT. The pinned
Microsoft Terminal revision remains `f6de9e0618015def1c9dda5b82f9d3abf03eb799`.
The [build manifest](local-msvc-build-manifest.json) records tool signatures,
package URLs and hashes, versions, native dependencies, commands and PE imports.
These are extracted standard Visual Studio packages, not an EWDK installation.

This machine had no registered Visual Studio or SDK installation. Tools were
placed under the ignored `build/local-msvc` directory. MSBuild uses `UseEnv=true`
with an explicit x64 compiler/SDK environment. Dependencies were built first
with vcpkg's pinned baseline and a local chainloaded compiler triplet, then the
host build used `VcpkgManifestInstall=false` to reuse that verified install.
The local triplet selects the available v143 toolchain; the upstream v145 CI
triplet and product source overlay were not changed to accommodate this machine.

The downloaded VS catalog's byte hash did not match the digest in its parent
channel. This discrepancy is retained in the manifest. Each selected VSIX
matched its own payload SHA-256, and the executed compiler, linker, MSBuild,
NuGet, vcpkg and SDK resource compiler had valid Microsoft signatures. SDK and
WIL packages were restored through the signed NuGet client.

## Validation scope

All 35 Windows core/offscreen executables passed under MSVC, including the 853
official Unicode grapheme vectors. [Core results](local-msvc-core-validation.json).
All 50 local native cases passed, including all four tab-strip positions,
background previews, both settings dialogs, real hardware renderer switching,
fault recovery, six detected shells, Unicode input, Sixel and resize cases.
Native results for this exact image are recorded separately in
[the local validation record](local-msvc-native-validation.json).
The local suite deliberately excludes real clipboard access; the normal CI
script retains those mandatory assertions.

Inspected captures: [grapheme setting](local-msvc-grapheme-settings.png),
[tab hover preview](local-msvc-tab-preview.png), and
[Courier RTL fallback](local-msvc-rtl-courier.png).

The native settings runner initially inherited PowerShell 7 module paths through
Python. Its UI and protocol operations completed, but report generation failed
when Windows PowerShell could not load `Get-FileHash`. The local orchestration
now supplies Windows PowerShell's built-in module directory for that test child;
both settings variants were replayed. The failed attempt is retained, rather
than counted as a pass.

The 160x48 dense scene retains two tabs and creates/closes twelve temporary tabs,
with a third tab live during some samples. Before capture instrumentation, its
observed peaks were:

| Renderer | Private working set | Total working set |
| --- | ---: | ---: |
| GDI | 10,104,832 bytes (10.10 MB / 9.64 MiB) | 32,059,392 bytes (32.06 MB / 30.57 MiB) |
| DirectX | 19,591,168 bytes (19.59 MB / 18.68 MiB) | 55,758,848 bytes (55.76 MB / 53.18 MiB) |

Those are process samples for this workload, not universal memory bounds.
Preview peaks and all child-process memory are not included in these two rows.
The single-image isolation record separately reports its frontend and host.
OpenGL uses the user's explicit memory-budget exception. DirectX has little
margin under the private-working-set target and still needs broader workloads.

## Windows PowerShell launch correction

Following the runner failure exposed the same issue in the actual terminal:
`pwsh -> Nemoterm -> Windows PowerShell` retained incompatible Core module paths
and lost `Get-FileHash`. Microsoft documents this intermediate-launcher behavior
and recommends removing the inherited child `PSModulePath` so Windows PowerShell
can construct its normal paths. [Microsoft documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_psmodulepath?view=powershell-7.6#starting-windows-powershell-from-powershell-7).

Commit `8955fb72a846ebad25b3fc834333f1dbf391573c` applies that rule only when
selecting the built-in Windows PowerShell shell, including a saved default.
It copies the child environment and preserves every other entry. The parent,
pwsh, custom shell commands and explicit `-e` commands keep their original
environment. Transient custom module paths can still be supplied using the
custom or explicit-command launch paths.

The corrected image is 4,417,024 bytes with SHA-256
`1fa253babd6baf0aa83ec07a5141780cbbc2c5bdf7dba9626a74f513654e034e`, at
`build/local-powershell-check/dist/nemoterm.exe`. Its focused native regression
passes selected Windows PowerShell, a saved Windows PowerShell default in tabs,
custom command, explicit command and pwsh cases. Positive cases execute the real
hash function and compare the executable's digest; the controls retain their
deliberately incompatible paths. MSVC and MinGW both pass the environment unit
test, including case-insensitive filtering, Unicode values, similarly named
variables and an unchanged parent block.
[Before/after evidence and source hashes](powershell-environment-validation.json).

Seven further native checks passed on that corrected image: single-file
isolation, all six shell launches, startup sizing, all three renderers, dense
GDI/DirectX tabs and restart lifetime. Its dense-tab private-working-set peaks
were 10,223,616 bytes for GDI and 19,456,000 bytes for DirectX; total working-set
peaks were 32,116,736 and 55,738,368 bytes respectively. The same sampling limits
described above apply. These focused reruns are distinct from the 50-case
pre-fix baseline and do not claim that all CI gates ran on the corrected image.

CI now includes this native regression in both Windows and single-image checks.
Account billing previously prevented the recent workflows from starting. Real
clipboard/Codex acceptance, the earlier unexplained tab-close access violation,
physical IME/multi-monitor testing, preview/process-tree memory and the broader
protocol inventory remain open. Passing local lifetime repetitions does not
explain the historical crash or transient handle growth.
