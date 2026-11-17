# Full Sarasa grid memory acceptance — 2026-11-17

## Coverage gap

The complete [2312edd regression](https://github.com/xiongnemo/nemoterm/actions/runs/44019109177) passed its existing tests. Its native memory workloads requested 160×48 cells but used Consolas on a smaller runner desktop. The dense Unicode workload actually ran at 109×34 (GDI) and 88×35 (DirectX). Those receipts do not prove the requested full-size Sarasa workload.

| Existing dense Unicode case | Actual grid | Font | Peak frontend private WS |
| --- | --- | --- | ---: |
| GDI / top tabs | 109×34 | Consolas | 13,799,424 bytes |
| DirectX / left tabs | 88×35 | Consolas | 17,764,352 bytes |

These are retained historical observations, not corrected or substituted measurements. Original records are in `remote-test-migration-evidence.zip`, under `final-summary/single-workloads.json`.

## Added remote coverage

The interaction catalog adds six workloads for each of GDI and DirectX: dense text/history, PNG, GIF, Kitty PNG, compressed Kitty PNG, and Unicode image cells. Each requests the pinned `SarasaTermSC Nerd Light` face and an actual 160×48 initial grid. `--require-grid` rejects screen clamping; DirectX also requires the actual DirectX renderer rather than fallback. Memory gates and natural-cleanup assertions are unchanged.

The test-only display probe selects an advertised display mode with enough work area on a GitHub-hosted runner. The workflow records its original/prepared/restored display state and requires real 96 DPI. It installs no display driver and changes no developer-machine display setting. Memory sampling precedes screenshot and injected input probes; process-tree reports keep frontend, console-host and fixture-client memory separate.

Product identity is unchanged: source `2312edd86e08c4454bde9f675af030ea3134d3e7`, single EXE 4,599,296 bytes, SHA-256 `dfb9c0093f18ce53ff056d850bc20defcbdeed89f179b4ced7f63a218aa65f6f`.

## Runs

[Replay 44027183736](https://github.com/xiongnemo/nemoterm/actions/runs/44027183736) used fixture commit `66412ad` against that exact product. Both memory jobs failed. Every case verified an actual 160×48 grid, the pinned Sarasa face and the requested renderer (no fallback). Both runners changed from 1024×768 to an advertised 1600×1200 mode at 96 DPI, then restored the original mode.

| Workload | GDI private WS peak, bytes | GDI result | DirectX private WS peak, bytes | DirectX result |
| --- | ---: | --- | ---: | --- |
| Text/history | 16,416,768 | pass | 26,451,968 | fail |
| Inline PNG | 17,358,848 | pass | 27,291,648 | fail |
| Animated GIF | 17,580,032 | pass | 27,516,928 | fail |
| Kitty PNG | 17,596,416 | pass | 27,918,336 | fail |
| Compressed Kitty | 17,690,624 | pass | 27,348,992 | fail |
| Unicode Kitty cells | 20,361,216 | fail | 29,241,344 | fail |

The unchanged bounds are GDI strictly below 20,000,000 bytes and DirectX at most 25,000,000 bytes. The dense GDI case sampled 3,344 times over 343.36 seconds without injection, with peak total WS 57,065,472 bytes and private commit 22,802,432 bytes. It reached the final memory assertion after its pixel and lifecycle checks; it was not a timeout. All cases exited their owned processes naturally. DirectX failures remain recorded; the user's instruction to stop further DX memory optimization does not turn these results into passes.

Original hosted receipts: [GDI artifact 14304715953](https://github.com/xiongnemo/nemoterm/actions/runs/44027183736/artifacts/14304715953), [DirectX artifact 14303194151](https://github.com/xiongnemo/nemoterm/actions/runs/44027183736/artifacts/14303194151).

## Compact derived records

Dense Unicode images had allocated the full ordinary-placement record for each derived cell run, including unused placement id, z, row count and parent offsets. Commit `5a5dd7b` separates the shared geometry from ordinary-placement fields. On the hosted x64 compilers, a derived record is intended to shrink from 128 to 96 bytes; its double-precision geometry and 64-bit identities are preserved. No cell capacity, history, image budget or workload is reduced.

The new allocation regression creates 7,268 independent runs (158×46 inner cells), verifies their public geometry, budget admission and release, and limits their aggregate requested allocation to 697,728 bytes. [Negative run 44031246611](https://github.com/xiongnemo/nemoterm/actions/runs/44031246611) at fixture `66662f8` rejects the old production layout on GCC, Clang and MSVC: all three first pass the 19,749 existing placement checks, then fail the new bound at 930,304 bytes. The component workflow also retains an older pinned implementation as a negative control.

[Component run 44031477073](https://github.com/xiongnemo/nemoterm/actions/runs/44031477073) passed all three compiler jobs at production commit `5a5dd7b37311944413e1a3f07076f50bce68003a`. Each measured exactly 697,728 derived bytes, a 232,576-byte reduction per full-grid tab. GCC and Clang also pass the compact-memory test under ASan/UBSan. Existing placement checks, 728 Unicode replay states, 238 relative-placement states and 32 exact selection copies pass. The retained older implementation still fails the new allocation bound.

The [full regression 44031481269](https://github.com/xiongnemo/nemoterm/actions/runs/44031481269) completed **19/21 jobs successfully**. It built a 4,599,808-byte single EXE with SHA-256 `87b5e97ff24850bc0ed03ad1518f11be313d163232eaf9895be9404ebdf63ef1`. All 169 single-image groups, 26 interaction cases and 24 real bilingual DPI cases pass against that exact image; the 200% Chinese Translation and English Bell screenshots were visually inspected. The aggregate run is not green: both full-grid memory jobs failed.

The complete MinGW comparison also passes, including its twelve existing screen-clamped memory workloads. Its separately built frontend has SHA-256 `6b862df301b57402488a24d3d682eea91b69b3d378f95a2a77e35088dfd3382b`; those results are not attributed to the single image or to the full Sarasa grid.

The [single-EXE artifact 14308312240](https://github.com/xiongnemo/nemoterm/actions/runs/44031481269/artifacts/14308312240) contains only `nemoterm.exe`. The downloaded ZIP is 2,620,948 bytes, SHA-256 `179d56144dd420509208817d47851b10fd84ca5119d88fc086059034c4668418`; its member matches the tested source-host image above. This candidate is available for inspection, but is not promoted as passing the added full-grid acceptance. The older distribution in `dist` is unchanged.

| Workload | GDI private WS peak, bytes | GDI result | DirectX private WS peak, bytes | DirectX result |
| --- | ---: | --- | ---: | --- |
| Text/history | 16,269,312 | pass | 25,649,152 | memory fail |
| Inline PNG | 17,195,008 | pass | 27,406,336 | memory fail |
| Animated GIF | 17,281,024 | pass | 27,447,296 | memory fail |
| Kitty PNG | 17,293,312 | pass | 27,222,016 | memory fail |
| Compressed Kitty | 17,141,760 | pass | 27,643,904 | memory fail |
| Unicode Kitty cells | 19,120,128 | capture timeout; incomplete | 28,372,992 | memory fail |

The dense GDI run completed its 24 redraw/resize transitions and final 160×48 reseed. Its 6,351 uninjected memory samples span 671.157 seconds, with total WS peak 53,760,000 bytes and private commit 22,425,600 bytes. The first inactive-tab snapshot verified all 7,268 image cells. After selecting that tab, the second strip's public automation request exceeded the unchanged six-second client deadline. Only 7,426 of the required 29,072 cell centres were verified; later lifecycle checks did not run. Cleanup exited naturally. **This is not a passing acceptance result**, even though its sampled private WS was below the target. It does not establish why the capture timed out.

All six DirectX cases reached their final unchanged memory assertion after functional/pixel/lifecycle checks; no cleanup was forced. Both original failure artifacts remain available: [GDI 14307072054](https://github.com/xiongnemo/nemoterm/actions/runs/44031481269/artifacts/14307072054) and [DirectX 14306288702](https://github.com/xiongnemo/nemoterm/actions/runs/44031481269/artifacts/14306288702).

Fixture commit `ee2cb90` adds per-strip request duration/completion receipts and an accurate post-memory pixel phase label. It changes no product source, timeout, pixel comparison, workload or memory limit. [Targeted replay 44035921495](https://github.com/xiongnemo/nemoterm/actions/runs/44035921495) repeats the six GDI workloads against the same `87b5e97f…` EXE. Five pass; dense Unicode fails again at the second strip of the first active-tab snapshot. All 46 inactive strips and the first active strip completed; the next request lost its pipe connection after **5.003389 seconds**. The server has a five-second UI-dispatch wait, so this is consistent with that deadline, but the record does not distinguish queueing from rendering time.

This replay sampled 6,393 times over 675.532 seconds: **18,849,792 private WS / 53,579,776 total WS / 22,470,656 private-commit bytes**. It again verified only 7,426 of the required 29,072 cell centres. Both incomplete runs exit their owned processes without forced termination; neither is a pass. [Replay artifact 14308696257](https://github.com/xiongnemo/nemoterm/actions/runs/44035921495/artifacts/14308696257) retains per-request timings. Further exact-image retries were not used to seek a green result.

## Remaining acceptance work

All test execution, including both failures and the focused replay, took place on GitHub-hosted runners. The migration is operational. The reproducible full-grid GDI capture failure still needs diagnosis/fixing and a complete pixel/lifecycle pass. DirectX's six full-grid private-WS failures remain explicit under the unchanged 25 MB regression limit; no further DX memory optimization is claimed. Sampled memory reductions and successful component tests do not close either outstanding result.

## Retained evidence

[The selected evidence archive](full-grid-memory-evidence.zip) retains 2,479 files plus an internal per-file SHA-256 index: original and new memory samples, failed and passing case receipts, focused capture timings, compiler negative controls, source snapshots, final run/artifact metadata, single-image and MinGW logs/JSON, all DPI JSON and the two visually inspected DPI screenshots. Complete DPI images remain in [artifact 14306145665](https://github.com/xiongnemo/nemoterm/actions/runs/44031481269/artifacts/14306145665). The archive is **8,032,595 bytes**, SHA-256 **`62ea006ac50d01b6a29f2d9865c9d9864104452f18f20fb91abbd058e2bfc3d3`**; ZIP integrity was checked without executing any downloaded product or test.
