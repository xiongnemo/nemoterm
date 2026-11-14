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
CI runs are pending. The resulting single image still needs the unchanged local
font/pixel/resource and 160 by 48 Sarasa memory workloads, especially DirectX GIF.
