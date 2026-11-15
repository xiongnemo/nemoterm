# Kitty relative placements: reference and partial implementation

Ordinary relative placements now match the retained upstream cases. The full
replay still fails five Unicode-placeholder states, so this branch is not a
product acceptance. The accepted 752f3be single executable remains unchanged.

## Independent reference

[Run 43669132190](https://github.com/xiongnemo/nemoterm/actions/runs/43669132190)
at fixture source fd252fbce9889090b3b867a3aff7a70393f57783 succeeds. It builds
unmodified Kitty 8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f with its own CI recipe,
then records its compiled parser and graphics manager through REA 6.8.0.
The upstream test_image_parents, test_image_put and test_gr_scroll
controls all pass. The capture contains **60 cases / 238 states**, with original
inputs, replies, cursor positions, image counts before/after layer updates and
raw layers. It exits normally, without truncation, and reports verified process
cleanup and removal of its temporary root.

The observations have SHA256
0382ddf7f09f8c6c7d47f4a751447dabb31ac472c1714a4ce6b4d1bfd4e83d98.
Compiled-file hashes and REA's limitations are retained separately: a prelaunch
digest is not an atomic OS image binding. This is a headless model observation,
not window/GPU pixel evidence. Layer updates are declared observation effects
and may retire orphan references. The fixture does not use the upstream
image_for_client_id convenience lookup: source inspection shows that a miss
creates an image, which would perturb lifecycle observations.

The fixture covers signed cell offsets, parent/child pixel offsets, crop/scale,
cursor suppression, named/anonymous parents, missing/self/cyclic/deep parents,
replacement, deletion families, scroll/history, alternate screens and a virtual
parent with actual Unicode placeholders. The [protocol specification](https://sw.kovidgoyal.net/kitty/graphics-protocol/#relative-placements)
defines the relationship; the captured runtime states determine the concrete
comparison, including edge cases.

## Real-core baseline

The generator retains every state, including unsupported virtual-parent cases.
It only converts normalized coordinates back to the reference's 120x160 pixels.
Successful and empty replies compare byte-for-byte. Errors compare the exact
image/placement ID and status prefix, require nonempty detail and the original
terminator; the upstream wording remains retained without requiring identical
English prose from Nemoterm.

The baseline core, with production source unchanged from 03c1f05, builds under
local MinGW GCC 16.2.0. Its corrected UTF-8 replay exits **1**: **145 of 238 states
fail across 58 cases**. All 60 seed states match, and every assertion failure
belongs to the new replay. The pre-existing 101 image, 36 compression, 176
feature-query and 216 query-error states still pass. This is baseline evidence
of missing behavior, not acceptance.

An initial replay inherited the mock's Latin-1 codepage. Its log and exact
fixture remain separately retained, and are not Unicode-conformance evidence.
The corrected replay sets CP_UTF8 before terminal initialization. Both runs
retain their exact test-executable hashes, fixture bytes, compiler version,
build commands and CMake configuration; neither modifies the distribution.

## Partial implementation and validation

The local real-core replay now matches **233 of 238 states**, compared with
93 at baseline. All 140 newly matching states are retained comparisons; no
reference states or assertions were removed. The remaining failures are
virtual-parent/virtual-root, relative-child, placeholder, earlier-placeholder
and erase-placeholders. The process still exits 1. Earlier image, compression,
feature-query and query-error replays remain passing.

The owner stores parent creation identities rather than borrowed parent
pointers. It resolves at most eight edges using wide signed offset arithmetic,
preserves identity on named replacement, and validates ancestry before mutation.
Each placement adds 24 bytes of metadata on the current x64 layout, charged to
the existing shared budget; ordinary relative placements add no per-cell data.

Deletion first selects every directly affected placement, then retires orphan
descendants. Cache callbacks can release another image's orphan references but
defer the actual removal until the current list mutation is finished. A decode
transaction protects the old image until commit or unwind. Scroll and row-change
loops also defer anonymous-image removal: a callback in the middle of iteration
could otherwise remove the preceding orphan and invalidate the iterator.

Local GCC 16.2.0 release and separate -Wall -Wextra -Werror -pedantic builds pass
the cache (1,982 checks), layout (150) and placement (2,841) component suites.
New ownership checks cover callback non-reentrancy, cascading final-reference
release, surviving independent references, replacement under eviction on both
decode success and failure, read-only queries with a pending orphan, mixed
anonymous/relative scroll and row deletion,
and maximum signed offsets across eight edges. These are authored ownership
tests, separate from the independent upstream comparison.

The first implementation run is retained too: it had the same five real-core
failures and one obsolete layout expectation that Q/H/V without P were rejected.
The expectation was corrected to the captured ignored-key behavior. The full
replay remains strict. Native pixels, sanitizers, other compilers and product
memory are not established by these local component results.

## Hosted validation of 656fed4

[Core run 43672313266](https://github.com/xiongnemo/nemoterm/actions/runs/43672313266)
and [component run 43672313233](https://github.com/xiongnemo/nemoterm/actions/runs/43672313233)
fail at the same five virtual-parent states. Their MinGW, GCC/Clang sanitizer
and MSVC logs preserve those exact failures. Cache, layout and placement
components pass with ASan/UBSan, and the MSVC native renderer diagnostic job
succeeds. The Clang matrix job is recorded as cancelled after GCC failed,
despite retaining its completed five-failure replay log; it is not a green job.
The matrix now disables fail-fast so future compiler runs finish independently.

[kitty-relative-ci-656fed4.json](kitty-relative-ci-656fed4.json) retains 109
completed core/component CI records. These are regression checks and do not
establish native relative-placement or single-executable product acceptance.
The broader [Unicode reference and baseline](kitty-unicode-placeholders.md)
now tracks virtual placements and text-driven image behavior separately.

## Observed behavior and remaining work

The observed child origin is the parent's cell anchor, without the parent's
pixel offset. Named-parent replacement preserves the relationship; rejected
cycles preserve the previous placement. Eight parent edges are accepted and a
ninth is rejected with ETOODEEP in this reference.

Deletion must distinguish directly selected child placements from descendants
retired because their parent disappeared. In the latter case, an image with no
other placement is released. The reference performs some retirement during
layer updates. Scroll filtering also uses each reference's stored creation
anchor, separately from its resolved drawing position; the corresponding raw
history/margin cases are preserved rather than replaced by a simpler model.

Virtual parents depend on Unicode-placeholder drawing, which is also still
required. Native GDI/OpenGL/DirectX pixels, resizing, disposal, full CI and
downloaded-single-image memory acceptance remain pending. No new capability is
advertised and no product acceptance is claimed by this checkpoint.

[kitty-relative-validation.json](kitty-relative-validation.json) indexes the
upstream capture, both baseline archives and local implementation runs with
per-record SHA256 hashes.
