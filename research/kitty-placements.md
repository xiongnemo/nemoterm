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

Drawing iteration is ordered by signed z and image ID. The owner will still
need to implement text/background layering and viewport clipping. The component
supports ordinary deletion selectors; animation-frame deletion, relative and
Unicode virtual placements remain unsupported. It retains full-page scrolling
within a caller-specified history bound. Scroll-region movement operates on
wholly contained placements and permanently crops exposed source pixels.
Source crops and cell anchors remain separate so changing the font afterwards
does not reinterpret the cropped edge as an offset in the old font size.

The generated reference header extracts 18 literal states from five scenarios
in the retained upstream capture at
`8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f`. It verifies the capture SHA-256,
identity and completion before extraction. It compares replacement, deletion,
image counts, pixel rectangles and source crop coordinates. Expected geometry
is copied from observations, not computed by another implementation. Terminal
APC parsing and cursor movement are deliberately outside this component test.
The broader selectors and post-crop font resizing have local regression checks,
but have not yet received independent upstream runtime comparison.

Local strict C99 release tests pass 1,977 checks, including all 18 observed
states. The CMake targets also pass: placements 1,977, existing cache 1,564 and
layout 153. GCC is selected explicitly; an initial implicit Clang configuration
could not find Windows SDK import libraries and did not compile project code.
That diagnostic is retained alongside successful logs and source hashes in
[the validation record](kitty-placements-validation.json). GCC/Clang sanitizer,
MSVC and full application CI are configured and pending.

Remaining integration includes per-screen ownership, APC dispatch and replies,
PNG decoding, shared budgets with Sixel/iTerm images, synchronized presentation,
cursor application, history pull on resize, and three-layer rendering. The
meaning of all-visible deletion outside the viewport and additional scrolling
selectors need independent comparison before claiming protocol equivalence.
No accepted executable has been replaced and no application memory acceptance
is claimed by these component tests.
