# Remote test migration — 2026-11-17

All automated execution is assigned to GitHub-hosted runners. No test suite, terminal window, clipboard interaction or display change was executed on the developer desktop during this migration.

## Product identity

Initial replays use source commit `24206a79d85b7b1428fe980ec70db067540ddb5a` from the successful source-host job in [run 44013160599](https://github.com/xiongnemo/nemoterm/actions/runs/44013160599). The single executable SHA-256 is `a84c6e7f8c57bb6c65cbcd1d2d2bedb50aafcce1cb7fb8c1cd466434e361169f`. Fixture commits are separate from product identity; replay rejects production/build changes.

## Migration

- `ci.yml` full scope now calls the single-executable, real DPI/i18n and interaction reusable workflows, alongside the existing compiler/protocol/profile jobs.
- `remote-interaction.yml` covers the former 26-case local catalog in ten isolated Windows groups, with original assertions and timeouts. It uploads per-case results, logs, screenshots and provenance even on failure.
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
