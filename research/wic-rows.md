# PNG scanline decoding experiment

Copying PNG pixels one scanline at a time did not establish a memory improvement.
The product change is not retained. The added 257x129 PNG regression remains:
it checks separated rows, odd width, both edges and a half-transparent interior
pixel independently of the decoder's copying strategy.

The experiment changed only PNG `IWICFormatConverter_CopyPixels` requests from
a whole frame to successive one-row rectangles. Destination storage, pixel
format, limits, GIF decoding and other image formats were unchanged. WIC
[supports rectangular requests](https://learn.microsoft.com/en-us/windows/win32/api/wincodec/nf-wincodec-iwicbitmapsource-copypixels);
that API does not guarantee a bound on the codec's internal workspace.

Baseline local single EXE SHA-256:
`9300a9cd87fc9f9fc4dff39408c07221addce0febc70e0b7b7fa2f7a3fee42c0`.
Experimental local single EXE, 4,523,520 bytes:
`aafe6a4ea3b0a232bd493d4ac8ba7361c1ecd0d46e89967a5d6a191da8586c88`.
The exact experimental source, build/link inputs, fixtures, raw samples and
screenshots are preserved in the [manifest](wic-rows-validation.json).

All 32 static image scenes pass on the baseline DirectX image and the experimental
image's actual GDI, OpenGL and DirectX backends. This proves those scenes' output,
not a memory optimization.

| Image / DirectX workload | Samples | Peak private WS | Peak total WS | Peak private commit |
|---|---:|---:|---:|---:|
| Baseline, PNG | 636 | 24,330,240 | 64,528,384 | 86,601,728 |
| Scanlines, PNG | 625 | 24,858,624 | 65,138,688 | 89,042,944 |
| Scanlines, GIF | 563 | **25,055,232 (fail)** | 65,392,640 | 88,240,128 |

Each run uses actual 160x48 SarasaTermSC Nerd Font Light terminals, external
uninjected memory sampling, two retained histories and the existing image,
tab/redraw/resize workload. No compilation runs concurrently. All nine
functional/resource groups complete and all 56 inner / 58 outer processes
exit naturally. The GIF run still fails the unchanged 25,000,000-byte private
working-set gate. The later GDI memory case is not run after that failure.

The paired PNG peak is 528,384 bytes higher in this observation. This does not
prove scanline requests cause that difference, and it gives no basis for adopting
them as a memory fix. The GIF decoder itself was not changed, so its failed
measurement cannot establish a PNG decoder cause. No threshold, pixel assertion,
sampling phase or cleanup requirement was relaxed. The accepted default binary
remains unchanged.
