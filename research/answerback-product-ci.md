# Combined candidate 253855b

Source `253855b481b2ccd6a13dae5490c42f19c8b9dd64` passes all four jobs in
[ordinary CI 43757506311](https://github.com/xiongnemo/nemoterm/actions/runs/43757506311)
and all **163 groups** in
[single-image CI 43757506287](https://github.com/xiongnemo/nemoterm/actions/runs/43757506287).
The component comparison also passes GCC/Clang sanitizers and MSVC; its separate
records are in `answerback-nul-ci-validation.json`.

The [downloaded single executable](https://github.com/xiongnemo/nemoterm/actions/runs/43757506287/artifacts/14181225772)
is **4,544,512 bytes**, SHA256
`f086fde1d97b33d231281a939dcf855150b2270726e672d99b68fca631e32107`.
The downloaded bytes match the native validation manifest, and the artifact
contains `nemoterm.exe` alone. This is a candidate, not a replacement for the
previous locally accepted executable.

This combined source includes the GDI display-cache repair, command-line
overrides across saved profiles, minimized tab-host restoration, stricter host
fixture checks, monitor-bounded resize expectations, configured topmost bell
fixtures, terminal-parameter query syntax, configured answerback recovery, and
the Unix embedded-NUL conversion fix. Ordinary CI builds the console host from
the pinned source; the single-image workflow links its host into the executable.

All twelve single-image memory workloads complete their existing gates. The
hosted GDI cases use a clamped 109x34 grid; DirectX cases use 88x35. Those runs
cannot replace local 160x48 Sarasa acceptance. The 49-group local plan separates
41 owned background cases from eight foreground/clipboard cases. Its prepared
audit requires the exact executable, source-matched fixtures, all planned groups,
raw pixel evidence and unchanged memory limits before reporting completion.
All 41 background groups have now run: **40 pass**, and the dense DirectX
workload fails only its unchanged private-working-set gate after its pixel and
lifecycle checks pass. The eight desktop/clipboard groups remain pending. The
completed background evidence is independently reviewed and retained below.

`answerback-product-ci-validation.json` binds the source, complete workflow/job
results, artifact metadata and all 163 group names. The three retained ZIPs are
the original GitHub artifact bytes, with SHA256 values matching GitHub's
published artifact digests:

| Archive | Artifact | Verified files |
|---|---:|---:|
| `answerback-product-ci-core-evidence.zip` | 14180033523 | 4,505 |
| `answerback-product-ci-single-evidence.zip` | 14180543142 | 4,562 |
| `answerback-product-ci-product.zip` | 14181225772 | 1 |

Every ZIP member was independently hashed and matched to the retained download
receipt. The evidence ZIPs retain raw BMP/PNG pixels, memory samples, native
observations and logs without expanding over a gigabyte of duplicate files in
Git. Prior failed revisions remain recorded separately; this successful CI run
does not explain their intermittent callback or lifetime observations. Complete
xterm-family coverage and remaining physical/application requirements are not
claimed by these finite regression groups.

## Local GDI checkpoint

The exact downloaded image completes the 160x48 **SarasaTermSC Nerd Font Light**
dense Unicode-image workload at **19,197,952 bytes private working set**,
**41,832,448 bytes total working set**, and **22,716,416 bytes private commit**.
All 3,966 samples over 431.767 seconds are uninjected; their maxima are
independently recomputed from the original samples. Memory sampling completes
before image-capture and key probes are loaded. The unchanged strict GDI
20,000,000-byte private-working-set gate passes.

After sampling, all **29,072 image-cell comparisons** pass on both active and
inactive tabs. Twelve retained PNG strips are independently decoded and checked
pixel by pixel. Ten tab/lifecycle checks pass, and all **56 owned processes**
exit naturally. The complete case takes 897.2 seconds, including its subsequent
image and lifecycle checks; this is a finite synthetic workload, not an
interactive performance or long-running agent certification.

`answerback-product-local-gdi.tar.gz` and its validation manifest retain this
case plus the twelve earlier completed groups: CLI profile precedence, hosted
geometry on all three actual renderers, resize on all four tab sides, 272
terminal-parameter streams, 160 configured-answerback streams, twelve shutdown
cases and startup sizing. The reviewer checks fixture bytes against Git source
`253855b`, original per-case file hashes, exact reply bytes, actual renderer
identity and natural cleanup. The resize checks also recompute work-area clamps.

The archive contains a stable thirteen-result prefix captured before the
background controller finished. Later results are retained separately below;
this prefix does not certify them or the full candidate.

## Completed background run

`answerback-product-local-background.tar.gz` retains the remaining 28 groups,
the complete 41-command result list and original per-case observations. Its
validation manifest rechecks every retained file hash and the original fixture
identity. All six installed shells execute commands: PowerShell 7, Windows
PowerShell, BusyBox ash, Git Bash, WSL Bash and cmd. Session/restart, font zoom,
both automation renderers, four tab-bar positions and 72 feature-policy cases
pass. The six image/geometry groups add **153 stages** across actual GDI,
OpenGL and DirectX; decoded geometry pixels and original BMP hashes are checked
again. These are retained-renderer captures, not a new presented-desktop test.

Ten ordinary image-memory workloads pass. The dense DirectX workload completes
**4,153 uninjected samples over 451.726 seconds**, with peaks of **27,602,944
private WS / 63,152,128 total WS / 89,686,016 private-commit bytes**. All 29,072
image-cell comparisons and ten lifecycle checks pass; all 56 owned processes
exit naturally. Its **25,000,000-byte** private-working-set regression gate
fails, so the original report remains `completed: false`, phase
`memory-acceptance`, and the controller exits with failure. No limit is relaxed
and no additional DX memory optimization is undertaken.

Together the two archives establish 40 passing background groups and preserve
the one failed gate. They do not certify the eight desktop/clipboard groups,
physical IME/DPI, long application sessions or full protocol coverage. The
previously accepted distribution is unchanged. Later parser fixes have separate
source identities and do not inherit these measurements.
