# Whole-cluster layout reuse experiment

Source `9bef90786e2bc1ccb8edbc180ac369b00c98ea4b` extends the existing 32-entry
DirectWrite layout cache to repeated whole clusters. The key is normalized UTF-16
plus emoji presentation, scoped to the selected font and size. Font changes clear
all entries. The round-robin bound stays 32; normalized expansions exceeding 66
UTF-16 units render uncached. Colours, destination geometry, pixels, transparency
and shadow bold remain draw-time state. No image budget or acceptance threshold
is reduced, and the accepted executable is unchanged.

The local MinGW offscreen integration test passes with Sarasa, Consolas and
Courier. Added comparisons exercise the same text in both emoji presentations,
different geometry and backgrounds, shadow bold, multi-unit cache replacement
and fresh-renderer equivalence. The existing NFC, RTL fallback, clipping,
double-height, sibling ownership and resource-lifetime checks also pass.

A diagnostic renders 47 rows of repeated combining, emoji, Hangul and RTL cells
into a 1280 by 960 GDI surface: 3,619 cluster draws per frame, 12 frames per
fresh process. Both implementations use the same compiler, flags and benchmark
source. The second pair reverses execution order. All 48 frames have exactly
the same RGB hash, `64c9e5614960c1d3`.

| Order | Old warm-frame median | New warm-frame median | Old sampled private commit max | New sampled private commit max |
| --- | ---: | ---: | ---: | ---: |
| Old then new | 62.644 ms | 43.356 ms | 8,527,872 bytes | 8,003,584 bytes |
| New then old | 63.646 ms | 43.297 ms | 8,486,912 bytes | 7,966,720 bytes |

This is a roughly 31–32% reduction in this diagnostic's warm-frame time.
The memory figures are end-of-frame private **commit**, not private working set
and not a sampled whole-application peak. The diagnostic excludes the terminal,
GPU compositor, console host, history and animation. It cannot close the retained
DirectX GIF failures or establish a whole-application memory reduction.

Raw source, compiler identity, frame observations and the integration-test log
are retained with hashes in [the validation record](cluster-layout-cache-validation.json).
Complete [core](https://github.com/xiongnemo/nemoterm/actions/runs/43615872418)
and [single-executable](https://github.com/xiongnemo/nemoterm/actions/runs/43615872392)
CI runs passed, including all 122 mandatory single-image checks. The downloaded
4,486,656-byte formal EXE has SHA-256
`432fdcb877cfba84422e9a336bf9fe8e0e919d6e02deb4e28ef28feb105141ac`.
The single-image manifest and retained renderer, font zoom, tab-profile and bell
records match that exact image. Full workflow logs and artifact identities are
retained; this does not promote it to the accepted executable.

The first local runs of that formal image passed all six unchanged 160 by 48
Sarasa workloads, each with nine groups of checks and natural process cleanup:

| Renderer | Workload | Samples | Peak private working set | Peak total working set | Peak private commit |
| --- | --- | ---: | ---: | ---: | ---: |
| DirectX | Dense text | 471 | 22,671,360 | 57,737,216 | 87,314,432 |
| DirectX | PNG | 581 | 23,781,376 | 59,359,232 | 93,335,552 |
| DirectX | GIF | 542 | 24,199,168 | 60,563,456 | 88,723,456 |
| GDI | Dense text | 463 | 15,876,096 | 37,969,920 | 18,251,776 |
| GDI | PNG | 512 | 16,465,920 | 39,206,912 | 19,521,536 |
| GDI | GIF | 515 | 16,801,792 | 39,546,880 | 19,431,424 |

Figures are bytes. Private working sets meet the original GDI <20,000,000 and
DirectX <=25,000,000 limits; DirectX total working set remains above the desired
roughly 50 MB. These are uninstrumented frontend samples, not summed host/client
memory. Both GIF tabs exhibited all three required colours within the original
three-second observation; screenshots occur after the memory sampling interval.

A separately built source-host artifact from the same commit has a different
EXE hash, `cf36e20a147a2f77b6c57c28239b9ef2091eca71350cc8373b95e4263a535466`.
Its local GIF workload **failed**: private working set peaked at 24,875,008 bytes,
but the first tab's 21 captures over 3.085 seconds missed green, and failure
cleanup terminated five remaining owned processes. Its complete raw records and
the two observed frame images are retained separately. That failure and the
older `69cd5a4` failures are not erased by the formal image's first-run pass.
Intermittent capture cadence and the small DirectX memory margin remain open;
these results alone do not prove their cause or resolution. The same formal
image subsequently passed local Sarasa renderer parity, grapheme font resize,
RTL shaping and resize, font zoom with independent reference glyphs, mixed
font/renderer tabs, visual bell restoration and single-image isolation checks.
Local OpenGL and DirectX were required and actually active. Those instrumented
pixel/resource checks are separate from the uninstrumented workload memory
results above. Physical input and real agent acceptance remain open.
