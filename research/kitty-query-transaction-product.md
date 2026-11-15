# Accepted query-transaction single executable

The accepted local `dist/nemoterm.exe` comes from source
`752f3be71f8a0dce6e24d46af7dcf3d6d87c70a2`: **4,515,840 bytes**, SHA256
`1655120a9a64bfd29b64f6ad0a5cc912484ba1d242ec560938591c03328e2cf1`. Its runtime directory contains only this executable; the source-built
console host uses the same image. The earlier feature-query product is backed up
locally at `build/accepted-before-query-transactions-6e05bd1.exe`.

This version fixes a lost unfinished image upload when a malformed query header
is interleaved between chunks. The original product failure and the independent
upstream comparison remain in [the query-error record](kitty-query-errors.md).
The fix does not introduce a rollback buffer or an additional heap allocation.

[Ordinary CI 43664330393](https://github.com/xiongnemo/nemoterm/actions/runs/43664330393)
passes all four jobs. [Single-image CI 43664330399](https://github.com/xiongnemo/nemoterm/actions/runs/43664330399)
passes **143 groups**. [Download this exact product](https://github.com/xiongnemo/nemoterm/actions/runs/43664330399/artifacts/14143105257); it expires at
`2026-12-15T02:16:19Z`. GCC, Clang and MSVC component checks passed at the preceding
`88743d3` product-fix commit; intervening changes affect tests and records only.
The current full core pipeline also covers sanitizers and the real-core replay.

## Downloaded product validation

All **39 local groups** pass: one suite containing 12 shutdown cases, 28 native
image suites and ten memory workloads. Image suites request SarasaTermSC Nerd
Font Light and require actual GDI, OpenGL and DirectX backends; fallback cannot
satisfy these checks. The retained OS font-mapper preflight is separate from the
terminal process.

| Fixture | Stages per actual renderer | Separate presented GDI stages |
| --- | ---: | ---: |
| Kitty image placement and lifecycle | 24 | 24 |
| Kitty font/window geometry | 12 | 12 |
| Compressed Kitty RGB/RGBA/PNG | 29 | 29 |
| Kitty feature-query state/reply replay | 176 | 176 |
| Kitty query errors during unfinished uploads | 216 | 216 |
| OSC 1337 static images | 32 | 32 |
| GIF animation | 36 | 36 |

All **1,575 API stages** and **525 direct GDI client-DC stages** pass. Replies are
compared byte-for-byte except one explicitly documented data-error control:
upstream and the strict local base64 decoder use different error codes, so that
control checks the same image ID/error envelope, unchanged seed pixels and the
cancelled upload. The unmodified upstream reply is retained alongside the actual
reply. Other queries and completion replies remain exact comparisons.

Every retained BMP is rehashed; geometry suites retain PNGs, whose red/blue pixel
counts and dimensions are independently rechecked. Their original capture-time
BMP hash is not represented as a separately retained BMP. All owned jobs exit
naturally, including shutdown cases.

## Ten uninjected memory workloads

Each workload uses an actual **160 x 48** Sarasa grid and two tabs. Sequential
sampling includes startup and resource settling, with no working-set trimming
and no injected observer or external crash debugger. GDI remains strictly below
20,000,000 private-working-set bytes; DirectX remains at or below 25,000,000.

| Workload record | Samples | Peak private WS (B) | Peak total WS (B) | Peak private commit (B) |
| --- | ---: | ---: | ---: | ---: |
| animated-workload-tabs-directx-left-observed.json | 527 | 23,855,104 | 59,453,440 | 91,856,896 |
| animated-workload-tabs-gdi-top-observed.json | 509 | 17,088,512 | 39,895,040 | 19,755,008 |
| compressed-kitty-workload-tabs-directx-left-observed.json | 610 | 23,654,400 | 59,105,280 | 92,438,528 |
| compressed-kitty-workload-tabs-gdi-top-observed.json | 642 | 16,515,072 | 39,108,608 | 18,870,272 |
| inline-workload-tabs-directx-left-observed.json | 574 | 24,113,152 | 59,686,912 | 93,917,184 |
| inline-workload-tabs-gdi-top-observed.json | 514 | 16,711,680 | 39,403,520 | 19,869,696 |
| kitty-workload-tabs-directx-left-observed.json | 659 | 23,539,712 | 59,158,528 | 86,433,792 |
| kitty-workload-tabs-gdi-top-observed.json | 569 | 17,321,984 | 40,050,688 | 19,587,072 |
| workload-tabs-directx-left-observed.json | 468 | 22,597,632 | 57,606,144 | 84,983,808 |
| workload-tabs-gdi-top-observed.json | 458 | 16,093,184 | 38,223,872 | 18,456,576 |

Frontend private-working-set peaks are **17,321,984 bytes for GDI** and
**24,113,152 for DirectX**. Total-working-set peaks are 40,050,688
and 59,686,912; DirectX still exceeds the approximate 50 MB total target.
Host/application/whole-tree samples and private commit remain separately recorded.
These finite workloads do not establish arbitrary-load or long-session bounds.

## Retention and remaining scope

`kitty-query-transaction-product-validation.json` indexes ordinary/single-image
CI evidence and **4,380 local records**, plus the promotion receipt in the
manifest and 313 committed fixture hashes. Every archived record has a checked
SHA256 hash. Component evidence is in `kitty-query-errors-validation.json`.

File/shared-memory graphics transport, Unicode placeholders, relative placements
and Kitty animation remain open. These deterministic native fixtures do not
establish physical keyboard/wheel input, live IME candidate selection, cross-monitor
DPI or sustained real-application behavior. The earlier audible-bell confirmation
retains its original image identity in [the bell record](font-zoom-and-bell.md).
Shutdown lifetime checks use isolated Frida 17.23.3; other instrumentation uses
17.24.3. The [captured observer wait and bounded workaround](query-transaction-shutdown.md)
retain the original failure and failed alternatives. The historical tab access
violation and undumped shutdown incidents remain separate; passing replays do not
prove their causes. The full
original goal remains active.
