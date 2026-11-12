# Win32 input protocol checkpoint

Nemoterm implements DEC private mode 9001 as an **opt-in experimental** input
path. Enable `Preserve Windows key events (experimental)` under
Terminal / Keyboard / Extended. `NemoWin32Input` defaults to false and is saved
with the profile. The existing direct xterm input path stays the default.

The protocol follows Microsoft's [Win32 input specification](https://github.com/microsoft/terminal/blob/f6de9e0618015def1c9dda5b82f9d3abf03eb799/doc/specs/%234999%20-%20Improved%20keyboard%20handling%20in%20Conpty.md):
`CSI Vk;Sc;Uc;Kd;Cs;Rc _` carries virtual key, scan code, UTF-16 code unit,
press/release, Windows control flags and repeat count. `Uc` is not a Unicode
scalar; supplementary characters occupy two records. It describes key records,
not an encoding for all Windows input event types.

## Negotiation and coexistence

* `CSI ? 9001 h/l` records the transport request. DECRQM reports set/reset,
  or permanently reset while the profile policy disables it. RIS clears the
  request; main/alternate screens share it. Reconfiguring the policy invalidates
  held raw keys and can apply an already-received request without restarting.
* The bundled ConPTY requests 9001 before launching the child. Native console
  clients receive the resulting records through `ReadConsoleInputW`. VT clients
  receive the console host's selected encoding. The console host handles an
  application's own 9001 request internally; disabling that application mode
  does not disable the outer transport.
* Any active kitty flags take priority over the transport, following the
  [Microsoft input encoder](https://github.com/microsoft/terminal/blob/f6de9e0618015def1c9dda5b82f9d3abf03eb799/src/terminal/input/terminalInput.cpp).
  Nemoterm additionally gives active xterm modifyOtherKeys priority. This is a
  local coexistence policy, not a claim that Microsoft implements that protocol.
* Local copy/paste and scroll shortcuts retain priority. Consumed local keys do
  not acquire a stray raw key-up. Focus loss releases reported held keys once;
  a mode/policy epoch prevents stale releases after disable/re-enable.

## Windows translation and bounds

The adapter preserves left/right Ctrl/Alt flags, Shift, Caps/Num/Scroll lock,
extended-key status, scan code and the message's repeat count. IME/WM_CHAR
committed text uses zero virtual key/scan and preserves UTF-16 units. These
automated messages do not test a real IME candidate window.

The Windows layout translator is stateful on presses and previews releases
without consuming pending dead keys. A multi-character dead-key release preview
does not create duplicate releases. US International composition and German
AltGr are tested without activating a layout globally. Microsoft's
[ToUnicodeEx documentation](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-tounicodeex)
describes these state and preview flags. Alt+numpad composition and further
physical keyboard layouts remain unverified.

Encoding uses a 48-byte stack buffer, emits complete records only, and handles
maximum field values and too-small output buffers. The shared held-key table
uses about 24 KiB, allocated on first enhanced/raw input. No heap allocation is
performed per encoded record.

## Why the default remains off

With pinned ConPTY 1.25.260930003, a raw F24 reaches a console client intact,
but the host drops it when converting to ordinary VT input. Its legacy encoder
maps F5 through F20 only. The native fixture records both outcomes explicitly.
Nemoterm's default direct VT path continues to emit F21–F24, and the original
capability-query/native-key regression remains unchanged. Native 9001 clients
and kitty clients have their own encodings.

Raw transport also bypasses PuTTY's configurable traditional key mappings and
application keypad translation. Therefore enabling it globally would change
existing behavior. The option allows Windows console applications to retain
Shift+Enter/Ctrl+Space and key identity while these integration differences are
still being resolved. This checkpoint does not claim complete keyboard parity.

## Verification

`test_win32_input` covers negotiation, policy/reconfiguration, reset, screen
sharing, parser recovery, bounded encoding, releases and Windows layouts.
`tests/win32_input_window_smoke.py` launches two owned terminal windows in
sequence: one child reads actual console records, the other reads VT bytes.
It checks key metadata/repeats, native F24, Unicode, focus cleanup, Ctrl+C and
Ctrl+Break handlers, resize records, application 9001, kitty/modifyOtherKeys
priority and return to ordinary VT, Shift selection under application mouse
mode and bracketed Ctrl+Shift+C/V paste. No global input injection or layout
activation is used. Clipboard formats are preserved and the temporary profiles
are removed. `PrintWindow` captures only the owned terminal window.

CI adds this core/native group, settings default/save/reload checks, and an
ASan/UBSan core run. Native observations and executable hashes are included in
the test artifact. The existing mouse, resize, reflow and direct VT capability
tests remain enabled.
