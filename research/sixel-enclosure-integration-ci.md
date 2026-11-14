# Accepted integration artifact: Sixel, enclosures and resource lifetime

Source `9e7549bc051147b3048636503f2b4c0e5d800ac7` passed both complete workflows:
[core/compiler tests](https://github.com/xiongnemo/nemoterm/actions/runs/43563686383)
and [single executable](https://github.com/xiongnemo/nemoterm/actions/runs/43563686361).
The core workflow's four jobs passed, including Linux ASan/UBSan, native MSVC
renderer diagnostics and the MinGW frontend with the same source-built host.
The single-file validation records all 108 required native check groups.

The [downloaded artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43563686361/artifacts/14101679444)
contains one `nemoterm.exe`, 4,451,840 bytes, SHA-256
`c239b4af83eb3ae341309c81f59afd7e7af8039f0c058a990eb7a9a5ac1cda84`.
The download expires at 2026-12-14T06:19:45Z. Its hash matches the CI validation
record. This exact file, not a local relink, was used for all checks below.

Local tests again pass eighteen scenes per actual GDI/OpenGL/DirectX backend,
twenty-two Sixel background scenes and sixteen palette scenes per backend,
239 protocol cases (193 unchanged XTerm references plus 46 explicit extensions),
and the Sixel resize/history/partial-scroll/erase suite. Separate private jobs
own every process; all controllers complete naturally without survivors.

Both full nine-group tab workloads use SarasaTermSC Nerd Font Light at actual
160x48, with twelve create/close cycles and menu ownership checks:

| Renderer | Samples | Private WS peak | Total WS peak | Private commit peak |
| --- | ---: | ---: | ---: | ---: |
| GDI | 531 | 16,056,320 | 42,844,160 | 18,710,528 |
| DirectX | 516 | 23,810,048 | 63,262,720 | 93,380,608 |

All values are bytes. Startup and bounded resource-return observations count
towards the maxima. The original handle/GDI/USER allowances remain unchanged;
the [settling method and negative control](resource-settle.md) distinguish
temporary GUI activity from a retained-session leak. Both workloads naturally
drain 56 inner / 58 outer processes. No working-set trimming is used; the memory
sampler stops before independent pixel-helper instrumentation.

GDI meets the strict 20,000,000-byte private limit and DirectX meets the agreed
25,000,000-byte limit. DirectX total working set is still above the approximate
50 MB target; these observations do not resolve that requirement or attribute
run-to-run differences to a particular feature.

The [CI/local manifest](sixel-enclosure-integration-ci-validation.json) verifies
368 compressed records (1,184,910 bytes), including job metadata, exact-image
CI validation, local pixels/protocol observations, all memory samples and owned
process cleanup. These are CI/local observations, not REA-server Evidence.
Earlier individual-branch failures remain in their original records. The
[previous local merge checkpoint](sixel-enclosure-integration.md) documents the
source changes and reused-host development build independently.

This artifact is suitable for the current accepted development download. It
does not contain the subsequent SGR 60-65 branch, and does not establish full
physical IME, multi-monitor, long real-agent or exhaustive protocol coverage.
