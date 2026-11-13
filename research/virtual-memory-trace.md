# Scoped virtual-memory observation

The [heap census](allocation-census.md) found a large DirectX private reservation
whose resident growth was not represented by outermost heap requests. This
checkpoint follows its virtual commit/release API paths. It does not change
the renderer or establish that DirectX meets its 20,000,000-byte limit.

## Native observer validation

The adapter observes `NtAllocateVirtualMemory`, `NtAllocateVirtualMemoryEx`
and `NtFreeVirtualMemory` for `NtCurrentProcess` and selected pre-existing
address ranges. It records entry and result addresses, sizes, flags, NTSTATUS,
immediate caller and up to 12 accurate stack frames. It reads API metadata;
it does not read allocated payloads, modify arguments or trim working sets.
The event buffer is bounded and overflow/errors invalidate the capture.

The layouts use complete `VirtualQueryEx` walks, including reserved and free
regions. API requested bytes are not summed as net commitment. Microsoft's
[allocation](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntallocatevirtualmemory)
and [free](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntfreevirtualmemory)
contracts distinguish reservation, commitment, decommit and whole-reservation
release. A repeated commit request need not create new committed pages.

[Native CI 43442030276](https://github.com/xiongnemo/nemoterm/actions/runs/43442030276)
passed a controlled 64 KiB reservation in a disposable owned worker:

| Operation | Committed bytes after operation |
| --- | ---: |
| Initial reservation | 0 |
| Commit 8 KiB | 8,192 |
| Commit in excluded reservation | 8,192 |
| Invalid-protection commit fails | 8,192 |
| Decommit 4 KiB | 4,096 |
| Commit 4 KiB through extended API | 8,192 |
| Release whole reservation | 0 |

The observer retains exactly five selected events; the excluded reservation
does not enter the trace. Addresses, flags, failure status and nonempty stacks
are checked. The final layout is free. These tests run remotely; local native
execution remains paused.

## Frontend observations

[CI 43443390680](https://github.com/xiongnemo/nemoterm/actions/runs/43443390680)
passed the observer checks and both GDI/DirectX diagnostic workloads on source
`5ba4df3`. Both use left tabs, the same dense-history/Sixel/resize workload and
the exact candidate SHA-256
`5f4d3f0a20171fc84c59c0e9afd8023916da80dab984849b6f0afce3c16b04f3`.
The [manifest](virtual-memory-validation.json) binds raw evidence hashes,
source byte formats and artifact identities.

The first run compared only pre-attach and final layouts. The repeat adds a
third snapshot after observer initialization and before workload execution.
For the selected 32 MiB DirectX reservation:

| Snapshot | Committed bytes | Private resident bytes |
| --- | ---: | ---: |
| Before attach | 2,519,040 | 2,486,272 |
| Observer initialized, before workload | 2,519,040 | 2,486,272 |
| After workload | 8,949,760 | 8,916,992 |

The **6,430,720-byte** increase occurred during the instrumented workload,
not during initial attachment. Nevertheless, no selected API event covers
that range. Nt and Zw export pairs had identical addresses on these runners;
an unhooked Zw alias does not explain this gap. Another GDI reservation also
grew without matching API records. These are coverage gaps, not proof that
Windows committed memory without an allocation path.

The API trace does capture commit/decommit activity in another private heap,
with stacks through ntdll, MSVCRT, Direct2D, and sometimes Nemoterm or the text
input framework. That does not attribute the large unobserved reservation.
The JavaScript stack observer itself adds substantial memory: the DirectX
frontend ends at **67,633,152 private resident bytes** in this diagnostic.
None of these injected measurements is an acceptance result.

## Kernel event follow-up

The dedicated workflow also supports `observation=etw`. It starts WPR's
`VirtualAllocation` profile on the isolated hosted runner, runs the bounded
workload without injecting Frida into the frontend, and stops its own recorder
in a `finally` block. It retains the ETL, decoded event XML, workload PID,
wall-clock phase markers, private-page maps and reservation layouts. This
follows Microsoft's [WPR virtual-allocation collection procedure](https://learn.microsoft.com/en-us/troubleshoot/windows-server/performance/troubleshoot-application-service-memory-leaks).

```powershell
gh workflow run allocation-census.yml --repo xiongnemo/nemoterm --ref feature/allocation-census-20261114 -f observation=etw
```

The fixture requires dedicated CI and the workflow recording flag. Like the
injected diagnostics, it deliberately returns diagnostic exit 2 and leaves
normal memory acceptance unevaluated. Samples declare `injected=false`,
`kernel_etw_recording=true` and `diagnostic_only=true`. Recording system events
can still affect execution; a later optimization needs the normal workload.

[Kernel recording 43444144664](https://github.com/xiongnemo/nemoterm/actions/runs/43444144664)
passed both diagnostic workloads without frontend injection. Tracerpt reports
**zero lost events** for both traces. Downloaded ETL hashes match their
validation manifests; full ETL/XML stay in CI artifacts and the local build
cache, while the repository retains the narrower owned-process metadata.

| ETW workload | Frontend private WS peak | Frontend total WS peak |
| --- | ---: | ---: |
| GDI | 10,858,496 | 42,954,752 |
| DirectX | 25,096,192 | 68,591,616 |

The DirectX trace contains the previously unobserved 32 MiB reservation:
one reserve, 489 commits, one decommit and one release. Replaying page-set
membership (rather than summing repeated request sizes) gives:

| Boundary | Committed bytes from ETW | Independent query |
| --- | ---: | ---: |
| Before workload | 2,519,040 | 2,519,040 |
| After workload | 8,966,144 | 8,966,144 |
| After process exit | 0 | Process exited normally |

The workload adds **6,447,104 committed bytes** in that range and its private
resident pages grow from 2,486,272 to 8,933,376 bytes. The same growth therefore
occurs without Frida injection. It remains allocated through the workload,
then releases at process exit; that alone does not prove a leak or the owner.
The [selected event replay](virtual-memory-evidence/etw-directx-selected-region-replay.json)
retains the exact 492 events, phase markers and page-set results.

Ordinary tracerpt XML does not decode all StackWalk payloads. A separate
`observation=etw-decode` dispatch reads the **existing, hash-checked ETL** and
requests [raw event timestamps](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/tracerpt)
for exact event/stack matching. It does not start Nemoterm or collect another
trace. Stack payload parsing follows Microsoft's
[StackWalk layout](https://learn.microsoft.com/en-us/windows/win32/etw/stackwalk-event)
and x64 pointer width. [Decode run 43446229913](https://github.com/xiongnemo/nemoterm/actions/runs/43446229913)
completed with zero payload decoding errors, including both raw and structured
StackWalk layouts. It retains 10,209 owned-process VM events and 5,971 stacks.

The [offline correlation](../tests/etw_region_report.py) matches the original
QPC timestamp, PID and thread exactly. It resolves module addresses only after
a recorded load/start rundown and before unload, and checks the selected
events against the independently replayed trace. The one reserve and all 489
commit events each have exactly one matching stack. The two free events have
no matching stack and are not assigned a caller. The [selected stack record](virtual-memory-evidence/etw-directx-selected-region-stacks.json)
retains the raw payloads, exact matching keys, image load identities and module
offsets. No nearest-time match is used.

The matched allocation stacks pass through `win32u.dll`, `DXCore.dll`,
`d3d11.dll`, `d3d10warp.dll` and `d2d1.dll`. This hosted runner therefore uses
WARP on this allocation path despite the requested hardware target type; the
renderer property alone does not establish physical-GPU execution. It does
not establish the local NVIDIA driver's allocation behavior.

Of 489 commits, 480 return through image RVAs `0x110c94` and `0x1116cd`.
Static disassembly of the exact hash-checked EXE shows the former following a
call to a wrapper that jumps to render-target COM slot 4 (`CreateBitmap`),
with BGRA/ignore-alpha/96-DPI bitmap properties. The latter is the run-cache
miss path in `nemo_d2d_end_run`; this mapping is source/disassembly inference,
not a recovered private symbol. The [disassembly excerpt](virtual-memory-evidence/etw-directx-create-bitmap-disassembly.txt)
retains the addresses and tool version.

Page-set replay attributes **5,009,408** newly committed workload bytes to
that path and **1,437,696** to the separate `0x1118dd`/`0xceab8` path, totaling
the independently measured **6,447,104** increase. These are new committed
pages in this reservation, not live bitmap bytes or a guaranteed saving.
The concrete next experiment is reusing same-sized evicted bitmap resources
instead of recreating them. Previous cache-limit and fixed-atlas experiments
failed on the local GPU; this different lifetime change still requires the
unchanged pixel, functional and memory gates, followed by local validation
when runtime testing is authorized again.

## Separate main-branch repeat

The earlier source `1b09f82` passed both workflows, including the
[57-group single-image run](https://github.com/xiongnemo/nemoterm/actions/runs/43431838348).
Its later [main-branch repeat](https://github.com/xiongnemo/nemoterm/actions/runs/43434238339)
hit the 45-minute job deadline. The last completed fixture was delegated
console lifetime; the next fixture was shutdown, with no retained shutdown
log or completed result. The cancellation does not identify the blocked call
or prove a product crash. Development already has shutdown stage checkpoints
and a controller deadline; main's older repeat lacked those diagnostics.
The earlier successful checkpoint must not be read as universal shutdown
stability. Local runtime tests and the accepted local EXE remain untouched.
