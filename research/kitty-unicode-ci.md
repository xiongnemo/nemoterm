# Indexed Kitty relative/Unicode single-image CI

Source `056fe87062d494127e5b880245f4b0db962463a0` passes
[single-image run 43690641263](https://github.com/xiongnemo/nemoterm/actions/runs/43690641263):
all **154 check groups** finish. The product source and build scripts are
unchanged from `f01927a`, whose
[ordinary full CI](https://github.com/xiongnemo/nemoterm/actions/runs/43686454496)
passes all four jobs. This is the first complete single-image checkpoint with
the lazy Unicode-cell index and both new dense-memory workloads passing.

[Download the development EXE](https://github.com/xiongnemo/nemoterm/actions/runs/43690641263/artifacts/14153711098).
It contains only `nemoterm.exe`, **4,523,520 bytes**, SHA256
`f36c3c997d37c668ab18054f1578d27192b989eb37942570eca0c1426134ddb8`.
The artifact expires at `2026-12-15T08:14:48Z`. The hash is checked against the
download and final validation manifest. It is a development artifact: local
160x48 Sarasa acceptance remains pending while desktop tests are paused.
The accepted local `752f3be` executable is unchanged.

## Verified remote scope

All twelve uninjected two-tab memory workloads pass, covering Sixel, inline
PNG, GIF, ordinary Kitty, compressed Kitty and dense Unicode placeholders on
GDI and DirectX. Sampling includes startup and resource settling; there is no
working-set trimming, injected observer or external diagnostic during these
memory samples. All memory fixtures drain their owned process trees naturally.

| Dense Unicode workload | Actual grid | Samples | Private WS peak (B) | Total WS peak (B) | Private commit peak (B) |
| --- | --- | ---: | ---: | ---: | ---: |
| GDI | 109x34 Consolas | 1,074 | 14,442,496 | 46,743,552 | 17,227,776 |
| DirectX | 88x35 Consolas | 739 | 17,571,840 | 55,140,352 | 20,754,432 |

These dense workloads also have the highest frontend private/total peaks among
the twelve groups. GDI stays below 20,000,000 private-working-set bytes;
DirectX stays at or below 25,000,000. DirectX total working set still exceeds
the approximate 50 MB target. The smaller remote grids do not prove the same
bounds for local 160x48 Sarasa or arbitrary long sessions.

After memory sampling, both tabs in active and inactive states pass **25,048
cell-centre pixel checks**. Separate fixtures pass **153 Unicode placement and
geometry stages** and **96 exact clipboard copies**. All 96 retained Unicode
placement BMPs are rehashed against their original records. Geometry and
selection PNGs retain their original observations and archive hashes; they
are not represented as separately retained raw BMP captures. The requested
OpenGL fixtures use GDI fallback on this runner.

The mixed-profile fixture completes seven functional groups and naturally
drains seven processes after the unchanged 15-second close check. Its three
post-failure dump controls pass; no terminal dump is taken because this run
does not fail. Shutdown lifetime checks retain isolated Frida 17.23.3; other
instrumentation retains 17.24.3.

## Limits and retention

The successful run does not explain the earlier
[single-image timeout](unicode-single-profile-close.md), the separate
[MinGW access violation](unicode-profiles-close-failure.md), or every historical
shutdown incident. Their failed observations and finite exact-image replays
remain separate records. The dense source-rebuild CPU bottleneck has its own
[native evidence](unicode-dense-memory.md).

`unicode-indexed-single-validation.json` indexes **4,534 records** in
`kitty-unicode-evidence/indexed-single-success-056fe87.tar.gz`: the exact EXE,
complete downloaded native evidence, run identities, logs and archive controller.
Every retained record is rehashed after archiving. This checkpoint neither
promotes the local executable nor removes the outstanding physical-input,
IME/DPI, sustained real-application, graphics/protocol and memory requirements.
