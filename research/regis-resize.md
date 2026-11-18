# ReGIS when a window changes height

With the cursor on the last row, shrinking a 40×12 terminal to 40×10 pushes two rows into temporary scrollback. ReGIS graphics previously stayed at their original screen position. A height change that only removes blank tail rows must keep the drawing in place instead.

[Before the fix](https://github.com/xiongnemo/nemoterm/actions/runs/44226686705), all four jobs used the identical `64c6f69` binary. After the child reported 40×10 and answered the DSR barrier, two 101-pixel green lines still appeared at graphic y=20 and y=80. With a 20-pixel cell height, the first should have moved off-screen and the second should have been at y=40. The first 50 checks passed; `resize-saved-shrink` failed with 202 green pixels where 101 were expected. The window DC and renderer captures agreed.

[After the fix](https://github.com/xiongnemo/nemoterm/actions/runs/44227298756), `4c3bc30` applies the actual number of rows saved or restored to the drawing origin once per resize. Growing the window restores both lines at their original positions. With the cursor at the top, the same resize leaves both lines in place. All four jobs passed **59/59** checks each, including the forced repaint at each size. Actual DirectX, GDI and the visible GDI client DC were observed. The OpenGL request fell back to GDI on this host. This verifies height changes at fixed width, not image clipping or reflow under every resize policy.

The new single executable is **4,853,760 bytes**, SHA-256 `2d9c37cffac9f5316387be47edd4da1503930323d61a921e2f1bede8484a71d2`, original source-host artifact `14394200562`. In the [component run](https://github.com/xiongnemo/nemoterm/actions/runs/44227298255) real terminal framing passed on GCC, Clang and MSVC. All three still fail the existing comparisons to XTerm's retained screen pixels; their recorded failures were preserved.

[Original evidence](regis-resize-evidence.zip): all eight original window artifacts, source-host identity, and all three runs' metadata and job and artifact inventories. SHA-256 `1728166c4297c91aa13920bcfb5a4d21f097802a19bc3f7217db4c61cb0948c5`.
