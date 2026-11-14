# Owned window inventory and DirectX resource-return diagnostics

This test-only change preserves the existing fixed baseline, two-second
post-close deadline and handle/GDI/USER allowances of +6/+3/+2. It does not fix
the outstanding resource-return failures or change the accepted executable.

`tests/tabs_window_smoke.py --resource-inventory` reads window metadata at each
resource sample and handle/thread metadata at the baseline and after each
close cycle. It retains the actual fixture process handle and verifies private
job membership and liveness before and after each window inventory. It includes
hidden, child and message-only windows, without reading text, activating windows,
opening menus or injecting a target script. Handle reuse and non-window USER
objects remain limitations. Extra observation changes timing, so this mode
always marks memory acceptance false and exits 2 on diagnostic completion.

The hidden-window canary verifies the three window classes of ownership, a new
child's creation/destruction, rejection of an exited owner, and natural private
job cleanup. Both local runs pass; the second also treats implicit text-encoding
warnings as errors. The existing observer workflow now runs this canary on
Windows 2022 and 2025 and retains its result and source. CI results for this
change are not established by these local checks.

## Exact executable and unresolved original failure

All three terminal observations below use the same locally linked single image:
source `82e1beffe9b630619385b5afb88f5d9fb04ac911`, 4,530,176 bytes, SHA-256
`9f224f62babece3cbaf225d9a9bbce38c15256a2c4a1385846e7b6479fd5aa90`.
The fixture base is `6ab186d687e48ac977e82e87b9acd11ad2b2bf8b`, with the exact
diagnostic fixture sources retained. Actual renderer is DirectX, grid 160x48,
font SarasaTermSC Nerd Font Light, left-side tabs and the dense workload warmup.

The original, uninstrumented acceptance attempt fails on close cycle nine:
baseline 547 handles / 39 GDI / 50 USER becomes 549 / 39 / 53 after 2.0044
seconds. USER exceeds its allowance. The full memory workload was not reached,
and the inner private job terminates five remaining processes. The outer job's
empty state does not turn that into successful natural cleanup. The original
failure and its early memory samples are retained, not replaced by later runs.

## Read-only inventory: no reproduction of that failure

The full inventory diagnostic completes nine groups and all twelve close
cycles in 60.179 seconds. Baseline is 474 / 37 / 37. Cycles one through eight
return exactly to it; cycles nine through twelve report 476 / 37 / 38. Handle
types increase by one Event and one IoCompletion. Window handles, retained thread
identities and loaded-module identities do not change across these milestones.
All window snapshots are error-free. Seventy-three menu snapshots and thirteen
retired-seat checks verify the existing host/submenu ownership assertions.
All 56 inner and 58 outer processes exit naturally.

This is a different process-wide initialization state and does not reproduce
the original +3 USER failure. It identifies the types of the two extra kernel
handles, not their creators. It is not evidence of a fix or fresh memory
acceptance, and it does not account for non-window USER objects such as timers.

## Bounded REA trace: a different resource failure

One additional freshly owned instance pauses after warmup for REA attachment,
then keeps the same baseline/close assertions. The staged fixture explicitly
marks injected observation and no memory acceptance. The probe observes Event
and IoCompletion create/open calls, closes of those observed generations, and
USER timer set/kill calls with process-wide counters and at most sixteen return
addresses. It changes no arguments or return values. Bounds are 4,096 events,
45 seconds, and a 210-second outer controller; fixture gates are bounded too.
The expected evidence is a creation stack for a surviving handle. Resource
assertion failure, target exit, truncation or script error is retained as a
failed/partial observation, not rerun to obtain a pass.

REA session `def0888c-69dd-48fd-8962-7db6bf136d30` attaches to owned PID 37268.
Probe SHA-256 is
`90a4568363d2030399ef668fc5409970df96256c06ca88bf3e3ddb0528c7b295`.
Complete status Evidence
`ev_05e87fe6ecdb2ab64cc3a8c43525fa825d962d28233320525683b55b1465e847`
retains 119 events in six messages, without provider truncation or script errors.
The fixture fails on its first close cycle: 575 / 39 / 49 becomes 583 / 39 / 51
at 2.0134 seconds, exceeding the OS-handle allowance. It retains five-process
inner-job forced cleanup; the eleven outer processes are gone at controller
completion. REA reports detached and its session is explicitly closed. No final
probe-duration marker is received because the fixture ends first; the capture
is partial and may omit its final unflushed event batch.

The surviving handle-type delta is Event +3, File +1, IoCompletion +1, Section
+1, Semaphore +1, Timer +1. No extra HWND appears; one new thread starts in
shcore.dll. Two observed Event creations at values still present in the later
snapshot have KERNELBASE/shcore call stacks; one includes USER32/DUser, and the
other occurs on that new shcore thread. Another matching value has already been
closed in the trace, demonstrating why handle-value matching alone cannot prove
object identity. No IoCompletion creation call is captured. Selected API hooks
do not cover all kernel/duplicate paths, and injection changes timing and counts.

This narrows the observed creation paths in this one diagnostic. It does not
attribute the original failure, the uninstrumented Event/IoCompletion pair, or
every added USER object. Earlier timer evidence remains separately documented in
[the menu investigation](tab-menu-lifetime.md).

The [manifest](owned-resource-inventory-validation.json) retains canaries, exact
diagnostic sources/controllers, original failure, full window/handle/thread
samples, continuous memory samples and complete selected REA records. The full
local REA export includes unrelated earlier captures and is deliberately not
published wholesale. Compressed and uncompressed hashes are verified.
