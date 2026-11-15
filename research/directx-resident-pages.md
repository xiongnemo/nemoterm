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

The workload follow-up below checks whether these image mappings grow during
history output and resizing. Changing the private limit, trimming working sets,
or repeating the earlier rejected atlas/readback changes would not explain
these measurements. The approximate 50 MB total-workload target and broader
terminal requirements remain open.

[`directx-resident-pages-validation.json`](directx-resident-pages-validation.json)
indexes the exact executable, fixture source, raw page flags, allocation/module
records, cleanup and observer source. Its compressed bundle retains all 13
records with verified SHA256 hashes. No memory-reading or injection mechanism
is added to the terminal product.

## Same workload, five metadata checkpoints

A separate copy of the existing tab fixture runs the original Sixel/dense-text
workload: 4,096 output lines per tab with a 2,000-line history limit, 24 redraw
frames and 24 resize transitions. It uses the same accepted executable and
160x48 Sarasa grid. The only observation additions are five external metadata
snapshots; it exits explicitly with diagnostic code 2 after sampling and before
the later injected UI checks. No memory gate is evaluated. The changed fixture,
base source identity, observer code and full output are retained.
The existing workload pairing uses top tabs for GDI and left tabs for DirectX;
this is not a randomized comparison with identical window chrome.

Both runs report diagnostic completion, zero sampling errors and natural
cleanup of their 31-member jobs. All ten metadata snapshots have no unavailable
queries, only committed regions, and no Frida agent in the frontend catalogue.
The GDI sampler records 507 samples and DirectX 460. Their sampled total-WS
peaks are 37,392,384 and 57,692,160 bytes respectively; these are diagnostic
observations, not replacements for ordinary uninjected acceptance runs.

| Checkpoint | Private WS (B) | Shareable WS (B) | Total WS (B) |
| --- | ---: | ---: | ---: |
| GDI, first history complete | 11,296,768 | 22,024,192 | 33,320,960 |
| GDI, settled after frame 23 | 14,688,256 | 22,028,288 | 36,716,544 |
| DirectX, first history complete | 18,288,640 | 34,787,328 | 53,075,968 |
| DirectX, settled after frame 23 | 22,118,400 | 34,803,712 | 56,922,112 |

The two named driver image mappings above are already resident at the first
history checkpoint: together 10,096,640 bytes, rising by only one 4 KiB page
through the final checkpoint. DirectX's later growth is predominantly private
pages: 3,829,760 bytes versus 16,384 shareable bytes. GDI likewise grows mainly
private pages in this workload. The page metadata does not identify allocation
owners inside anonymous heaps, so it cannot assign that growth to a driver,
terminal cache or allocator retention.

The useful next boundary is a concrete resource/allocation experiment on the
current copy compositor, with separate uninstrumented workload validation.
There is no renderer change or demonstrated memory saving in this checkpoint.
The validation index adds a second bundle with all 16 workload records; the
earlier idle observations remain intact.
