# Unicode image placeholders: independent reference and baseline

The complete [upstream run 43673330735](https://github.com/xiongnemo/nemoterm/actions/runs/43673330735)
captures **97 cases / 728 states**, including all **297 row/column diacritics**.
Nemoterm's new real-core replay currently fails **681 states across 97 cases**.
This is an implementation baseline, not product acceptance. The accepted
752f3be single executable remains unchanged.

## Reference identity and scope

Fixture source f536f4c58de4103ab5b45e6a3f445f5c1c1f8edb builds unmodified
Kitty 8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f using its upstream CI recipe.
REA 6.8.0 records the compiled parser and graphics manager, normal exit 0,
verified process cleanup and temporary-root removal. Eight upstream controls
pass, covering basic placeholders, image high bytes, multiple placements,
scrolling, reverse scrolling, history margins/fill and relative parents.

The successful observation has SHA256
feda36b2971fbc29059b4c80ddf989c228e8c4b5c18ffe07fb064b05bbd78a44.
The fixture records exact input/reply bytes, cursor, normal-screen text,
image counts before/after layer updates, viewport history offset, geometry,
raw layers, upstream source hashes and compiled-file hashes. Resize and
viewport-scroll calls are explicitly declared actions. Layer updates are
declared observation effects; they can recreate cell images or retire orphans.
This is headless model evidence, not native window/GPU pixels. REA's sampled
process tree and non-atomic prelaunch file-identity limitations remain retained.

The [Unicode-placeholder protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/#unicode-placeholders)
provides the input vocabulary. Cases cover indexed/RGB foreground IDs,
underline placement IDs, all diacritic mappings, inherited coordinates/high
bytes, extra/unrecognised marks, incremental combining input, aspect fitting,
edits, graphics deletion selectors, retransmission, relative descendants,
alternate screens, history and resizing/reflow. Expected geometry is observed
from the compiled upstream, not computed in the fixture.

The initial [run 43673001055](https://github.com/xiongnemo/nemoterm/actions/runs/43673001055)
completed all states and controls, but its 256 KiB rendered-terminal journal
budget omitted 44 frames. The complete observation file was hashed, and process
cleanup succeeded; nevertheless the no-truncation gate correctly failed.
The second run changes only that recorder budget to 2 MiB. The fixture and
assertions are identical. Both captures are retained separately, including the
initial truncation details; only the complete second capture generates tests.

## Strict real-core replay

The generator preserves every state, converts normalized layer coordinates
using each captured window size, and reproduces the declared resize/scroll
operations. Replies and normal-screen text compare directly. Error replies
require the captured ID/status prefix, nonempty detail and the exact terminator.
Text extraction omits blank tail cells like the upstream line representation;
the generator asserts that none of these captured lines ends in a literal space.
The replay also checks cursor, history offset, image count, source/destination
rectangles, z order and the shared image budget.

With production source unchanged from 656fed4, local GCC 16.2.0 builds and runs
the new suite. It exits 1 with 681 failed states, while the earlier relative
suite remains at 233/238. Its executable SHA256 is
a47dcfccc86aaee20e929964100f09bb2b3c45f057b8de043985bf2aa055d2da.
The log, exact fixtures, compiler identity, CMake configuration and source diff
are retained in the baseline archive.

Most failures expose the missing virtual-placement/cell-image path. Six text
assertions also differ in REP, alternate-screen entry and ED 3 scenarios; seven
cursor assertions differ in REP and alternate-screen scenarios. These need an
independent xterm comparison before choosing text-semantics changes. The replay
keeps those observations and does not silently exempt them or classify all
cross-terminal differences as graphics defects.

The implementation must preserve existing text storage and its bounded
combining-character chains, account for derived image metadata, distinguish
invisible templates from text-driven visible cells, and handle invalidation,
history, parent visibility and disposal. Native compositor/pixel, selection,
resize/lifecycle and uninjected single-image memory acceptance remain required.

[kitty-unicode-validation.json](kitty-unicode-validation.json) indexes both
upstream captures and the unchanged-production baseline with per-record hashes.
