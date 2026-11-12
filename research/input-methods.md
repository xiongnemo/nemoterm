# IMM input, Unicode byte reads and DPI

The single executable now preserves committed Unicode through IMM and the
source-built OpenConsole byte-input path. Short IMM reads no longer send stale
tail characters; WM_UNICHAR supports valid UTF-32 scalars and its capability
probe. Active IMM composition fonts follow terminal font/DPI changes.

## Accepted artifact and validation

Source commit: `badf932e75e083a072fb232b44debcc6dc108263`.
The installed `dist/nemoterm.exe` is the downloaded CI artifact, 4,307,968 bytes,
SHA-256 `25d734ce58418509d423d7091f76c5efe23821759fbee929bc16176e8bf7a892`.
The directory contains only this file. It embeds 79,365 bytes of complete
license notices, uses the same image for its hidden host, and extracts no host
or DLL at runtime. It still uses Windows system DLLs and ConDrv.

- [Single-executable CI](https://github.com/xiongnemo/nemoterm/actions/runs/43180077492):
  all 28 native validation checks passed. Artifact `13925999291`; build/test
  evidence `13926900211`. Twenty-eight JSON observations/manifests containing
  artifact hashes matched the downloaded file.
- [Core CI](https://github.com/xiongnemo/nemoterm/actions/runs/43180077387):
  28 Windows core suites and 11 terminal ASan/UBSan suites passed.
- The exact final artifact passed local isolation, input-method, Unicode-byte,
  mouse, margin/resize and six-shell groups. Input-method testing used Sarasa
  and included a real IMM API submission through the installed Chinese IME.
  All 24 console byte-read combinations passed; CI used installed Consolas
  and correctly recorded its lack of a compatible IME.
- REA parsed all 79 import descriptors (598 regular and 11 delayed functions)
  without issues. There are no `conpty.dll`, `WebView2Loader.dll`,
  `vcruntime*.dll` or `msvcp*.dll` entries. This is static table evidence,
  not a runtime call trace.

`input-method-checkpoint.json` binds CI, local results and installed identity.
`input-method-observed.json`, `unicode-input-observed.json` and
`input-method-dpi.png` retain final-artifact observations.
`input-method-pe-evidence.json` retains the complete REA import result.

Uninstrumented frontend peaks during 300 repeated image splits/scrolls and
font/grid resizing were 10,006,528 bytes private working set, 32,813,056 total
working set and 11,771,904 private commit. The isolated hidden host separately
sampled 1,597,440 / 10,559,488 / 2,326,528 bytes. These are different workloads
and processes; they are not an aggregate lifetime peak. No working-set trimming
was used. Frida-instrumented memory is excluded from budget measurements.

An earlier diagnostic artifact passed 27 local checks, but its OSC 52 delayed
clipboard fixture missed `ready`: another read triggered rendering 1.4 ms after
publication, before the test sent a terminal query. That local attempt is not
reported as passed. Its exact event sequence remains in the checkpoint JSON;
the final artifact's independent CI OSC 52 test passed.

## Baseline evidence

The old single EXE at commit `90d4eb0` has SHA-256
`7f73ad19089f583fac169eedd5f35cda3d6c6dd38ce3073a5d437f457e1fd873`.

- `ime-short-read-baseline.json`: REA/Frida attached to a newly owned terminal.
  A controlled IMM query reports 10 bytes, then the result read reports two.
  The old frontend sends `nihao` instead of `n`. The test writes a known tail,
  proving the ignored return count without depending on uninitialized memory.
- `unicode-input-baseline.json`: a real console child uses WriteConsoleInputW
  and ReadFile with one-byte destinations. `A中🙂B🧪é` becomes `A中��B��é`.
  Expected/observed UTF-8 and executable identity are recorded. Frontend
  WriteFile instrumentation separately showed correct UTF-8 before the host
  converted it.

## Implementation

The frontend follows Microsoft's [IMM byte-count contract](https://learn.microsoft.com/en-us/windows/win32/api/imm/nf-imm-immgetcompositionstringw)
and preserves default [composition UI handling](https://learn.microsoft.com/en-us/windows/win32/intl/wm-ime-composition).
It allocates at most 64 KiB for a commit, uses the second call's actual length,
and rejects failed, odd or oversized results. Composition boundaries clear a
pending WM_CHAR surrogate. Font initialization updates the IMM composition font.

The pinned Microsoft Terminal revision is
`f6de9e0618015def1c9dda5b82f9d3abf03eb799`.
The reproducible overlay in `scripts/prepare-single-exe.py` changes
`src/host/inputBuffer.cpp/.hpp` and `src/host/stream.cpp`; the upstream submodule
stays unmodified. Raw byte reads previously converted individual UTF-16 units.
The overlay retains one leading surrogate until the next unit, caches UTF-8
bytes that do not fit and waits when no byte has been emitted. Internal stream
reads preserve decoder state instead of switching to event mode. Public
read-mode changes, input flush and reinitialization clear the pending unit.
The existing batch-conversion slow path advances by UTF-16 units, not scalar
count. Additional persistent state is one wchar_t per input buffer; pair
conversion uses bounded stack storage.

## Reproduction and remaining limits

`tests/input_method_window_smoke.py` attaches Frida only to its own frontend PID.
It covers short/error/cancelled/invalid-size IMM reads, a 64 KiB commit, Chinese,
supplementary and combining text, kitty encoding, WM_UNICHAR and composition
boundaries. Synthetic 96/144/192/120/96 DPI transitions check the cursor and
Sixel in the same newly scaled frame, plus IMM font size and composition
position. Real IMM API submission runs only with a compatible installed IME.
Frida is a pinned test dependency and is not shipped.

`tests/unicode_input_window_smoke.py` uses 1/2/3/4/7/1024-byte destinations in
raw, VT raw and cooked input with processing enabled/disabled (24 combinations).
It checks exact UTF-8, delayed partners, orphan leaders, input flush and no
premature zero-byte read. Cooked reads exercise batch conversion across
supplementary scalars and the appropriate CR or CRLF suffix. Test processes and
registry profiles are private and cleaned up. UTF-8 tests explicitly select
CP_UTF8; they do not depend on the runner's default console codepage.

The MinGW comparison bundle uses a published Microsoft host and does not contain
the source-host correction. Physical IME typing/candidate selection, actual
monitor-to-monitor DPI changes, other layouts, full grapheme shaping and the
remaining terminal protocol families remain separate acceptance work. The local
desktop has one 96-DPI monitor. IMM API submission and synthetic messages do not
certify physical interaction.
