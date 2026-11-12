# Shell mark implementation notes

Work in progress on `feature/shell-marks`. Core implementation and regression
tests are in progress. Native menu actions and configurable shortcuts are wired;
cloud end-to-end acceptance is pending.
Local interactive tests are paused by
the user's request; use GitHub-hosted execution until the user resumes them.

## Verified protocol and source boundaries

* [Windows Terminal](https://learn.microsoft.com/en-us/windows/terminal/tutorials/shell-integration)
  defines OSC 133 A/B/C/D as prompt start, command start, output start and command
  finish. D may carry an exit status. The useful outcomes are prompt navigation
  and selection of command text/output, not merely consuming the sequences.
* [VS Code](https://code.visualstudio.com/docs/terminal/shell-integration)
  additionally documents OSC 633 A/B/C/D, E with escaped command text and optional
  nonce, and P properties. `Cwd` is already implemented; `IsWindows` and
  `HasRichCommandDetection` are not. An unverified nonce never authenticates a
  command. Metadata must not trigger execution or modify shell profiles.
* OSC 1337 SetMark is a navigation mark. CurrentDir/RemoteHost are already
  implemented. It should not invent an output range for an unknown command.
* Pinned Microsoft's `AdaptDispatch::DoFinalTermAction` processes OSC 133 inside
  the host, while `ConhostInternalGetSet::NotifyShellIntegrationMark` is empty.
  `DoITerm2Action` also recognizes SetMark. However, `_stream.cpp::WriteCharsVT`
  forwards the original string after `ProcessString`, with only its recorded
  injections and newline translation. Dispatcher recognition does **not** mean
  the raw sequence is consumed. No duplicate forwarding overlay is warranted
  by this source. Confirm exactly-once delivery with native cloud tests.
* `terminal.c::do_osc` now dispatches main-screen OSC 133/633/1337 marks alongside
  the existing working-directory handler, with a 16 KiB overflow bound.
* `NemoReflowPoint` currently maps the current and saved cursor during streaming
  reflow. Completed rows are immediately compressed, avoiding a whole-paragraph
  allocation. New marks must preserve that bound, including zero-length marks
  beyond the last nonblank cell and wide-character wrap boundaries.
* Row changes are centralized mainly in `scroll`, `term_size`, `nemo_reflow`,
  `erase_lots`, `insch`, screen swapping, scrollback clearing and reset. Partial
  horizontal margins and rectangle operations also require an explicit policy.

## Storage and movement implementation to validate

The lazily allocated table holds at most 256 records with A/B/C/D cell positions,
optional signed 64-bit exit status and up to 4 KiB decoded command text each,
within a 64 KiB retained text allocation budget. This avoids adding a
field to every character in the grid and scrollback. Record source positions;
selection continues to use the terminal's existing logical-to-rendered handling.

Coordinate anchors move with full and partial scrolling, history eviction,
height changes and width reflow. Reflow sorts at most 1024 anchors and maps them
in the existing streaming pass. Anchors are positions, not per-character tags:
ordinary overwrite, erase, ICH/DCH and rectangular cell copies do not duplicate
or move them. Selection reads the current cells at these positions. Removed rows
invalidate anchors; lost history permanently clips them, even after enlargement.
RIS clears the table; DECSTR retains it. Alternate-screen marks are ignored and
main-screen marks survive a TUI visit. A clipped range contains retained history
only. Native selection menu items display `(Truncated)` for clipped ranges and
are disabled when there is no usable range, including on the alternate screen.

Alternative: semantic fields in `termchar` naturally follow copying/reflow but
increase every cell and require compression/equality changes. They do not alone
represent empty prompts or distinguish copied fragments. Microsoft's TextBuffer
uses both row marks and per-attribute MarkKind; that source is useful comparison
evidence, not a drop-in data model for the PuTTY core.

## Required completion checks

The Shell Integration menu offers previous/next prompt and command/output
selection. `Window / Bindings / Commands` configures their shortcuts; all four
start disabled. Selection populates the local clipboard and the normal Copy
shortcut writes it to the system clipboard. Navigation chooses a record;
ordinary scrolling clears that target and selection then chooses the latest
usable range. An evicted target falls back to the latest retained record.
Inactive/alternate-screen behavior, duplicate
marks, aborted/empty commands and missing/out-of-order events must be deliberate.

Core tests must cover fragmented BEL/ST streams, malformed/overflow input,
signed/absent exit statuses, escaped command text, metadata budgets, history
eviction, CR/progress output, wide/combining text, reflow, resize, partial scroll,
erase, reset and main/alternate isolation. Sanitizers must exercise lifetime and
repeated mark churn. Native cloud tests must verify host passthrough, exact copied
Unicode ranges, pixel selection and memory; hardware/local tests remain paused.
Keep unsupported 633/1337 subcommands in the protocol ledger rather than labeling
the entire OSC families complete.

## Validation history

First core revision `0a57a38` passed the Windows core suites in run
[43231572145](https://github.com/xiongnemo/nemoterm/actions/runs/43231572145).
The Unix sanitizer job stopped at compilation because the new test's `setup`
helper conflicted with a Unix declaration. Rename it to `shell_setup` and rerun;
this was not a sanitizer runtime finding. Native actions, settings and metadata
churn are added to both cloud test workflows. No new local runtime test was run.

Revision `30602ae` passed the core and sanitizer suites and the new Windows
native shell-mark test. Both full workflows then stopped at the existing
hyperlink menu test: its hard-coded row 4 selected Open Link after the new
submenu shifted the entries. Preserve the established copy/link group order
and resolve native test targets by command ID before navigating the real menu.
This was a fixture targeting failure, not evidence of corrupted link metadata.
Runs: [core 43232871703](https://github.com/xiongnemo/nemoterm/actions/runs/43232871703),
[single 43232872026](https://github.com/xiongnemo/nemoterm/actions/runs/43232872026).
The single EXE from this failed run remains unverified and is not promoted.

Revision `75da966` passed both jobs of
[core run 43234950506](https://github.com/xiongnemo/nemoterm/actions/runs/43234950506),
including 30 core suites, 13 terminal sanitizer suites, native shell actions,
truncated-range menu state and settings save/reload. Its MinGW comparison EXE
hash was `19d668034e84d92936bbdf3da03bdb5c19691c11b13045a7d97516b02998a80d`;
the shell fixture observed 5,771,264 private WS / 35,586,048 total WS /
8,609,792 private commit bytes at sampled peaks. These are comparison-build
results, not single-EXE acceptance. Reviewing an earlier cloud capture showed
that a screenshot could precede the deferred selection paint. The native test
now waits for the exact selected-output pixel bounds before capturing evidence.

## Accepted bounded shell integration checkpoint

Application revision `ff693f8292c89c6ebf3a0c82359fca0f6bcc4fbe` passed
[core CI 43236732838](https://github.com/xiongnemo/nemoterm/actions/runs/43236732838)
(30 core suites, 13 terminal sanitizer suites and native regressions) and
[single EXE CI 43236732510](https://github.com/xiongnemo/nemoterm/actions/runs/43236732510)
(37 checks). The downloadable [single executable artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43236732510/artifacts/13952698481)
contains the 4,338,176-byte EXE with SHA-256
`453db4ea641cedf56a8a80b843dc51c2bf5690a5190ad7b22aa0df15a9583571`.

After the user resumed local testing, the exact artifact passed the same 37
check groups in sequential segments, plus both real Codex modes using hardware
OpenGL. [The local manifest](shell-marks-local-validation.json) records the
segments, hashes and limitations. Two test-harness corrections were necessary:
desktop focus changes made an active-cursor assertion compare passive pixels;
the query fixture now models both focus states inside the owned process and
records intercepted events. The old fixed working-set buffer could not sample
a Codex child above 256 MiB; it now follows QueryWorkingSet's required count,
with bounded growth and tests for errors. Neither correction changes the EXE.
Original failures remain in the local evidence hashes; all affected checks were
rerun successfully. The full harness was not restarted from its first test.

Local [shell evidence](shell-marks-local.json) verifies 19 exact-copy cases,
prompt navigation, four width changes with eight copy checks, alternate-screen isolation, metadata
churn and clipped history. Its sampled private WS peak was 7,737,344 bytes.
The selected output [capture](shell-marks-selected.png) agrees with the exact
expected bounds; [settings](shell-marks-settings.png) fit and saved/reloaded all
four bindings. The [cloud shell evidence](shell-marks-ci-shell-marks-observed.json)
has the same EXE hash and a sampled private WS peak of 6,426,624 bytes.

The real Codex 0.167.0 local-response fixtures used SarasaTermSC Nerd Font Light.
GDI default/inline frontend sampled peaks were 7,041,024 / 6,070,272 private WS,
32,878,592 / 27,848,704 total WS, and 8,957,952 / 7,294,976 private commit bytes.
Hardware OpenGL default/inline sampled private WS peaks were 50,032,640 /
44,077,056 bytes, using the user's explicit optional-GPU exception. Each passed
Unicode input, streamed Markdown, 32 live resizes, Shift grid copy and paste.
Host/client samples are separate in the four `shell-marks-codex-*.json` records.
This does not establish live-service or extended agent-session acceptance.

[REA PE inspection](shell-marks-pe-imports.json) reports complete table coverage:
79 descriptors, 605 regular and 11 delayed imports, no parsing issues. The
single-file runtime test verifies same-image console startup without sidecars;
PE imports alone do not establish that no library is dynamically loaded.
DirectX frontend rendering, tabs and the rest of OSC 133/633/1337 remain open.
