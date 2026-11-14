# Large pixel storage experiment and failed CI-image acceptance

This is an experiment, not an accepted memory fix. The paired DirectX PNG
peak increased by 102,400 bytes. The earlier downloaded artifact's 25 MB
acceptance failure remains unresolved, and the default executable is unchanged.

## Exact CI artifact

Source `a3eb24ea21ea767a2fd6269222bbe6441c279813` passes both
[core](https://github.com/xiongnemo/nemoterm/actions/runs/43577937506) and
[single-image](https://github.com/xiongnemo/nemoterm/actions/runs/43577937494)
CI. The latter completes 116 checks and publishes
[artifact 14108180986](https://github.com/xiongnemo/nemoterm/actions/runs/43577937494/artifacts/14108180986).
Its executable is 4,465,152 bytes, SHA-256
`106439ed2b4f099091229e965c74cf55b32e6326432d47ee58f1c2972d113959`.

Local acceptance passes all 20 renderer scenes and all 31 static/36 animated
image scenes on actual GDI, OpenGL and DirectX. DirectX baseline memory also
passes at 23,842,816 bytes. The following PNG workload passes all nine functional
and resource groups, with 56 inner/58 outer processes exiting naturally, but
its private-WS peak is **25,202,688 bytes** across 623 samples. This exceeds
25,000,000 by 202,688 bytes. Total WS peaks at 65,556,480 and private commit at
83,845,120. Acceptance stops there; the remaining planned memory cases are not
counted as tested.

A subsequent finite read-only address-region comparison records peaks of
24,399,872 for that CI image and 24,440,832 for the local `9300a9cd...42c0` image.
Both runs finish, but these diagnostic replays do not replace the failed
acceptance. They map resident private pages to allocation/type metadata without
reading page contents. They show variation, not which allocator caused it.

## Experimental change

Windows raster pixel buffers of at least 64 KiB use independent
[VirtualAlloc reservations](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualalloc)
and release the whole allocation with
[VirtualFree](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualfree).
Small buffers and non-Windows builds continue to use malloc/free. Static WIC
images and composed GIF frames share this ownership pair. Dimensions are set
before allocating the first frame so partial allocation failure can select the
correct deallocator. PNG decode failures retain the requested byte count for
cleanup. No working-set trim, image transformation or cache-limit change is
involved. The existing logical byte budget still excludes allocator/page
rounding and WIC's internal workspace.

The local experiment is 4,523,520 bytes, SHA-256
`52ae9cd898b61d43714706084b9fd764aa250b86e3f016953049903b185fa530`.
Its same-toolchain predecessor is `9300a9cd...42c0`. All runs below use actual
160x48 SarasaTermSC Nerd Font Light, two histories and 24 redraw/resize phases.
Memory is sampled before any capture/injection, with the unchanged gates.

| Image / workload | Samples | Private WS peak | Total WS peak | Private commit peak |
|---|---:|---:|---:|---:|
| Previous, DirectX PNG | 631 | 24,735,744 | 64,901,120 | 88,977,408 |
| Experiment, DirectX PNG | 632 | 24,838,144 | 64,966,656 | 88,940,544 |
| Experiment, DirectX GIF | 568 | 24,793,088 | 65,118,208 | 93,057,024 |
| Experiment, GDI PNG | 592 | 17,571,840 | 45,191,168 | 20,029,440 |
| Experiment, GDI GIF | 588 | 17,571,840 | 45,092,864 | 20,348,928 |

Every workload passes all nine tab/lifetime groups and drains naturally. Both
GIF runs also observe changing image pixels after sampling. The experiment
passes 201 static/animated scenes across the three actual renderers, MSVC
warnings-as-errors raster tests, and Linux normal plus ASan/UBSan/LSan raster,
inline transport, terminal image, OSC 52 and SGR suites. Windows unit tests cover
sizes around 64 KiB, exact contents, released virtual ranges, large animation
frames and a partially initialized frame array. These correctness checks do not
establish a stable memory saving.

The [manifest](image-pixel-storage-validation.json) retains the failed CI image's
local records, read-only diagnostics, all experiment results, sources, link
inputs and compiler logs. The storage experiment stays off main; further work
must produce a reproducible improvement before it is treated as a fix.
