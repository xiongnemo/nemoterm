# DirectX resident-page metadata (2026-11-15)

This is a diagnostic of the accepted `6e05bd1` executable, SHA256
`dfae1cdea10e091d209aa56ce291b63e3ae5ada2f02035254c3c3398cda6c5ab`.
It does not change the renderer, replace the accepted image, or establish a
new workload/peak memory result. The current query-error candidate `752f3be`
has identical `nemo_d3d11.c` and `nemo_gpu.c` source.

Two new, independently owned frontends run a controlled child at an actual
160x48 grid with the requested SarasaTermSC Nerd Font Light. GDI and DirectX
are observed as actual backends 1 and 3. Each has one view, without automation,
Frida, a debugger or working-set trimming. Windows reports build 19044. This
is an idle comparison, separate from the ten two-tab acceptance workloads.

The observer queries the resident page list, then reads virtual-region and
module **metadata**, never page contents. One snapshot is taken after the child
is ready and one two seconds later. Both snapshots produce the same totals
within each run; no metadata query is unavailable. Both three-process jobs
exit naturally. The page list and subsequent region/module queries are
sequential, not an atomic picture of a running process.

| Idle frontend | Private WS (B) | Shareable WS (B) | Total WS (B) |
| --- | ---: | ---: | ---: |
| GDI | 4,358,144 | 19,341,312 | 23,699,456 |
| DirectX | 11,653,120 | 31,285,248 | 42,938,368 |

The Windows working-set flag calls a page *sharable*; it does not assign that
page's physical cost exclusively to this process. The observer retains that
flag and the bounded share-count field. These categories follow the existing
private-working-set measurement, and sum exactly to the queried page count.
See Microsoft's [working-set block definition](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-psapi_working_set_block)
and [QueryWorkingSet contract](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-queryworkingset).

Two image mappings present in the DirectX process account for 10,076,160
resident bytes in this snapshot:

| Image mapping | Private WS (B) | Shareable WS (B) | Total WS (B) |
| --- | ---: | ---: | ---: |
| `nvwgf2umx.dll` | 507,904 | 6,103,040 | 6,610,944 |
| `nvgpucomp64.dll` | 802,816 | 2,662,400 | 3,465,216 |

They are not present in the GDI module catalogue. Additional resident mappings
include D3D11, DXGI and driver support libraries. This establishes where those
image pages are mapped; it does not attribute anonymous heap allocations to
the driver or identify a leak. The overall idle difference is 19,238,912 bytes,
including 7,294,976 private bytes. It is not a causal decomposition of the
accepted workload's 59,822,080-byte DirectX peak.

Source inspection rules out removing a shader compiler called by our compositor:
the current backend only copies textures and makes no `D3DCompile` call.
`D3DCOMPILER_47.dll` is nevertheless already present in **both** processes:
409,600 resident bytes for GDI and 364,544 for DirectX. Its presence alone is
not evidence that our backend compiles shaders, nor that it can be unloaded
without regard to other system components.

The next useful memory experiment needs a workload-aligned resident-page
snapshot or a concrete allocation/resource change. Changing the private limit,
trimming working sets, or repeating the earlier rejected atlas/readback changes
would not explain these measurements. The approximate 50 MB total-workload
target and broader terminal requirements remain open.

[`directx-resident-pages-validation.json`](directx-resident-pages-validation.json)
indexes the exact executable, fixture source, raw page flags, allocation/module
records, cleanup and observer source. Its compressed bundle retains all 13
records with verified SHA256 hashes. No memory-reading or injection mechanism
is added to the terminal product.
