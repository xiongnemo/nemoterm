# Direct2D's underlying device flags

The existing Direct2D renderer already requests a single-threaded D3D11 device
on this machine. A first-creation observation records **Flags = 41 (`0x29`)**:
`D3D11_CREATE_DEVICE_SINGLETHREADED` (`0x1`),
`D3D11_CREATE_DEVICE_PREVENT_INTERNAL_THREADING_OPTIMIZATIONS` (`0x8`), and
`D3D11_CREATE_DEVICE_BGRA_SUPPORT` (`0x20`). Merely adding the single-threaded
flag therefore is not a new optimization for the observed path. This finding
does not establish which allocations account for the remaining DX memory excess.

The exact target is the downloaded `9370c1f` single-image CI executable,
SHA-256 `21e217254bec0cd10158b7da791c42da238095fe277e71033af1253f5e0eb356`.
That image was also used for the [first graphics initialization census](graphics-initialization.md).
A new owned process starts in GDI with SarasaTermSC Nerd Font Light at actual
160x48 cells and draws a small fixed scene. A bounded Frida hook is installed
before its own PID/HWND-bound settings driver switches it to DirectX. The hook
observes `D3D11CreateDevice` integer arguments and return values without changing
arguments, return values or rendering resources. A final DSR and redraw complete
before the hook is removed and the test process closes.

Exactly one observed call comes from `d2d1.dll+0x27475c`. It supplies an adapter
pointer with driver type 0 (`D3D_DRIVER_TYPE_UNKNOWN`), requests seven feature
levels from 11.1 down to 9.1, succeeds with HRESULT 0, and selects feature level
`0xb100` (11.1). The terminal's actual-renderer property is 3 (DirectX), rather
than a fallback. There are no hook errors or truncated events. All seven owned
job members exit naturally, with zero active or force-terminated processes.

Microsoft's [creation flag definitions](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_create_device_flag)
describe these bits; BGRA support is required for Direct2D interoperability.
The [creation API](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-d3d11createdevice)
documents the argument and result interpretation. The internal-threading bit
has a documented WARP-specific effect and is not recommended for general use;
this observation is not a recommendation to alter that bit. No device flags
were changed.

This is one instrumented first-initialization observation of one existing CI
image, not a workload benchmark, memory acceptance result, or universal claim
about every adapter/driver. It does not prove a custom newer DirectX renderer
would have identical memory costs. It does rule out treating a missing
single-threaded flag as an established explanation of this capture's excess.

The [manifest](graphics-device-flags-validation.json) retains the exact binary
identity, observer and fixture source, complete trace, diagnostic log and both
cleanup records. The diagnostic deliberately exits 2 after collecting a valid
trace; its acceptance-oriented outer controller therefore reports non-success.
No production code or accepted distribution is changed.
