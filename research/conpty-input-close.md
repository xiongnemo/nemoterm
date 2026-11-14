# Closing input while draining final console output

The downloaded `c2606cd` image (4,450,816 bytes, SHA-256
`d49b1c5bccd88cc5ab1f8ea34df35793d1266c985650e4c8cf5ea46b4900dd56`)
passed the complete local 848-case relative-cursor fixture in 73.578 seconds
with the corrected periodic traceback observer. Its unmodified Sarasa 160x48
GDI workload also passed nine groups: 15,904,768 bytes private working set,
42,741,760 total, 18,726,912 private commit, 447 samples over 48.340 seconds.
Both controller jobs exited naturally. This does not turn its failed CI green.

Its startup visibility check failed after completing all visibility operations
for the first tabbed case: the client and console host exited, while the frontend
remained. A second, explicitly diagnostic run recorded an owned, responsive
`Nemoterm Fatal Error` dialog whose text was **Error writing to conpty device**.
Only that newly spawned job was terminated for cleanup. No existing terminal or
global input was used.

A separate owned WriteFile observer saw `ERROR_NO_DATA` (232) during one of 12
otherwise successful shutdowns. A query-burst variant saw expected invalid-handle
completions after cancellation. Instrumentation changed the ordering enough that
neither diagnostic run reproduced the modal failure. These observations plus
the backend's unconditional fatal-write handling support an input-close/output-
drain race; they do not identify the exact error code of the uninstrumented
dialog. Failed checks and timing-sensitive successful diagnostics are preserved.

The fix treats only `ERROR_BROKEN_PIPE`, `ERROR_NO_DATA` and
`ERROR_PIPE_NOT_CONNECTED` as the write side becoming unavailable. It frees that
I/O context, closes its handle and clears its backlog. The reader and process
wait stay alive so trailing output and output EOF retain control of session
lifetime. Other write errors retain their fatal path. No wait was lengthened
and no resource threshold changed. This also preserves the delegated-client
rule: an initial launcher exiting does not by itself kill its console children.

The locally rebuilt image is 4,508,672 bytes, SHA-256
`e3c9918d555fbb4fecf91625d3a105ec1fabf928327473d5b4819b45dc788a1c`.
Validation completed with natural cleanup:

- Eight normal/minimized standalone/tabbed cases, including repeated tabbed
  restores and immediate child exit: 16 visibility groups.
- Delegated console child lifetime and last-client exit.
- All six GDI/OpenGL/DirectX child-exit/window-close shutdown cases.
- Mixed renderer tab profiles, 36 switches, retained synchronized frames and
  frontend exit code 0; the fixture now records the exit code before asserting.
- RTL with the bitmap Courier primary font.
- Original full Sarasa 160x48 GDI workload, nine groups: 16,388,096 bytes private
  working set, 43,196,416 total, 19,230,720 private commit; 444 samples over
  48.105 seconds. Inner/outer jobs exited naturally (56/58 processes).

The preceding `9f96fb0` CI runs remain failed: single-image run
[43548927052](https://github.com/xiongnemo/nemoterm/actions/runs/43548927052)
timed out waiting for the Courier RTL frontend to exit; core run
[43548927069](https://github.com/xiongnemo/nemoterm/actions/runs/43548927069)
observed a nonzero mixed-tab frontend exit but did not preserve its numeric code.
No application crash dumps were produced. Neither cloud failure is yet proved
to have the same cause as the locally observed dialog. Three other core jobs
passed. Earlier core run `43546782794` at `c2606cd` completed successfully.

The [manifest](conpty-input-close-validation.json) retains local and selected CI
records, source, link inputs and both failed startup checks. Archives have
verified decompressed SHA-256 hashes. These are local Win32/subprocess
observations, not REA-server Evidence. Full CI and exact downloaded-image
validation remain required before promotion; the root accepted EXE is unchanged.
