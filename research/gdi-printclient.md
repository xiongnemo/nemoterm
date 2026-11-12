# Explicit GDI client capture

Main's post-merge Single-EXE run 43318033743 failed the existing renderer test
at the resize comparison. Both compared cases were actually GDI (OpenGL was
unavailable). The first capture retained the old scrollbar at x=722 inside
the new 812-pixel client image and omitted restored scrollback rows; the other
capture showed the resized content. Native source code had not changed from
the previously accepted 74993af binary. This is evidence of an inconsistent
capture/presentation boundary, not evidence that an OpenGL device rendered
different content.

Standalone GDI windows now explicitly implement `WM_PRINTCLIENT` with the
same bounded snapshot renderer already used by tab views. Frozen synchronized
output and retained GPU capture keep their existing paths. The renderer test
uses `PW_CLIENTONLY` to request that explicit client render instead of
`PW_RENDERFULLCONTENT`, which can use a stale DWM redirection surface. It waits
for both resized grid dimensions. Pixel tolerances and scene assertions are
unchanged; no failing scene is skipped or redrawn with replacement content.

`renderer-printclient-observed.json` records a local native development build
passing GDI, actual OpenGL and actual DirectX with SarasaTermSC Nerd Font Light.
It includes text, Sixel, synchronized output, retained expose, resize, palette
and cursor checks. Capture instrumentation means its later memory values are
not memory acceptance results. This build is not the distributed single EXE;
MSVC single-EXE verification of the same source is recorded below.

## Accepted single executable

Source `8f7a9d2674e39f7435a42a0810a6c8cad8a99a51` passed
[portable and sanitizer CI](https://github.com/xiongnemo/nemoterm/actions/runs/43320056823)
and all 57 checks in
[single-EXE CI](https://github.com/xiongnemo/nemoterm/actions/runs/43320056960).
The downloaded 4,371,456-byte executable has SHA-256
`a108894f50f7d797f7d2c01558a71f268a1c812fe365270e5a6a7fb7868ca4ed`.

This exact binary passed local text/Sixel/synchronization/resize/cursor pixel
comparisons with GDI, actual OpenGL and actual DirectX using SarasaTermSC Nerd
Font Light. It also passed the nine-group tab-host fixture at 160 x 48 in
GDI/top and actual DirectX/left, including preview updates and owned-process
cleanup. `gdi-printclient-acceptance.json` records the pre-instrumentation
memory scope; the `capture-8f-*` JSON files retain the detailed observations.
The prior 74993af executable remains backed up under `build/accepted-74993af`.
Grapheme development is separate and is not part of this accepted binary.
