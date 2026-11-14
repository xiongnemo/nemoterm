# Independent kitty graphics reference

The `kitty-graphics` family in the manually dispatched `protocol-reference.yml`
workflow builds upstream commit `8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f`
using its own CI build recipe on a disposable Linux runner. No upstream source
is patched and no local terminal or desktop is used. The pinned REA 6.8.0
`capture-process` recorder owns a single `kitty +runpy` process, with a 60-second
deadline and two-second termination grace period. The input scenario and full
Evidence, executable/extension hashes, package lock, raw observations and build
log are uploaded even when a stage fails.

The fixture runs four upstream graphics tests, then records 29 scenarios and
54 states using the actual compiled kitty parser, screen and graphics manager.
Each state retains input/reply bytes, cursor position, native layer coordinates,
derived pixel rectangles and image count. Inputs cover natural/explicit/aspect
dimensions, crop, pixel offsets, cursor movement, edge wrapping, text erasure,
screen reset, placement identity/deletion, layer order and scroll-region edges.
The captured model has no OS window; it does **not** establish GPU pixels or
an end-to-end visible application result. Raw model values are the observations;
the fixture does not implement a second layout algorithm to produce answers.

Success requires every upstream test to pass without skips, all observations
to finish, natural process exit, verified ownership cleanup, no truncated capture,
and an observation-file digest matching REA's after snapshot. The first run is
pending. Do not infer results from these fixtures before inspecting the capture.

This reference will resolve the two source/documentation differences recorded
in [the image cache notes](kitty-image-cache.md). It does not connect the cache
to Nemoterm, advertise kitty graphics support, or close local memory acceptance.
