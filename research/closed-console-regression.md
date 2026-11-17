# Full hosted regression after closed-console admission fix

[Run 44058990446](https://github.com/xiongnemo/nemoterm/actions/runs/44058990446)
tests production commit `808433881ec0776265b1361e6576b0f86382857e`.
The shared single image is 4,600,320 bytes, SHA-256
`bf403e3d4a6451ca90c6898a0617af63dc85987ae3725c1c383385f9035fa394`.
All builds and runtime checks execute on GitHub-hosted runners. Local work
only inspects source, downloaded records and image files.

The completed aggregate is **21/22**: only full-grid DirectX memory fails.
The isolated single image passes all **169 groups**, including its twelve
existing screen-clamped memory workloads; the complete MinGW suite and its
twelve workloads also pass. This is not an all-green build or an automatic
replacement for the separately identified distribution.

The [single-file development artifact 14320479224](https://github.com/xiongnemo/nemoterm/actions/runs/44058990446/artifacts/14320479224)
contains only `nemoterm.exe`. Downloaded ZIP contents, length and SHA-256 match
the identity above. The separately built 4,035,023-byte MinGW frontend has
SHA-256 `8f3475af977e10b94ad7c095d3a2c54d1adb3754e0cbb5656443616f0c9c3673`;
its results are not attributed to the single image.

## Completed acceptance

| Area | Observed result on this exact single image |
| --- | --- |
| Interaction | 26/26 cases pass, all with natural cleanup: input, selection, clipboard/drop, real Codex/OpenCode, rendering, mouse, four tab sides, settings, all six shells and bell APIs/pixels. |
| Shell lifetime | 24/24 Git Bash repetitions and 6/6 native controls pass; no forced cleanup or exceeded natural-drain grace. |
| Actual DPI | 24/24 bilingual standalone/tab cases pass, including cold 100–200% and live transitions. |
| Settings layout | 44 frames, 440 pages and 2,508 control checks complete; 200% Chinese tab-host Bell and Translation screenshots also visually inspected. |
| Language persistence | Eight save/cancel/restart/override checks pass; the runner preference is restored. |
| Full-grid GDI | All six actual 160×48 Sarasa workloads pass. The dense case checks 29,072 cell centres in 184 strips and ten lifecycle conditions; longest capture request 0.760771 seconds. |
| Full-grid DirectX | All six fail the unchanged 25,000,000-byte private working-set gate; functional checks complete and every private job drains naturally. |

The Linux sanitizer, MSVC diagnostics and profile jobs also pass. All twelve
interaction identity records name the exact image above, source fixture
`8084338`, and a clean fixture checkout. The
[closure study](closed-console-connections.md) separately retains the old-image
negative controls; those results are not merged into this run's pass count.

## Full-grid memory

These are uninjected frontend peaks in bytes, using the actual
`SarasaTermSC Nerd Light` family, GDI or DirectX as requested, and an unclamped
160×48 grid. Sampling records contain no measurement errors. Host/client
measurements are retained separately and are not substituted for frontend
memory. The older Consolas screen-clamped workloads remain distinct.

| Workload | GDI private WS | GDI total WS | GDI private commit | DirectX private WS |
| --- | ---: | ---: | ---: | ---: |
| Text/history | 16,171,008 | 49,463,296 | 18,296,832 | 26,296,320 |
| Inline PNG | 17,170,432 | 51,728,384 | 19,329,024 | 27,627,520 |
| Animated GIF | 17,522,688 | 51,728,384 | 19,668,992 | 27,033,600 |
| Kitty PNG | 17,424,384 | 52,092,928 | 19,767,296 | 27,316,224 |
| Compressed Kitty | 17,453,056 | 52,142,080 | 19,550,208 | 27,303,936 |
| Unicode Kitty cells | 18,690,048 | 53,383,168 | 22,208,512 | 29,446,144 |

GDI meets its <20 MB private working-set requirement; its total working set
remains approximately 50 MB. The lower peak than the earlier paint-batching
run is an observation, not evidence that the closure fix optimizes rendering.
The dense GDI fixture records 56 total owned processes, zero active at final
drain and no forced termination.

DirectX's existing regression limit remains failed. The user's instruction to
stop further DirectX memory optimization is preserved; no gate is waived and
no new DirectX optimization is claimed.

Hosted DPI does not exercise moving between physical monitors with different
scales. Injected input and bell API success do not certify physical devices,
third-party IME windows or audible sound on the user's machine. Missing
protocol families in the coverage ledger remain missing.

## Retained evidence

[The compact archive](closed-console-regression-evidence.zip) contains 1,852
records plus a per-file SHA-256 manifest: final run/job/artifact metadata,
downloaded executable identity, all interaction receipts, complete selected
single-image/MinGW logs and JSON, compiler/profile evidence, memory records,
DPI geometry and two inspected screenshots. It is 4,428,599 bytes, SHA-256
`bd7d2f3a0944f10242e9b8d0a94201c4772a532ae5ff12c903dbabb2cf60ce4f`.
The original positive/negative closure archive remains separate and unchanged.
