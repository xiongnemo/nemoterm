# IMM input, Unicode byte reads and DPI

The native frontend now uses the actual byte count from the second
`ImmGetCompositionStringW` call. Failed, odd, growing or over-budget reads send
no text; commits allocate at most 64 KiB. Composition boundaries reset a pending
WM_CHAR surrogate. WM_UNICHAR accepts valid UTF-32 scalars and the capability
probe, using the same ordinary/kitty text path as other committed text.
Font initialization also updates an active IMM composition font after DPI or
font changes.

This follows Microsoft's [byte-count contract](https://learn.microsoft.com/en-us/windows/win32/api/imm/nf-imm-immgetcompositionstringw)
and preserves the default [composition UI handling](https://learn.microsoft.com/en-us/windows/win32/intl/wm-ime-composition).

## Baseline evidence

The installed single EXE at commit `90d4eb0` has SHA-256
`7f73ad19089f583fac169eedd5f35cda3d6c6dd38ce3073a5d437f457e1fd873`.

- `ime-short-read-baseline.json`: REA/Frida attached to a newly owned terminal.
  A controlled IMM query reports 10 bytes, then the result read reports two.
  The old frontend sends `nihao` instead of `n`. The test writes a known tail,
  proving the ignored return count without relying on uninitialized memory.
- `unicode-input-baseline.json`: a real console child uses WriteConsoleInputW
  and ReadFile with one-byte destinations. `A中🙂B🧪é` becomes
  `A中��B��é`. The record includes expected and observed UTF-8 bytes and the
  executable hash. Frontend WriteFile instrumentation separately showed correct
  UTF-8 before the host converted it.

## Source-host changes

The pinned Microsoft Terminal source is
`f6de9e0618015def1c9dda5b82f9d3abf03eb799`.
The reproducible overlay in `scripts/prepare-single-exe.py` changes
`src/host/inputBuffer.cpp/.hpp` and `src/host/stream.cpp`; the upstream submodule
stays unmodified. Raw byte reads previously converted individual UTF-16 units.
The overlay retains one leading surrogate until the next unit, caches any
UTF-8 bytes that do not fit, and waits when no byte has been emitted. Internal
stream reads preserve this decoder state instead of switching to event mode.
Public read-mode changes, input flush and reinitialization clear the pending
unit. The existing batch-conversion slow path also advances by UTF-16 units,
not Unicode scalar count. Persistent additional state is one wchar_t per input
buffer; the pair conversion uses bounded stack storage.

## Reproduction and limits

`tests/input_method_window_smoke.py` attaches Frida only to its own frontend PID.
It covers short/error/cancelled/invalid-size IMM reads, a 64 KiB commit, Chinese,
supplementary and combining text, kitty text encoding, WM_UNICHAR and composition
boundaries. Synthetic WM_DPICHANGED transitions 96/144/192/120/96 check cursor
and Sixel pixels, IMM font size and composition position. Real IMM API submission
is attempted only with a compatible installed IME and recorded separately.
Frida is a test dependency, is not shipped, and its instrumented working sets
are not used for the product memory budget.

`tests/unicode_input_window_smoke.py` uses 1/2/3/4/7/1024-byte destinations in
raw, VT raw and cooked console input. It checks exact UTF-8, delayed surrogate
partners, orphan leaders, input flush and no premature zero-byte read. Cooked
reads exercise batch conversion across supplementary scalars. All fixture
processes and registry profiles are private to the test and cleaned up.

The source-linked CI runs these groups as part of 28 single-executable checks.
The MinGW comparison bundle uses a published Microsoft host and is not claimed
to contain the source-host correction. Physical IME typing/candidate selection,
actual monitor-to-monitor DPI changes, other layouts and full grapheme shaping
remain separate acceptance work. The local desktop has one 96-DPI monitor.

Validation status: the baseline failures and frontend DPI correction are
reproduced locally. Full source-host validation is pending the new CI build.
