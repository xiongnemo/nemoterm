# Preserve minimized startup through ConPTY initialization

A caller requesting minimized startup could see Nemoterm restore itself almost
immediately. The frontend correctly applied the requested show state. The
bundled console host then emitted `CSI 1 t` during creation of its hidden
pseudo-window, and the frontend correctly processed that restore request.

Commit `c2606cd` adds a small source-overlay guard in
`InteractivityFactory::_WritePseudoWindowCallback`: visibility callbacks are
ignored until `CreateWindowExW` has returned and `_pseudoConsoleWindowHwnd` is
assigned. The initial `WM_SIZE(SIZE_RESTORED)` is not an application visibility
request. Subsequent callbacks retain their original behavior. The pinned
Microsoft submodule is unchanged; `scripts/prepare-single-exe.py` applies the
checked replacement to the build copy. No terminal escape sequence is filtered.

## Direct evidence and regression

The downloaded I/O image, SHA-256
`b1a1f25ca3014714b03de2559ce695281b3ef26bc3c2b450f8ca3e85cdceec50`, fails
the new regression when a standalone terminal is requested with show mode 7.
The test waits for the child's DSR acknowledgement through ConPTY before
checking `IsIconic`; it observes a restored window. The failed case's three
remaining processes are cleaned up by its private job; the outer eight-member
job drains. This failure is retained, not retried into a passing result.

A temporary diagnostic frontend records `show=7` and `IsIconic=1` immediately
after ShowWindow, SetForegroundWindow and SetFocus. The window becomes restored
later. Ordinary raw-output logging captures `ESC [ 1 t` as the first ConPTY
output, before device queries and the Python fixture's title. An otherwise
identical image with the source-overlay guard emits no initial restore sequence
and remains minimized until the controller explicitly restores its owned window.

The final local image removes all diagnostic frontend properties. Its SHA-256
is `eeb61feb5e7ca220d9af5850ab6736ad6d087ae6acbb9284f6be7ef74303c7b3`,
4,508,672 bytes. Eight regression groups pass: normal/minimized startup for
standalone and tabbed windows, then explicit VT restore/minimize/restore and
native ShowWindow minimize/restore for each case. All 12 inner / 14 outer
processes exit naturally. Each child operates only on its own console HWND;
no global keyboard/mouse input, existing terminal attachment or IME setting
change is used. CI runs this test against the complete newly built single image.

The local proof uses MSVC 14.44.35207 with the unchanged source-host objects
from the prior pinned build, recompiling InteractivityFactory and the frontend.
Compiler, library and linker response files and input hashes are retained.
It is not a substitute for full CI rebuilding the overlay. The initial frontend
configure failed because it retained CMake's NDEBUG default; the corrected
configuration uses the repository's existing assertion-preserving flags. A
first isolated host-object compile rejected the old precompiled header's PDB
identity; the corrected build compiles that translation unit without that PCH.
The original source-host build files and PDB were not modified.

## Startup resources and full GDI workload

With the guard and a minimized start, the controlled diagnostic remains at
341 handles / 27 GDI objects before restore. After restoring only the owned
window, it reaches 385 handles / 29 GDI objects and adds `NativeHWNDHost` and
`Mode Indicator Button`. USER objects change from 29–30 to 43–44. The 44-handle
increment matches the difference between previously observed startup baselines.
This strengthens the delayed-input-UI initialization hypothesis, but does not
identify each resource's owner or reproduce the original two-tab failure's
exact timing. See the earlier
[startup timeline](https://github.com/xiongnemo/nemoterm/blob/main/research/gdi-startup.md).

The clean local image also passes all nine groups of the unchanged full GDI tab
workload at actual SarasaTermSC Nerd Font Light 160x48. Baseline is 405 handles /
38 GDI / 50 USER; all 12 cycles are 407 / 38 / 52. Across 491 samples over
49.4 seconds, frontend peaks are 16,224,256 private-working-set bytes,
42,893,312 total-working-set bytes and 18,972,672 private-commit bytes. All
56 inner / 58 outer processes exit naturally. Original numerical assertions
and memory limits remain in force; these samples precede pixel instrumentation.

The [manifest](startup-visibility-validation.json) verifies 89 compressed
records, including diagnostic/clean sources, original failures, raw output,
controlled observations, full workload and cleanup. Full
[compiler/core CI](https://github.com/xiongnemo/nemoterm/actions/runs/43546782794)
and [single-image CI](https://github.com/xiongnemo/nemoterm/actions/runs/43546782899)
were still running when this checkpoint was recorded. This change remains on
its research branch. The earlier GDI resource timing gate and proposed worker
wait fixture remain open, and the accepted local distribution is unchanged.
