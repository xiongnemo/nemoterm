# Remote Windows DPI checks

The `Remote Windows DPI acceptance` reusable workflow runs on a disposable
GitHub-hosted `windows-2025` desktop. It does not run UI tests or change display
settings on the developer's computer. Display mutations in the native helper
and the real-DPI controller require `GITHUB_ACTIONS=true` and
`RUNNER_ENVIRONMENT=github-hosted`.

## Run against an exact product

For changed production code, **Test and build** can build a fresh single
executable and run DPI acceptance against that exact artifact in one workflow:

```powershell
gh workflow run ci.yml --ref fix/legacy-key-modifiers-20261116 -f scope=dpi
```

The `dpi` scope runs the source-host build and the reusable DPI job. The default
`full` scope and ordinary push/PR jobs keep their existing full-suite behavior.
This targeted workflow is not a claim that all protocol or renderer tests ran.

The existing **Windows UI artifact replay** workflow exposes `suite=dpi`:

```powershell
gh workflow run font-zoom-replay.yml --ref fix/legacy-key-modifiers-20261116 `
  -f suite=dpi -f source_run=43872383575 `
  -f source_commit=1f4db229cd9bc5763dc880126ecc0ba3b7fb2a96
```

Replace the run and full source SHA when production changes. The workflow
requires the source-console-host build job to have succeeded, verifies
`SOURCE-HOST.json`, EXE size and SHA-256, and refuses reuse when production
sources or build scripts differ. The source run can have failures in unrelated
jobs; its artifact is not a claim that the whole source CI passed.

The new `dpi.yml` can also be dispatched directly once it exists on the default
branch. Its inputs are `product_run` and `product_commit`. Until then, the
registered replay entry above calls the reusable workflow from the selected ref.

## What the checks prove

**Real scaling:** enumerate active displays, DPI awareness, physical monitor
bounds, work area, advertised resolution modes and supported DPI scales. Try
the advertised mode with most logical desktop room in both axes (for example,
1600×1200) to make higher real scales available. Request only supported scales
from 100%, 125%, 150%, 175%, 200%.
Verify the resulting DPI on the uninstrumented product's host, terminal view
and settings dialog with `GetDpiForWindow`; API success alone is insufficient.
The settings probe is a small native COM/UI Automation client, compiled only
for CI. It avoids the hosted image's legacy .NET UIA fallback that exposed
standard controls as generic panes and omitted tree nodes. No probe is linked
into the shipped executable.

The real suite tests GDI in English and Simplified Chinese, in standalone and tab modes, with fresh processes at
each available scale and live scale changes while settings are already open.
It checks Profile, Shell, Keyboard, Keyboard/Terminfo, Keyboard/Extended, Bell, Bell/Overload, Bindings, Font, Translation,
Translation/Line drawing, Tabs and Interface language controls
against dialog boundaries and the footer, saves screenshots, compares terminal
cell dimensions and fixed-size Sixel pixels, and checks that input still reaches
the child after closing settings. Owned processes must exit cleanly. Original
display scale and resolution are restored in cleanup.

**Synthetic coverage:** a separate Frida fixture injects `WM_DPICHANGED` at
96, 120, 144, 168, 192, 96 DPI in standalone and tab modes. It checks terminal
pixels, Sixel placement, IMM composition font size and caret position. It saves
both the injected value and the actual Windows DPI, plus a screenshot for each
frame. This tests message handling; it does not establish real high-DPI support.

The test-only DPI scale setter uses undocumented DisplayConfig packets -3/-4;
it is not linked into Nemoterm. Unsupported capabilities are reported explicitly.
Resolution enumeration and changes use the documented
[EnumDisplaySettingsExW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumdisplaysettingsexw)
and [ChangeDisplaySettingsExW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-changedisplaysettingsexw)
APIs, including `CDS_TEST` before applying a mode. Resolution changes by
themselves are never counted as DPI changes.

## Evidence and limits

The Actions summary and `dpi-evidence-<run>-<attempt>` artifact contain:

- `DPI-REPORT.md`: separate real and synthetic results, with coverage gaps.
- `SOURCE-HOST.json`: exact product identity.
- `display-environment.json` and `dpi-real-gdi-{en,zh-CN}.json`: capabilities, requested
  changes, actual window DPI, cell geometry, cleanup and any failure traceback.
- `*-settings.json`, logs and PNGs: page/control geometry and screenshots.
- `synthetic-*/`: IMM/message evidence and per-scale screenshots.

Artifacts are retained for 14 days. Unsupported real scales remain uncovered;
an advertised scale that fails to take effect fails the suite. A single monitor
does not cover moves between monitors with different DPI. This suite does not
certify physical GPU drivers, nested system dialogs, or real IME candidate UI.
The separate `i18n-interaction.json` checks language persistence, Cancel, restart,
per-launch override, Unicode profile names and translated menus on the same image.
These checks do not certify complete translation of every inherited diagnostic.
See [interface language support](I18N.md).
