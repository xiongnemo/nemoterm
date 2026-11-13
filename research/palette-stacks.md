# Palette stacks and title-stack positions

The development frontend implements `CSI Pm #P` (XTPUSHCOLORS), `CSI Pm #Q`
(XTPOPCOLORS), `CSI #R` (XTREPORTCOLORS), and `CSI #S` (XTTITLEPOS). Applications
can temporarily change the implemented text palette and restore it without
reprinting their text. Palette restoration invalidates renderer caches and
respects synchronized presentation. This is a protocol checkpoint, not a
full-goal completion or promotion of the accepted main executable.

## Reference and behavior

The independent reference is [XTerm 412, source
5c75ead9a75d4b2e666ca06fa94503b5766ed93f](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f).
The current reference executable was verified as SHA-256
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
The [specification](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html),
`misc.c::xtermPushColors/xtermPopColors/xtermReportColors`, and the parser
provide the documented and implementation behavior. A private Xvfb display
captured [101 exact cases](palette-stack-evidence/xterm.json); no replies were
rewritten or excluded. The generated C and native fixtures retain those bytes.

Some details require the runtime reference rather than a loose reading of the
specification:

* An omitted push argument increments the current index. Explicit zero saves
  at the current index and then seeks to zero. Arguments 1–10 save a specific
  slot and set the index to that argument; other values are ignored.
* A pop restores an existing slot and seeks to its zero-based index. Slots
  remain available for later indexed reads. Missing slots do not move the
  index. Multiple arguments execute in order.
* `CSI #R` returns `CSI ? used ; last #Q`. The high-water field `last` follows
  ordinary pushes, not the number of allocated slots or indexed writes.
* RIS, DECSTR and alternate-screen changes preserve these stacks. The warm
  oracle cases explicitly initialize all slots and indices; RIS alone would
  not isolate them. Empty parameters, zero, out-of-range values, colon syntax,
  cancellation, overflow and levels 61–65 are included.

Palette snapshots allocate only when written. They retain all 262 entries of
the implemented terminal palette, including 256 indexed colors and PuTTY's
six default/bold/cursor slots. Ten snapshots contain 7,860 color bytes, plus
88 bytes of x64 stack metadata and allocator overhead. Empty reads and invalid
writes allocate nothing. Terminal destruction frees every snapshot. These
controls did not add OSC 5/6 or 13–19 operations, or modify the independent
Sixel palette. The subsequent [selection-colour development](selection-colours.md)
adds OSC 17/19 and eight bytes to each allocated snapshot; that later change
has build evidence only and has not passed this checkpoint's runtime gates.

## Title overflow correction

`CSI #S` reports the logical title-stack depth and ten retained slots. The
previous implementation clamped depth to ten; this gave the wrong position
after eleven pushes and changed which indexed title could be restored after
overflow. The counter now tracks logical pushes while the same ten string
slots remain bounded. A push at `UINT_MAX` is refused atomically rather than
wrapping. No extra strings are retained. This supersedes the earlier deliberate
depth-clamp difference in [the title-stack checkpoint](window-controls.md).

The oracle covers depths through 32, pop underflow, indexed access, reset,
alternate screens, malformed reports and indexed writes interleaved after
overflow. Existing title update/query policies remain; a position reply
contains counts only. The 4096-byte limit per saved title field is unchanged.

## Validation

The local single-image candidate is SHA-256
`2deba6c22973f24439e92de7e1a304e57d5719e21698835ae05e71abcb4de332`.
It was built with the source-linked OpenConsole/ConPTY host. The accepted
`dist/nemoterm.exe` on main is unchanged. The [manifest](palette-stack-validation.json)
binds the 4,430,848-byte image, source files, raw captures and logs. Source
records contain both raw workspace and LF-normalized hashes; evidence files
retain their exact captured bytes.

* 35 MSVC core suites, six MinGW core suites and five Linux ASan/UBSan suites
  passed. Linux now builds the OSC color suite too, including all 101 cases,
  every palette entry's round trip and 5,000 push/pop overflow iterations.
* GDI, actual DirectX and actual OpenGL each passed all 101 wire comparisons
  through the owned native ConPTY path with SarasaTermSC Nerd Font Light.
  Eight pixel checkpoints per mode verify restoration without rewriting text,
  indexed underline/default colors, Sixel retention, synchronized presentation,
  resizing and 1,000 further save/restore cycles. GPU capture observes retained
  renderer frames and uses instrumentation; it is not physical-display or GPU
  memory acceptance.
* The existing 23 native title-stack checks and 87 title-mode checks passed.
* Copying only this executable into a new empty directory passed the isolated
  single-image test: embedded licenses, same-image console host and a delegated
  shell that outlives its launcher all worked, with no extra deployed files.
* The updated GDI image passed the longer two-tab workload: 455 uninstrumented
  samples over 49.228 seconds, **14,815,232 private WS bytes (14.82 MB / 14.13
  MiB)** and 36,917,248 total WS bytes (36.92 MB / 35.21 MiB). Private commit
  peaked at 16,998,400 bytes. Host/client and whole-tree sums are retained
  separately; summed working sets count shared pages more than once.
* Palette, title and workload runs drained their owned jobs naturally; the
  isolated single-image test also returned cleanly. No global input, local
  clipboard access or working-set trimming was used.

Initial harness mistakes are recorded in the manifest, not counted as passes:
an extra GPU-capture argument, a missing Unicode vector argument, absent Linux
test targets and a WSL command whose outer shell expanded its loop variable.
The final sanitizer run uses an explicit script and `wsl --exec`, with a
separate completed log per suite. This avoids treating a shell exit status as
proof that the intended tests actually ran.

Both CI workflows include the new native fixture; the main workflow also
checks generated cases and runs the color suite under ASan/UBSan. For source
commit `1251fc62fd1a2b9769e2574e6b636137ce9f8109`, the
[test/build run](https://github.com/xiongnemo/nemoterm/actions/runs/43402441704)
and [single-image run](https://github.com/xiongnemo/nemoterm/actions/runs/43402441424)
were both rejected before any step started. GitHub reports an account payment
or spending-limit problem; both runs have zero artifacts. These failures do
not validate or invalidate the code; remote CI acceptance remains open.
The existing DirectX memory failure,
clipboard/real-agent work, physical devices and remaining protocol families
are still open. This change does not relax any memory gate.
