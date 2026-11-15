# Kitty relative-placement reference and baseline

Relative placements are still an implementation gap. The accepted 752f3be
single executable is unchanged; this branch currently adds an independent
reference and a deliberately failing real-core replay.

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

The current core, with production source unchanged from 03c1f05, builds under
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

## Implementation consequences

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

The existing cache-removal callback runs while mutation is blocked. Adding a
parent pointer and recursively deleting children inside that callback would
violate existing reference-count and iteration contracts. The implementation
therefore needs an explicit, tested phase for releasing orphan references and
images, plus stable parent identity, bounded ancestry checks and wide offset
arithmetic. It must account for placement metadata within the existing shared
image budget and add no per-character storage for ordinary relative placements.

Virtual parents depend on Unicode-placeholder drawing, which is also still
required. Native GDI/OpenGL/DirectX pixels, resizing, disposal, full CI and
downloaded-single-image memory acceptance remain pending. No new capability is
advertised and no product implementation is claimed by this checkpoint.

[kitty-relative-validation.json](kitty-relative-validation.json) indexes the
upstream capture and both baseline archives with per-record SHA256 hashes.
