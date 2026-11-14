# Animated image memory workload

`tabs_window_smoke.py --workload-memory --animated-images` adds a separate GIF
case to the existing baseline and translucent-PNG workloads. It retains the
same two 2000-line histories, dense text, Sixel images and 24 tab/redraw/resize
transitions. Each terminal additionally holds a four-frame 256x144 GIF displayed
at 512x288, with 100 ms frame delays and infinite playback. The composed pixel
storage is 589,824 bytes per image, before frame metadata; its encoded payload
is 111,157 bytes. This opaque GIF workload supplements the half-alpha PNG case.

The frontend starts with automation enabled, but no screenshot or injected
observer runs during memory sampling. After sampling stops, the local API must
observe distinct solid red, green and blue patches in each selected tab's
actual renderer within three seconds. The same returned BMP supplies the saved
PNG evidence. This catches missing or frozen animation without including
capture buffers in the ordinary workload measurement. The existing later
injected hover/pixel tests and all nine tab/lifetime groups still run.

The local image is the 32-row Direct3D staging candidate, SHA-256
`9300a9cd87fc9f9fc4dff39408c07221addce0febc70e0b7b7fa2f7a3fee42c0`,
4,523,520 bytes. Both runs use actual 160x48 SarasaTermSC Nerd Font Light grids.

| Renderer | Samples | Private WS peak | Total WS peak | Private commit peak |
|---|---:|---:|---:|---:|
| GDI | 585 | 17,514,496 | 45,105,152 | 20,242,432 |
| DirectX | 570 | 24,920,064 | 65,183,744 | 94,543,872 |

Both pass their unchanged strict-under-20,000,000-byte GDI and at-most-25,000,000-
byte DirectX gates, show ongoing animation in both tabs and pass all nine
functional/resource groups. Each run drains 56 inner/58 outer processes
naturally. DirectX has only 79,936 bytes of private-WS margin here, and its total
WS remains above the approximate 50 MB target. This finite synthetic workload
does not establish a bound for every animation or a sustained real agent.

The preceding static-image CI executable (`8e52b517...8585`) is a negative
canary. Its GDI memory passes at 16,265,216 bytes, but all 17 post-memory captures
lack the required changing colour patches and the test correctly fails.
Cleanup records five remaining private-job processes being terminated; the
canary is not counted as a naturally closing product pass.

The [manifest](gif-memory-validation.json) retains exact executable identities,
fixtures, samples, captures, results and cleanup evidence. The new GDI/DirectX
workloads are registered in both CI packaging paths, in addition to the existing
baseline/PNG gates. Their full CI and downloaded-artifact local acceptance are
still pending. The accepted default executable has not been replaced.
