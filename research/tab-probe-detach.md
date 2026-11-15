# MSVC tab-fixture access violation after probe detachment

The MSVC diagnostics job in [core run 43652684756](https://github.com/xiongnemo/nemoterm/actions/runs/43652684756/job/132624406615)
at `2f478e7` failed its first repeated tab fixture. The exact sidecar-host frontend
has SHA256 `04339e0b69d0ca57492068380163b28a07fb856921c2d48246b3b9f8bea0bb78`
and is retained in unverified artifact `14136911157`. Product source is unchanged
from the accepted compression checkpoint; this is a distinct executable build.

The fixture completed its first five groups, including 12 resource-return cycles,
keyboard actions, injected creation failures and hover preview updates. After
detaching the key/fault/hover Frida session, the first tab-selection wait timed
out. The frontend had exited with `0xc0000005` (access violation); all 54 owned
processes had exited and cleanup did not terminate survivors. Requested OpenGL
had fallen back to actual **GDI** on this runner. No WER event or dump was retained.
There is no stack proving whether product behavior, instrumentation or another
component caused the fault. This is distinct from the earlier close timeouts.

The uploaded hyperlink observation was already a tracked source file; the failed
job did not reach that command. It is preserved as uploaded, not counted as a
newly passed hyperlink test.

## Exact-image local comparison

Three runs of the unchanged fixture with the original OpenGL/right/88x35/Consolas
arguments passed locally using actual OpenGL. Three additional runs selected GDI
to match the runner's actual backend and also passed. All six naturally drained
54 owned processes. These finite successful repeats do not reproduce or fix the
original access violation.

The opt-in `--probe-boundaries` observer records process liveness and 32 bytes at
the owned host window-procedure entry. The existing hover probe captures its
initial bytes before installing its listener; the controller then performs
bounded read-only snapshots after loading, before/after detachment and after the
first tab selection. It validates the retained process/job, HWND owner and code
range inside `nemoterm.exe`. It does not alter arguments, return values, pixels,
memory thresholds or deadlines, and does not assert the crash's cause.

The initial observer attempt could not resolve the procedure through the
controller's `GetWindowLongPtrW` call and retained observation errors; the native
fixture passed but the observer's separate validation failed. The corrected
observer uses the address already resolved by the existing in-process probe and
checks the executable's module bounds once. This avoids trying to enumerate a
module that may unload during detachment. The API can return a procedure pointer
or a representative handle; failed calls return zero. [Microsoft API reference](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowlongptrw).

Two further exact-image local runs, GDI and actual OpenGL, passed the diagnostic
validation. Both recorded patched entry bytes before detachment, restored original
bytes immediately after it and a live process after tab selection. Every owned
process exited naturally. These observations are finite successes, not evidence
about the missing crash stack from the original runner.

`tab-probe-detach-validation.json` indexes 87 byte-verified original records,
including the failed job, six original replays, the failed first observer and
two corrected observer runs. `tabs-close-replay.yml` now supports this exact failed
MSVC artifact and records the same boundary metadata on a hosted runner. The
diagnostic can run once the selected MSVC job has failed without cancelling the
other jobs still running in that source workflow. The accepted local single EXE
and the original full-goal requirements remain unchanged.

## Hosted exact-image diagnosis

[Focused run 43654728264](https://github.com/xiongnemo/nemoterm/actions/runs/43654728264)
at fixture `6a7ba5a` passed three independent lifetimes of the exact failed image.
All used actual GDI after the requested OpenGL profile fell back, matching the
original runner. Each passed nine interaction groups, recorded patched procedure
bytes while the probe was installed and restored bytes after detachment/selection,
and naturally drained all 54 owned processes. Artifact `14137517841` and 12 raw
records are retained in the validation index. This is a successful diagnostic
comparison; the cause of the original access violation remains unproven.

An [external exception observer](native-exception-observer.md) now provides an
additional opt-in diagnostic. Its handled/fatal-exception and detach/exit controls
pass locally and on MSVC CI; three more exact-image hosted replays pass while it
is attached. It is not enabled for product memory acceptance, and these passes
still do not explain the original missing fault stack.
