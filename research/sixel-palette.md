# Sixel register identity and shared palette lifetime

The isolated `fix/sixel-palette-20261114` branch fixes an observed difference
from XTerm: pixels painted through a Sixel register must follow later changes
to that register. The previous decoder baked RGB at paint time. It therefore
kept old colors within one image and could not recolor retained shared images.
The branch has passed local core, sanitizer and native tests; full CI and a
downloaded-image check remain pending. The accepted `9c22311` distribution
does not yet contain this fix.

## Reference evidence

The investigation uses official XTerm snapshot source commit
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f`, with URLs and file hashes retained.
Existing XTerm 412 executable SHA-256 is
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
Its adjacent graphics sources match the pinned downloaded files byte for byte;
the complete build provenance of that existing executable was not reconstructed.

Bounded, owned Xvfb/XTerm runs retain exact output bytes, DSR replies,
XImage bytes and PPMs. Same-DCS redefinition recolors earlier
pixels. Private images keep separate palettes; shared images keep their shared
ownership even after mode 1070 changes for future images. A completed shared
definition still affects old images if the later DCS is canceled with CAN.
Equal RGB values in different registers remain distinct, and overwritten pixels
follow their replacement register. DECSTR retains images; RIS clears them.

In this XTerm build, changes to earlier shared images can appear only after
an explicit Expose. The source's shared dirty marking uses a graphic-slot index
where a color-register index is expected, consistent with that observation.
The fix matches the observed repaint colors and invalidates promptly; it does
not reproduce this delayed-repaint defect. The archived reference report retains
the distinction between immediate capture and forced Expose, plus its limits.
These are local source/runtime observations, **not REA-server Evidence IDs**.

## Implementation and memory

Product commit `8c38072` stores a tagged register index inside the existing
32-bit tile, resolving it during row readback. Literal initial foreground,
background and transparent pixels remain distinct. No second bitmap is added.
Private decoders own their palette. Shared decoders borrow the owning terminal's
existing palette array for their whole lifetime, independent of subsequent mode
changes. Parsed color definitions mutate that shared array immediately and
invalidate retained content. Cancellation does not roll back the definition.

Decoder reset detaches the borrowed array and callback. Hard reset/destruction
release retained and pending decoders before resetting/freeing terminal storage.
Split image views continue sharing their refcounted pixel source. Both Linux
GCC and Windows x64 MSVC size probes report fixed decoder size 3176 -> 3200
bytes; the 4112-byte tile is unchanged. Existing 4 MiB total image accounting
and rejection tests retain their original limits.

## Verification

New core regressions first fail against the original implementation. After the
change, `test_sixel`, `test_sixel_terminal` and `test_state_control` pass in the
ordinary build and with ASan, UBSan and leak detection. Decoder coverage retains
20,000 deterministic fuzz cases. Tests check redraw invalidation before ST,
private/shared mode changes, CAN, equal-RGB register identity, overwrite,
soft/hard reset, split-source references and budget accounting. Strict C99
warning-as-error compilation passes. An initial invocation naming nonexistent
Linux target `test_modes` is retained as a procedural failure.

The Windows local single-file candidate is 4,509,696 bytes, SHA-256
`a991a5173ead454dfa0271b8684bce95a8c9553e8d847a32771c3bb797bde5b7`.
It uses the previously validated integrated host objects and freshly rebuilt
frontend libraries. It passes the existing Sixel resize/scroll/history fixture
and all 16 existing renderer scenes in each of GDI, OpenGL and DirectX.

New native fixture `5daf6e2` uses the public automation API's PID discovery,
explicit session ID and active-renderer BMP capture. It sends output through a
real owned ConPTY child, waits for ordered DSR replies, and checks exact color
positions/counts rather than accepting a new screenshot hash. Each stage stores
BMP, PNG, sent bytes and replies. There is no desktop capture, clipboard access,
global input, target injection or existing-session attachment.

- Downloaded old `9c22311` image: the red setup passes; same-DCS redefinition
  fails as expected with 48 red / 48 green pixels instead of 96 green.
- New GDI, OpenGL and DirectX: all **16 scenarios per renderer** pass, with
  actual renderer IDs 0, 1 and 2 respectively. This includes retained shared
  recoloring after CAN through the real ConPTY path, mode changes and resets.
- All four native palette jobs exit naturally, including the intentionally
  failing old-image job, and remove their unique registry profiles.

Separate unchanged full tab workloads use SarasaTermSC Nerd Font Light and
verify actual 160x48 grids. Each passes nine groups and closes all 56 inner /
58 outer owned processes naturally. Memory is sampled before pixel-helper
injection; no working-set trimming or threshold changes are used:

| Frontend peak, decimal bytes | GDI | DirectX |
| --- | ---: | ---: |
| Private working set | 16,130,048 | 24,068,096 |
| Total working set | 42,942,464 | 63,520,768 |
| Private commit | 18,817,024 | 86,192,128 |
| Samples | 467 | 444 |

DX total working set still exceeds the approximate 50 MB target. Full-screen
invalidation on shared definitions may cost extra CPU for palette-heavy streams;
these tests do not establish broad performance or complete Sixel compatibility.
Implicit opaque background palette rules, other versions/hardware, exhaustive
malformed streams and remaining image/DPI boundaries need separate coverage.

The [manifest](sixel-palette-validation.json) verifies the original reference
hash catalogue and decompressed hashes of retained source, reference captures,
before/after failures and successes, build scripts, native pixels, memory and
cleanup. CI now includes the new fixture for all three renderers.
