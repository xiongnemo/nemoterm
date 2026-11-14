# Implicit Sixel registers and declared background fill

The independent `fix/sixel-background-20261114` branch corrects the implicit
Sixel foreground and opaque fill against pinned XTerm behavior. Local portable,
sanitizer, Windows core and actual GDI/OpenGL/DirectX checks pass. Full CI and
downloaded-image verification remain pending; the accepted `e436ecd` image
does not contain this additional fix.

## Reference and scope

The reference uses official XTerm source commit
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f` and an existing XTerm 412 executable,
SHA-256 `089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
Adjacent runtime graphics sources match the pinned downloaded source; the full
binary build provenance was not reconstructed. The retained source manifest
contains exact URLs and hashes.

Owned Xvfb/XTerm jobs exercise 35 bounded phases: 26 main, seven narrow
confirmations and two VT330 model controls. They retain exact sent bytes, DSR
replies, raw XImage bytes, PPM images and 8x6 RGB probe matrices, both immediately
after the barrier and after explicit Expose. The examined regions agree in
both captures. All owned processes exit; no existing desktop is controlled.

Pinned XTerm initially draws through register 3. VT340's existing palette gives
that register green; VT330 gives it white. P2=0/2 fills through register 0,
while P2=1 leaves holes transparent. Text SGR/OSC foreground and background
colors do not select these Sixel registers. Same-DCS and later shared palette
redefinitions recolor both set pixels and opaque fill.

Opaque fill covers only the declared raster rectangle and activates on the
first Sixel byte, including zero-bit `?`. Raster declaration alone does not
cover an existing image. With no declaration, or outside a small declaration
when set pixels grow the actual image, unset pixels remain transparent. OSC11
changes show through those holes while register-0 fill retains its own color.
The archived old decoder comparison demonstrates each previous mismatch.

These are pinned XTerm behaviors, not a claim of physical VT340 hardware or
all emulator models. The upstream initial-register choice itself has a
hardware-certainty FIXME. Raster-only cursor motion, repeated late raster
commands and exhaustive malformed input are outside this reference scope.

## Implementation

Product commit `a7cb7bb` removes literal text foreground/background arguments
from the internal decoder API. Set pixels use tagged palette registers,
initially register 3. Empty tile slots remain zero. Two frozen dimensions let
row readback synthesize register-0 fill only within the activated rectangle;
no fill tiles, second bitmap or extra pixel plane are allocated.

Private/shared palette ownership, cancellation side effects and immediate
invalidation follow the preceding palette fix. A raster-only decoder is freed
without retaining a covering image. Reset detaches shared storage and restores
defaults. The existing 4 MiB storage/logical-size budget remains unchanged.
Linux x86-64 probes measure decoder size 3200 -> 3208 bytes and unchanged
4112-byte tiles; this is a structure-size observation, not working-set evidence.

## Verification

New tests first fail against the original implementation, with the raw failed
assertions retained. `test_sixel`, `test_sixel_terminal` and `test_state_control`
pass normally and under ASan/UBSan with leak detection. Strict C99 compilation
passes `-Wall -Wextra -Werror -pedantic`. Windows MSVC also passes the decoder
with `/W4 /WX` and the two terminal suites. Coverage includes both tile edges,
partial rows, declared/no-raster bounds, zero-bit activation, private/shared
recoloring, CAN, DECSTR, RIS and the existing 20,000 deterministic fuzz cases.

The local single executable is 4,509,696 bytes, SHA-256
`f7afbe507a47ed3147481b5712a323fad55225ecbba3729e2f6ca820687e7e4c`.
Fresh frontend libraries link with previously validated host objects; input
hashes and the link command are retained. The merge of newer main documentation
does not change `vendor`, `scripts`, `tests` or `.github` from `a7cb7bb`.

The new native fixture uses the public discovery/session/image interface in
fresh owned processes. Output travels through real ConPTY; DSR barriers order
the response before capture. It checks all RGB values in three disjoint 8x6
regions, including background and transparent holes, and saves the original
BMP/PNG, bytes, replies and mismatch coordinates. No injection, global input,
clipboard access or existing-session attachment is used.

- Accepted `e436ecd` image: the first implicit-color scenario fails as expected.
- New image: all 22 background scenarios pass for actual renderer IDs 0, 1 and
  2. This includes same/shared redefinitions, CAN, soft/hard reset, OSC11,
  sparse holes, declaration-only underlay and first-zero-bit activation.
- Refactored palette harness: all original 16 palette scenarios still pass in
  each actual renderer. Its original whole-client RGB probe is retained; only
  the new background suite uses bounded RGB regions.
- Existing renderer comparison passes all 16 scenes per backend; existing
  Sixel scroll/history/resize checks pass. These use their original capture
  methods and are not memory acceptance runs.
- All nine outer native jobs, including the expected old-image failure, exit
  without forced cleanup. Unique registry profiles are removed.

The [manifest](sixel-background-validation.json) verifies the reference hash
catalogue and decompressed hashes of retained source, before/after tests,
native pixels, image inputs and cleanup. These are local source/runtime
observations, not REA-server Evidence IDs. Exact CI-image memory acceptance,
long sessions, physical input, multimonitor DPI and full Sixel compatibility
remain outstanding.
