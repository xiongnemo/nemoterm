# Remote DPI acceptance

Product: source `1f4db229cd9bc5763dc880126ecc0ba3b7fb2a96`, single
`nemoterm.exe` (4,556,288 bytes), SHA-256
`7c5c8bb866cafa4506b97cc52214b9b90c7d8b50353e5ae6e9eef4a9be9fb4cb`.
No production code or executable was changed for this test work.

The [full DPI run](https://github.com/xiongnemo/nemoterm/actions/runs/43917759452)
passed with fixture `88651fa` on a GitHub-hosted
Windows Server 2025 runner. Evidence is in its
[artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43917759452/artifacts/14249614600)
and the repository archive [dpi-ci-88651fa.zip](dpi-ci-88651fa.zip).
The previous complete run `43917085419` also passed; the final run adds explicit
host-class evidence (`Nemoterm` / `NemotermHost`) and confirms active GDI.

## Measured results

The default 1024×768 desktop advertised only 100% and 125%. An advertised
1600×1200 mode enabled all five target scales. Changing to 1920×1080 alone
provided at most 175%; the final fixture chooses a mode with room in both axes.

| Real scale | Host / terminal / dialog DPI | Consolas cell pixels |
|---|---|---|
| 100% | 96 / 96 / 96 | 9×19 |
| 125% | 120 / 120 / 120 | 11×23 |
| 150% | 144 / 144 / 144 | 13×28 |
| 175% | 168 / 168 / 168 | 15×33 |
| 200% | 192 / 192 / 192 | 18×37 |

Both GDI host modes passed five fresh-process starts and a live sequence
100→125→150→175→200→100% with a settings dialog open during each change.
Across 22 real-DPI frames, the seven settings pages were inspected 154 times.
All tested control rectangles were visible, contained and clear of the footer.
The 24×12 Sixel remained at the expected cell-relative position with unchanged
pixel dimensions. Input still reached the same child after closing settings.
All owned process jobs exited without forced termination. Cleanup restored
the initial 1024×768, 96-DPI desktop.

Representative 125% and 200% Bell, Overload, Font, Shell, Tabs and terminal
screenshots were also visually reviewed. The seven page assertions cover
selected controls; they are not exhaustive text-overflow analysis of every
possible user value or every settings page.

Separate synthetic standalone/tab fixtures passed injected DPI values
96,120,144,168,192,96, checking pixels and IMM composition geometry. Actual
Windows DPI stayed at 96 throughout those cases. They are clearly separated
from real-system acceptance in JSON and the Actions summary.

## Fixture diagnosis and remaining coverage

Initial real-system attempts reached each requested DPI but failed to locate
the settings tree through the hosted image's legacy managed UIA client. Its
element dump showed generic HWND panes with no tree nodes; captured dialogs
were present. A test-only native COM/UIA client resolved this. Missing controls
and clipping still fail the test; no layout assertion was relaxed.

This is English/GDI acceptance. Mixed-DPI multiple monitors, physical GPU
drivers, DirectX/OpenGL DPI behavior, nested system dialogs, real IME candidate
UI and the planned Chinese UI remain outside this run. No local desktop tests
or display changes were performed. See [DPI CI instructions](../docs/DPI-CI.md)
for the reusable workflow and exact-artifact replay command.
