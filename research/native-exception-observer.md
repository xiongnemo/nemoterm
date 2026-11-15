# External exception capture for the unresolved tab crash

The earlier MSVC access violation still has no fault stack. Finite successful
replays in [the original record](tab-probe-detach.md) do not establish its cause.
An optional test-only external Windows debugger now retains first/second-chance
exception metadata, module load addresses, the faulting thread context and a
small minidump on an unhandled exception. It is not linked into Nemoterm.

The helper accepts inherited handles to one live process and its private fixture
job, validates membership itself, and attaches only to that process. It continues
the initial attach breakpoint, returns other exceptions to Windows/application
handling, and disables debugger-exit termination before signaling readiness.
It closes debug-event image-file handles and leaves system-owned debug process
and thread handles to the documented event lifecycle. All debug API calls run
on the same helper thread. The dump includes thread/unloaded-module information,
not a full-memory capture. References: [attach events](https://learn.microsoft.com/en-us/windows/win32/api/debugapi/nf-debugapi-debugactiveprocess),
[debugger exit behavior](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-debugsetprocesskillonexit),
[event handle lifetime](https://learn.microsoft.com/en-us/windows/win32/api/debugapi/nf-debugapi-waitfordebugeventex),
and [external dump capture](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/nf-minidumpapiset-minidumpwritedump).

Four dedicated native controls pass with strict-warning MinGW builds: a handled
custom exception followed by ordinary exit; a deliberate write to an inaccessible
page, observed on both chances and retained in a valid exception-stream dump;
normal detach while the target remains alive; and forced debugger exit after
readiness while the target remains alive. Each control's private job drains
naturally. These are small purpose-built control programs, not terminal crashes.

The exact failed frontend (`04339e0b...bea0bb78`) passes nine tab groups on local
GDI and actual OpenGL with the debugger and existing Frida probes active. Both
drain all owned processes naturally and report no second-chance exception.
This still does not reproduce or fix the original CI crash. Debugger attachment
changes scheduling and exception dispatch, so these results cannot establish
uninstrumented behavior or be used for memory acceptance.

`tabs_window_smoke.py --exception-observer <helper.exe>` rejects memory/resource
observer combinations. The focused artifact replay workflow has an opt-in
`capture_exceptions` input, compiles the helper on its disposable MSVC runner,
and requires all four controls before replay. Ordinary product/acceptance tests
continue without this debugger. The validation manifest retains raw local logs,
control dumps, both exact helper executables and the fixture source snapshot.
[Hosted run 43657368739](https://github.com/xiongnemo/nemoterm/actions/runs/43657368739)
at `6449919` passes strict MSVC compilation, all four native controls and three
independent lifetimes of the exact original failed image. Each replay used GDI
after the requested OpenGL mode fell back, passed all nine groups, observed
ordinary process exit and naturally drained 54 owned processes. There was no
second-chance exception or terminal dump. The hosted raw records and control
dumps are retained separately in `hosted.tar.gz` (artifact `14138227152`).
