# Distinguishing tab closure from worker retirement

The experimental DirectX resource failure includes two frontend I/O threads
which are still running after the shell and console-host processes have exited.
The existing fixture waits for descendant processes and window destruction,
then samples resources before those frontend threads finish. Waiting on their
actual thread objects is a stronger completion condition; numerical handle,
GDI, USER and memory assertions remain unchanged in the proposed fixture.

## Validated external observer

`tests/thread_snapshot.py` checks a retained process's owned-job membership,
enumerates only that process's thread metadata, and pairs IDs with creation
times. It dynamically calls
[NtQueryInformationThread](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntqueryinformationthread)
for start addresses and maps them against the owned process's module catalogue.
The catalogue and thread queries are sequential snapshots. No suspension,
injection, stack reads, target calls or UI activation are used.

The optional observer-side leases open query/synchronization handles, reject
changed creation identities, and bound waits to at most five seconds. Windows
[signals a thread object when the thread terminates](https://learn.microsoft.com/en-us/windows/win32/procthread/terminating-a-thread).
The terminal receives no additional handles. The native adapter creates two
known threads and independently verifies IDs, timestamps, exact start pointers,
unchanged observer/target handle counts over repeated snapshots, sibling
retirement, failed partial-acquisition cleanup, bounded waits and owner rejection.

The first six checks pass locally and on Windows 2022/2025 in
[43540854013](https://github.com/xiongnemo/nemoterm/actions/runs/43540854013).
The final eight checks, including retained thread identities, pass locally and
on both runners in [43541843784](https://github.com/xiongnemo/nemoterm/actions/runs/43541843784),
source `7ef34dd`. These are observer checks, not full product integration.

## Exact worker and resource evidence

All DirectX observations use experimental single image
`00f9a30d6a4660efc020cfebef5bddc51146a460ebd0308a15b6ee50cc26fe49`.
The first diagnostic preserves the original 540-to-548 failure. By the first
thread snapshot, 67 ms later, the process has returned to its original 31
thread identities and 542 handles. This alone cannot prove the earlier state.

The next diagnostic retains both new I/O thread handles before closing each
temporary tab. Matching PDB publics locate the input/output constructors;
their disassembly passes RVAs `0x11ecb0` and `0x11efc0` to the verified
`CreateThread` import. The symbolizer's nearest-public names are not used as
exact labels for those private thread procedures.

On every recorded cycle, both retained threads still return `WAIT_TIMEOUT`
adjacent to the original handle count. Two independent count reads bracket the
thread checks, which take 12.8 to 21 microseconds. Cycles 0 through 9 read 546
handles and return to 540 after both thread objects signal. Cycle 10 reads 548
on both sides of the checks and returns to 542 after both signal. The original
failing assertion remains in the diagnostic. It forces five remaining inner
processes, then the outer 31-member job drains. The persistent two-handle
increment is still unattributed; thread-start modules do not identify handle owners.

## Proposed fixture and remaining GDI gate

Commit `5fbc4fc` binds the two new worker identities from before/after snapshots,
using repeated frontend entry addresses rather than fixed image offsets. It
waits at most two seconds for those exact objects, closes the observer handles,
then performs the original resource measurements and comparisons. It adds no
sleep, count-based polling or target instrumentation. The warm-up and all 12
cycles each record both thread objects becoming signalled.

With the experimental renderer's child-window class name adapted, the complete
DirectX workload passes nine groups at actual SarasaTermSC Nerd Font Light
160x48. Across 450 samples over 48.525 seconds, frontend peaks are 23,482,368
private-working-set bytes, 63,127,552 total-working-set bytes and 92,254,208
private-commit bytes. All 56 inner / 58 outer processes exit naturally. The
private peak is below the unchanged 25,000,000-byte limit. Total working set is
reported separately and remains above the user's approximate 50 MB target.

The same proposed fixture under GDI fails its original USER-object assertion:
36 at baseline becomes 39, above the allowance of two. The original downloaded
I/O CI image separately fails an unmodified GDI workload with a 361-to-407
handle transition; see its [checkpoint](https://github.com/xiongnemo/nemoterm/blob/feature/io-lifetime-20261114/research/io-lifetime.md).
A later copied startup diagnostic begins at 405, observes `NativeHWNDHost` and
`Mode Indicator Button` windows, and completes nine groups with natural cleanup.
It remains `completed=false` and diagnostic-only. It does not reproduce the
original startup transition or identify the owner of its new resources.

The [manifest](thread-lifetime-validation.json) verifies 111 compressed records,
including both original failures, exact observer/test sources, PDB/disassembly
evidence and CI results. The proposed tab fixture remains unmerged pending GDI
startup investigation and full integration CI. Experimental renderer recovery
and final distribution acceptance also remain open; the local accepted EXE is
unchanged.
