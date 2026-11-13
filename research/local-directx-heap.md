# Local DirectX heap lifetime checkpoint

The 160x48, SarasaTermSC Nerd Font Light, two-tab workload still exceeds the
25,000,000-byte DirectX private-working-set ceiling. No renderer change or
replacement of the accepted local executable is included in this checkpoint.
The current public product remains the automation/input source `abafbbf` with
the previously passing 93-group CI run. See [automation/input](automation-input.md).

## Wider owned-process observation

The earlier census selected pre-existing reservations, which excluded later
reservations and blocks outside those ranges. A new explicit
`--local-heap-census` option observes all post-attachment outermost calls to
`RtlAllocateHeap`, `RtlReAllocateHeap`, `RtlFreeHeap` and `RtlDestroyHeap` in the
fresh fixture-owned frontend. It reads allocation metadata, never allocation
payloads. The existing CI-only reservation and ETW modes keep their restrictions.

```powershell
$env:NEMOTERM_TEST_EXE = 'C:\path\to\nemoterm.exe'
python tests/tabs_window_smoke.py --renderer directx --side left --cols 160 --rows 48 --font 'SarasaTermSC Nerd Font Light' --workload-memory --local-heap-census
```

This is an explicitly instrumented diagnostic. It has a 180-second controller
deadline, a bounded 262,144-entry native table and a private kill-on-close job.
A successful capture exits **2**, leaves `completed=false` and
`memory_limit_passed=null`, and sets `diagnostic_completed=true`. It must never
be interpreted as a working-set acceptance pass. Use a separate evidence
directory for each executable to retain earlier results.

The unchanged local `9e79a655...` image was observed once per renderer with the
same 160x48 grid, Sarasa font, left tabs and existing history/Sixel/resize
workload. Both snapshots report zero bookkeeping errors and overlapping
records; both observers detach and all owned processes exit naturally.

| Post-attachment live metadata | GDI | DirectX |
| --- | ---: | ---: |
| Allocation records | 7,620 | 8,840 |
| Requested live bytes | 5,335,330 | 5,998,540 |
| Requests whose immediate caller is UCRT | 4,568,672 | 4,580,192 |
| Requests whose immediate caller is GDI | 764,034 | 772,724 |
| Requests whose immediate caller is NVIDIA's user-mode driver | 0 | 553,392 |

All recorded requested bytes were resident in the following page snapshot.
The **663,210-byte** difference in recorded live requests does not explain the
ordinary workload's entire DirectX excess. Immediate caller modules are not
resource owners. Pre-attachment allocations, non-heap allocations, allocator
overhead and released-block retention remain outside the accounting. The
observer itself changes allocation behavior, so these numbers neither prove
a leak nor quantify a production saving. The private-page and allocation
snapshots are not atomic. Injected working sets are retained in the manifest
but excluded from acceptance.

The native adapter test now validates two independent heaps in the same
capture, absence of a freed block and rejection of conflicting scope options,
in addition to the existing allocation/reallocation/destruction, reservation
filter and low-fragmentation-heap cases. All 27 checks pass locally. The five
offline page-correlation tests also pass.

[Diagnostic CI 43488913656](https://github.com/xiongnemo/nemoterm/actions/runs/43488913656)
passes on source `2bebf40`: Windows independently repeats all 27 adapter checks
and the virtual-memory adapter; Linux passes allocation bookkeeping under
ASan/UBSan and all five page-accounting tests. Three CLI rejection checks also
pass locally (missing workload, CI-only mode outside CI and conflicting modes).
This focused validation builds no new product image and does not repeat or
replace the earlier 93-group product acceptance run.

## Rejected renderer experiments

Two separately built experiments ran the unchanged uninstrumented workload.
Both obtained actual DirectX, the full 160x48 grid, all nine functional groups
and natural cleanup. Both failed the existing memory assertion:

| Experiment | Private WS peak | Decision |
| --- | ---: | --- |
| GPU-only frame with a bounded 256 KiB GDI readback strip | 30,597,120 bytes | Reverted |
| Retain the larger frame when shrinking, crop presentation and reuse it on regrowth | 30,367,744 bytes | Reverted |

The preceding unchanged-source observation was 30,547,968 private bytes.
These single-run differences establish no useful saving. The readback result
also repeats the earlier [rejected readback finding](tab-workload-memory.md)
against the newer automation/input baseline; it is not a new solution.
The frame experiment retains its current viewport dimensions and history;
the threshold, workload, font and screen geometry were never reduced.
Neither failed candidate was promoted or subjected to full renderer parity
acceptance. Their exact patches, source hashes, logs and raw samples are
retained for audit.

The [manifest](local-directx-heap-validation.json) binds executable identities,
collector sources and all compressed raw records. Further optimization needs
to account for pre-existing and non-heap graphics allocations or avoid their
cost through a different compositor implementation; the full terminal goal
and the local DirectX memory gate remain open.
