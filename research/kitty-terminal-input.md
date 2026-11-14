# Kitty terminal input integration

This checkpoint connects the bounded graphics components to the real terminal
byte parser. At source `4b21bce`, the Windows frontend left `kitty_graphics`
false; those tests did not establish native image display or application memory
acceptance. The subsequent [Windows compositor](kitty-windows-compositor.md)
enables the capability on its development branch. The accepted root
`dist/nemoterm.exe` has not been replaced.

The adapter streams APC `G` input independently of UTF-8 and ISO 2022 decoding,
accepts ST framing, cancels on CAN/SUB or interrupted ESC, and handles direct
`t`, `T`, `q`, `p` and `d` commands. Replies go through the actual line discipline,
including quiet modes, resolved image numbers and explicit unsupported errors.
The existing frontend image decoder supplies PNG decoding; the terminal tests
use raw RGB/RGBA and a separate mock codec for ownership checks. Feature queries,
file/shared-memory transport, compression, animation commands, relative
placements and Unicode placeholders remain unsupported. Feature queries preserve
an unfinished upload even when answered with `ENOTSUP`.

Main and alternate screens own separate caches and placement lists. Both share
the terminal's existing 4 MiB image budget with Sixel/iTerm data, transport growth,
decode temporaries and placement metadata. Query and metadata admission cannot
evict displayed images. Native process working set is a separate acceptance
measurement. Transmission remains limited to 2 MiB decoded data, 4096 Base64
characters per chunk, 128 images and 512 placements per screen; placement cell
extents and inferred cursor movement are additionally bounded at 8192.

Text overwrite, EL, ED0/ED1 and IL/DL preserve ordinary image placements. Page
scrolling moves them, with permanent source clipping inside vertical margins;
RI leaves history in place. ED2 clears non-history views and unreferenced data,
ED3 clears active-screen image data, and hard reset preserves main history while
clearing alternate images. Mode 47 preserves alternate contents; resetting
1047/1049 clears them. Window height changes can move images into and out of
temporary history. Font changes permanently clamp pixel offsets. Horizontal
subregion edits leave overlays in place; Unicode cell images and full compositor
ordering are not implemented by this stage.

The real parser replays all **43 cases / 101 states** from the independently
captured upstream Kitty commit `8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f`.
Expected replies, cursor positions, image counts and visible layer geometry are
literal observations from capture SHA-256
`139b42639c4bba3be07dbeee02c0863374af1e0e1fd5d2a193828b0c934a8efd`.
Six captured APC payloads exceed the documented chunk bound; the generator
splits those into legal chunks without changing headers, decoded data or expected
states. Other wire inputs are unchanged. All input is fed one byte at a time.
These are native terminal-model observations, not GPU screenshots.

The first replay exposed a fixture configuration error: PuTTY's trusted-output
sigil reserved columns that Kitty did not reserve. Setting the same untrusted
application-output mode as the other terminal tests fixes the text-only cursor
comparison; both logs are retained. A subsequent source comparison found IL/DL
incorrectly sharing the page-scroll hook. A failing regression was retained,
then the hooks were separated. No upstream expected state was changed.

Additional tests cover capability gating, cancellation, quiet replies, forbidden
transport, interleaved feature queries, screen isolation, resize, permanent font
offset clamping, oversized geometry and shared-budget pressure. The existing
graphics lifecycle target runs these on MinGW locally and on GCC/Clang sanitizers
and MSVC in CI. The exact source `4b21bce590b17d35fcb36d391ab000670b1ea715`
passes the [GCC/Clang/MSVC matrix](https://github.com/xiongnemo/nemoterm/actions/runs/43630967146),
including full terminal replay under both Linux sanitizers. The source manifests
and all 44 compiler/test/artifact records are retained in
[validation records](kitty-terminal-input-validation.json). The complete product
workflows for that source remain pending.
The remaining work is the Windows GDI/GL/DX layer composition, real PNG decoding
through this path, synchronized/native pixel validation and exact-EXE memory
acceptance before enabling the frontend capability.
