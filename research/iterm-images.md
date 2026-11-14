# iTerm2 inline images: transport implementation in progress

This branch is preparing OSC 1337 inline-image support. The transport component
and its tests are implemented. The terminal parser, image codec, placement and
partial-alpha compositor are not connected yet, so this branch does not enable
inline-image display. The native image fixture deliberately fails on the current
accepted executable; its failure is retained as the before-change observation.

## Reference and integration boundary

The [official protocol](https://iterm2.com/documentation-images.html) defines
single-sequence `File`, multipart `MultipartFile`/`FilePart`/`FileEnd`, image size
units and aspect preservation. Source inspection is pinned to iTerm2 commit
`b3010f0d41a1ee9b0bebbc751b1342d428616cc2`:
[VT100Terminal.m](https://github.com/gnachman/iTerm2/blob/b3010f0d41a1ee9b0bebbc751b1342d428616cc2/sources/VT100/VT100Terminal.m)
and [imgcat](https://github.com/gnachman/iTerm2/blob/b3010f0d41a1ee9b0bebbc751b1342d428616cc2/OtherResources/Utilities/imgcat).
The reference client encodes the complete file, then splits its base64 stream
into 200-character parts. Therefore partial quartets belong to the transfer,
not to each OSC. The reference's `size` field is metadata, not a byte-allocation
instruction. These are documentation/source findings; no macOS runtime parity
is claimed.

Current Nemoterm inspection found two important integration requirements:

* OSC 1337 currently reaches the bounded working-directory/shell-mark string
  handler. Image payloads need a separate streaming route, with normal OSC
  termination and cancellation behavior and no increase to every OSC buffer.
* Image retention currently owns Sixel sources. The Windows image compositor
  treats every nonzero alpha as opaque. A generic raster source and proper
  partial-alpha composition are required; a base64 parser alone is insufficient.

## Transport component

`terminal/nemo_iterm.c` has no platform or third-party dependency. It accepts
arbitrarily split single and multipart data and exposes a borrowed completed
file once. New transfers replace unfinished ones; cancellation discards owned
bytes; invalid multipart ordering is rejected. Strict base64 padding and trailing
bits are checked, with valid unpadded final groups accepted. Binary NUL bytes
are preserved.

The component parses cell, pixel, percentage and auto dimensions and preserves
aspect intent. Nonnegative integer sizes are retained for later placement
validation; no image-size semantics are claimed yet. Unknown optional metadata
is ignored. An inline flag other than 1 is rejected by this image-only component;
no filename is opened and no download is written. File downloading remains a
separate unimplemented capability.

Limits are explicit: 4,096 header bytes, 2 MiB decoded file bytes and 1 MiB base64
payload per FilePart. The allocation budget also includes decoder storage and
the old-plus-new buffers during growth. An admission callback can account for
retained images in the same owner before allocation. Invalid/over-budget input
releases payload storage immediately; the caller must still consume the enclosing
OSC terminator. The full terminal-level image budget is not wired yet.

## Verification completed

The independent transport suite passes strict C99 (`-Wall -Wextra -Werror
-pedantic`), Linux ASan/UBSan with leak detection, MSVC `/W4 /WX`, and release
builds with `NDEBUG` defined. Test assertions explicitly remain enabled in release
builds. Coverage includes RFC base64 vectors at every split, binary zeros,
multipart splits inside quartets/padding, metadata and overflow, ordering and
cancellation, one-shot completion, allocation-overlap admission, exact header,
part and decoded-file limits, rejected-buffer release and 200,000 deterministic
state/byte fuzz operations. The CMake target is `test_iterm`; core CI now builds
and runs it with MinGW, MSVC and sanitizers.

The native fixture supplies twenty future PNG scenarios through real ConPTY
and public automation snapshots: intrinsic size, BEL/ST, multipart split sizes,
pixel/cell/percentage dimensions, aspect preservation, partial alpha and changed
background, reset/erase, alternate screens and malformed/cancelled recovery.
On accepted artifact `c239b4af83eb3ae341309c81f59afd7e7af8039f0c058a990eb7a9a5ac1cda84`,
its first intrinsic PNG check fails because the image is absent, while the
following DSR barrier succeeds. All five owned processes drain naturally. Later
scenarios have not executed yet; the fixture is not registered as a passing CI
native check until implementation satisfies it.

The [transport/before-change manifest](iterm-transport-validation.json) records
source/reference digests, commands, compiler results and the original missing
pixel observation. These are local records, not REA-server Evidence.

Remaining implementation: connect OSC framing/reset/resize lifetime; add bounded
image decoding and shared-budget raster ownership; implement dimensions, cursor
and scrolling semantics; blend alpha in all renderers; then run the full fixture,
resource and memory workloads. Other image formats, animated GIF, multiplexer
passthrough, feature reporting and file-download behavior remain separate work.
The full iTerm/kitty image and xterm compatibility objective remains open.
