# Bounded resource-return checks

This changes the native test's observation timing, not the terminal's resource
management or memory limits. It is based on menu-reuse candidate `c5535a6`.
The [preceding investigation](tab-menu-lifetime.md) retains failed immediate
samples and REA traces showing temporary USER timers, including successful
timer destruction calls in MSCTF and the terminal after an I/O worker has exited.
Worker exit alone is not a guarantee that all GUI timers have expired.

## Fixed baseline and unchanged allowances

The existing workload warmup remains. Before the 12 measured create/close
cycles, the fixture observes initialization for at least three seconds and
requires the handle/GDI/USER tuple to stay unchanged for two seconds, with a
ten-second failure deadline. This yields one fixed baseline for every cycle;
the baseline never moves upward after a close.

After the child window, processes and both retained I/O worker identities have
retired, every cycle must return within the original allowances: OS handles +6,
GDI +3, USER +2. Counts must remain within those allowances for 250 ms, and the
whole observation must finish within two seconds. Timeout fails. The original
three numeric assertions remain in the fixture after the bounded check.

Each observation sequence preserves the original forced redraw on its first
sample. Subsequent polls read counters and memory without repeatedly repainting
the window. The first diagnostic mistakenly forced a redraw at every poll:
all three cases failed startup stabilization, with USER counts oscillating
53/54 and occasional GDI changes. Repainting was itself restarting GUI work.
Those failed cases and their five-process inner-job cleanup are retained.

Every startup and post-close sample remains in the JSON evidence. Their memory
values participate in the private-working-set maximum, as do the existing
continuous process-tree samples throughout startup and the full workload.
No sample, phase or transient peak is excluded; no working-set trimming,
counter subtraction, numeric-limit increase or target injection is introduced.
GDI remains below 20,000,000 bytes, DirectX at most 25,000,000, while optional
OpenGL retains the user-approved exception.

## Positive and negative controls

The corrected three-cycle diagnostic uses the same main-420 fixture for both
the accepted `aa11c539...` image and local menu candidate `18d20efb...`, with no
menu-identity assertions influencing the comparison. Both report a fixed USER
baseline of 51, initially report 54 after each close, and satisfy the unchanged
limits after approximately 0.47-0.48 seconds including the quiet interval.
All 13 inner / 15 outer owned processes exit naturally in each case.

A separate run deliberately holds a third native session open. At the deadline
it still has 551 OS handles, 46 GDI and 57 USER objects, against baseline
540/38/51, and is correctly rejected. After closing that session, the counts
return within the original bounds. All nine inner / eleven outer processes
exit naturally. This is a persistent-resource negative control, not a claim
that every possible leak shape has been exercised.

These short diagnostic cases intentionally exit 2 and are not acceptance. The
generic controller maps any nonzero child exit to 1; the first driver incorrectly
expected its own subprocess result to remain 2. A read-only review of the
retained child/controller records confirms the intended results without
rerunning the cases. Both the original orchestration failure and reviewed
results are retained.

Six deterministic unit tests cover delayed initialization, non-settling startup,
retained memory peaks, brief returns followed by growth, each original numeric
boundary and observer calls that overrun the deadline. They pass and run in the
core, single-executable and allocation diagnostic workflows.

## Full native workload

The exact local executable remains 4,509,696 bytes, SHA-256
`18d20efbc85257fb8a04822debf2bc8a0a9a49d6a8e7c86a6871c10eb10eae6c`;
this test-only change does not relink it. Fresh owned processes use actual
SarasaTermSC Nerd Font Light. All four native cases complete their nine groups:

| Renderer / tab side | Actual grid | Private WS peak | Total WS peak | Private commit peak |
| --- | --- | ---: | ---: | ---: |
| GDI / top, full workload | 160x48 | 16,650,240 | 43,466,752 | 19,058,688 |
| DirectX / left, full workload | 160x48 | 23,150,592 | 58,712,064 | 87,605,248 |
| OpenGL / bottom, ordinary tab test | 80x24 | 50,802,688 | Not a full memory workload | Not a full memory workload |
| GDI / right, ordinary tab test | 80x24 | 7,647,232 | Not a full memory workload | Not a full memory workload |

GDI and DirectX have 529 and 501 process-tree samples, respectively, with no
sampling errors. Both pass all 12 resource-return cycles and 73 menu snapshots;
all 56 inner / 58 outer processes exit naturally. The two smaller-grid cases
pass 12 cycles and 45 menu snapshots each; all 54 inner / 56 outer processes
exit naturally. Memory sampling finishes before independent pixel instrumentation.
DirectX's total working set remains above the approximate 50 MB target.

The [manifest](resource-settle-validation.json) retains 92 compressed records
(278,438 bytes), including failed and corrected fixtures, samples, native
controls, unit output and natural/forced cleanup. Decompressed lengths and
SHA-256 hashes were verified. These are local observations, not REA-server
Evidence. Full CI and a downloaded artifact still need verification before
this branch is merged or the accepted executable is replaced.
