# DEC user-defined key reference

The independent reference is complete for the cases below. Nemoterm does not
yet implement DECUDK downloads or dispatch; its current unavailable-status reply
remains truthful. This checkpoint changes only reference tests and evidence.
Local interactive testing remains paused.

## Reference and original failure

[Run 43716642922](https://github.com/xiongnemo/nemoterm/actions/runs/43716642922)
at `9b798e25007929ea7d7bda957cd163d3eb654661` passes **91 fresh cases, 238 steps
and three literal controls** against unmodified XTerm(412), pinned to
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f`. Each case uses an 80x24 VT525 window,
measured 6x13 cells, two-pixel padding and real XTest key events on an owned
private Xvfb display. All 91 XTerm children exit naturally without stderr.
Two DSR barriers delimit each step; complete received bytes and physical input
actions are retained, rather than reconstructed from authored expectations.

The main keyboard profile is `keyboardType:vt220` with `ctrlFKeys:12`; a separate
case retains the default profile. The literal controls verify unlocked status,
the downloaded `ABC` value on Shift+F6, and the unchanged unshifted F6 sequence.
The fixture records its own hash, the shared harness hash, upstream revision,
executable hash, generated configuration and seven upstream source files.

The first [run 43716161735](https://github.com/xiongnemo/nemoterm/actions/runs/43716161735)
at `f743c91` stops at F13 because the default virtual keyboard has no keycode for
it. Its first 16 completed cases remain byte-for-byte identical in the passing
run. The replacement only assigns missing F13-F20 symbols to unused keycodes on
the private display, before creating any XTerm. It records the complete keyboard
map before and after, plus the actual keycodes used by every case. An owner
connection prevents Xvfb from resetting that map between cases. No desktop or
keyboard mapping on the user's computer is touched. This uses the documented
[Xlib keyboard mapping interface](https://www.x.org/releases/current/doc/libX11/libX11/libX11.html#Manipulating_the_Keyboard_Encoding).

`dec-udk-reference.tar.gz` retains **370 records / 668,087 bytes**, including
both original runs and their exact fixture sources. Its companion
`dec-udk-reference-validation.json` indexes and hashes every record. The passing
merged capture SHA256 is
`b6917d91165d635fc7d202be432028faa27104fc62e947ddc4d48c046c2dada3`.

## Observed behavior

- `DCS Ps;Pl | key/hex;... ST` downloads values at DEC level 2 and above. A
  missing or zero first parameter clears prior definitions; tested nonzero
  values retain definitions not replaced in the new command.
- The tested lock parameters do not prevent replacement. `CSI ?25n` reports
  `CSI ?20n`, including after RIS; DEC level 1 has no status response and ignores
  downloads. This follows XTerm's behavior, rather than assuming physical
  DEC keyboard locking semantics.
- Shift+F1 through Shift+F20 select the corresponding downloaded values in the
  VT220 keyboard profile. The default profile instead emits its ordinary
  modified-function-key sequence. With the explicit `ctrlFKeys:12` resource,
  Ctrl+F6 maps to F18, and Shift+Ctrl+F6 can select F18's definition.
- Decoded values retain NUL, DEL, high bytes and escape bytes exactly. The
  observations include lengths 1, 255, 256, 1,024 and 4,096 bytes.
- Payload hex parsing skips nonhex characters; trailing odd nibbles are
  discarded. Empty replacement values preserve old definitions. Duplicate
  nonempty definitions select the last value. Malformed headers, unknown keys
  and missing separators have separate original captures.
- CAN, SUB and a new ESC sequence cancel the pending definition without clearing
  previous definitions. BEL inside the tested DCS does not cancel it. RIS clears
  definitions; DECSTR, DECSCL and alternate-screen transitions preserve them.
  A separate case verifies raw eight-bit DCS/ST framing.

These observations are consistent with the pinned upstream
[DCS parser](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/misc.c),
[keyboard dispatcher](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/input.c)
and [reset/status parser](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/charproc.c).

## Implementation boundary

Do not copy arbitrary downloaded values into PuTTY's fixed function-key output
buffer. Use explicit byte lengths and a separately bounded send path. Storage
must be lazy, bounded per terminal and released on RIS/destruction; cancelled
downloads must not partially clear or replace existing definitions. The tested
4,096-byte value is a reference case, not an established upstream maximum.

Expose VT220 keyboard behavior explicitly rather than silently changing the
existing default or the legacy PuTTY VT400 profile. Establish precedence with
configured local bindings, Win32 input mode and Kitty keyboard mode. Core replay
must compare the unchanged reference bytes in whole and fragmented input, with
direct allocation/cancellation checks. Native ConPTY input, settings persistence,
complete product regression and local acceptance remain pending.
