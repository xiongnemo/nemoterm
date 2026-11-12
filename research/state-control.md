# Soft reset and saved terminal state

The implementation adds DECSTR (`CSI ! p`) and XTSAVE/XTRESTORE (`CSI ? Pm s/r`)
to the PuTTY-derived core. It also supplies DECNKM 66, homes the cursor when
DECOM changes, reports CPR rows relative to the origin region, and restores
the saved origin flag with DECRC. This is a bounded extension to the existing
mode set, not a claim of complete DEC/xterm conformance.

## Independent reference

`tests/xterm_state_oracle.py` runs a separate XTerm on a private Xvfb display,
using a real PTY for input and replies. It never injects input into the user's
desktop. The checked-in [raw results](state-control-xterm.json) identify
XTerm 412, executable SHA-256
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
The source baseline is
[xterm-snapshots 5c75ead9](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f),
especially `charproc.c` (`ReallyReset`, `savemodes`, `restoremodes`) and
`cursor.c`. The [control-sequence reference](https://invisible-island.net/xterm/ctlseqs/ctlseqs.txt)
and [DEC VT510 manual](https://vt100.net/docs/vt510-rm/DECSTR.html) define the
protocols. Microsoft's
[SoftReset implementation](https://github.com/microsoft/terminal/blob/f6de9e0618015def1c9dda5b82f9d3abf03eb799/src/terminal/adapter/adaptDispatch.cpp)
provides an additional implementation comparison.

To repeat on a Linux system with Xvfb and a built XTerm:

```sh
python3 tests/xterm_state_oracle.py --xterm /path/to/xterm --output /tmp/state.json
```

## State lifecycle

DECSTR restores normal attributes and indexed palette entries, clears insert
and origin mode, restores full vertical margins, resets G0/G1 designations and
the active screen's saved cursor to home. Wrapping, application cursor/keypad,
cursor shape/blinking and modifyOtherKeys return to configured defaults.
The live cursor position and pending wrap survive. Other preserved state
includes visible cells, compressed history, images, current screen, other
screen's saved cursor, tab stops, UTF-8, reverse video, mouse tracking/encoding,
focus reports, bracketed paste and kitty/Win32 transports. Dynamic foreground,
background and cursor colours survive. Current OSC 8 marking ends; existing
cells retain their links. Synchronized presentation remains frozen until its
normal release or timeout.

The mode cache contains 21 integers (84 bytes), with no allocation or stack:
1, 3, 5, 6, 7, 8, 9, 12, 25, 47, 66, 80, 1000, 1004, 1005, 1007, 1070, 2004,
2026, 8452 and 9001. Unknown or locally prohibited modes have no effect.
It starts at zero, saving overwrites the relevant slot, and RIS/DECSTR preserve
it. Mouse modes 1000–1003 share the full tracking value; X10 mode 9 has a
separate slot. Encodings 1005/1006/1015/1016 share a full integer. Alternate
screen aliases 47/1047/1049 share the screen flag; restoring it switches buffers
without the clearing/cursor side effects of directly setting 1049. Mode 1048
saves/restores the existing cursor slot instead of a Boolean value.

The reference experiment exposed two deliberate differences: XTerm 412 leaves
dim and strike-through set after soft reset, whereas NemoTerm resets all SGR
attributes; XTerm's saved mouse encoding is narrowed through an 8-bit Boolean
on restore, whereas NemoTerm retains the complete encoding, including 1016.
NemoTerm also saves its existing autorepeat mode and newer 2026/9001 extensions
where supported; the reference XTerm build does not implement all of them.

## Verification and limits

`test_state_control` checks fragmented sequences, active/alternate cursor
slots, origin and changed margins, palette/configured defaults, preserved
text/history/Sixel/link metadata, cache aliases and overwrite/reset lifecycle,
local policy, pending wrap, cancellation, malformed parameters and 20,000
unknown save/restore requests. It runs on Windows and under Linux ASan/UBSan
with leak detection. `test_modes` also checks mode 66's set/reset/query bytes.

`tests/state_control_window_smoke.py` launches an owned native window with the
pinned bundled ConPTY. It compares PrintWindow pixels before and after DECSTR,
checks actual child input after keyboard/mouse reset and restoration, moves
the window and checks pixel-coordinate increments, and verifies exact Shift
selection text through the real clipboard. Queries also verify origin/CPR,
alternate-screen cursor restoration and preservation of a synchronized frame.
Results and a screenshot are CI artifacts. Private working set, total working
set and private commit are sampled without trimming; ConPTY/child processes
are separate from the measured terminal.

The cache does not add unsupported modes. Complete G2/G3 cursor-state handling,
left/right margins, selective erase, rectangular editing, physical input/DPI
and long-running real-agent acceptance remain separate open work.
