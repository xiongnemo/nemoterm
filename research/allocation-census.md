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

The [Frida CModule API](https://frida.re/docs/javascript-api/#cmodule) requires
writable globals to be supplied externally. This adapter retains those buffers
and checks its record size against the layout used by the JSON exporter.

## Validation checkpoint

Commit `f6d1ce2` passed the dedicated
[collector workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43434405328).
The [manifest](allocation-census-validation.json) binds the retained raw results.

The C11 tests ran with ASan and UBSan. They cover failed operations, in-place
and moved reallocations, nested callbacks, delayed free/address reuse, heap
handle reuse, collision chains, tombstone reuse, exhaustion, counter bounds and
freeze. These model callback orderings; they are not a concurrent allocator stress test.

Windows validation injected the adapter only into an owned disposable Python
process and operated on a newly created private heap. Each of two cases checked
empty state, two allocations, realloc, free and 100 allocate/free cycles. One
then destroyed the heap and confirmed zero live records. The other froze a
single live 128-byte block and checked its exact address, heap, requested size,
nonzero caller and generation. The observer detached while the process was
alive, then the private job deliberately terminated that disposable worker.
This cleanup is unrelated to terminal natural-exit acceptance.

Local validation was compilation and syntax inspection only. Local runtime
testing remains paused.

## Coverage limits and next use

No Nemoterm allocation census has been collected with this version yet. The
native test validates explicit-heap filtering; the optional pre-injection
address-range filter still needs its own native coverage before attribution.

Only post-attachment allocations in the declared scope are represented.
Pre-existing live allocations, out-of-range reservations and allocation paths
outside the four hooked functions remain unassigned. Allocator overhead and
page sharing are not recorded by requested byte counts. Instrumentation can
change allocation behaviour, and an immediate caller is not a full allocation
stack or necessarily the component that ultimately owns the resource.

Future frontend captures must correlate the frozen records with separately
observed private resident pages, retain mixed/unassigned pages explicitly, and
keep all injected measurements out of the 20,000,000-byte acceptance gate.
An optimization still requires a fresh uninstrumented workload afterwards.
