# DEC user-defined key reference

DECUDK downloads and optional VT220 function-key dispatch are implemented on
the development branch. The independent reference and three-compiler component
replay pass, as does the focused native Windows checkpoint. Complete product
acceptance remains pending.
Local interactive testing remains paused.

The first complete single-image run,
[43718800782](https://github.com/xiongnemo/nemoterm/actions/runs/43718800782)
at `fec0af2`, fails before UDK replay: the isolated fixture directory omitted
`research/dec-udk-reference.tar.gz`. Its preceding Locator and protocol checks
pass, but this run is not accepted as a complete product checkpoint. The
isolation script now copies the retained reference into the fixture's research
directory; the executable directory still contains only `nemoterm.exe`.
The product source and the original expected UDK bytes are unchanged.
`dec-udk-single-first.tar.gz` retains all 4,336 records / 6,956,430 bytes from
that failure, including the unaccepted 4,536,832-byte executable, logs and
preceding test outputs. Its manifest hashes every record. The corrected full
single-image workflow is
[43721295539](https://github.com/xiongnemo/nemoterm/actions/runs/43721295539)
at `23615de`. It passes the 89 UDK cases / 232 exact streams, then hits the
45-minute overall job deadline while the dense Unicode workload is still
advancing (`frame-13 after-window-resize`). GitHub's annotation confirms the
job exceeded 45 minutes. This is incomplete product acceptance.
`dec-udk-single-timeout.tar.gz` retains all 4,518 records / 8,729,798 bytes,
including the original cancellation and unverified executable. The combined
bell/UDK single-image run
[43725867215](https://github.com/xiongnemo/nemoterm/actions/runs/43725867215)
at `f9e6e82` now has a 60-minute total budget, with individual fixture and
shutdown deadlines unchanged. Its result is pending.

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

## Implementation and component evidence

`2a6a163` adds a lazy store, explicit byte lengths and a send path independent
of the fixed function-key formatting buffer. Idle terminals add two pointers
(16 bytes on x64), with no per-cell storage. Pending encoded payloads are capped
at 65,536 bytes, and retained decoded values at 1,048,576 bytes per terminal;
allocator capacity and metadata are additional bounded overhead. Oversized
downloads leave prior definitions intact. Complete commands commit at ST;
CAN/SUB, a different ESC sequence, RIS and destruction release pending input.
RIS and destruction also release retained values. The tested 4,096-byte reference
value is not claimed to be an upstream maximum.

The new `VT220 (UDK)` function-key option is stored as value 7 in the existing
`LinuxFunctionKeys` setting. The default Xterm 216+ and legacy VT400 options
retain their prior behavior. Shift selects downloaded keys; Ctrl accesses the
next twelve function-key positions. The Windows dispatcher evaluates local
bindings and negotiated Win32/Kitty keyboard input before the UDK path. Raw
downloaded bytes bypass C1 framing conversion. DSR 25 now reports unlocked;
the older DEC-status projection includes the unchanged upstream `?25` case
instead of excluding it as an unsupported feature.

[Run 43717926965](https://github.com/xiongnemo/nemoterm/actions/runs/43717926965)
at `f8a20d3` passes GCC and Clang with ASan/UBSan/LSan, plus MSVC. Each compiler
matches all **238 original replies both whole and bytewise** and exercises input
and aggregate budgets, profile changes, binary output and 64 complete/cancelled
reset cycles. Existing Locator, CAN/SUB, ANSI charset, query, keyboard, pointer,
OSC 52, Sixel, SGR, selective erase and termcap regressions pass.

The original [run 43717684952](https://github.com/xiongnemo/nemoterm/actions/runs/43717684952)
passes MSVC but fails the raw eight-bit DCS case on Linux: the fixture changed
the numeric codepage without initializing its byte-mode translation tables.
The corrected fixture initializes ISO-8859-1 tables and disables locale override,
matching the upstream byte-mode case. Production source is identical between
these two runs; no input or expected reply was edited to obtain the pass.
`dec-udk-components.tar.gz` retains **169 records / 768,581 bytes** from both
runs. Its validation manifest records 102 compiler-source hash matches.

The cloud-native fixture projects 89 reference cases / 232 streams
through physical Windows keys and the bundled console host, including both
saved keyboard profiles and Kitty precedence. Two cases remain explicitly
core-only: raw non-UTF-8 framing and arbitrary high-byte payloads cannot be
treated as a byte-preserving path through Unicode ConPTY.

## Native Windows checkpoint

[Run 43718137156](https://github.com/xiongnemo/nemoterm/actions/runs/43718137156)
at `1aff8c8` passes all **89 cases / 232 exact received streams**, the Kitty
precedence/restore checks, and existing DEC status, keyboard, modifyOtherKeys
and Win32 input regressions. The two profile sessions and their owned children
exit naturally. This is real physical input on a disposable Windows CI desktop;
no input was injected into the user's computer.

The 4,536,832-byte single image has SHA256
`94680622004d4489534eddf74d0979ca6ee39e18cb74cd043ec08c5e100d3bfd`.
Its production and single-image build inputs match the passing `f8a20d3`
component checkpoint. `dec-udk-native.tar.gz` retains 47 records / 2,984,933 bytes,
indexed by `dec-udk-native-validation.json`, including the executable, source
inputs, exact observed bytes and cleanup records. Offline validation compares
every native input/action/reply/barrier stream directly to the original capture.

Full ordinary and single-image workflows now include UDK at
`fec0af2b24e952a68f9d1deb20fee28e8273db14` (runs 43718798329 and 43718800782).
The standard `build.ps1 -Tests` target list also now includes both Locator and
UDK, matching the test runner. The first single-image failure and its corrected
157-group run are described above; full single-image and local Sarasa acceptance
are not inferred from the focused native pass.

## Complete ordinary workflow

[Run 43718798329](https://github.com/xiongnemo/nemoterm/actions/runs/43718798329)
at `fec0af2` passes all four jobs, including the complete native UDK projection,
27 Locator phases, 413 earlier ANSI/C0 streams and three exact pixel pairs.
All twelve uninjected tab memory workloads pass; 25,048 Unicode image cells are
checked after memory sampling and all owned jobs exit naturally.

The MinGW frontend is 3,953,182 bytes, SHA256
`fc423c946182026b057f059843c1ed7c5887c7e38dc4c6ac0486637707deea9a`;
the source console host and its overlay inputs have separate verified hashes.
Remote dense GDI at 109x34 peaks at 14,643,200 bytes private working set and
45,563,904 total; DX at 88x35 peaks at 17,813,504 private and 54,857,728 total.
These are remote Consolas workloads, not renewed local 160x48 Sarasa acceptance.
DX's total is informational under the user's clarified GDI-only target.

`dec-udk-ordinary.tar.gz` retains 4,597 records / 9,422,029 bytes. Its manifest
verifies every original UDK input, gesture and received stream against XTerm,
keeps compiler/source-host/artifact identity, and indexes all retained records.
