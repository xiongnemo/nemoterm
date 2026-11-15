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
The current local run is still in progress.

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
