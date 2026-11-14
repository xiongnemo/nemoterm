# Integrated Direct3D 11 CI artifact and local acceptance

Source `9c22311e8e0ae56facfc7cfcac15bb8242bc8324` passes both complete workflows:
[Test and build](https://github.com/xiongnemo/nemoterm/actions/runs/43550497901)
and [Single executable from source](https://github.com/xiongnemo/nemoterm/actions/runs/43550497894).
The latter records **102 passed checks**, with only `nemoterm.exe` in its isolated
distribution directory. The core workflow's four jobs also succeed, including
ASan/UBSan and MSVC native renderer checks.

The [downloaded single-file artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43550497894/artifacts/14096259785)
is **4,451,328 bytes**, SHA-256
`ebd2d24edcf9ba10f0435597e15ad8aff44320fad1a707b6e4cbc10654345a63`.
Its recorded expiry is `2026-12-14T03:39:31Z`. This exact downloaded image,
rather than the separately linked local candidate, is used for the acceptance
results below and the updated local `dist/nemoterm.exe`.

The product combines bounded Direct3D 11 composition, I/O context retirement,
minimized ConPTY startup preservation and normal input-pipe closure handling.
See [integration](d3d11-integration.md), [I/O lifetime](io-lifetime.md),
[startup](startup-visibility.md) and [input closure](conpty-input-close.md)
for the respective changes and earlier failed observations.

## Downloaded-image checks on this machine

All tests use fresh owned jobs and the unchanged candidate fixtures. Each
controller has a 180-second bound, and records the executable hash and cleanup.
No existing user terminal is attached. The full tab workloads use SarasaTermSC
Nerd Font Light and verify an actual 160x48 grid.

| Check | Result | Owned outer processes, all natural exits |
| --- | --- | ---: |
| Standalone/tabbed, normal/minimized startup and explicit visibility | 16 groups pass | 26 |
| Discovery, targeted input, paste/key, text/image and teardown | 10 groups pass; actual DX; zero screenshot channel differences | 10 |
| GDI full tab workload | 9 groups pass; 474 memory samples | 58 |
| DX full tab workload | 9 groups pass; 454 memory samples | 58 |

| Frontend peak, decimal bytes | GDI | DirectX |
| --- | ---: | ---: |
| Private working set | 16,408,576 | 23,568,384 |
| Total working set | 43,368,448 | 63,107,072 |
| Private commit | 18,972,672 | 87,322,624 |

Memory is sampled before the pixel helper is injected. Private working-set
limits remain 20,000,000 bytes for GDI and 25,000,000 for DX. Each workload
retains and waits for the exact two temporary-tab I/O worker identities before
checking the unchanged handle/GDI/USER allowances. Both workloads close 56
inner processes naturally; the two outer controller processes account for the
58 total. There is no working-set trimming.

CI independently records real hardware DirectX and all three device/present/
resize fault-injection recovery cases. Those instrumented recovery measurements
are not memory acceptance. Its automation screenshot comparison also has zero
changed channels; renderer parity covers GDI, OpenGL and DirectX.

## Boundaries retained

DX total working set remains above the approximate 50 MB target. A separate
[delay-load experiment](delay-load.md) did not produce a useful measured saving
and is not included. That experiment also retains an unmodified local baseline's
late handle growth and an experimental USER-object failure. Their causes remain
open; these successful downloaded-image tests do not erase them or prove
universal resource stability.

Physical IME, different monitors/GPUs, long sessions, broader terminal protocol
coverage and the newly identified Sixel palette semantics remain separate work.
This checkpoint does not claim completion of those requirements.

The [manifest](d3d11-ci-validation.json) verifies decompressed hashes for the
workflow identities, complete logs, relevant CI reports, exact local test
controller, native reports, memory samples, screenshots and cleanup records.
