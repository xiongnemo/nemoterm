# Kitty placeholder paint batching — 2026-11-17

## Reproduced failure and source finding

The two compact-record GDI runs in the [full-grid memory record](full-grid-memory-ci.md) sampled below 20 MB private working set, but both stopped at the second strip of the first active-tab image capture. They verified only 7,426 of 29,072 cell centres; neither is a passing result. The timing-enabled replay lost its pipe after 5.003389 seconds, consistent with the automation server's unchanged five-second UI-dispatch wait. The retained receipts do not establish the UI thread's exact state at that instant.

Source inspection found an avoidable cost in `terminal.c:do_paint`: Kitty U+10EEEE placeholders already render as blank text, and their positional combining marks are omitted from both rendered text and its cache, but the generic combining-character rule still broke the text run on both sides of every placeholder. The GDI frontend checks image intersections and composes the image background for each text run. A full dense image grid therefore repeated those placement scans thousands of times per paint. Image-band capture also invalidates the terminal for a following paint.

Production commit `9b549fcc264838556e9852c15f065e6c467f9eea` exempts only these hidden Kitty positional marks from the combining-character run boundary. Existing style, colour, character-set, width, cursor and selection rules remain in place. Visible combining glyphs still get separate shaping runs; frontends without Kitty support retain their original PUA text and combining marks. No capture deadline, image budget, history size, grid size, font or memory gate changes.

## Compiler evidence

The new regression forces a complete 160×48 paint with 7,268 image cells and counts calls at the frontend draw callback. It requires all 7,680 text units and at most 144 runs, allowing distinct border character sets. Separate cases exercise adjacent placeholders, visible `e` plus acute accent, colour changes, cursor highlighting, raw protocol text preservation, and Kitty/grapheme modes independently enabled or disabled.

| Revision and run | GCC | Clang | MSVC |
| --- | --- | --- | --- |
| Test-only `0dc6f6f`, [44040910919](https://github.com/xiongnemo/nemoterm/actions/runs/44040910919) | 7,362 runs; fails bound | 7,362 runs; fails bound | 7,362 runs; fails bound |
| Production fix `9b549fc`, [44041427002](https://github.com/xiongnemo/nemoterm/actions/runs/44041427002) | 140 runs; pass | 140 runs; pass | 140 runs; test character-code assertion fails |
| Corrected fixture `62478182996cc0957800f2d03aa009382f86d7fe`, [44041610368](https://github.com/xiongnemo/nemoterm/actions/runs/44041610368) | 140 runs; pass | 140 runs; pass | 140 runs; pass |

The initial Windows assertion assumed every rendered base character uses its Unicode code point. PuTTY's mock Windows font supplies the rendered `e` as direct-font value `0xDD65`. The fixture now decodes that existing direct-font form for the draw assertion; raw terminal-content assertions remain exact. It does not relax the run-count, combining-mark or cursor checks. GCC and Clang also execute the component suite with ASan/UBSan.

This is a reduction from 7,362 to 140 frontend runs (98.1%) for the same 7,680 text units on all three compilers. It demonstrates elimination of the excessive run splitting, not by itself resolution of the full-window capture failure.

## Full regression

[Full run 44041617145](https://github.com/xiongnemo/nemoterm/actions/runs/44041617145) tests source and fixtures at `62478182996cc0957800f2d03aa009382f86d7fe`. Its source-host job built a 4,599,808-byte single EXE, SHA-256 `294912cf11f5cc5be92148ba95435415dabe40c32ea62345d35d5625872bb89f`; the downloaded file matches that receipt. All builds, tests, desktop input and captures run on GitHub-hosted runners; local work is limited to source changes, dispatch and artifact inspection.

The completed aggregate is **19/21 jobs**, not green. All **169 single-image groups**, **24 real bilingual DPI cases**, compiler/sanitizer diagnostics, profiles and the complete MinGW suite pass. The interaction catalog has **25/26 functional cases** and **6/12 full-grid memory cases** passing in this run: shell cleanup and full-grid DirectX memory fail. The GDI failure from the previous candidate is resolved for the tested workload. A later single passing shell replay is reported separately below.

### Full-grid memory and capture results

All six GDI workloads pass at the required actual 160×48 Sarasa grid. All six DirectX workloads reach their final memory assertion after functional checks and natural process exit, but still exceed the unchanged 25,000,000-byte bound. This change does not close the DX memory failure or claim further DX memory optimization.

| Workload | GDI private WS peak, bytes | GDI | DirectX private WS peak, bytes | DirectX |
| --- | ---: | --- | ---: | --- |
| Text/history | 15,548,416 | pass | 26,046,464 | memory fail |
| Inline PNG | 17,100,800 | pass | 27,463,680 | memory fail |
| Animated GIF | 17,539,072 | pass | 27,525,120 | memory fail |
| Kitty PNG | 17,092,608 | pass | 27,594,752 | memory fail |
| Compressed Kitty | 16,941,056 | pass | 27,574,272 | memory fail |
| Unicode Kitty cells | 19,320,832 | pass | 29,245,440 | memory fail |

The dense GDI workload samples 1,223 times across 129.047 seconds before any screenshot or input injection. Its peaks are **19,320,832 private WS / 53,923,840 total WS / 22,138,880 private-commit bytes**. It completes all 24 redraw/resize transitions, final reseeding, four snapshots (two tabs, each active and inactive), **29,072 exact cell-centre comparisons**, all ten lifecycle checks, and natural exit of all 56 owned processes. There is no forced cleanup. Its whole fixture takes 194.531 seconds.

All 184 GDI image-strip requests complete on their first attempt, taking 0.034263–0.739134 seconds each, 57.218248 seconds in total. The old compact-record replay stopped after 47 successful requests, with the next request losing its pipe after 5.003389 seconds. The successful new full workload resolves that previously reproducible GDI capture failure for this tested configuration; the former incomplete records remain intact. Component run counts explain the removed work, while these timings are observations from different hosted runners, not a controlled microbenchmark or proof of the original blocked thread's stack.

Receipts: [GDI artifact 14310064541](https://github.com/xiongnemo/nemoterm/actions/runs/44041617145/artifacts/14310064541), [DX artifact 14310352390](https://github.com/xiongnemo/nemoterm/actions/runs/44041617145/artifacts/14310352390). The DirectX dense case also completes all 29,072 pixel checks, ten lifecycle checks and natural cleanup; its memory result remains failed.

### Other coverage

The 24 real bilingual DPI cases pass against this exact EXE, including five cold scales and live transitions in standalone and tab hosts. The 200% Chinese Translation and English Bell screenshots were inspected for containment and footer separation. Complete images remain in [DPI artifact 14310386267](https://github.com/xiongnemo/nemoterm/actions/runs/44041617145/artifacts/14310386267).

The shell interaction case executes commands and verifies startup directories in all six shells, but fails the controller's natural-exit gate: a same-image process and Git Bash remain after the original three-second grace period. This is a separate unresolved failure, not a successful shell acceptance. [Original shell artifact 14309608283](https://github.com/xiongnemo/nemoterm/actions/runs/44041617145/artifacts/14309608283) retains the failure. Fixture-only `bd0bc40` adds retained process identities and phase snapshots for [diagnostic replay 44043921945](https://github.com/xiongnemo/nemoterm/actions/runs/44043921945), with no timeout or termination-policy change.

That diagnostic replay passes once against the same `294912cf…` image, naturally draining all 271 job members. Its retained handles distinguish frontend, console hosts and shell clients: the Git Bash duplicate's tracked clients and host have exited when its window closes, and all tracked Git Bash processes have exited with the original frontend; the final snapshot has no live tracked processes or diagnostic errors. The earlier forced-cleanup failure remains unexplained. This single replay does not prove that an intermittent shutdown failure is fixed, and it does not overwrite the aggregate run's failed shell job.

The single-image suite passes all 169 groups, including its twelve existing screen-clamped Consolas memory workloads. [Single-image evidence 14311834769](https://github.com/xiongnemo/nemoterm/actions/runs/44041617145/artifacts/14311834769) records the same EXE hash. [Published artifact 14312323506](https://github.com/xiongnemo/nemoterm/actions/runs/44041617145/artifacts/14312323506) contains only `nemoterm.exe`, with the exact 4,599,808-byte image above. Its downloaded ZIP is 2,621,017 bytes, SHA-256 `c004055a00380e4e58d208040228027b68cf29512b03e7966b3ba55d062b0cce`. The candidate is available for inspection, but the aggregate is not an all-green acceptance and the older `dist` distribution is unchanged.

The complete MinGW comparison also passes, including its twelve existing memory workloads. Its separate frontend hash is `57fb28c56752113d6a7dabc9fdef3b242f9d0540406cad1b4fbb68bb91fbb85d`; the dense GDI case uses a 109×34 grid, so those measurements are not substituted for the full Sarasa acceptance above. [MinGW evidence 14313047236](https://github.com/xiongnemo/nemoterm/actions/runs/44041617145/artifacts/14313047236) retains its native logs and receipts.

## Retained evidence

[The selected evidence archive](kitty-placeholder-runs-evidence.zip) contains 2,353 files plus a per-file SHA-256 manifest: all compiler controls, exact committed changes, full run/artifact metadata, downloaded-product verification, single-image and MinGW logs/JSON, 38 original catalog receipts, the diagnostic shell replay, raw full-grid memory samples, all DPI JSON/logs and the two inspected 200% screenshots. The archive is **6,180,109 bytes**, SHA-256 **`ca49f551f11e41da8d26399de49a6d90b46a68960e64bea78aae8132713abfef`**. ZIP integrity was checked without executing downloaded programs or project tests locally. Prior failure evidence stays in the separate archive linked from the full-grid record.
