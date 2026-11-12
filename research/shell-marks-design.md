# Shell mark implementation notes

Work in progress on `feature/shell-marks`. Core implementation and regression
tests are in progress; native UI and end-to-end acceptance are pending.
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
within a 64 KiB total text allocation budget. This avoids adding a
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
only; a native indication of truncation remains a UI requirement.

Alternative: semantic fields in `termchar` naturally follow copying/reflow but
increase every cell and require compression/equality changes. They do not alone
represent empty prompts or distinguish copied fragments. Microsoft's TextBuffer
uses both row marks and per-attribute MarkKind; that source is useful comparison
evidence, not a drop-in data model for the PuTTY core.

## Required completion checks

Support prompt/output navigation and command/output selection via native menu
actions and configurable bindings. Do not steal existing application shortcuts
without an explicit saved binding. Inactive/alternate-screen behavior, duplicate
marks, aborted/empty commands and missing/out-of-order events must be deliberate.

Core tests must cover fragmented BEL/ST streams, malformed/overflow input,
signed/absent exit statuses, escaped command text, metadata budgets, history
eviction, CR/progress output, wide/combining text, reflow, resize, partial scroll,
erase, reset and main/alternate isolation. Sanitizers must exercise lifetime and
repeated mark churn. Native cloud tests must verify host passthrough, exact copied
Unicode ranges, pixel selection and memory; hardware/local tests remain paused.
Keep unsupported 633/1337 subcommands in the protocol ledger rather than labeling
the entire OSC families complete.
