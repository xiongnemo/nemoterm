# Hosted interaction measurements for `d817161`

[Interaction run 44219449176](https://github.com/xiongnemo/nemoterm/actions/runs/44219449176) reused the `d817161f32a3ef0699927da1c0739764dcd5c3dd` EXE from source run `44131192187`, SHA-256 `34ae5cc92ab681e253955435b462f04b8b7c66db87b2c3f49bdc7debe55bf2a6`, 4,853,248 bytes. Fixture `b0122f165496196c964cee294d6906cf6e3e79fb` executed all 39 cases: **38 passed**, including all 12 memory cases. The functional failure, the corrected fixture and [the three passing selection cases on the same image](agent-selection-roundtrip.md) are recorded separately. The first run stays failed. Together these runs exercise every interaction case, not every terminal protocol. The complete rebuild has its own [aggregate run 44220302070](https://github.com/xiongnemo/nemoterm/actions/runs/44220302070). Its unchanged ReGIS historical comparison again reports 10 differing frames on each of GCC, Clang and MSVC, in whole and bytewise input.

Both renderers used `SarasaTermSC Nerd Light` and an unclamped 160×48 grid. The table gives the **frontend** peaks in decimal bytes. Each record identifies the observed renderer and separates host/client counters. No injection, forced working-set trimming or sampling error is reported for these memory observations. Both jobs exited naturally.

| Workload | GDI private WS | GDI total WS | GDI private commit | DirectX private WS | DirectX total WS | DirectX private commit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Text/history | 16,420,864 | 52,146,176 | 18,874,368 | 26,644,480 | 70,881,280 | 29,130,752 |
| Inline PNG | 17,530,880 | 54,087,680 | 20,094,976 | 27,385,856 | 72,433,664 | 30,101,504 |
| Animated GIF | 17,731,584 | 54,427,648 | 19,800,064 | 27,844,608 | 73,035,776 | 30,941,184 |
| Kitty PNG | 17,526,784 | 54,157,312 | 19,804,160 | 27,189,248 | 72,228,864 | 30,265,344 |
| Compressed Kitty | 17,739,776 | 54,292,480 | 20,246,528 | 27,594,752 | 72,503,296 | 30,265,344 |
| Unicode Kitty cells | 19,578,880 | 56,086,528 | 22,802,432 | 28,839,936 | 74,104,832 | 32,731,136 |

GDI peaks at **19.58 MB** against the strict 20,000,000-byte private-WS ceiling; DirectX peaks at **28.84 MB** against the inclusive 30,000,000-byte ceiling. GDI total WS peaks at **56.09 MB**, above the approximate 50 MB guide. DirectX total WS peaks at **74.10 MB**; the 50 MB guide does not apply there. The real Codex GDI run is a different workload (6.89 MB private WS); it is not a substitute for these stress cases.

The [hosted evidence archive](interaction-d817161.zip) includes both original memory artifact ZIPs (`14389334757` and `14389778086`), final run/job/artifact records and unchanged per-group result/identity records for the other ten groups. The separate [agent/selection archive](agent-selection-roundtrip.zip) retains the native screenshots, clipboard observations, original failure and corrected selection replay. The memory archive has SHA-256 `d6e7e336624ed7e70740d7e4fa0ad1c68ae3bba8f08865b656dc5913688792f6` (818,232 bytes).
