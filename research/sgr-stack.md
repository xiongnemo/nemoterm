# Rendition stack and rectangular SGR reports

The development frontend now implements `CSI Pm #{` / `CSI Pm #p`
(XTPUSHSGR), `CSI #}` / `CSI #q` (XTPOPSGR), and
`CSI Pt;Pl;Pb;Pr #|` (XTREPORTSGR). These are independent of the existing
current-state DECRQSS `m` query. This record does not establish complete
xterm compatibility or replace the accepted executable on `main`.

## Independent reference

The reference is [XTerm 412, pinned source
5c75ead9a75d4b2e666ca06fa94503b5766ed93f](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f).
The [control-sequence specification](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.txt),
`misc.c` (`xtermPushSGR`, `xtermPopSGR`, `xtermReportSGR`,
`xtermFormatSGR`), and `charproc.c` supply the documented/parser behavior.
An isolated Xvfb instance ran the reference executable; its SHA-256 is
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.

`tests/xterm_sgr_stack_oracle.py` records 199 raw cases in
`sgr-stack-xterm.json`. `generate_sgr_stack_oracle.py` retains 193 exact
wire expectations. Six cases involving `4:2` or `4:3` and all/4/4;21
selection are explicitly excluded because this XTerm ignores modern
underline substyles. Their original replies remain in the raw capture;
14 separately authored extension cases cover Nemoterm's modern styles,
underline colors and combinations. No captured reply is rewritten.

## Behavior and storage

* A parameterless push saves all supported rendition attributes. Explicit
  zero saves no attributes but still occupies a frame. Selectors include
  bold, faint, italic, single underline, blink, inverse, conceal, strike,
  double underline and foreground/background (30/31, with aliases 10/11).
* The stack retains ten frames. Overflow consumes only a saturating
  64-bit counter; matching excess pops do not restore an earlier frame.
  A single fixed allocation is made on the first push and freed when the
  stack drains or the terminal is destroyed. An unused stack costs one
  pointer in the terminal, with no allocation.
* RIS, DECSTR, SGR reset and alternate-screen switches retain the stack,
  matching the reference. The two screen buffers share it. DECSCA
  protection, occupancy, hyperlinks and cursor state are not SGR state.
* Single underline and legacy double underline are independent. Bit 31
  of the existing decoration field stores the latter; cell size and
  compressed-history field width are unchanged. A legacy double line
  takes visual precedence, while popping selector 21 can reveal an
  underlying modern curly/dotted/dashed line. SGR 24 clears both.
* Parameterless pushes also save the modern underline color. Selective
  pushes preserve the current underline color on pop. Rectangle reports
  include modern styles/colors only when common to the queried cells.
* Rectangle bounds use the active grid and DECOM origin/margins. The
  report intersects stored cell attributes without moving the cursor,
  clearing selection, consuming pending wrap/grapheme attachment or
  expanding sparse rows. Reply allocation is bounded by the supported
  attributes, not rectangle area. Indexed colors use colon syntax.

The reference also exposed a BCE error: erased cells lost foreground RGB
and the bright foreground resolved from bold-color policy. The erasure
template now preserves these colors while removing rendition flags.
This matters when a later rectangle operation applies inverse video.
Related checksum checks now enforce the VT420 operating-level gate for
XTCHECKSUM selection and clear its flags on DECSCL 61–65. This is not a
claim that every DECSCL reset side effect has been implemented.

## Validation and boundaries

`sgr-stack-validation.json` identifies the exact source files, executable,
compiler tests and native evidence. The executable is isolated at
`build/local-sgr-stack-check/dist/nemoterm.exe`; the accepted main
distribution remains untouched.

Core tests compare all 193 reference and 14 extension replies using
fragmented input. They also exercise 5,001 nested pushes, overflow/drain
behavior, allocation reuse/release, retained selections, pending wrap,
combining marks, sparse rows, and checksum level/reset behavior.
The SGR suite covers independent underline flags through compressed
history and resize. The Linux SGR target is now available to sanitizers.

The owned native `sgr_stack` fixture uses the single-image host and checks
all 207 wire cases, resized/origin-relative corners and 30 read-only
repetitions. GDI pixels prove legacy/modern double-underline equality,
selective restoration of curly underline, underline-color restoration,
joint reset, and RGB erase followed by inverse. The renderer fixture
also includes legacy double and selective-pop scenes in GDI/OpenGL/
DirectX comparisons. Its instrumentation overhead is separate from
the uninstrumented SGR fixture's memory samples.

The SGR fixture sampled a root-window private working-set peak of
6,594,560 bytes and total working-set peak of 28,102,656 bytes (initially
80×24, resized to 83×22). These are sampled peaks for this bounded
scenario, not a 160×48, whole-process-tree or real-agent memory guarantee.
All three processes in its private job exited naturally.

Native clipboard/RTF export and real-Codex tests were not run locally;
their existing CI gates remain mandatory. The RTF exporter retains its
previous generic-underlining treatment for legacy double underline;
full modern RTF style export remains unimplemented. Physical IME,
long GPU workloads and the previously recorded CI tab-close crash also
remain separate acceptance work.

CI checks generated fixtures, runs core/Sanitizer SGR tests, and requires
the new single-executable native fixture. Hosted run startup and artifact
availability must be checked for the resulting commit; local success
does not imply GitHub Actions ran.
