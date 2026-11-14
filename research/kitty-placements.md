# Ordinary kitty placement ownership

`nemo_kitty_placements.c` adds a bounded, lazy metadata store on top of the
existing image cache and layout calculator. It is not yet connected to the
terminal parser or renderer and does not advertise kitty graphics support.

Positive image/placement pairs replace one view atomically; zero placement IDs
add views. Anonymous images are released when their last view disappears.
Cache removal notifications discard borrowed views before the image is freed.
Named image data can survive deletion of its placements. The uppercase range
selector also removes unreferenced named images with no placement. Metadata
admission accounts for the cache through an owner callback, and there is a hard
limit of 512 placements. Replacement does not allocate another metadata node.

Drawing iteration is ordered by signed z, internal image creation order and
placement creation order. Named replacements retain their ordering. The owner still
need to implement text/background layering and viewport clipping. The component
supports ordinary deletion selectors; animation-frame deletion, relative and
Unicode virtual placements remain unsupported. It retains full-page scrolling
within a caller-specified history bound. Scroll-region movement operates on
wholly contained placements and permanently crops exposed source pixels.
Source crops and cell anchors remain separate so changing the font afterwards
does not reinterpret the cropped edge as an offset in the old font size.

The generated reference header now extracts 65 literal states from 19 scenarios
in the retained upstream capture at
`8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f`. It verifies the capture SHA-256,
identity and completion before extraction. It compares replacement, deletion,
image counts, pixel rectangles and source crop coordinates. Expected geometry
is copied from observations, not computed by another implementation. Terminal
APC parsing and cursor movement are deliberately outside this component test.
Post-crop font resizing has local regression checks, but has not yet received
independent upstream runtime comparison.

The expanded reference exposed an all-visible deletion mismatch: a placement
scrolled below the viewport must also be removed. The original component left
it alive and it reappeared after scrolling back. That failing comparison is
retained. The fix selects non-history cell footprints. The capture also corrects
same-z ordering to use internal creation identities and permits zero-valued
image-id keys alongside a nonzero image number. The cache retains its internal
identity across named retransmission; individual placement replacements retain
their identity as well. The tests check both forms of stable overlap ordering.

The corrected component passes 2,719 local checks, including all 65 literal
states. Existing transport, cache and layout targets pass 2,111,776, 1,569 and
153 checks respectively. The earlier compiler results below describe `f6f727e`,
not these subsequent production changes. Updated source hashes and logs are in
[the lifecycle correction record](kitty-placement-lifecycle-validation.json).
The corrected [focused workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43628150590)
passes GCC and Clang normal/ASan/UBSan checks and MSVC at
`c48af03bd03ce688531ac295d518003059a6deed`. Each passes 2,719 placement checks;
all 18 files in each compiler manifest match that commit. Its complete
[core](https://github.com/xiongnemo/nemoterm/actions/runs/43628150628) and
[single-image](https://github.com/xiongnemo/nemoterm/actions/runs/43628150654)
application workflows remain pending.

Local strict C99 release tests pass 1,977 checks, including all 18 observed
states. The CMake targets also pass: placements 1,977, existing cache 1,564 and
layout 153. GCC is selected explicitly; an initial implicit Clang configuration
could not find Windows SDK import libraries and did not compile project code.
That diagnostic is retained alongside successful logs and source hashes in
[the validation record](kitty-placements-validation.json). The
[focused workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43625661587)
at `f6f727e4c324cddf9aeda267a378ee2d9f1d11d3` passes GCC and Clang normal and
ASan/UBSan runs, plus MSVC, with 1,977 placement checks in each run. All three
compiler manifests match the committed sources. Their logs and manifests are
retained. Complete application
[core](https://github.com/xiongnemo/nemoterm/actions/runs/43625661617) and
[single-image](https://github.com/xiongnemo/nemoterm/actions/runs/43625661585)
workflows are still pending.

Remaining integration includes per-screen ownership, APC dispatch and replies,
PNG decoding, shared budgets with Sixel/iTerm images, synchronized presentation,
cursor application, history pull on resize, and three-layer rendering. The
remaining font/DPI rescale handling must also clamp retained pixel offsets when
cells shrink. Additional lifetime scenarios need comparison before claiming
protocol equivalence.
No accepted executable has been replaced and no application memory acceptance
is claimed by these component tests.
