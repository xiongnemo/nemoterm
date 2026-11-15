# Portable tab callback exception

[Core run 43755825354](https://github.com/xiongnemo/nemoterm/actions/runs/43755825354)
at `23c90fe` failed its MinGW tab fixture after completing five groups. The
requested OpenGL/right/160x48 case used actual GDI. After detaching the
key/failure/hover probes, selecting the first tab timed out; the frontend had
exited with `0xc000041d`. All 54 owned processes had exited naturally. The
exception code and phase do not identify the failing callback. No terminal
exception stack or WER event was captured. This is separate from that revision's
Unix NUL conversion failure and from a proven OpenGL renderer defect.

The exact failed portable frontend is 3,962,350 bytes, SHA256
`75c88c5236b53853ea7c992c870fef322822939592b07476d99730a88543663d`,
from artifact `14179250011`. Its source-built host and DLL accompany the local
replays; this does not substitute the accepted single executable.

Six local GDI/right/160x48/Consolas replays passed all nine existing groups with
Frida 17.24.3 and unchanged fixture deadlines. Three used the optional external
exception observer, whose four native controls passed first. Those three saw
only the expected initial debugger breakpoint. All six recorded the host
procedure's original bytes restored after probe detachment, a live frontend
after tab selection, and 54 naturally drained owned processes. The tests used
owned-window messages and did not require physical keyboard/mouse or clipboard.
These finite successes do not reproduce or resolve the original CI exception.

`tab-callback-portable-local-validation.json` hashes the original failure,
compiler/package identity, exact executable and sidecars, six local records,
observer controls, source-matched fixtures and a failed initial helper link
attempt. Their bytes are retained in `tab-callback-portable-local.tar.gz`.

The focused replay workflow now accepts `tabs-mingw` as well as its existing
MSVC case. It requires the selected compiler job to have failed, verifies the
full source commit and executable hash, retains all runtime hashes, and rejects
production-source differences before running. Its MinGW case preserves the
original 160x48 grid. External exception capture remains opt-in and separate
from memory or product acceptance.

[Hosted diagnostic 43758602960](https://github.com/xiongnemo/nemoterm/actions/runs/43758602960)
passes all four external-observer controls and 12 independent lifetimes of the
same failed artifact. Every replay used actual GDI, passed nine groups, restored
the original procedure bytes after detachment, and naturally drained all 54
owned processes. Each recorded one first-chance exception `0x40080201`; none
recorded a second-chance exception or generated a terminal crash dump. These
records do not establish the meaning of that handled exception or the cause of
the original failure. The external debugger changes exception dispatch and
scheduling, so passing diagnostic repeats are not product acceptance.

`tab-callback-portable-hosted-validation.json` indexes artifact `14179114486`
and the byte-verified archive `tab-callback-portable-hosted.tar.gz`. Together
with the local archive it preserves all 18 comparisons and the original
failure without reclassifying that failed CI run as successful.
