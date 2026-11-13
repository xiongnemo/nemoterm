# DirectX allocation attribution checkpoint

The 20,000,000-byte DirectX private-working-set requirement remains unmet.
This checkpoint adds runtime evidence and records a rejected cache experiment;
it retains no renderer change. The accepted main executable is untouched.
The baseline [workload result](tab-workload-memory.md) remains GDI 14,778,368
bytes and actual DirectX 29,532,160 bytes. Optional OpenGL already has an
explicit memory exception. A question about extending that exception to
DirectX is pending; the DirectX gate has not been weakened.

## Controlled observations

REA attached only to newly spawned, fixture-owned frontend processes. All
three successful probes used the exact baseline image
`d6a46003b58a48bc5927437af6214c5492d78273e98911da6c21dda49b5546c3`, with the
same 160x48, SarasaTermSC Nerd Font Light, two-tab workload. Each finished all
nine functional groups and drained its owned job without forced termination.
Each REA session detached without a cleanup error, script error or truncated
message collection. Scripts and complete inline Evidence are retained in
[directx-allocations](directx-allocations/), with hashes and cleanup records in
[the validation manifest](directx-allocation-validation.json).

The fixture pauses immediately before its history/resize workload, records
the owned PID, image path and resident-private-region metadata, and waits for
the observer. The observer releases this gate, detaches its hooks after the
workload, and releases a second gate before normal functional tests proceed.
There is no global input, clipboard access or working-set trimming.
**All instrumented memory readings are excluded from acceptance.**
The ad hoc gates set `allocation_probe_instrumented=true`; the original
fixture's `memory_instrumented=false` field was not updated by those gates
and must not be interpreted as an uninstrumented measurement. The manifest
labels all three probes as instrumented and unsuitable for memory acceptance.
The retained scripts contain the exact local evidence paths from these runs;
they are audit artifacts, not a general-purpose launch harness.

| Probe | Coverage | Result |
| --- | --- | --- |
| `virtual-large` | Successful current-process `NtAllocateVirtualMemory` requests of at least 64 KiB, plus frees | 57 allocations and 61 frees |
| `virtual-all` | Same observation without the request-size filter | 156 allocations and 61 frees |
| `heap-regions` | Native callbacks for `RtlAllocateHeap` and `RtlReAllocateHeap`, grouped by immediate caller and pre-injection allocation range | Counters completed with zero table overflow |

The virtual-allocation stacks include UCRT calls returning to Nemoterm,
MSVCRT calls from Direct2D, GDI, D3D11 and the loaded NVIDIA user-mode driver.
They do not account for all resident growth. They cover the selected entry
points, not every possible Windows allocation path, and request bytes are
neither live bytes nor private working set.

In the native heap probe, one pre-existing 8 MiB range grew from 2,658,304 to
7,815,168 resident private bytes. A full `VirtualQuery` walk before the
workload found 3,031,040 committed bytes in that reservation. Allocations
returning into this range came from **several** callers, including UCRT,
GDI, D3D11 and `nvwgf2umx.dll`. For example, it saw 133,238 driver allocation
calls and 42,994 calls from one D3D11 return address. This establishes mixed
heap activity; it does not assign the 5,156,864-byte resident increase to any
one component.

The heap counters deliberately do not follow frees. Reallocation can also
call allocation internally, so nested calls can both be counted. Cumulative
requested bytes must not be summed as retained memory or used to claim a leak.
The observed ranges exclude reservations with less than 512 KiB private WS at
the gate and any later reservation. There is no allocation-lifetime census.

The earlier region snapshots' `committed_regions_with_private_pages` field
only counts regions containing a resident private page. It is not the complete
committed extent of an allocation. The native heap probe separately walks
each selected allocation's entire extent and records `committed`.

REA's records declare external-service authority and do not themselves bind
the artifact digest. The fixture image hash and explicitly checked owned
PID/path provide that binding. One first heap-probe attempt failed before
installing hooks because its JavaScript size comparison rejected all ranges;
the fixture timed out and cleaned up. It is excluded from results and the
corrected probe converts the native `size_t` return explicitly.

## Rejected fixed-atlas experiment

The existing cache creates a GPU bitmap on each uncached text run and releases
the old bitmap on eviction. Given the observed graphics allocation activity,
an experiment replaced these per-run resources with one bounded 2048x128
bitmap, keeping cached source rectangles and a shelf allocator. It used
[`CopyFromMemory`](https://learn.microsoft.com/en-us/windows/win32/api/d2d1/nf-d2d1-id2d1bitmap-copyfrommemory),
whose contract permits flushing outstanding draws before an active bitmap is
updated. This was a hypothesis about resource churn, not an established cause
of the working-set excess.

Image `9fff8ad2d029dfa04e39589cd50048f76fa3c4c13bac1ef7cc9fcb274e9fe971`
passed GDI/OpenGL/DirectX pixel parity, Sixel, repaint, resize and synchronized
presentation. Its actual DirectX tab test passed all nine functional groups
and exited naturally, then failed the memory assertion:

| Metric | Fixed-atlas experiment |
| --- | ---: |
| Uninstrumented frontend private WS peak | 28,962,816 bytes |
| Frontend total WS peak | 65,388,544 bytes |
| Frontend private commit peak | 97,873,920 bytes |
| Sampling | 357 samples over 38.609 seconds |

The result does not demonstrate a useful improvement over baseline, and the
experiment was reverted. Its patch and exact raw test records are retained
for audit, not as a proposed implementation. The restored build's `.text`
section is byte-identical to the baseline probe image; this comparison is not
a full-image identity or a new native acceptance run.

## Remaining work

Allocation lifetime tracking or a different compositor architecture would be
needed to separate live application data, graphics allocations and heap
retention. No driver leak, GDI-cache cause or guaranteed 20 MB DirectX solution
has been established. Do not repeat the rejected limit/readback/atlas changes
and describe single-run differences as a fix. The product's DirectX memory
gate and the broader open acceptance items remain in force.
