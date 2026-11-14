# Smaller Direct3D 11 staging bands

The static inline-image CI artifact exceeded the local DirectX private-working-
set limit; its [failed acceptance record](iterm-inline-ci.md) remains retained.
The subsequent animated-GIF local build also exceeded the limit in a finite
inline-PNG workload run. All nine functional/resource groups passed and its
processes closed naturally, but 25,034,752 bytes is above 25,000,000 and the run
correctly failed.

This experiment changes the shared Direct3D 11 staging-band height from 64 to
32 pixels. The fixed 512-pixel readback tile becomes 64 KiB instead of 128 KiB.
The upload staging texture and GDI scratch DIB also use the smaller minimum
height; taller glyph runs can still grow the strip. Frame resolution, image
quality, pixel formats, retained frame textures and renderer fallback behavior
are unchanged. Smaller bands trade some batching capacity for less temporary
storage; this is not a working-set trim or a memory-limit adjustment.

The local single executable is 4,523,520 bytes, SHA-256
`9300a9cd87fc9f9fc4dff39408c07221addce0febc70e0b7b7fa2f7a3fee42c0`.
It was built with the same MSVC configuration and source-built console host as
the preceding 64-row image
`c83b8f54000b017116069419eedb7f6cfbaacd1fd8b7d69d134f4d1a5f734299`.
The intervening merges changed observation fixtures and records, not product
sources. Exact link inputs, source, fixtures and all before/after results are
retained in the [manifest](d3d11-staging-validation.json).

## Local results

Workloads use actual 160x48 SarasaTermSC Nerd Font Light terminals, two retained
histories and 24 tab/redraw/resize transitions. The inline case adds 512x288
half-alpha PNGs to the Sixel workload. Sampling precedes injection, includes
startup and resource settling, and applies the unchanged limits. The local
pixel tests require actual requested GPU backends.

| Image and workload | Samples | Peak private WS | Peak total WS | Peak private commit |
|---|---:|---:|---:|---:|
| 64 rows, DirectX inline PNG | 672 | 25,034,752 | 65,105,920 | 87,969,792 |
| 32 rows, DirectX baseline | 548 | 23,875,584 | 63,348,736 | 92,762,112 |
| 32 rows, DirectX inline PNG | 710 | 24,608,768 | 64,692,224 | 88,510,464 |
| 32 rows, GDI inline PNG | 677 | 17,854,464 | 45,326,336 | 20,496,384 |

The paired DirectX inline-image peak decreased by 425,984 bytes. The new image
passes the 25,000,000-byte DirectX and strict 20,000,000-byte GDI limits for these
workloads. Each of the three after-change memory runs passes all nine tab,
resource and lifetime groups, with 56 inner and 58 outer processes exiting
naturally. The original over-limit run also closed naturally and remains a
failure. DirectX total working set is still above the approximate 50 MB target;
the remaining private-working-set margin is only 391,232 bytes. This is a
measured workload result, not a bound on all images or environments.

The same image passes all 20 renderer scenes on actual GDI/OpenGL/DirectX,
31 static inline-image scenes on DirectX, and all 36 GIF animation scenes on
DirectX. Pixel tolerances, resource allowances and deadlines were not relaxed.
This run uses the independently validated API renderer capture and scoped
preview pointer fixture; its uninstrumented memory phase is unchanged.

The subsequent [animated-image workload](gif-memory.md) also passes locally;
full CI and downloaded-artifact local verification remain outstanding.
The separate earlier resource-return and hosted
startup/close failures are not declared fixed by this staging change. The
accepted default `dist/nemoterm.exe` has not been replaced.
