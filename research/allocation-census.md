# Allocation lifetime census

The earlier [DirectX attribution probes](directx-allocation-attribution.md)
counted allocation and reallocation requests but did not follow releases.
Those cumulative requests cannot establish which blocks remain live, which
component retains them, or how many of their pages are privately resident.

The diagnostic collector in `tests/allocation_census.h` now keeps a fixed-size
table of observed address, heap, immediate caller, requested size and generation.
Its adapter observes `RtlAllocateHeap`, `RtlReAllocateHeap`, `RtlFreeHeap` and
`RtlDestroyHeap`. Hot callbacks run in C, with an external SRW lock serializing
the table; they do not allocate memory or read allocation payloads.

## Lifetime rules

* A failed allocation/reallocation preserves existing records. Successful
  in-place resizing replaces the recorded requested size.
* Reallocation may produce a nested allocation callback for the same result.
  The final record replaces that address instead of counting both observations.
* Free captures a generation on entry and removes only that generation after
  successful return. An address reused before the leave callback is preserved.
* Heap destruction captures a generation cutoff. Later allocations in a reused
  heap handle are not removed by the old heap's delayed callback.
* Table exhaustion and counter overflow set explicit errors. Such a snapshot
  has `valid=false`; losing records never silently produces an accepted census.
* Freeze disables updates under the same lock before detaching hooks. Tables,
  invocation callbacks and CModule storage remain referenced until script unload.
* The native adapter records only outermost intercepted heap API calls. Nested
  allocator requests are counted separately, so backing allocations do not also
  appear as live application blocks. Frozen overlapping records invalidate the
  snapshot. This observer must be the only interceptor in the owned process.

The [Frida CModule API](https://frida.re/docs/javascript-api/#cmodule) requires
writable globals to be supplied externally. This adapter retains those buffers
and checks its record size against the layout used by the JSON exporter.

## Validation checkpoint

Commit `033157e` passed all four jobs in the dedicated
[collector workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43438776689).
The [manifest](allocation-census-validation.json) binds the retained raw results.

The C11 tests ran with ASan and UBSan. They cover failed operations, in-place
and moved reallocations, nested callbacks, delayed free/address reuse, heap
handle reuse, collision chains, tombstone reuse, exhaustion, counter bounds and
freeze. Five Python cases additionally check half-open page boundaries,
nonresident gaps, mixed callers, unknown callers, zero-size requests and invalid
overlapping metadata. These do not certify all concurrent allocator orderings.

Windows validation injected the adapter only into an owned disposable Python
process and operated on newly created private heaps. Two cases checked
empty state, two allocations, realloc, free and 100 allocate/free cycles. One
then destroyed the heap and confirmed zero live records. The other froze a
single live 128-byte block and checked its exact address, heap, requested size,
nonzero caller and generation. A third case selected a complete reservation by
address, including its uncommitted tail, and verified that another heap's
allocation, realloc and free did not enter the selected scope.

The fourth case enables and queries Windows low-fragmentation heap mode,
allocates 2,048 blocks, frees half, and resizes 32 survivors. The final **1,024**
addresses and requested sizes exactly match the controlled caller's records:
**144,896 bytes**, zero overlaps. The observer excluded 88 nested allocation
calls and 53 nested frees. It detached while the process was alive, then the
private job deliberately terminated that disposable worker.
This cleanup is unrelated to terminal natural-exit acceptance.

Local validation was compilation and syntax inspection only. Local runtime
testing remains paused.

## First frontend capture and corrected scope

The first frontend run, [43437675368](https://github.com/xiongnemo/nemoterm/actions/runs/43437675368),
was rejected. Its DirectX snapshot contained 1,648 overlapping records. Large
ntdll requests overlapped smaller runtime requests; adding both would double
count storage. The retained `rejected-nested-directx-census.json` is diagnostic
failure evidence, not valid attribution. The original two small heap cases
had not exposed this allocator behavior.

The adapter now uses Gum's
[invocation depth](https://github.com/frida/frida-gum/blob/main/gum/guminvocationcontext.h)
to exclude nested heap API calls rather than excluding a module by name.
The new native case confirms
[LFH mode](https://learn.microsoft.com/en-us/windows/win32/api/heapapi/nf-heapapi-heapsetinformation)
and checks the resulting external requests exactly. The corrected GDI and
DirectX frontend captures both have zero overlapping records; their observers
detach before normal host closure and their private jobs drain naturally.

## Frontend diagnostic workflow

Manual dispatch of `.github/workflows/allocation-census.yml` first runs the
bookkeeping and native adapter checks, then runs GDI and DirectX on Windows
hosted runners. Both use the same pinned 4,436,992-byte candidate from
[run 43431940613](https://github.com/xiongnemo/nemoterm/actions/runs/43431940613),
SHA-256 `5f4d3f0a20171fc84c59c0e9afd8023916da80dab984849b6f0afce3c16b04f3`.
This failed its ordinary DirectX memory gate; it is not a newly accepted build.
The workflow verifies the downloaded image hash. The failed-build image is
retained for seven days; expiry requires explicitly selecting another verified
candidate identity, not silently substituting the latest image.

```powershell
gh workflow run allocation-census.yml --repo xiongnemo/nemoterm --ref feature/allocation-census-20261114
```

`tabs_window_smoke.py --workload-memory --allocation-census` is CI-only and
uses two retained 2,000-line histories, 24 dense-text/Sixel redraws, tab switches
and window resizes. After warmup and 12 tab create/close cycles, it selects up
to 64 pre-existing private reservations, each with at least 64 KiB of private
resident pages. `VirtualQueryEx` walks each entire reservation before attach.
The metadata uses the Windows
[allocation-base and region-size fields](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-memory_basic_information).

The entire diagnostic run, including its startup samples, is conservatively
labelled injected. It exits **2**, leaves `completed=false` and
`memory_limit_passed=null`, and writes `diagnostic_completed=true` only after
successful capture and normal process cleanup. Only this dedicated workflow
recognizes that outcome. The normal fixture retains all 30 prior assertions
and its uninstrumented 20,000,000-byte gate.

## Results and remaining attribution gap

The ordinary candidate run observed these frontend peaks, without injection:

| Existing workload case | Private WS bytes | Total WS bytes | 20 MB gate |
| --- | ---: | ---: | --- |
| GDI, top tabs | 11,214,848 | 42,631,168 | Pass |
| DirectX, left tabs | 25,055,232 | 65,208,320 | Fail |

Those existing suite cases use different tab sides. The separate allocation
diagnostics use **left tabs in both modes**. Their frozen metadata is:

| Diagnostic | Recorded live blocks | Requested bytes | Requested bytes on private resident pages | Private page snapshot bytes |
| --- | ---: | ---: | ---: | ---: |
| GDI | 5,184 | 2,220,518 | 2,220,518 | 14,721,024 |
| DirectX | 1,942 | 1,127,992 | 1,046,072 | 31,776,768 |

All numbers in the second table are **instrumented diagnostics**, not memory
acceptance. The recorded requests cover only 15.08% and 3.29% of the respective
private-page bytes. Mixed caller pages, gaps and unknown storage remain
unassigned. Immediate caller modules include runtime libraries; those names
do not identify the application subsystem that ultimately owns an allocation.

One DirectX reservation was 32 MiB, with private resident pages growing from
**2,486,272 to 8,642,560 bytes** between the pre-attach and post-workload snapshots.
No recorded outermost heap requests began in that reservation. This identifies
an area needing different observation; it does not prove an owner or explain
all DirectX excess. The manifest retains each selected reservation's before,
after and requested-byte totals. Next work should observe virtual commit and
release operations for that area and classify newly created reservations.

## Coverage limits

Only post-attachment allocations in the declared scope are represented.
Pre-existing live allocations, out-of-range reservations and allocation paths
outside the four hooked functions remain unassigned. Allocator overhead and
page sharing are not recorded by requested byte counts. Instrumentation can
change allocation behaviour, and an immediate caller is not a full allocation
stack or necessarily the component that ultimately owns the resource.

The working-set query follows the frozen allocation export; these snapshots
are not atomic. Instrumentation itself contributes memory, including requests
in existing heaps. Source hashes are checked against the committed blobs or
their exact Windows CRLF checkout conversion, and raw evidence hashes are
retained without line-ending normalization.

DirectX remains above its limit in the ordinary workload. No production
optimization, local executable replacement or physical runtime acceptance is
claimed here. Any optimization still requires a fresh uninstrumented workload.
