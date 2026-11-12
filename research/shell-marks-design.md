# Shell mark implementation notes

Work in progress on `feature/shell-marks`. No shell-mark implementation or
acceptance is claimed by this document. Local interactive tests are paused by
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
  `DoITerm2Action` also recognizes SetMark. The overlay must preserve these
  sequences through ConPTY to the frontend, using the original pinned source
  and `scripts/prepare-single-exe.py`; do not edit the submodule directly.
* `terminal.c::do_osc` currently passes 633/1337 only to `nemo_cwd_update` and has
  no OSC 133 handling. The string-size/overflow path must be considered as well.
* `NemoReflowPoint` currently maps the current and saved cursor during streaming
  reflow. Completed rows are immediately compressed, avoiding a whole-paragraph
  allocation. New marks must preserve that bound, including zero-length marks
  beyond the last nonblank cell and wide-character wrap boundaries.
* Row changes are centralized mainly in `scroll`, `term_size`, `nemo_reflow`,
  `erase_lots`, `insch`, screen swapping, scrollback clearing and reset. Partial
  horizontal margins and rectangle operations also require an explicit policy.

## Candidate storage approach to validate

Keep a bounded, lazily allocated command/mark table with A/B/C/D cell positions,
optional exit status and bounded decoded command metadata. This avoids adding a
field to every character in the grid and scrollback. Record source positions;
selection continues to use the terminal's existing logical-to-rendered handling.

Coordinate anchors must move with full and partial scrolling, history eviction,
height changes and width reflow. For reflow, sort the bounded anchor list and
map it in the existing streaming pass rather than searching every mark for every
cell. Preserve erased/retained-history semantics, zero-width endpoints and
one-column wide-character rows. A command whose leading output has left bounded
history needs a visibly truncated range, not an unbounded hidden text copy.

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
