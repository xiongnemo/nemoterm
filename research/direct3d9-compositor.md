# Direct3D 9Ex compositor experiment

Neither candidate meets the local **25,000,000-byte private working set** limit.
The normal cached implementation peaks at **31,731,712 bytes**; bypassing its
per-run cache peaks at **33,579,008 bytes**. Both experimental implementations
are rejected. The production Direct2D dispatch and accepted `dist/nemoterm.exe`
are unchanged. These results supersede any inference that the earlier
[minimal 9Ex probe](graphics-initialization.md) demonstrated a terminal-level
memory saving.

## Implementation and exact images

The experiment starts from `9cf51ace2aa17f7b2358967e0a5c7615b5e4e642` and uses the
same single-image MSVC frontend/OpenConsole build. It adds a complete C renderer
through the existing `NemoGPU` interface. A dynamically loaded system `d3d9.dll`
creates a HAL-only 9Ex device with hardware vertex processing. No extra runtime
DLL, shader compiler, managed resource pool or software graphics fallback is
introduced. A failed graphics operation uses the existing frontend GDI fallback.

The retained frame is a non-lockable GPU render target. A separate child-window
swap chain can resize without resetting the device; the default swap chain is
a never-presented 1x1 surface. Text is rasterized by the existing GDI code into
a bounded scratch DIB and uploaded through a reusable system-memory surface.
Sixel uses the same upload path. Fixed 512x128 GPU/system-memory tiles support
cursor overlays, screenshots and preview readback without a second full CPU
frame. The cached arm retains at most 256 text-run surfaces and 4 MiB of their
pixel storage, reusing exact-size allocations where possible. This byte bound
does not include driver allocation overhead.

The uncached control changes only `end_run` to upload directly into the retained
frame; no text-run cache entries or surfaces are populated. All other renderer
code, tests, font, window dimensions and workload are identical. Its source is
retained as a diagnostic variant, not a selectable product mode.

| Local incremental image | Bytes | SHA-256 |
| --- | ---: | --- |
| Cached | 4,468,224 | `31fa18f7af2def6e16700f265b13e1a8cde9023d2670714e32d98760a15c845e` |
| Uncached | 4,467,712 | `cce48665c0f84e72fc0a03434aff45382d11cb52d4487d76253050cf4048b1a9` |

These are experimental local builds, not published CI artifacts. The settings
label and old Direct2D-specific fault-injection fixture were not converted;
memory rejection occurred before that acceptance work. The native tab fixture
changes only its expected graphics-child class to `NemotermDirect3D9`.

## Runtime results

Both arms use **SarasaTermSC Nerd Font Light**, actual **160x48** grids, two tabs,
4,096 generated history lines per tab with a 2,000-line history limit, dense
clusters, links, images, 24 redraw/resize transitions and the existing tab
lifetime cases. Sampling is uninstrumented and finishes before the separate
pixel capture probe attaches. No working-set trims or relaxed memory assertions
are used.

| Observed frontend result | Cached | Uncached |
| --- | ---: | ---: |
| Private working set peak | 31,731,712 | 33,579,008 |
| Total working set peak | 69,582,848 | 72,286,208 |
| Private commit peak | 100,536,320 | 85,209,088 |
| 100 ms samples | 263 | 470 |
| Sampling duration, seconds | 26.415 | 47.249 |
| Entire controller duration, seconds | 29.851 | 50.775 |
| Completed tab behavior checks | 9 | 9 |
| Memory assertion | Fail | Fail |

The cached arm's separate renderer suite passes the existing GDI/OpenGL/DirectX
pixel comparisons, including text, Sixel, overline, cursor overlays, cache
eviction, expose, resize and synchronized output. The requested GPU modes are
required; fallback does not count as a pass. This suite's memory observations
are instrumented and are not used for the memory decision above. The uncached
arm was not put through this additional suite after failing the full workload.

Both workload fixtures complete all nine behavior checks: independent tabs,
12 create/close cycles, input-thread shortcuts, failed-child handling, bounded
background previews, synchronized frame transfer, fullscreen restoration,
grid resizing and sibling/process lifetime. Each then exits with code 1 at its
unchanged memory assertion. Both outer 58-member owned jobs finish naturally,
with zero remaining processes or forced termination. The separate cached pixel
fixture's 11-member job also finishes naturally.

The cache removal control lowers private commit but does not lower private
resident memory in this run. Its controller also takes longer. These single
observations do not establish statistical performance differences or allocate
the excess to a particular driver resource. In particular, driver bookkeeping,
allocator retention and in-flight work are not measured by the cache byte
counter. The prior production Direct2D result of 29,569,024 private bytes comes
from a different CI image/run; it is context, not a matched causal comparison.

The local machine still reports Windows 10 IoT Enterprise LTSC build 19044,
NVIDIA GeForce RTX 3060 Laptop GPU driver 32.0.15.8132, and an enumerated MuMu
virtual display adapter. No other driver, adapter, compiler or operating system
has been validated for this candidate. Device-loss recovery, settings switching
and full CI remain untested. Pixel parity and nine tab checks alone would not
justify promoting a renderer even if its memory result had passed.

## Retained evidence

The [manifest](direct3d9-compositor-validation.json) records both executable
identities, all samples, failures, cleanup, native screenshots, build logs,
full new source files and the tracked dispatch/build/test patch. It verifies
both compressed and decoded SHA-256 values for all 82 evidence files. To
reconstruct the cached candidate, start at the base commit, restore the retained
`nemo_d3d9.c` and `.h` under `vendor/putty-0.85/windows`, and apply
`tracked-integration.patch`. The uncached arm replaces only `nemo_d3d9.c`.
The unchanged build procedures are in `scripts/build-single-exe.ps1`; the retained
logs identify the incremental frontend and host rebuilds used here.

The full workload command is:

```powershell
python build/run-owned-check.py build/d3d9-check-1 tabs --renderer directx --side left --workload-memory --font 'SarasaTermSC Nerd Font Light' --cols 160 --rows 48
```

The retained controller points `NEMOTERM_TEST_EXE` at the isolated image, requires
real GPU modes and bounds execution to 180 seconds. Its copied test directory
comes from the base commit plus the retained class-name change. The cached
pixel run uses the same controller with `renderer` instead of `tabs` and its
arguments. Neither experiment replaces the accepted root binary.

Implementation contracts: Microsoft
[UpdateSurface](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-updatesurface),
[StretchRect](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-stretchrect),
and [GetRenderTargetData](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-getrendertargetdata).
