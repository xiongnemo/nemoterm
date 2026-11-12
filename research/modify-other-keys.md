# xterm modified-character keys

This checkpoint implements `modifyOtherKeys` (resource 4). Other xterm keyboard
resources and Windows input mode 9001 are separate outstanding work.

## Independent reference

The reference executable was built from Thomas Dickey's official source mirror,
commit [`5c75ead9a75d4b2e666ca06fa94503b5766ed93f`](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f).
It reports `XTerm(412)`; that revision's control-sequence document still labels
itself patch 411. Source archive SHA-256:
`f4e74e560f0a7a1d225dc5bc27decc4b67af4ed38fdfc773fe53e87d4656fbe7`.
The locally built Linux executable SHA-256 is
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.

The raw observations are in [xterm-mok-reference.json](xterm-mok-reference.json).
The harness creates an isolated Xvfb server, addresses only its own xterm by PID
and window, and reads bytes from a raw PTY child. It does not send physical input
or use the user's X display. Resources enable synthetic events and ESC-prefixed
Alt/Meta, and select DEL for Backspace. These resource choices are part of the
reference, not a claim that all xterm installations use identical defaults.

Reproduction on Debian/WSL, after installing the Xaw/Xt/X11/Xft/ncurses development
packages, Xvfb, xdotool and base X fonts:

```sh
# In a checkout of the pinned source revision:
./configure --disable-setuid --disable-setgid --disable-tek4014
make -j6
# In the Nemoterm checkout:
python3 tests/xterm_mok_reference.py --xterm /absolute/path/to/xterm
```

Primary references are the [control-sequence specification](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html),
[modified-keys rationale](https://invisible-island.net/xterm/modified-keys.html),
and the pinned source's [input.c](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/input.c)
and [charproc.c](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/charproc.c).
Nemoterm's encoder is an independent implementation, using the specification
and observed outputs as fixtures.

## State and encoding

`CSI >4;level m` selects levels 0 through 3. An omitted level restores the saved
initial value; `CSI >m` resets the supported resource. `CSI >4n` disables it,
and `CSI ?4m` returns `CSI >4;65535m` while disabled, matching the reference.
The state is shared by the main and alternate screens. Resize and cursor
save/restore preserve it; RIS restores the initial configuration.

Level 1 preserves traditional control aliases and ESC-prefixed Alt/Meta while
encoding additional combinations such as Ctrl-period and Ctrl-Tab. Level 2
encodes modified character keys, including shifted alphabetic characters;
ordinary shifted punctuation such as `!` remains literal. Level 3 also encodes
unmodified character input. Function, cursor and keypad keys retain their
existing translators. Local commands retain priority.

The default form is `CSI 27;modifier;codepoint ~`. `CSI >4;1f` selects
`CSI codepoint;modifier u`; even an unmodified character includes `;1`.
The modifier parameter is one plus Shift=1, Alt=2, Ctrl=4, Super=8. CapsLock
and NumLock affect lookup but are not included in this wire parameter.

`CSI >4;level:mask m` uses X11 state bits: Shift=1, CapsLock=2, Ctrl=4,
Alt/Mod1=8, NumLock/Mod2=16, Windows Super/Mod4=64. A sole ignored modifier
suppresses reporting in levels 1/2; combinations retain their modifier
parameter while using the factored character. The ordinary query omits the
mask; DECRQSS `>4m` returns it when nonzero. Setting a level without a mask
clears the mask. No unbounded key history or per-event allocation is added.

## Explicit platform and reference differences

* The specification documents format query `CSI ?4g`, but this reference
  parser handles `CSI >4g`. Nemoterm accepts both.
* The reference's DECRQSS answer to `>4f` ends in `m`. Nemoterm returns `f`,
  so the response can restore the format using its documented setter.
* The reference ignores the inline spelling `CSI >4:mask m`; its implemented
  mask belongs to the second parameter. Nemoterm follows that implemented form.
* XKB maps Shift-Tab to the distinct `ISO_Left_Tab` keysym, producing `CSI Z`
  in some reference cases. Windows supplies Tab plus Shift; at level 2,
  Nemoterm follows the character-key rule and sends `CSI 27;2;9~`.
* xterm's local translations can consume combinations such as Alt-Return.
  Nemoterm's local settings similarly take precedence; its native fixture
  disables the fullscreen binding to inspect the terminal encoding.

## Windows verification and bounds

`test_mok` covers fragmented negotiation, malformed/cancelled/overflowing
sequences, exact replies, configuration resets, mask semantics, encoding
bounds and kitty coexistence. Windows cases call `ToUnicodeEx` with explicit
US, US International, German and Russian layouts without activating them.
Preview uses the no-state-change flag; only a handled key commits the
translation, leaving dead keys for the legacy path when appropriate.

`tests/mok_window_smoke.py` verifies bytes delivered through the bundled ConPTY,
including repeats, Unicode/surrogate/IME character messages, kitty priority,
focus cleanup, synchronized output, resize, Shift-local selection under SGR
mouse mode, and Ctrl+Shift+C/V bracketed paste. It samples memory every 25 ms
without trimming the working set and captures only its own window with
PrintWindow. CI also runs a saved level-3/CSI-u configuration using Courier New.
Synthetic IME character messages do not validate a real IME candidate window.

Protocol state is 8 bytes per terminal. Each character encoding uses a bounded
32-byte stack buffer; the Windows multi-scalar path uses at most 512 bytes.
The existing approximately 12 KiB physical-key tracker is allocated on demand
and shared with kitty. Further physical-keyboard, IME and real application
validation remains necessary.
