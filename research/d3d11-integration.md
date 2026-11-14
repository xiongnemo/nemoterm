# Direct3D 11 integration checkpoint

This branch combines the I/O worker-lifetime fix `7a3b95e`, the initial
pseudo-window visibility guard `c2606cd`, the exact worker-wait fixture
(`13d12f2`, from `5fbc4fc`), and the D3D11 copy compositor from `0382062` /
`d5fd1b1`. The source-built Microsoft host remains pinned to
`37ef26dae839319f7bf703bb648038c343c357f1`. The guard is applied through the
checked source overlay; the submodule is unchanged.

The locally linked image is 4,509,696 bytes, SHA-256
`bfebc7c8636c91e474aeb2013fca67d8886745a1a4dbbc34957db771daac58a3`.
It contains no diagnostic window properties or product fault-injection hooks.
The [manifest](d3d11-integration-validation.json) retains source snapshots,
build/link inputs, successful checks and the two failed observer attempts.
These are local Win32/subprocess observations, not REA-server Evidence.
The accepted root `dist/nemoterm.exe` has not been replaced. Full CI is pending.

## Implementation

GDI still rasterizes text. D3D11 uploads bounded strips and presents the retained
swap-chain back buffer; it does not compile shaders or introduce a distributed
DLL. Scratch pixels are capped at 4 MiB, frame size at 128 MiB, and readback is
tiled at 512 by 64 pixels. Driver allocations are additional. All GPU resources
belong to the UI thread. The device is hardware-only, single-threaded, with
`PREVENT_INTERNAL_THREADING_OPTIMIZATIONS`; that flag trades driver scheduling
for a smaller observed footprint and does not establish a general speedup.
Unavailable hardware or failed device/present/resize operations fall back to GDI.

## Native verification

Both workload runs use SarasaTermSC Nerd Font Light and actual 160 by 48 grids,
two persistent tabs, 12 temporary-tab cycles, screen output, resizing, selection,
Sixel and previews. The worker-wait fixture retains the exact two new I/O thread
handles before closing each temporary tab, waits for both to signal, then applies
the original resource allowances. It does not poll resource counts until green.
All 13 warm-up/cycle waits completed; both runs passed all nine check groups.

| Mode | Private working set peak | Total working set peak | Private commit peak | Samples |
| --- | ---: | ---: | ---: | ---: |
| DirectX | 23,728,128 | 63,340,544 | 85,491,712 | 447 |
| GDI | 16,404,480 | 43,315,200 | 19,087,360 | 467 |

Memory sampling was uninjected, with no working-set trimming. DX meets the
25,000,000-byte private target on this machine; its total is above the approximate
50 MB target. GDI meets its 20,000,000-byte private target. Each inner job exited
naturally (56 processes), as did the outer controller job (58 processes).

The separate renderer test completed 16 scenes per GDI/OpenGL/DirectX mode,
including Sixel, retained synchronized frames, resizing, palette, cursor shapes,
cache eviction and overlines. Its original one-channel-step fallback-font
rounding allowance is unchanged. The DX automation check passed ten groups,
including discovery, explicit tab targeting, input/paste/key routing, stale IDs,
malformed clients, natural shutdown and screenshot comparison: **zero differing
channels**. The startup test passed eight groups across standalone/tabbed and
normal/minimized startup, including later explicit VT and Win32 visibility.

The updated owned-process fault observer follows D3D11/DXGI COM objects from the
exact executable path through the selected surface's parent HWND. SDK slot
indices and the x64 swap-chain description layout were checked against the
installed headers (OutputWindow offset 48, structure size 72). Device creation,
Present and ResizeBuffers failures each reached the intended call once, caused
GDI fallback, produced the expected GDI pixels, and recovered to DX on request.
Four additional renderer-switch cycles passed the original resource allowances.
The inner seven-process and outer nine-process jobs exited naturally.

The first two fault checks failed because Frida reported `cscapi.dll` as
`Process.mainModule`; no intended fault was injected. The final observer selects
the unique module by the owned EXE's full path. Both failures and the successful
third attempt are retained, rather than counted as renderer failures or erased.
Injected pixel/fault checks are not memory-acceptance measurements.

## Remaining limits

Other drivers, physical IME interaction, multiple monitors, latency and long
sessions remain unvalidated. The earlier intermittent GDI input-UI initialization
timing is not proved solved by this passing workload. A persistent pair of
handles remains unattributed; no driver-leak conclusion is made. Full CI and
downloaded-artifact validation remain required before promoting this image.
