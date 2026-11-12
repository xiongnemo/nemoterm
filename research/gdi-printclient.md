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
MSVC single-EXE CI still needs to verify the changed capture path.
