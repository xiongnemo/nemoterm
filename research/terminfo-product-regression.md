# Full hosted regression after Terminfo keyboard integration

[Run 44083541137](https://github.com/xiongnemo/nemoterm/actions/runs/44083541137)
completed at production commit `329019d65618bc547f9f52e8b7277f1800341184`:
**21 jobs pass and one fails**. Only the full-grid DirectX memory job fails.
All builds, product execution, input and screenshots ran on GitHub-hosted
runners; local work only inspected downloaded records, images and binary files.

The [single-file development artifact](https://github.com/xiongnemo/nemoterm/actions/runs/44083541137/artifacts/14332971661)
contains only `nemoterm.exe`: **4,800,000 bytes**, SHA-256
`b4ed0f124b3e17d165b6c0d31c9a02a083477d556dd34ecbdb37d6d9db3458d7`.
Its actual downloaded bytes match the source-host and validation manifests.
This is a development download with the explicit DirectX limitation, not an
all-green release or a replacement for the separately identified `dist` image.

## Completed checks on the exact product

| Area | Result |
| --- | --- |
| Single executable | All 170 groups pass, including its twelve existing screen-clamped memory workloads. The execution directory contains only `nemoterm.exe`. |
| Terminfo keyboard | 1,293 native input streams, zero mismatches; all four independent SetTcap/GetTcap combinations pass. The 85 named physical-key/local-binding exclusions remain explicit. |
| Compiler comparison | Complete MinGW native suite and its twelve existing memory workloads pass; Linux ASan/UBSan and MSVC diagnostics pass. |
| Interaction | 26/26 cases pass: input, selection, clipboard/drop, isolated real Codex/OpenCode clients, rendering, mouse, four tab sides, settings, six shells and bell APIs/pixels. |
| Shell lifetime | 24 Git Bash repetitions and six native controls pass with natural private-job drainage. |
| Real DPI and layout | 24 bilingual standalone/tab cases; 44 frames, 572 page checks and 3,344 control checks pass. The 13-page matrix includes Keyboard, Terminfo and Extended; their English/Chinese 200% screenshots were also visually inspected. |
| Full-grid GDI | All six actual 160x48 Sarasa workloads pass, including post-memory pixel/lifetime checks and natural cleanup. |
| Full-grid DirectX | All six fail the unchanged 25,000,000-byte private working-set gate; functional checks and natural cleanup complete. |

The MinGW frontend is a separate **4,236,309-byte** image with SHA-256
`c51c13e076dd15527e23d6705b683f2dcb9575119249427674530339310c21ce`.
Its own 1,293 native Terminfo streams also have zero mismatches. Its results
are not substituted for the single-image results. Core lookup, native
projection, identity boundaries and original failures are documented in the
[Terminfo record](terminfo-database.md).

## Memory scope

The actual font is `SarasaTermSC Nerd Light`, the full 160x48 grid is not
clamped, and memory samples are uninjected frontend peaks. The complete six-row
table remains in the [Terminfo record](terminfo-database.md).
GDI peaks at **18,817,024 private-WS bytes / 53,497,856 total-WS bytes** and meets
its <20 MB private / approximately 50 MB total requirement. Private commit is
recorded separately and is not substituted for private working set.

DirectX private working sets range from **25,436,160 to 28,778,496 bytes**.
The user's instruction to stop further DirectX memory optimization remains in
effect. The failed regression limit is retained, not waived or reported green.
Hosted input and sound API checks do not certify physical devices, audible
sound or third-party IMEs; hosted DPI does not test moving physical monitors.
Missing protocol families remain missing.

## Portable package notices

File inspection found that the original MinGW ZIP omitted the standalone
Ncurses and X11 colour notices. The single EXE already embeds the notices;
the complete Ncurses text was also located in its downloaded binary.
The ordinary CI packaging recipe now includes both separate text files.

[Notice-only replay 44095587057](https://github.com/xiongnemo/nemoterm/actions/runs/44095587057)
passes on a hosted Ubuntu runner at fixture
`9a630054a74d45e226826b94fe133481804fa557`. It first verifies the original
source commit, successful build jobs, unchanged production sources and image
hashes. It then copies only the two notice files and adds `PACKAGING-REPLAY.json`.
**All 14 original files remain byte-identical**, including all three binaries.
The [completed portable package](https://github.com/xiongnemo/nemoterm/actions/runs/44095587057/artifacts/14332514476)
contains 17 files. It retains the original production identity; it is not a
new build or a new regression result.

The first replay, [44095359889](https://github.com/xiongnemo/nemoterm/actions/runs/44095359889),
failed because the checksum reader did not recognize GNU sha256sum's binary
`*` marker. The parser now accepts the exact recorded checksum format without
relaxing the hash check. The failed job, logs and original artifact are retained.

## Evidence

[The integration archive](tcap-integration-evidence.zip) includes final run,
job and artifact metadata, complete single-image/MinGW evidence ZIPs,
interaction/memory records, the original failed/cancelled predecessors and
both notice replays. Product ZIP receipts and all file hashes are retained;
duplicate binaries are omitted after file-only identity verification.
Large successful DPI artifacts retain all JSON/logs and the six inspected
200% Keyboard/Terminfo/Extended images in explicitly named selected ZIPs.

The archive has **179 entries**, **20,689,733 bytes**, SHA-256
`c978c3c8ae0776184faa38190fda77f2aeaab7c5bcc5f35713dd9b5a9f32d8e9`.
Historical in-progress snapshots remain named as such; final metadata now
records the completed 21/22 result.
