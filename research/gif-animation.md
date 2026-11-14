# Bounded GIF frame composition and playback

This development checkpoint extends OSC 1337 inline images with GIF animation.
It is not the accepted default executable. Full CI and animated-image memory
acceptance remain outstanding; the static parent's downloaded CI artifact
[already exceeded the local DirectX image-workload limit](https://github.com/xiongnemo/nemoterm/blob/a6c94ccfc1dd4cfc8caeb1523eaaa8b515f4f293/research/iterm-inline-ci.md).

## Decode, compose and retain

Windows WIC decodes GIF frame rectangles, local/global palettes and interlaced
data. A portable composer builds complete immutable canvases using frame offsets,
transparency and disposal modes 0/1 (retain), 2 (background clear), and 3 (restore
previous). Restore-previous refers to an earlier composed canvas and pending
clear rectangle; it needs no extra full-canvas save allocation. Transparent GIF
background disposal exposes terminal content; opaque disposal uses the global
background palette entry when available. No new runtime DLL is distributed.

At most 256 composed frames and 8192 pixels on either axis are accepted. All
composed BGRA pixels and frame metadata are accounted before allocation and
share the terminal's existing 4 MiB image budget with pending encoded data,
Sixel, views and masks. Each encoded input still has the 2 MiB transport limit.
Oversized caches are rejected before allocating them. The Windows codec's own
workspace and heap overhead are outside this logical budget and need separate
process measurement. Frames decode through one fixed-width scratch row, not a
second temporary full canvas.

The decoder releases every WIC interface before returning. Sources retain all
composed canvases until their final view is erased or freed. Animation uses one
timer context per terminal, independent of cursor/blink timers; deletion and
reset retire that context. Shared and partially erased views sample the same
current source frame, keeping their existing erase masks and screen ownership.
Frame changes repaint visible views; off-screen images advance without forcing
an off-screen repaint. Existing GPU image composition is reused.

## Playback policy

GIF delays are interpreted in centiseconds. Zero-delay intermediate frames are
composed but skipped during playback; an all-zero animation stops at its final
composed frame. With no loop extension, playback runs once. NETSCAPE2.0 and
ANIMEXTS1.0 loop counts use zero for infinite playback and positive counts for
that many repeats after the first pass. Finite animations remain on their final
frame. Delayed callbacks catch up to elapsed time instead of issuing a burst of
missed paints. Timing arithmetic handles 32-bit tick rollover.

These choices are explicit compatibility behavior, not a claim of matching all
iTerm2 or browser edge cases. Pixel aspect ratio, user-input-gated GIF frames,
non-GIF animated formats, and kitty graphics remain outside this checkpoint.

Primary references: [GIF89a](https://www.w3.org/Graphics/GIF/spec-gif89a.txt),
[WIC metadata queries](https://learn.microsoft.com/en-us/windows/win32/wic/-wic-native-image-format-metadata-queries),
[Microsoft's animated WIC sample](https://github.com/microsoft/Windows-classic-samples/blob/434f6002bdf9cf9829406c3ff2b33387982d6168/Samples/Win7Samples/multimedia/wic/wicanimatedgif/WicAnimatedGif.cpp)
and [WebKit's loop-count correction](https://bugs.webkit.org/show_bug.cgi?id=39857).
The Microsoft sample uses different short-delay and absent-loop policies; it
provides WIC API evidence, not the playback policy implemented here.

## Validation

The final local single executable is 4,523,520 bytes, SHA-256
`c83b8f54000b017116069419eedb7f6cfbaacd1fd8b7d69d134f4d1a5f734299`.
It reuses the existing source-built console host. Link responses and concrete
input hashes are retained. An earlier local link
`34c402e868e9af94ea94f7053109aa5859466ff1068416cdba7cf14ef8958e8c`
also passed the native suites; final-link validation is recorded separately.

Native fixtures construct explicit GIF89a bytes with a small standard-library
encoder. Pixel expectations are independent of WIC and the terminal composer.
Against the preceding static-only local image, the first animated-red pixel
check fails as expected with black pixels, while the process exits naturally.
The final image passes 36 animation scenes on each actual GDI, OpenGL and
DirectX backend: repeated and finite playback, zero delays, all four disposal
values, restore-previous after clearing, transparency, frame offsets, logical
background, local palettes, interlacing, active-timer erase/reset/alternate
screens, scaled erase masks across frames, and frame/cache/dimension limits.
Finite-stop and erase cases require repeated matching captures over an interval,
not just a single transient match. The 31 static image scenes also pass on all
three backends. All six final native jobs drain naturally.

Portable unit tests compare the composer against an independent full-canvas
copy oracle over 2048 generated frame transitions, plus timing/catch-up,
tick rollover, allocation and arithmetic boundaries. Terminal mock tests cover
animation ownership, accounting, scheduling, erase and reset. MSVC tests pass;
Linux normal and ASan/UBSan with leak detection pass raster, transport, terminal
graphics, OSC 52 and SGR suites. The new standalone raster suite also passes
strict C99 warnings-as-errors and MSVC /W4 /WX with NDEBUG defined, while its
assertions remain enabled. CI registers the new unit and native fixtures.

The [validation manifest](gif-animation-validation.json) retains source hashes,
exact test fixtures, negative canary, compiler/sanitizer logs, native captures,
link identities and cleanup evidence. No memory limit was changed and no
animated-image memory pass is claimed by this original codec checkpoint.
The subsequent [GIF workload checkpoint](gif-memory.md) records separate local
GDI/DirectX measurements and the remaining acceptance work.
