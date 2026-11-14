# Kitty graphics implementation work

The terminal does **not yet implement kitty graphics at runtime**. APC is still
consumed without a graphics handler; no successful support reply is advertised.
This development checkpoint adds a bounded transport component and its compiler
and sanitizer checks. It is one stage toward image decoding, placement and full
lifecycle support, not a substitute for that functionality or its acceptance.
Local native testing remains paused at the user's request.

## Reference

The [official protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/) was
inspected at kitty source commit
`8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f`,
[`docs/graphics-protocol.rst`](https://github.com/kovidgoyal/kitty/blob/8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f/docs/graphics-protocol.rst).
The downloaded reference SHA-256 is
`c51470cc0bd16c804ff2d1652507f6fc6966271ab1164359012b8bbdb0375dbb`.
No upstream implementation is copied and no third-party library is added.
The reference includes newer indexed formats and feature queries, which must
not be inferred from older RGB/PNG support.

## Transport component

`nemo_kitty.c` accepts bytes after APC's `G`; its caller owns the framing and
cancellation. It retains single-letter keys and whether each was present, with
checked unsigned and signed 32-bit values. Format/action/medium support remains
an owner decision: parsing a key is not evidence of implementing its operation.
Duplicate keys use the last value; leading/trailing commas are rejected, as
permitted by the reference's undefined-comma policy.

The component incrementally decodes base64, allowing arbitrary input read splits
but requiring complete quartets at non-final graphics-chunk boundaries. It
rejects bad padding, nonzero unused bits and data after padding. The final chunk
may omit padding. No image bytes are exposed before completion. Subsequent chunks
carry only the continuation/quiet keys, plus the required frame action for an
animation upload. Valid feature queries preserve the pending upload and discard
their own payload. Delete cancels a pending upload; other interleaved graphics
commands reject and release it. Explicit cancellation and interrupted APC input
release all transport storage.

Header storage is capped at 1,024 bytes, each encoded payload chunk at 4,096
characters and the decoded transfer at 2 MiB. The caller supplies a total budget
and an allocation admission callback. A buffer growth reservation includes both
the old and new allocation before copying, not just their eventual difference.
The terminal integration must include this storage in the existing shared
4 MiB image budget, including retained sources, placement metadata and masks.
The transport performs no file access, shared-memory operation, image decoding,
terminal response or rendering.

## Verification scope

The new standalone test has fixed base64 vectors, all read-boundary splits,
binary data, signed/unsigned boundaries, case-sensitive keys, metadata defaults,
normal/frame chunks, quiet inheritance, feature-query interleaving, cancellation,
malformed recovery, exact/over-limit headers and chunks, exact 2 MiB and one-byte
over-limit transfers, denied allocation admission and deterministic noise.
Its budget probe checks allocation overlap; it does not measure process memory.

GCC and Clang strict C99 builds plus ASan/UBSan, and MSVC C11 with warnings as
errors, are configured in `kitty-graphics.yml`. The same target is added to the
regular MinGW, MSVC and sanitizer workflows and local build/test scripts.
At this checkpoint only source/static review has run locally; remote behavioral
results are pending. These component tests are specification assertions, not
independent kitty runtime evidence.

## Remaining implementation and acceptance

1. Connect APC G/ST parsing, cancellation and exact quiet/error replies without
   changing unrelated APC, C1, OSC, Sixel or multipart iTerm behavior. A query
   must exercise the requested decoder/medium, and feature reports must describe
   only implemented operations.
2. Add image identity and image-number lookup, shared image sources, placement
   identity/replacement/deletion and quota eviction. Prefer unplaced sources
   during eviction. Validate a replacement before publishing it and keep every
   temporary allocation in the shared image budget.
3. Decode direct RGB/RGBA/PNG, then indexed formats and bounded zlib transport.
   Explicitly report unsupported media instead of falsely returning success.
   Filesystem/shared-memory media need separate platform behavior and access
   policy; parsing their metadata in this component does not enable them.
4. Render crops, cell/pixel offsets, aspect-aware placement, cursor policy and
   z-order, including blending above/below text and nondefault backgrounds.
   Preserve correct scrolling, history, erase/reset, font/DPI changes, alternate
   screens, synchronized updates and tab previews without making bitmap copies
   per placement. Existing Sixel's destructive cell masks are not automatically
   the correct kitty lifetime policy.
5. Add relative placements, Unicode placeholders and animation/frame editing
   with their separate semantics and bounded retained state.
6. Capture an independent kitty reference and compare replies, pixels and
   lifetimes. Exercise real applications and all three actual renderers; a CI
   OpenGL fallback is not OpenGL acceptance. Then validate the exact downloaded
   single executable under the Sarasa 160x48 functional/resource/memory workloads
   when the user resumes local testing. Preserve the already observed DirectX
   failure and all remaining original-goal requirements.
