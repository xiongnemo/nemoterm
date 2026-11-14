# Optional graphics DLL loading experiment

The isolated linker experiment is **not adopted**. In one complete DirectX pair,
the total working-set peak decreased by only 303,104 bytes, while private working
set and private commit increased. This does not establish a repeatable benefit
or meet the approximate 50 MB total-working-set target. Product source, link
flags and the accepted distribution are unchanged.

## Identity and method

The baseline is the local integrated input-close image at source `9c22311`,
4,509,696 bytes, SHA-256
`8092e3e89ef243bd19726d91966def8f907b9394e638db53d033a50b7e59b00a`.
The experiment uses exactly the same input object/library hashes and changes
only output locations and five linker delay-load options: `d2d1.dll`,
`DWrite.dll`, `dxgi.dll`, `d3d11.dll`, and `D3DCOMPILER_47.dll`.
The resulting 4,510,720-byte image has SHA-256
`c9a8d10453d8cda593f81c5a4e27bee1ed86198a9c8e07f3bd884645143330dd`.

REA static PE import records are retained in full:

- Before: `ev_38a7808982119edba2c9df3afaa0cad24a609b877a2355b0ab4cf703650623f4`.
- After: `ev_c5c79b4b26ee789820a3b31b77b9408225a4874ec4065fb12a01edc6dc8ba2e8`.

Standard function imports changed from 645 to 639, and delayed imports from
11 to 17; all five DLL descriptors moved to the delay table. Static imports do
not prove which modules are loaded at runtime. The separate local Win32 module
catalogue observes that distinction; it is **not REA-server Evidence**.

All runs use fresh owned jobs and the existing 180-second outer controller.
The original tab workload, numerical assertions, SarasaTermSC Nerd Font Light,
160x48 grid and worker-exit checks are retained. The catalogue reads only the
owned frontend's window classes, HWND metadata and loaded-module paths at
existing resource checks. It adds no target injection, global input, focus
change or IME setting change. Later existing screenshot tests retain their
usual instrumentation, after memory sampling. Catalogue runs are diagnostic,
explicitly `completed=false` and `memory_acceptance=false`, even when their
original assertions all pass.

## Results and failures

The unmodified delayed-image startup and DX automation tests pass. The initial
unmodified paired workload stops on the baseline GDI image: handles increase
from 361 to 405, GDI objects from 36 to 38, USER objects from 37 to 52. Both
retained I/O workers have already signalled exit. This prevents drawing a full
paired memory conclusion from that attempt.

The catalogue diagnostic completes the baseline GDI workload, but the delayed
GDI case stops on the original USER-object gate: baseline 36, post-close 39,
allowance +2. Handles remain 355 and GDI objects remain 36. Its HWND catalogue
shows no additional retained enumerated windows. That does not identify all
USER-object types or prove a leak. Four of the five optional DLLs are absent;
DirectWrite is still loaded. A subsequent diagnostic adds two seconds of
post-failure samples while retaining the original failed-sample verdict. That
run does not reproduce the failure, so it supplies **no evidence** that the
three objects later retire. It completes the workload with USER baseline 50
and post-close 52. The original failures remain unresolved and are retained.

Both complete DirectX catalogue workloads pass all nine original functional
groups, with 56 inner and 58 outer processes exiting naturally:

| Frontend peak, decimal bytes | Baseline | Delay-load experiment |
| --- | ---: | ---: |
| Private working set | 23,543,808 | 23,760,896 |
| Total working set | 63,123,456 | 62,820,352 |
| Private commit | 85,663,744 | 92,946,432 |
| Samples | 457 | 447 |

The baseline has all five DLLs loaded. The delayed DX process has D3D11, DXGI
and DirectWrite loaded at both the initial and final catalogue, while D2D and
D3DCompiler are absent. Thus the intended loading change is observed, but the
measured benefit is insufficient. This is one diagnostic pair on one machine,
not a statistical performance comparison.

The default MSVC helper calls `LoadLibraryEx` with flags zero, as confirmed in
the installed 14.44.35207 `delayhlp.cpp` and
[Microsoft's helper documentation](https://learn.microsoft.com/en-us/cpp/build/reference/understanding-the-helper-function?view=msvc-170).
Any future adoption also needs to review initialization order and DLL search
policy for both frontend and host entry paths. No new loading policy is added
by this rejected experiment.

The [hash manifest](delay-load-validation.json) retains the static records,
link inputs, scripts, original failures, diagnostic reports, logs, memory
samples and cleanup. It verifies decompressed bytes, not just archive names.
