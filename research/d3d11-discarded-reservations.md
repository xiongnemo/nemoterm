# Reuse DirectX staging space after fully clipped draws

Three [caption-control runs](bell-caption-control-failure.md) stop at the same
47-check boundary during the DirectX normal-window profile. The third run,
[43783402188](https://github.com/xiongnemo/nemoterm/actions/runs/43783402188),
attaches the controlled external debugger only to the standalone cover process.
Its four observer controls pass. The cover records a first-chance write access
violation (`0xC0000005`), followed by a second-chance `0xC000041D` and a retained
379,711-byte dump. The two earlier runs did not use this debugger. The cover
process is not injected with the tab host's Frida probe.

In the exact failed EXE, the faulting RVA is `0x13df80`, an aligned 32-byte store
inside the optimized memory-clearing routine. The first raw stack word is
`nemoterm.exe+0x1237eb`; disassembly immediately before that address contains a
call to the clearing routine in a loop matching `nemo_d3d11_begin_run` and its
staging-strip fields. The retained parser labels stack words as candidates,
not an unwound call chain; the small dump does not include the renderer's heap
object, so its full allocator state cannot be read back from that dump.

Source inspection identifies a bounds defect independently. Reserving a text
rectangle advances the strip packing position. If the final rectangle lies
outside the visible frame, `queue_copy` discards it without adding a GPU copy.
When later reservations exhaust the strip, `flush_batch` sees zero copies and
returns without resetting the packing position. `reserve_run` then returns a
rectangle beyond the strip, which `begin_run` clears before drawing.

The fix resets the packing position at the exhausted-strip allocation boundary,
after a successful flush, even when there were no copies. It deliberately
preserves empty `flush_batch` behavior elsewhere: overlay readback can flush
while a current reservation is still live. No allocation, dependency, renderer
state field or GDI behavior is added.

`test_d3d11_reservations.c` includes the actual production allocator. It creates
no window or GPU device and checks bounds before any pixel access. With the
old source, its third 64x16 reservation returns `(0,32)` in a 64x32 strip and
fails safely. With the fix, **10,012** discarded rectangles of varied sizes
remain in bounds; an additional overlay control verifies that an empty flush
does not reset a live reservation. Both tests use the same test-source hash.
The archive and validation manifest `d3d11-reservation-controls*` retain exact
old/new source, binaries, compiler identity, logs, dump interpretation and
disassembly. Initial build-configuration and link errors are documented.

The regression is part of Windows core build/test commands and the single-EXE
build's frontend checks. Local MinGW validation passes. The [fixed-image
bell-native run 43787972196](https://github.com/xiongnemo/nemoterm/actions/runs/43787972196)
builds one 4,549,120-byte EXE (SHA-256
`68424c75540640f6f37f8027d98985ddc65c82d2e66d00631439abc6faac93fd`)
and passes all 74 GDI/DirectX bell-state checks, with 48 natural process exits.
The same image then passes the forced real-caption control in
[run 43796351005](https://github.com/xiongnemo/nemoterm/actions/runs/43796351005):
45 actual caption clicks, 74 checks and 48 natural exits. The first forced
caption run at this source, 43796085724, also passed the 74 native checks and
44 clicks but the controller failed afterward because it required a
`cursor_restored` record on every click. That record is conditional: Windows
may move the pointer during activation. The corrected assertion remains strict
on real focus, exact replies, process exit and bell behavior. Original ZIPs,
member hashes and source/image identities are retained in
`d3d11-fixed-hosted-validation.json`.

The reproduction's unintended double clicks and off-screen caption candidates
were deliberately unchanged for this comparison. Correcting preparation before
replaying the product fix would remove the original trigger. A later
[on-screen replay 43796940288](https://github.com/xiongnemo/nemoterm/actions/runs/43796940288)
uses the same fixed image and passes 74 checks with 44 titlebar clicks, all
within the virtual screen, and 48 natural process exits. Fifteen repeated
clicks were spaced by the system double-click interval. Four click results
still show maximized windows, so the spacing is not claimed to eliminate
maximization; the renderer remains stable through those changes. The original
artifact and member hashes are retained in `on-screen-caption-60d50b6-validation.json`.

The exact product source `f3b5b6539fede4f13dfb2ef12c1ec9e1657a8fd8` has
now passed [ordinary CI 43796092526](https://github.com/xiongnemo/nemoterm/actions/runs/43796092526)
in all four jobs and [single-image CI 43796089119](https://github.com/xiongnemo/nemoterm/actions/runs/43796089119)
in all 167 native check groups. The isolated 4,549,120-byte executable has
SHA-256 `de2f9e105e9186cb99fd925f8824e0573ae144ff62954b63ab3cda7c15ff0d28`.
The ordinary CI's densest GDI Unicode/Kitty tab workload recorded a frontend
private working-set peak of 14,065,664 bytes, total working-set peak of
44,990,464 bytes and private-commit peak of 17,076,224 bytes, with no sampler
errors. These values describe the CI workload and its frontend process, not
every possible local screen and font configuration.

`d3d11-product-ci-validation.json` records the exact run, source, executable,
check identities and verified artifact receipts. The three original GitHub
ZIPs `d3d11-product-ci-{core-evidence,single-evidence,product}.zip` are retained;
their GitHub SHA-256 digests, 9,095 ZIP member hashes and extracted receipt
hashes were checked. This candidate is not an accepted distribution. Exact
product local/physical acceptance and the separate historical MSVC
tab-selection crash remain open; main and `dist/nemoterm.exe` are unchanged.
