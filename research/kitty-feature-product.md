# Accepted feature-query single executable

The accepted local `dist/nemoterm.exe` is the formal CI product from
`6e05bd1a70515ede970323eb633563021d80ac3e`: **4,515,840 bytes**, SHA256
`dfae1cdea10e091d209aa56ce291b63e3ae5ada2f02035254c3c3398cda6c5ab`. Its runtime directory contains only this executable; the source-built
console host uses the same image. The prior accepted compression image is kept
locally at `build/accepted-before-feature-queries-b3e03bb.exe`.

[Ordinary CI 43653882910](https://github.com/xiongnemo/nemoterm/actions/runs/43653882910)
passed all four jobs and [single-image CI 43653882888](https://github.com/xiongnemo/nemoterm/actions/runs/43653882888)
passed **140 groups** at that exact source. [Download artifact 14138801522](https://github.com/xiongnemo/nemoterm/actions/runs/43653882888/artifacts/14138801522)
expires at `2026-12-15T00:13:04Z`. The strict GCC/Clang/MSVC component run also passed.
The [implementation record](kitty-feature-implementation.md) explains the
independent 84-case/176-state reference, supported-key projection and limits.

## Downloaded product validation

All **35 local groups** pass: one suite of 12 shutdown cases, 24 native image suites
and ten memory workloads. The image suites use SarasaTermSC Nerd Font Light and require
actual GDI, OpenGL and DirectX backends. GPU fallback cannot satisfy these runs.
The retained OS font-mapper preflight is independent of the terminal process.

| Fixture | Stages per actual renderer | Separate presented GDI stages |
| --- | ---: | ---: |
| Kitty image placement and lifecycle | 24 | 24 |
| Kitty font/window geometry | 12 | 12 |
| Compressed Kitty RGB/RGBA/PNG | 29 | 29 |
| Kitty feature-query state/reply replay | 176 | 176 |
| OSC 1337 static images | 32 | 32 |
| GIF animation | 36 | 36 |

All **927 API stages** and **309 direct GDI client-DC stages** pass. Feature-query
stages check exact wire replies with an input barrier, retained seed pixels and
completion of interleaved uploads. Every stored BMP is rehashed during review.
All test-owned jobs drain naturally, including each shutdown path.

## Ten uninjected memory workloads

Every workload uses an actual **160 x 48** Sarasa grid and two tabs. Sequential
sampling includes startup and resource settling with no working-set trimming.
GDI remains strictly below 20,000,000 private working-set bytes and DirectX at or
below 25,000,000. The additional external crash debugger is absent from all these
product acceptance runs.

| Workload record | Samples | Peak private WS (B) | Peak total WS (B) | Peak private commit (B) |
| --- | ---: | ---: | ---: | ---: |
| animated-workload-tabs-directx-left-observed.json | 540 | 24,236,032 | 59,822,080 | 88,600,576 |
| animated-workload-tabs-gdi-top-observed.json | 511 | 16,838,656 | 39,571,456 | 19,447,808 |
| compressed-kitty-workload-tabs-directx-left-observed.json | 654 | 23,781,376 | 59,236,352 | 83,005,440 |
| compressed-kitty-workload-tabs-gdi-top-observed.json | 579 | 16,687,104 | 39,337,984 | 19,746,816 |
| inline-workload-tabs-directx-left-observed.json | 575 | 23,707,648 | 59,244,544 | 91,910,144 |
| inline-workload-tabs-gdi-top-observed.json | 512 | 16,646,144 | 39,383,040 | 19,824,640 |
| kitty-workload-tabs-directx-left-observed.json | 659 | 23,834,624 | 59,387,904 | 87,908,352 |
| kitty-workload-tabs-gdi-top-observed.json | 576 | 16,515,072 | 39,137,280 | 18,948,096 |
| workload-tabs-directx-left-observed.json | 462 | 22,724,608 | 57,663,488 | 87,187,456 |
| workload-tabs-gdi-top-observed.json | 461 | 15,552,512 | 37,666,816 | 17,944,576 |

The maximum frontend private working sets are **16,838,656 bytes for GDI**
and **24,236,032 for DirectX**. Total WS peaks are 39,571,456 and
59,822,080; DirectX still exceeds the approximate 50 MB total target.
Private commit is recorded separately. Host, application and whole-tree samples
remain in the raw evidence; finite workloads do not prove arbitrary-load bounds.

## Retention and scope

`kitty-feature-product-validation.json` indexes all raw ordinary/single-image CI
records and **2,627 local records**, including a byte-verified promotion
receipt and 301 committed fixture hashes. The local acceptance and CI
archives have separately checked SHA256 hashes for every record.

Feature discovery reports the implemented bounded subset. File/shared-memory
transport, Unicode placeholders, relative placements and Kitty animation remain
open. Physical keyboard/wheel input, live IME candidate selection, cross-monitor
DPI and long-running real-application coverage are not established by these
deterministic native fixtures. The earlier audible-bell listening confirmation
retains its original executable identity in [the bell record](font-zoom-and-bell.md).
The [unresolved historical tab crash](tab-probe-detach.md) and shutdown failures
are preserved; successful replays and the new diagnostic observer do not prove
their causes. The original full-goal scope remains active.
