# DirectX startup window-resource observations

The original two retained unmodified-image resource failures remain unresolved. The
`18e912d` failure changed from 492 handles / 37 GDI objects / 43 USER
objects to 549 / 39 / 56 on the ninth post-close sample, before the full memory
workload. Its five remaining owned processes required forced cleanup. See the
[original record](alignment-reset.md); the observations below do not replace it.

Three bounded diagnostic runs use that exact downloaded EXE and the same
160x48 Sarasa, two-tab setup. They preserve all three original resource
assertions, stop after the twelve temporary-tab cycles and intentionally exit 2
instead of reporting acceptance. No target code is injected, input-language
settings are unchanged, and only freshly owned PIDs are inspected.

Two runs use a process-filtered, out-of-context
[WinEvent hook](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwineventhook)
for window creation/destruction. The callback stores window class, thread,
parent and module metadata, without reading window titles or calling application
code. The observer thread pumps messages and unhooks before it exits. The
second run additionally compares
[class callback addresses](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getclasslongptrw)
against the target's loaded module address ranges. Opaque callback handles and
system thunks are left unresolved.

The third run installs no event hook. It samples owned top-level, child and
[message-only windows](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-findwindowexw)
every 50 ms. Its create/destroy labels mean first/last observation, not exact
event times; windows shorter than the sampling interval may be missed. Module
metadata is read at named snapshots rather than on every poll. Each observer
has event/snapshot/enumeration limits, reports truncation/errors and joins on
shutdown. All three observers stopped without errors or truncation.

| Diagnostic | Observation | Baseline | Resource-phase outcome |
| --- | --- | --- | --- |
| 02 | 72 WinEvents | 543 handles, 39 GDI, 56 USER at 1.393 s | 12 cycles pass |
| 03 | WinEvents plus class callback ranges | 543 handles, 39 GDI, 56 USER | 12 cycles pass |
| 04 | 62 observed transitions in 103 snapshots | 543 handles, 39 GDI, 56 USER at 1.445 s | 12 cycles pass |

All three start their comparison with the larger resource set already present.
The `UIM`, `UIMCOM` and `UIMCW` window families appear before that baseline:
roughly 0.26 seconds in the event traces and by 0.33 seconds in the passive
snapshot trace. In run 03 their class callback addresses fall within the loaded
module named `msctfuimanager.dll`. A class's declared module can instead be the
EXE, so that field alone is not treated as proof of the code handling the window.
Other observed classes include `CicMarshalWndClass`, `MSCTFIME UI`,
`NativeHWNDHost`, `Mode Indicator Button` and message-only COM windows.

These results identify concrete input-manager window initialization to capture
if it coincides with the next failing resource jump. They **do not prove the
original failure's cause**, a resource leak, or identical timing without an
observer. Neither original failure had this before/after window metadata. No
resource tolerance, baseline or product behavior has been changed to pass.

Each diagnostic completes two functional groups, not the full nine-group
workload. Its 31 inner-job and 33 outer-job members drain naturally; startup-only
memory samples remain diagnostic and are not a 25 MB result. The
[manifest](dx-window-resources-validation.json) retains all three complete
observations, exact fixture/observer versions, module mappings, samples and
cleanup records. The next useful observation is metadata during an actual
low-baseline-to-high-count failure, rather than more unchanged passing repeats.

## Subsequent exact-image failure and sequence controls

The downloaded `f079f80` image repeats the same low-baseline-to-high-count failure
on its ninth post-close sample. A failure-only fixture extension takes passive
window/module snapshots **after the original sample already fails**, before the
unchanged assertion and cleanup. No observer runs before that sample. The
snapshot includes 18 windows and maps the three UIM class callbacks into
`msctfuimanager.dll`, but has no baseline window set. This confirms their presence
at failure, not that they caused it. The [relative-cursor record](relative-cursor.md)
retains the exact fixture, samples, observer and five-process forced cleanup.

Since the failures followed full GDI workloads, two bounded sequence controls
use that same image and unmodified GDI fixtures followed by diagnostic DX fixtures.
Pair 01 prepares both fixtures before GDI; pair 02 copies the DX fixture only
after GDI finishes, matching the original copy order. GDI passes all nine groups
in both controls. Both DX runs already have the larger 543 / 39 / 56 resource
baseline, complete 12 cycles without exceeding the original resource limits,
then stop intentionally with exit 2. They are two-group diagnostics, not full
memory acceptance. All 31 inner and 33 outer DX job members drain naturally.

The DX fixtures enumerate only owned window classes/PIDs/threads at baseline,
with an 8192-message-window bound; they install no event hook or target code.
The 18-window baseline sets already include UIM families. Failure-only module
observation and eight additional diagnostic cycles are prepared but never run,
because neither control fails. The original failed sample and baseline would
remain unchanged for the assertion even if those extra observations ran.

| Pair | Counts immediately before baseline enumeration | Immediately after | DX resource outcome |
| --- | --- | --- | --- |
| 01, fixtures prepared together | 543 handles, 40 GDI, 55 USER | 543 / 40 / 55 | 12 cycles pass |
| 02, DX copied after GDI | 543 handles, 40 GDI, 55 USER | 543 / 39 / 55 | 12 cycles pass |

The sequential count samples are not atomic snapshots; they do not show a
query-induced upward jump. These negative controls do not prove the copy order
or GDI predecessor caused the original failures. Their complete logs, fixture
versions, observations and cleanup add 28 files to this manifest, now 56 files.
The separate unmodified DX full-workload follow-up reaches **30.63 MB** and fails
the 25 MB gate; its complete record remains in the relative-cursor manifest.
