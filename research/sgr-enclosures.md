# Framed and encircled rendition

The independent `feature/sgr-enclosure-20261114` branch implements SGR 51
(framed), 52 (encircled) and 54 (clear both). Core, sanitizer, three-renderer
pixel and real-ConPTY wire checks pass. The full local GDI workload passes;
the DirectX workload fails its original resource-retirement assertion before
the memory exercise. This branch is not the accepted distribution. CI and
downloaded-image validation remain pending.

## Semantics and implementation

[ECMA-48, fifth edition](https://ecma-international.org/wp-content/uploads/ECMA-48_5th_edition_june_1991.pdf),
section 8.3.117, printed pages 61–62, defines these rendition values.
The downloaded 1,607,865-byte PDF has SHA-256
`9577ad2514c411584b274ef7a4b3238c80aa93defbb349b18b8c78f78873f450`.
The names and cancellation codes come from the standard; the following pixel
geometry is an explicit Nemoterm policy, not an XTerm pixel-parity claim.

Each logical character cell or combining cluster gets its own outline. A wide
character uses its complete two-cell width; double-width lines scale the width,
and double-height line pairs clip one continuous tall outline. Frames and
ellipses are independent aspects and can be combined. Their color follows the
foreground, including inverse/selection/cursor handling. Conceal hides them;
the separate underline color does not recolor them.

Product commit `58985da` uses two spare bits in the existing 64-bit decoration
field, without increasing character-cell storage. The ten-entry, lazy SGR stack
uses a wider selector mask. Selective stack selectors 51 and 52 are Nemoterm
extensions, like the existing overline selector 53. Full and selective restores,
DECRQSS and common-rectangle rendition queries preserve/report these aspects.
Reset and ordinary cursor/alternate-screen state use the existing style paths.

Rendering uses the existing GDI text surface with a stock pen and null brush,
then the existing OpenGL/Direct3D upload paths. It allocates no additional
per-cell bitmap or persistent GDI object. The saved device context restores
clip, pen and brush state after drawing.

## Verification and limits

The new core tests first fail against the original implementation. After the
change, `test_sgr`, `test_queries`, `test_state_control` and `test_rectangle`
pass on Linux, under ASan/UBSan with leak detection, and under Windows MSVC.
They cover combined aspects, cancellation, malformed colon groups, selective
and full stacks, cursor/alternate-screen restoration, soft/hard reset,
protected metadata and compressed-history/reflow style lifetime.

The local single executable is 4,510,208 bytes, SHA-256
`2f65d99323df10e1f381662a652782d8033c5938d6c3b4eefcb77a3d83bb8c9a`.
It links freshly built frontend libraries with the previously validated host
objects; the input hashes and link command are retained. It is based on
`c88dc7e`, without the separate Sixel palette/background changes.

- The downloaded old `9c22311` image passes the original 16 renderer scenes,
  then fails the first independent frame-edge pixel assertion, as expected.
- The new image passes all 18 scenes in each actual renderer: GDI, OpenGL and
  DirectX. Frame perimeter/interior, ellipse extrema/corners/interior,
  combination, cancellation, conceal, inverse color, wide/combining text,
  double width and double height have independent geometry assertions.
- The real ConPTY path passes 193 unchanged XTerm reply cases and 46 explicit
  extension cases, including 17 new enclosure cases. The extension cases are
  not represented as XTerm reference replies.
- Renderer comparison uses existing owned-process capture instrumentation;
  it is not a memory acceptance measurement. The before/after renderer jobs
  and wire job exit naturally, with no remaining owned processes.

The unchanged full tab workload uses SarasaTermSC Nerd Font Light and verifies
actual 160x48 grids. GDI passes nine groups, with 464 samples and peaks of
16,396,288 bytes private working set, 43,180,032 total working set and
18,800,640 private commit. All 56 inner / 58 outer processes exit naturally.
Memory sampling precedes pixel-helper injection and does not trim working sets.

DirectX fails on the second post-close cycle: handles 489 -> 540 (allowance +6),
GDI objects 37 -> 38 (+3), USER objects 40 -> 54 (+2). Both tracked I/O workers
are signaled. The test stops before the history/frame workload; its 57 early
memory samples do not establish DirectX memory acceptance. The inner job
terminates its five remaining test-owned processes after the assertion; the
outer controller then finds no survivors. The original failure and diagnostics
are retained, and none of the resource thresholds are relaxed.

A separate diagnostic run reproduces the 489 -> 540 handle transition. At the
same transition it records new `msctfuimanager.dll`, `DUser.dll`, `DUI70.dll`,
`UIAnimation.dll` and installer-related modules, a thread starting in
`msctfuimanager.dll`, and hidden `NativeHWNDHost` / `Mode Indicator Button`
windows on that thread. The 51-handle delta consists of 19 events, 10 ETW
registrations, five timers, five threads, four semaphores, four I/O completions,
three files and one registry key. Handles remain at 540 throughout 20 subsequent
samples over 3.7 seconds; USER objects mostly settle at 50, still above the
original baseline. This is evidence of delayed per-process input-method UI
initialization coinciding with the failed resource sample, not proof assigning
every object to a component. No object names or payloads are read.

The paired accepted-image diagnostic starts with these windows/components
already present and completes the original checks. Both diagnostics are
explicitly marked non-acceptance; they add bounded, read-only metadata queries
and retain the original failed sample for assertion. No global input-method
setting changes, global input, existing-session attachment or target injection
are added. A deterministic lifecycle baseline still needs separate validation.

The first full core CI at `8431e82` fails its generated-fixture consistency
check: the new Python direct cases had not been regenerated into
`tests/sgr_stack_oracle_cases.h`. Its sanitizer and MSVC diagnostic jobs pass,
but that does not make the core workflow successful. The 17 missing generated
entries are now added using the existing generator, which passes `--check`.
`test_queries` with the regenerated entries passes ordinary Linux,
ASan/UBSan/LSan and MSVC builds. The unchanged XTerm capture is not regenerated
or edited, and the product image is unaffected by this test-data correction.
The original [failed run](https://github.com/xiongnemo/nemoterm/actions/runs/43556854787)
is retained. The corrected commit passes both full workflows; the
[downloaded-artifact checkpoint](sgr-enclosure-ci.md) records successful local
rendering/wire/GDI checks and the still-failing local DirectX resource gate.

The [evidence manifest](sgr-enclosures-validation.json) retains original logs,
pixels, sent/replied wire records, image provenance, resource failures and
cleanup records with decompressed SHA-256 checks. These are local observations,
not REA-server Evidence IDs. Ideogram SGR 60–65 and exhaustive compatibility,
font/DPI combinations and long-session behavior remain separate work.
