# Kitty Windows compositor checkpoint

Production source: `97d60254e3bae94fbba9803ff15e1abfce5373f8`.

The development branch enables direct Kitty graphics in the Windows frontend.
It adds native drawing to the previously tested terminal parser, image cache
and placement lifecycle. The root accepted executable is unchanged. This is
an implementation checkpoint, not a claim of complete Kitty compatibility.

## Drawing and ownership

The painter preserves three layers: placements with `z < -1073741824` appear
above the default background but below explicit cell backgrounds; remaining
negative placements appear above backgrounds and below glyphs; nonnegative
placements appear above glyphs. This follows the pinned [upstream specification](https://github.com/kovidgoyal/kitty/blob/8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f/docs/graphics-protocol.rst)
and the `draw_cells_with_layers` order in upstream `kitty/shaders.c` at
`8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f`.

The new MIT implementation uses a lazy 1024-by-1 BGRA scratch DIB, one compatible
DC and 4096 pixel bytes per terminal. It does not allocate an image-sized bitmap
or an additional full-window backbuffer. Source crops and placements use nearest
neighbour sampling. Straight alpha is premultiplied for Windows blending; GPU
drawing uses the existing bounded run upload/readback path. Closing a seat frees
its scratch DC and bitmap.

Text runs intersecting negative placements bypass the GPU text cache. Any visible
Kitty image invalidates the text grid for that presentation before composition,
so transparent pixels never accumulate over the previous image frame. This is
a correctness-first repaint policy; per-region damage and throughput optimization
remain future work. Snapshot bands and hidden-tab previews use the same painter.

## Native checks

The MinGW developer frontend has SHA-256
`9cfc95d85343fd481903c143ce9c801213494ad9be35cdbc11a25238fef6da73`.
It uses a separately source-built OpenConsole/ConPTY pair and is **not** the
single-executable distribution. Runtime file hashes, exact VT input and replies,
capture hashes, source identities and cleanup are retained in
[the validation manifest](kitty-windows-validation.json).

GDI, actual OpenGL and actual DirectX each passed 24 exact pixel cases with
SarasaTermSC Nerd Font Light. They cover native WIC PNG decoding, direct RGB/RGBA,
crop/scale/transparency, all three layer positions and the exact layer threshold,
text/combining/CJK clusters, same-z ordering, deletion, repeated alpha presentation,
synchronized output, alternate screens, scrolling, vertical margins, ED2 and RIS.
The terminal-core suite also passed, including the pinned 43-case/101-state replay.

The [GCC/Clang/MSVC workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43633479290)
passed on that exact production commit, including the full terminal replay under
Linux ASan/UBSan and leak detection. Its complete compiler logs, artifact metadata
and source manifests are retained with the native evidence; the Linux terminal
source hashes match the committed files after LF normalization.

The GDI pixel run used REA/Frida to observe `GdiAlphaBlend`. Evidence
`ev_cffca0605178da8640a2c424bb96f45a96d8394b9dd6a1db4c761286d4699255`
retained 3794 calls and zero failed returns at the last periodic observation.
This is not an exit-time count or an instrumented memory acceptance run. The
owned target exited naturally, REA reported detached, and the session was closed.
The complete observation, load record, and closure are retained. Binary identity
comes from the fixture manifest; REA itself did not provide a target digest.

The API captures real retained GPU pixels for active GPU sessions; GDI and hidden
sessions use bounded native snapshot rendering. These checks do not observe the
physical desktop compositor. Each of the three jobs drained all three owned
processes without forced termination and removed its temporary profile.

## Workload and remaining acceptance

The new `--kitty-images` workload keeps two 2000-line histories, renders dense
Unicode text plus Sixel and translucent 512-by-288 PNGs, cycles 12 temporary
tabs, switches tabs and resizes 24 times. Memory sampling runs before screenshots
and before the later input/hover instrumentation. Active and hidden image patches
are then checked through cropped API captures, and an enlarged Kitty placement
must appear in the hidden tab's live preview without selecting it.

The first developer GDI run used 160-by-48 cells with Sarasa and passed:
588 samples, private working-set peak 15,798,272 bytes, total working-set peak
37,183,488 bytes and private commit peak 17,948,672 bytes. GDI and USER counts
returned to their 40/35 baseline across all 12 close cycles. All 56 owned
processes exited naturally. This is not acceptance of a formal single EXE.

The developer DirectX run also passed at 160-by-48 with Sarasa: 660 samples,
private working-set peak 23,269,376 bytes, total working-set peak 57,462,784
bytes and private commit peak 86,315,008 bytes. GDI objects returned to 41;
USER objects stayed within 37--38 across the close cycles (baseline 37).
All 56 owned processes exited naturally, and all four active/inactive image
patches plus the hidden image preview passed. The private working-set target
passes; the approximately 50 MB total-working-set goal is still outstanding.

The optional OpenGL run also passed the tab, image, preview and resource checks:
446 samples, private working-set peak 63,442,944 bytes, total working-set peak
96,227,328 bytes and private commit peak 175,091,712 bytes. All 56 owned processes
exited naturally. As previously authorized, no GDI/DX memory threshold is applied
to OpenGL; this result must not be described as a 20/25 MB pass.

The full product workflows now run the Kitty pixels across all three renderers,
and the new GDI/DX workload with the unchanged mandatory memory thresholds:
GDI strictly below 20,000,000 bytes and DX at most 25,000,000 bytes. The full
[core workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43633479250) and
[single-EXE workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43633479299)
are running on that production source. Formal CI
artifacts and exact-artifact local memory acceptance are still pending at this
checkpoint; OpenGL is allowed to exceed the GDI memory cap.

File/shared-memory transport, compression, animation, relative placement and
Unicode placeholders remain unsupported. The four-MiB shared raster budget,
two-MiB transfer cap, 128 images/512 placements per screen and bounded placement
extents remain explicit implementation limits. Independent upstream captures
establish parser/layout behavior, not pixel equivalence to upstream GPU filtering.
