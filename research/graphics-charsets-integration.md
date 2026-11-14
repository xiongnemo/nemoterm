# Inline graphics and ISO 2022 integration candidate

This combines the charset/checksum source `82e1bef`, inline images and GIF
animation through `4c8ccde`, owned resource diagnostics `7522344`, and main's
accepted-artifact documentation `647a58b`. The integration retains both families'
test targets, native fixtures and workload gates. The accepted root EXE remains
the separately validated `8ff214f` artifact; this candidate has not replaced it.

PNG/JPEG/BMP and GIF share the existing 4 MiB per-terminal image budget with
Sixel, pending transfers and view metadata. The 32-row D3D staging change is
included; the rejected scanline/pixel-allocation experiments are not. WIC remains
a Windows component, with no new distributed sidecar DLL or WebView. Original
scope and unresolved cases remain in [inline display](iterm-inline-display.md),
[GIF animation](gif-animation.md), [ISO 2022](iso2022-upss.md), and
[checksum provenance](iso2022-checksums.md).

## Local build and functional coverage

The locally linked single EXE is 4,541,440 bytes, SHA-256
`f59a0e759eee75abb3cf647b5b7baa26afdc0d1cb1f6d607f446c6e53d365845`.
Fresh frontend archives are linked with the existing source-built console host;
the exact link response and input hashes are retained. This is not a downloaded
CI artifact. The isolated test distributions each contain only `nemoterm.exe`.

Twenty-nine Windows MSVC suites pass. Twenty-three headless Linux suites pass
both normally and with ASan/UBSan/leak detection. The initial Linux command
incorrectly requested six targets unavailable without a native/GTK frontend;
that orchestration failure is retained, and those six suites are covered by the
Windows run. The initial link response assumed cached archive output paths;
the corrected response points to the fresh platform archives without changing
product objects or compiler flags.

A cross-family regression streams a complete image while Greek G1 is selected,
then changes G1 to ASCII between multipart pieces. It checks decoded image
ownership, subsequent text and overwrite/erase behavior. The first test draft
checked a one-cell image after text had already erased it; the second compared
an ASCII-tagged internal cell against an untagged scalar. Those failed fixture
logs remain retained. The corrected expectations follow the established cell
encoding and overwrite semantics; the test passes MSVC, Linux and sanitizers.
These expectation corrections required no product-code change.

Fresh private jobs use actual SarasaTermSC Nerd Font Light and the requested
GDI, OpenGL and DirectX backends. Each backend passes nine charset/paste scenes,
32 static-image scenes, and 36 animation scenes: 231 scenes in total. The
charset grid is actual 160x48; the dedicated image fixtures retain their own
pixel-test geometry. All seven controllers and their owned processes close
naturally. No later passing replay replaces a failed observation.

## Memory and resource gate

Each workload uses actual 160x48 Sarasa, two 2000-line histories, Sixel, twelve
temporary-tab closes and 24 tab/redraw/resize transitions. PNG adds half-alpha
images; GIF adds four-frame animated images. Sampling precedes screenshot or
hover instrumentation. No compilation runs during sampling. The strict GDI
limit remains 20,000,000 bytes and the inclusive DirectX limit 25,000,000 bytes.

| Case | Samples | Private WS peak | Total WS peak | Private commit peak | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| GDI baseline | 546 | 16,396,288 | 43,143,168 | 19,161,088 | Nine groups and memory pass |
| GDI PNG | 638 | 16,515,072 | 39,886,848 | 19,070,976 | Nine groups and memory pass |
| GDI GIF | 617 | 17,489,920 | 44,875,776 | 20,942,848 | Nine groups and memory pass |
| DirectX baseline, early samples only | 226 | 19,595,264 | 58,814,464 | 73,703,424 | Resource gate fails; not memory acceptance |

All values are bytes. Each GDI run naturally drains 56 inner / 58 outer job
members. DirectX fails after its eighth temporary-tab close: baseline
547 handles / 39 GDI / 50 USER becomes 549 / 39 / 53 at 2.0040 seconds. USER
exceeds the unchanged +2 allowance. It does not reach the full workload. The
inner job terminates five remaining members and records zero afterward; the
outer job is empty at completion. This is still a failed cleanup/resource run.

The driver stops on that failure. DirectX PNG and GIF workloads are not run.
The user subsequently requested a pause in actual-machine testing; no local
native/window/input/memory tests should resume until they explicitly permit it.
Offline source/documentation work and remote CI remain available. The original
resource failures, total-DX-working-set target, exact downloaded image acceptance,
full protocol/graphics scope and physical/long-session verification remain open.

The [validation manifest](graphics-charsets-integration-validation.json) retains
the build commands and failures, final regression results, image identity,
native observations, raw memory samples and cleanup records.

## Remote integrated CI

Source `26f50c8796b6ba4ee5e941490a1dbd63021383f4` passes the complete
[core workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43601787424)
and [single-executable workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43601787330).
The single-image manifest contains 119 passed groups, including the charset,
static-image and animation fixtures and all six mandatory memory workloads.
The [downloadable artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43601787330/artifacts/14117501693)
contains one `nemoterm.exe`, 4,482,048 bytes, SHA-256
`2bdb95280ded966c653c4c6b80d1ad0308e331fcc52a92fb09098b3b2284a0fa`.
This is distinct from the local image tested above and has not been executed
locally or promoted to the accepted download.

| CI case | Private WS peak | Total WS peak | Private commit peak |
| --- | ---: | ---: | ---: |
| GDI baseline | 11,345,920 | 42,676,224 | 13,455,360 |
| GDI PNG | 12,832,768 | 45,076,480 | 15,364,096 |
| GDI GIF | 12,722,176 | 44,953,600 | 14,848,000 |
| DirectX baseline | 15,446,016 | 52,322,304 | 18,178,048 |
| DirectX PNG | 16,781,312 | 54,063,104 | 19,664,896 |
| DirectX GIF | 16,633,856 | 53,809,152 | 19,800,064 |

All values are bytes recomputed from the retained frontend samples. All six
workloads pass nine groups and drain naturally. CI uses Consolas and smaller
windows: its recorded grid is 109x34 for GDI and 88x35 for DirectX. These results
cannot resolve the local 160x48 Sarasa DirectX failure, substitute for local
validation of this downloaded EXE, or establish the approximate 50 MB total
working-set target. No thresholds were changed and no local tests resumed.
The [CI manifest](graphics-charsets-ci-validation.json) records workflow and
artifact identities, recomputed peaks, cleanup, and hashes of 19 retained
compressed logs/manifests/observations/sample files.
