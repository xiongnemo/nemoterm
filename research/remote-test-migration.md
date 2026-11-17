# Remote test migration — 2026-11-17

All automated execution is assigned to GitHub-hosted runners. No test suite, terminal window, clipboard interaction or display change was executed on the developer desktop during this migration.

This page retains the initial migration baseline. The later expanded product
regression at `8084338` completes **21/22 jobs**, with only full-grid DirectX
memory failing; see the [final product record](closed-console-regression.md).
The subsequent [reference collector migration](remote-reference-migration.md)
also supplies hosted entry points and passing receipts for all 33 current
invocations of 25 older XTerm collectors, plus independent ncurses controls.
Original failures remain recorded in both follow-ups.

## Accepted full run

[Run 44019109177](https://github.com/xiongnemo/nemoterm/actions/runs/44019109177) completed successfully: **19/19 jobs** at product and fixture commit `2312edd86e08c4454bde9f675af030ea3134d3e7`. No production source changed during this migration.

The [downloadable single-executable artifact](https://github.com/xiongnemo/nemoterm/actions/runs/44019109177/artifacts/14303645464) contains only `nemoterm.exe`, **4,599,296 bytes**, SHA-256 **`dfb9c0093f18ce53ff056d850bc20defcbdeed89f179b4ced7f63a218aa65f6f`**. The downloaded ZIP was inspected without executing it; its SHA-256 is `68fdad78e9f79124057108b70c0f4bae9368a1c17cbb98e4309e1b75c5e0b781`.

| Coverage | Final result |
| --- | --- |
| Isolated single executable | 169 groups passed, including native protocols, pixels, GPU recovery, modality, profiles, real Codex and twelve memory workloads. |
| Hosted interaction catalog | 26/26 passed across ten groups; every case records the same product hash and fixture commit, with no forced cleanup. |
| Real DPI | 24/24 cases passed: English/Chinese, standalone/tabs, five cold scales from 100% to 200%, and live 96→120→144→168→192→96 DPI transitions. |
| DPI settings geometry | 44 frames, 440 page checks and 2,508 control checks passed containment, footer separation and text fitting; eight language preference/persistence checks passed. |
| MinGW comparison | Complete native suite and all twelve memory workloads passed; legacy modifiers include 2,704 native cases plus 112 startup cases. |
| Other aggregate jobs | Source host, MSVC diagnostics, Linux ASan/UBSan, profiles, interaction orchestration and pinned BusyBox build all passed. |

The single-image, interaction and DPI receipts share the exact executable above. The separately built MinGW frontend has SHA-256 `3e3169a93b35e78c3175c42cd2a65b334ede9e499265f794e2c38622187ba8ae`; its results are not attributed to the single image. Existing native memory workloads use Consolas and retain their actual screen-clamped grids (the single-image run records 109×34 and 88×35). All gates passed unchanged; these runner measurements do not overwrite historical full-desktop Sarasa measurements. The interaction matrix separately uses the pinned Sarasa Light font.

The retained 200% Chinese tab-host Bell and Translation screenshots were also visually inspected. Complete DPI screenshots and logs remain in [DPI artifact 14301175362](https://github.com/xiongnemo/nemoterm/actions/runs/44019109177/artifacts/14301175362); the complete single-image evidence is [artifact 14302564355](https://github.com/xiongnemo/nemoterm/actions/runs/44019109177/artifacts/14302564355).

[The compact evidence archive](remote-test-migration-evidence.zip) retains 821 files, including an internal per-file hash index, final run/job/artifact metadata, downloaded-product verification, 26-case receipts, DPI JSON, selected screenshots, memory records and original failure/replay logs. It is **5,344,993 bytes**, SHA-256 **`5212b6626e02bc9e4faae0ad70e8bce993617c7d599d253d151bda4843536b3c`**. Complete originals remain in the linked Actions artifacts; the archive is an intentionally selected long-term record.

## Initial replay identity

Initial replays use source commit `24206a79d85b7b1428fe980ec70db067540ddb5a` from the successful source-host job in [run 44013160599](https://github.com/xiongnemo/nemoterm/actions/runs/44013160599). The single executable SHA-256 is `a84c6e7f8c57bb6c65cbcd1d2d2bedb50aafcce1cb7fb8c1cd466434e361169f`. Fixture commits are separate from product identity; replay rejects production/build changes.

## Migration

- `ci.yml` full scope now calls the single-executable, real DPI/i18n and interaction reusable workflows, alongside the existing compiler/protocol/profile jobs.
- `remote-interaction.yml` covers the former 26-case local catalog in ten isolated Windows groups, preserving functional assertions and bounded timeouts. It uploads per-case results, logs, screenshots and provenance even on failure; the evidence-driven OpenCode timeout change is described below.
- The controller preserves CI identity and refuses non-hosted desktops. Windows PowerShell fixtures get their own module path instead of inheriting pwsh's modules.
- The Sarasa v2.3.1 archive is pinned by SHA-256. Its actual English Windows Light family is `SarasaTermSC Nerd Light`, unlike the developer machine's older family name. The installer reads the TTF name table and verifies the actual GDI selection.
- BusyBox uses upstream commit `5f09fb446adf81d005f0aad9dc47eca19ac3b74c`, cross-compiled with `mingw64u_defconfig` on a hosted Linux runner. Windows shell/drop jobs consume that exact artifact. This avoids the publisher download host's 403 response to hosted runners.
- Codex 0.167.0 and OpenCode 1.19.3 use locked native packages and isolated loopback providers, with tools/permissions disabled. The shell group requires all six supported shells, including WSL Bash.

## Retained runs

| Run | Purpose / observed result |
| --- | --- |
| [44013160599](https://github.com/xiongnemo/nemoterm/actions/runs/44013160599) | Baseline full CI: source-host, MSVC and sanitizers passed; profile tests failed waiting for old pre-i18n button names. |
| [44014652245](https://github.com/xiongnemo/nemoterm/actions/runs/44014652245) | First hosted interaction attempt: font substitution was rejected before GUI cases ran. |
| [44015087432](https://github.com/xiongnemo/nemoterm/actions/runs/44015087432) | Input, selection, rendering, mouse, tabs and bell groups passed; Codex image paste passed. BusyBox download, inherited PowerShell modules and OpenCode image attachment exposed additional runner issues. |
| [44014656219](https://github.com/xiongnemo/nemoterm/actions/runs/44014656219) | Single-executable replay reached GPU lifetime, then exposed the old UIA top-level-only dialog lookup. Earlier native protocol/pixel cases passed. |
| [44015750519](https://github.com/xiongnemo/nemoterm/actions/runs/44015750519) | Settings and the existing non-client groups passed; retained OpenCode diagnostics proved the image arrived after the old timeout. |

The same initial product now has passing receipts for all 26 catalog cases: input/selection/rendering/mouse/tabs/bell in 44015087432, settings in 44015750519, both real clients in [44016623766](https://github.com/xiongnemo/nemoterm/actions/runs/44016623766), both drop modes in [44017088076](https://github.com/xiongnemo/nemoterm/actions/runs/44017088076), and all six shells with clean fixture teardown in [44017963026](https://github.com/xiongnemo/nemoterm/actions/runs/44017963026).

OpenCode's successful image attachment took 18.922 s and 11.829 s on the fresh runner. The failure-only independent WinForms reader had returned the generated image, and the retained failure screenshot showed the attachment after the original 20 s bound. The new 60 s limit records actual latency; image-content and natural-exit assertions are unchanged.

WSL 1 retains Linux init processes beyond the terminal shell's lifetime. The hosted-only shell fixture first verifies that Bash/ash no longer appear in `ps`, then terminates its test distribution before the Job's unchanged no-leftover-process assertion. ANSI BusyBox's Chinese-path failure remains recorded; UTF-8 coverage uses the upstream Unicode build, not relaxed path comparisons.

[UI replay 44018420802](https://github.com/xiongnemo/nemoterm/actions/runs/44018420802) passed three repetitions each of standalone/tabbed modality and zoom, plus GPU failure/recovery/lifetime. GPU UIA lookup now searches only the owned process's window subtrees. Modal checks wait for a valid atomic mailbox snapshot instead of interpreting a sharing-violation read as empty input; every blocked check retains before/after snapshots and still requires exact equality.

The initial profile failure was resolved by expecting the English UIA mnemonic suffixes. The standalone Unicode image selection fixture now explicitly requests `--no-tabs`, preserving its content-window identity assertion after tabs became the product default.

A green API bell test is not a human hearing result. Hosted injected input and real DPI evidence do not certify arbitrary physical devices, third-party IME candidate windows or multiple physical displays. No previous local result is attributed to a different executable.
