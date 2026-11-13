# Graphics initialization observations

Follow-up: the [complete Direct3D 9Ex compositor](direct3d9-compositor.md)
passes the local pixel suite but fails the unchanged full-workload budget at
31,731,712 private-working-set bytes. Disabling its run cache reaches 33,579,008
bytes. Neither candidate is retained in the product.

A [first-device flag observation](graphics-device-flags.md) also confirms that
the existing Direct2D path already requests a single-threaded D3D11 device on
this machine; setting that flag is not an untried memory optimization.

This checkpoint changes no product renderer. The exact downloaded `9370c1f`
image remains over the local DirectX budget: **30,433,280 private-working-set
bytes** in the full Sarasa 160x48 two-tab workload. See [overline acceptance](overline.md).
The probes below investigate a gap in the earlier [post-workload observer](local-directx-heap.md):
that observer attached after the graphics device had already been created.

## First renderer application

Two fresh, owned instances of the same CI image start in GDI, warm the same
Sarasa scene at actual 160x48 cells, then install the existing all-heap metadata
observer. Each opens its own settings dialog through the existing PID/HWND-bound
UI Automation driver. The control applies GDI again; the other applies DirectX
for the first time. Both redraw the same scene before freezing the observer.
There are no global keystrokes, allocation payload reads or working-set trims.

| Frozen outermost heap requests | GDI control | First DirectX application |
| --- | ---: | ---: |
| Live records | 2,373 | 8,346 |
| Requested live bytes | 137,084 | 4,095,451 |
| Requested bytes on sampled private resident pages | 137,084 | 3,669,467 |
| Requests whose immediate caller is `nvwgf2umx.dll` | 0 | 2,865,010 |
| Requests whose immediate caller is `d3d11.dll` | 0 | 337,929 |
| Requests whose immediate caller is `msvcrt.dll` | 1,000 | 311,064 |

Both captures have zero bookkeeping errors or overlapping live records. The
observers detach and both seven-member owned jobs drain naturally. The fixture
intentionally exits **2** after successful diagnostic collection; the outer
acceptance-oriented controller reports non-success. These are not passing
memory acceptance tests.

The newly observed driver requests establish activity missed by the later
attachment point. They do not establish ownership of all associated pages or
explain the full DirectX excess. Immediate caller is not resource owner, requested
bytes are not private working set, and the captures include observer activity.
Pre-attachment blocks, non-heap paths, allocator overhead and retained freed
storage remain outside the live-request accounting. The single-window scene
also differs from the full two-tab history/resize workload. Do not add its
numbers to the earlier census or subtract its instrumented working set from an
uninstrumented acceptance result.

The machine reports Windows 10 build 19044 and an NVIDIA GeForce RTX 3060 Laptop
GPU, driver 32.0.15.8132. A MuMu virtual display adapter is also enumerated. The
observed NVIDIA caller module identifies the graphics activity in this capture;
the probe does not establish which adapter every future configuration will use.

## Standalone Direct3D 9Ex feasibility probe

A separate small MSVC `/MT /O2` executable creates the same 1600x960 client area
in three fresh processes. It compares a plain window, an explicitly hardware
Direct2D target plus a retained GDI-compatible frame, and a Direct3D 9Ex HAL
device plus a retained GPU texture. The GPU arms fill and present 32 frames.
The 9Ex path requests hardware vertex processing and records NVIDIA vendor ID
4318; neither path silently substitutes a software renderer.

| Standalone process | Private WS peak | Total WS peak | Private commit peak |
| --- | ---: | ---: | ---: |
| Plain window | 831,488 | 6,758,400 | 1,253,376 |
| Direct2D | 9,367,552 | 35,135,488 | 62,124,032 |
| Direct3D 9Ex | 8,355,840 | 28,299,264 | 49,340,416 |

These samples are uninstrumented and all processes exit after releasing their
COM resources. This one observation shows **1,011,712 fewer private resident
bytes** in the minimal 9Ex arm. It does not establish a terminal-level saving or
a 25 MB solution. The arms do not implement equivalent full renderer features:
9Ex has no GDI readback surface, and neither arm exercises terminal text caching,
uploads, Sixel, selection, previews, resizing, synchronized output or device
recovery. The probe therefore cannot justify replacing the current renderer.
A complete candidate would still need that functionality and the unchanged
full workload/pixel gates. The displayed figures must not be summed with the
terminal's GDI measurement to predict a future frontend working set.

Only Windows SDK headers and system DLLs are used in the probe. API references:
[Direct3DCreate9Ex](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-direct3dcreate9ex),
[device creation flags](https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3dcreate),
and [Direct2D HWND targets](https://learn.microsoft.com/en-us/windows/win32/api/d2d1/nn-d2d1-id2d1hwndrendertarget).

The [manifest](graphics-initialization-validation.json) retains exact image and
source identities, both complete heap/page snapshots, natural cleanup records,
prototype source/build command output, every standalone memory sample and the
observed OS/driver versions. Its compressed and decoded hashes are verified.
The product EXE, renderer selection and accepted distribution are unchanged.
