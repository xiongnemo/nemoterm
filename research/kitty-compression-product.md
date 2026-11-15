# Earlier accepted compressed-image single executable

This is a historical checkpoint, superseded by the accepted [feature-query
product](kitty-feature-product.md). Its measurements and failures remain unchanged.

The then-accepted local `dist/nemoterm.exe` comes from
`b3e03bb3a3a1f75e3403b7dd5a9e0d14065c46ac`: **4,515,328 bytes**, SHA256
`65145ffb30d8a75199161f526b690794b66f6d593deab6f88cfd078ce5a795a0`.
The runtime directory contains only this file; the console host uses the same
image. The prior accepted `97d6025` executable is retained locally as
`build/accepted-before-compression-97d6025.exe`.

[Single-image CI 43646925393](https://github.com/xiongnemo/nemoterm/actions/runs/43646925393)
passed **137 check groups**. [Product artifact 14135728448](https://github.com/xiongnemo/nemoterm/actions/runs/43646925393/artifacts/14135728448)
expires at `2026-12-14T22:51:47Z`. The
[ordinary CI run 43644074575](https://github.com/xiongnemo/nemoterm/actions/runs/43644074575)
passed all four jobs at `48a0263`; product source is identical between that
revision and `b3e03bb`. The intervening change concerns the shutdown observer
and its controls. Strict GCC, Clang and MSVC component validation also passed.
The [implementation record](kitty-compression.md) links the independent decoder
reference and preserves the earlier compiler/decoder failures.

## Exact-image native validation

The downloaded formal image passed 31 local groups: shutdown, 20 native image
suites and ten memory workloads. The image suites use the requested
`SarasaTermSC Nerd Font Light`. A separate Windows font-mapper preflight resolves
that exact face and finds its native CJK glyph; it is explicitly not an observer
inside Nemoterm.

| Fixture | Stages on each actual renderer | Separate presented GDI stages |
| --- | ---: | ---: |
| Kitty RGB/RGBA/PNG, placement and lifecycle | 24 | 24 |
| Kitty font/window geometry | 12 | 12 |
| Kitty compressed RGB/RGBA/PNG | 29 | 29 |
| OSC 1337 static images | 32 | 32 |
| GIF animation | 36 | 36 |

All three actual GDI/OpenGL/DirectX backends pass: **399 API pixel stages**.
An additional **133 stages** read the owned visible GDI client DC without using
the image API or `WM_PRINTCLIENT`. GPU runs require the requested backend and
cannot pass by falling back to GDI. The 12 shutdown cases pair instrumented and
uninjected child-exit/window-close paths. Every owned process group exits
naturally, with no forced termination recorded.

These are deterministic application inputs and native windows. They do not
establish physical keyboard/wheel operation, live IME candidate selection or
cross-monitor DPI behavior. Default audible-bell listening remains attributed
to the previously observed image in [the bell record](font-zoom-and-bell.md).

## Ten full-grid memory workloads

Each workload uses an actual **160 x 48** Sarasa grid and two tabs. Sampling is
uninjected throughout, including startup, temporary-tab closure and resource
settling; no working-set trimming is used. Memory runs execute sequentially,
and the additional PNG/GIF pixel runs start only after all memory sampling ends.
The unchanged GDI rule is strictly below 20,000,000 private working-set bytes;
DirectX is at most 25,000,000 bytes. All ten pass.

| Workload | Renderer | Samples | Peak private WS (B) | Peak total WS (B) | Peak private commit (B) |
| --- | --- | ---: | ---: | ---: | ---: |
| Sixel | GDI | 461 | 15,499,264 | 37,638,144 | 17,780,736 |
| Sixel | DirectX | 470 | 23,330,816 | 58,384,384 | 91,529,216 |
| PNG | GDI | 512 | 16,564,224 | 39,211,008 | 19,210,240 |
| PNG | DirectX | 565 | 23,904,256 | 59,473,920 | 87,035,904 |
| GIF | GDI | 507 | 16,822,272 | 39,485,440 | 19,161,088 |
| GIF | DirectX | 526 | 24,248,320 | 59,813,888 | 93,073,408 |
| Kitty | GDI | 572 | 16,752,640 | 39,387,136 | 19,189,760 |
| Kitty | DirectX | 656 | 23,871,488 | 59,379,712 | 92,696,576 |
| Compressed Kitty | GDI | 573 | 16,465,920 | 39,096,320 | 19,095,552 |
| Compressed Kitty | DirectX | 652 | 23,842,816 | 59,285,504 | 92,442,624 |

These are sampled frontend peaks; host, child and whole-tree observations are
retained separately. Private commit is not private working set. DirectX's total
working set still exceeds the approximate 50 MB target. Finite workloads do not
prove arbitrary configurations, tab counts, hardware or long-session bounds.

## Retained evidence and remaining scope

`kitty-compression-product-validation.json` indexes 1,200 original local records
in a deterministic tar/gzip bundle, hashes the committed fixture snapshot, and
retains a separate byte-hashed promotion receipt. All 1,201 records were checked
after encoding. Full ordinary/single-image CI records remain in
`kitty-compression-full-ci-validation.json` and
`kitty-compression-single-ci-validation.json`.

The earlier source-host precheck, failed formal shutdown observation and
successful exact-image diagnosis retain their distinct executable identities.
The successful observer change does not establish the original timeout's cause.
The reference for feature queries is now complete, but their product dispatch
still returns `ENOTSUP`. File/shared-memory transport, Unicode placeholders,
relative placements, Kitty animation, the remaining protocol ledger and real
input/application scope remain work toward the original goal.
