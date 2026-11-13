# Owned handle lifetime investigation

The six short-lived handles seen during experimental D3D11 tab closure now have
observed creation and successful close paths. Two events come from Nemoterm's
input/output handle workers; two timers and two semaphores have NVIDIA driver
frames. A separate persistent Event/IoCompletion pair remains **unattributed**.
The original resource failures remain failures. No renderer or resource limit
changed, and this is not a new memory acceptance result.

The [manifest](handle-lifetime-validation.json) retains 177 compressed records:
both failed observer validation attempts, corrected native checks, CI results,
exact diagnostic fixtures, raw handle tables, traces, analysis and cleanup.
Every record has compressed and decompressed SHA-256 and byte counts. The
production executable is the [99-group CI image](relative-cursor.md); the
experimental image is the sequential [D3D11 copy candidate](d3d11-copy.md).

## Observer validation

`tests/handle_snapshot.py` queries the retained owned process handle using
`NtQueryInformationProcess(ProcessHandleInformation)`. Type names come from the
system object-type catalogue, not from object names. It does not duplicate
target handles or inject target code. The native layout reference is pinned to
[PHNT 53fbbdc](https://github.com/winsiderss/phnt/tree/53fbbdc5b5d2b08761db1c7b26bfa8c820924356).
Queries have allocation/retry bounds and reject a wrong job or exited process.
The Win32 count and native table are sequential observations, not an atomic view.

The first two local tests expected eight controlled handles but observed nine.
An independent per-call ledger identified the first `CreatePipe` call as the
extra File-handle transition: it added three handles although the API returned
two. The test now records an explicit pipe creation/close before its baseline;
the exact eight-handle assertion is unchanged. This identifies initialization
behavior, not the extra File object's name or owner. Attempt one retained no
inner cleanup report; attempt two forced two inner job members. Neither is
rewritten as a pass. Corrected local validation passes six checks, with natural
two-member inner and four-member outer cleanup.

The six checks cover Win32/native count agreement, wrong-job rejection, exact
controlled handle values/types/deltas, repeated observation without target
handle growth, controlled closure, and rejection after process exit. Both
Windows 2022 and 2025 passed at `fc2d468` in
[run 43528837723](https://github.com/xiongnemo/nemoterm/actions/runs/43528837723).

## External observations

All terminal cases obtain SarasaTermSC Nerd Font Light and a 160x48 grid. The
copied fixtures keep the original handle/GDI/USER assertions and preserve the
sample that triggered a failure. Four extra observations over two seconds are
recorded after a failure; they never replace its original sample. These runs
stop at the tab cycles and do not exercise the complete memory workload.

| Image / observation | Original result | Later process-local tables |
| --- | --- | --- |
| Production `0db4c0d...` | All 12 cycles within original limits | Baseline and all post-close tables: 544 handles |
| D3D11 `bb73edd...`, ordinary snapshots | Cycle index 11 fails: 559 to 567 handles | 561 handles; Event +1, IoCompletion +1 persists through all four extra observations |
| Same D3D11, snapshot immediately after Win32 count | Cycle index 10 fails: 559 to 567 | Same persistent pair; earlier tables capture the transient six handles |

The immediate observation captures 565 handles at records 9, 17 and 21, with
Event +2, Semaphore +2, Timer +2 relative to stable record 3 (559). Its Win32
count is already 559 by the end of each query. Other observations catch partial
transitions. This shows concurrent closure during observation; it does not show
the observer closing target handles.

The production run exits with diagnostic code 2 after two groups and natural
31-member inner/33-member outer cleanup. Both experimental cases retain their
assertion failures and require five-member inner cleanup. Their outer jobs then
have zero active members; this does not make the inner cleanup natural. The
production result does not resolve its earlier nonreproduced 492-to-549 resource
failure recorded in [DX resources](dx-window-resources.md).

## Bounded creation and close traces

The test-only tracer uses the documented
[Frida Interceptor and backtrace APIs](https://frida.re/docs/javascript-api/).
It attaches only after checking the freshly spawned process's retained handle
and job membership. It captures integer handle metadata and at most 12 raw
caller PCs, with an 8,192-event / 60-second bound. PCs are resolved outside the
hooks against retained module inventories. Object names and contents are not
read. Each creation has a generation ID, so reuse of a numeric handle does not
make a previous object the owner of a current handle.

The first local adapter check validates 100 known creations/closes. The second
adds 20 local duplicates; the final version adds 20 opens of the fixture's own
event. The final four checks verify all 140 generations, caller frames, exact
types, observed value reuse, successful closes, bounds and detachment. All
three local variants pass and drain their two-member inner/four-member outer
jobs naturally. Open/duplicate metadata does not establish ownership of a
different process: only the current-process pseudo handle is tracked locally.

Two D3D11 traces retain 308 and 708 events, with no overflow or script error and
confirmed detachment. The latter also hooks event/completion-port opens,
`NtDuplicateObject` and `NtCreateWaitCompletionPacket`. Every one of their 12
tab cycles records exactly the following six creations and successful closes
before the post-close marker:

| Handles per cycle | Observed creator | Observed close path |
| --- | --- | --- |
| Two Event handles | `nemoterm.exe+0x11f4f2` and `+0x11f232`; matching local PDB resolves `handle_output_new` and `handle_input_new` | Nemoterm caller frames, `NtClose` success |
| Two Timer handles | `nvwgf2umx.dll+0xee24a9`, through Kernel32/KernelBase | `nvwgf2umx.dll+0xee2662`, `NtClose` success |
| Two Semaphore handles | `nvwgf2umx.dll+0xee24c3`, through Kernel32/KernelBase | `nvwgf2umx.dll+0xee266f`, `NtClose` success |

This agrees with the source's deferred handle-worker teardown and the external
type counts. Driver module names/RVAs are observed; an exact driver file hash
was not captured. The instrumented process has a higher baseline (587), fails
at 595, and settles to 589. Its private memory is explicitly instrumented and
cannot be used for the 25 MB acceptance target. Both failed terminal traces
force five remaining inner processes after detaching; outer jobs then drain.

The final Event/IoCompletion pair has no matching unclosed creation in either
trace. One numeric value was previously used by a Timer in trace one; both
values were previously Semaphores in trace two. Those generations have already
closed and have different types. They are **not** evidence that NVIDIA created
the persistent pair. The expanded trace has no matching duplicate or open for
the pair either. Unhooked paths and kernel-created handles remain possible;
this bounded negative observation does not identify the owner or prove a leak.

## CI and remaining work

At `7b3c52ce6ec34d091cab488ca7d1052d6d4444a5`, both Windows runners pass the
six metadata checks and four tracing checks in
[run 43530556414](https://github.com/xiongnemo/nemoterm/actions/runs/43530556414).
The downloaded native results confirm natural two-process cleanup and observed
handle-value reuse on both systems. CI artifacts 14087291758 (2022) and
14086474637 (2025) retain the exact scripts and results for 30 days; their
contents and API metadata are also preserved in this repository's manifest.
These focused observer checks are separate from the product's 99-group suite.

The next investigation can distinguish frontend worker completion from
descendant-process exit, which the old tab fixture currently waits for. Any
change needs to preserve the original failure evidence and validate actual
resource lifetime, rather than merely increasing the allowed count or adding
an arbitrary delay. The persistent pair's origin, earlier production resource
failure, experimental renderer recovery and full memory target remain open.
Main's product sources and accepted `dist/nemoterm.exe` are unchanged.
