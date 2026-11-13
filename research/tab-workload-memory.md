# Two-tab workload memory checkpoint

**The DirectX memory requirement is not satisfied.** GDI passes this bounded
workload; this does not establish full real-agent or sustained-hover acceptance.
The product image remains the reverse-wrap candidate from
`fab17ec243463613524d3f7fd8746f08012a57fb`, SHA-256
`d6a46003b58a48bc5927437af6214c5492d78273e98911da6c21dda49b5546c3`.
This checkpoint changes tests and evidence, not product code. The accepted main
distribution is unchanged.

## Measured workload

The owned native window requested and obtained 160x48 cells using
SarasaTermSC Nerd Font Light. Two tabs retain independent terminal state and
2000 history lines each. The fixture creates/closes twelve temporary tabs,
writes 4096 distinct lines per retained tab (true colour, links, Chinese,
combining characters and bidirectional text), and performs 24 dense redraws
with 512x288 Sixel images and 24 host-size transitions.

An external sampler observes the frontend, same-image OpenConsole hosts and
Python workload clients at a nominal 100 ms interval. Every stable workload
sample must contain one frontend, two hosts and two clients. The earlier
temporary-tab phase can contain three hosts and three clients. No working-set
trimming is performed. GPU capture, hover and shortcut instrumentation starts
only after sampling stops.

| Mode | Private WS sampled peak | Total WS sampled peak | Private commit sampled peak | Result |
| --- | ---: | ---: | ---: | --- |
| GDI, top | 14,778,368 B / 14.78 MB / 14.09 MiB | 37,662,720 B / 37.66 MB / 35.92 MiB | 16,928,768 B | Pass for this workload |
| DirectX hardware, left | 29,532,160 B / 29.53 MB / 28.16 MiB | 65,937,408 B / 65.94 MB / 62.88 MiB | 102,064,128 B | **Fails 20,000,000 B private WS limit** |

GDI has 451 samples over 48.785 seconds; DirectX has 352 over 38.030 seconds.
Earlier captures of the same product also exceeded the DirectX threshold,
including 28,135,424 private bytes. These are sampled peaks, not instantaneous
maxima or claims about an unlimited number of tabs.

The raw `tab-workload-{gdi,directx}-memory.json` records every sampled process,
role, private/total working set and private commit. Their `peaks` also retain
separate host/client sums and the whole observed tree. For example, GDI's
whole-tree private peak was 43,130,880 bytes, including the Python clients.
Working-set sums count shared pages per process and are not unique physical
system RAM. Child memory is not part of the frontend threshold and is not
silently omitted.

Both modes completed all nine tab functional groups, including isolated input,
create/close cycles, preview updates, synchronized presentation, fullscreen,
resize and original-tab close. DirectX then fails the memory assertion. All
owned processes exited naturally, with no forced job cleanup. Separate GDI
bottom and actual OpenGL right runs passed the same functional groups. OpenGL
retains the user's explicit memory exception.

## Diagnosis and rejected experiments

Optional `NEMOTERM_TEST_MEMORY_REGIONS=1` records `VirtualQueryEx` metadata for
resident private pages without reading their contents or injecting code.
The extra DirectX usage is primarily in private allocations, with an additional
private image-page component. Region addresses do not identify the allocator
or calling module. Allocation ownership remains unresolved.

Two experiments passed renderer pixel parity and the tab functional groups,
but both failed the memory requirement and were reverted:

* A bounded GDI readback surface produced a 27,402,240-byte private peak, with
  114,495,488 bytes private commit. Microsoft's [GetDC documentation](https://learn.microsoft.com/en-us/windows/win32/api/d2d1/nf-d2d1-id2d1gdiinteroprendertarget-getdc)
  describes flushing the target and its BeginDraw/EndDraw contract; it does not
  establish the observed driver's allocation cost.
* Reducing the run cache from 256 objects/4 MiB to 64 objects/512 KiB while
  preserving the transfer allowance produced a 28,147,712-byte private peak.

Single-run variations are not a causal attribution. Neither experiment is
present in product source. `tab-workload-validation.json` records both image
identities, patch hashes, measurements, final tests and evidence hashes. The
next optimization requires evidence attributing the additional private
allocations, rather than another speculative limit change.

## Measurement and remaining gates

A sampling attempt stopped on a process read error and was rejected. The
sampler now handles a read/exit race only when the retained process handle is
signaled; it records the PID, exit status and error. A live-process read error
or failed termination check still fails. Six process-identity/exit tests, three
working-set-query tests and two owned-job tests pass.

An uninstrumented synthetic-hover probe was unreliable: real leave tracking
could cancel hover before its timer because the physical cursor was elsewhere.
That probe is not an acceptance test. Sustained preview functionality continues
to use the existing owned-process instrumentation, after memory sampling, and
**uninstrumented sustained-preview memory remains open**. No global pointer or
clipboard operation was used.

Both CI workflows now run the longer workload instead of the former dense-tab
memory sample. They preserve the process records and fail if GDI or actual
DirectX exceeds the private limit. A hardware fallback is recorded explicitly;
it does not certify DirectX hardware memory. GitHub startup/billing status must
be checked separately from these local results.

To reproduce, set `NEMOTERM_TEST_EXE` to the exact image under test, then run:

```powershell
$env:NEMOTERM_REQUIRE_DIRECTX = '1'
$env:NEMOTERM_TEST_MEMORY_REGIONS = '1' # optional allocation-region metadata
python tests/tabs_window_smoke.py --renderer gdi --side top --workload-memory
python tests/tabs_window_smoke.py --renderer directx --side left --workload-memory
```

The local default font is SarasaTermSC Nerd Font Light; CI uses Consolas and
records that distinction. The DirectX invocation currently exits nonzero on
this machine, preserving its memory and natural-cleanup evidence.

Real-agent interactions and long workloads, physical IME/multi-monitor use,
clipboard acceptance, unexplained historical tab-close/handle observations,
and the remaining protocol inventory are still open. This checkpoint does not
promote a new accepted executable or complete the user goal.
