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
build's frontend checks. Local MinGW validation passes; the fixed MSVC single
image and the unchanged native caption sequence still require hosted replay.
The reproduction's unintended double clicks and off-screen caption candidates
are deliberately unchanged for this comparison. Correcting preparation before
replaying the product fix would remove the original trigger.

This candidate is not an accepted distribution and does not resolve the separate
historical MSVC tab-selection crash. Complete CI, native fixed-image replay and
exact-product local acceptance remain required.
