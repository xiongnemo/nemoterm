# Bounded rectangle capture

Source `f6b3d6412ef3f6fb6ad607b3c00968459fdc500b` extends the existing opt-in
automation image operation with an optional client-pixel rectangle. Empty
payloads retain full-client behavior. Discovery advertises `image-rectangle`
and the current client pixel dimensions. The protocol and CLI are documented
in [AUTOMATION.md](../docs/AUTOMATION.md).

The renderer reads only the requested vertical band into its existing bounded
row buffer, then clips into a rectangle-sized DIB. Synchronized captures use
the retained presentation for both active and inactive tabs. Invalid or empty
rectangles are rejected before allocation. Existing per-axis and output-byte
limits remain. No new dependency or persistent full-window buffer is added.

Animation verification still requires red, green and blue within three seconds
on each tab, after uninstrumented frontend memory sampling. It requests the
same 8 by 8 interior patch when the capability exists, falling back to full
images for older executables. PNG encoding and file writes now occur after
observation. Recorded frame times denote completed image receipt. An 8 by 8
BMP is 310 bytes, compared with 4,933,190 bytes for the retained 1282 by 962
full-client frame.
This improves the observation path; it does not retroactively resolve earlier
failed GIF runs or identify their sole cause.

The local MinGW frontend is 3,934,918 bytes, SHA-256
`54883c9c8d10b62bab8f998e5b1a1ffbcb2ee5d33d967f44a7374349de4f31f5`.
It uses the separately retained source-built console host from `077733e` and
the pinned ConPTY DLL. This is a local development build, **not** single-image
acceptance and not a replacement for the accepted executable.

Actual local GDI, OpenGL and DirectX each pass 24 exact RGB comparisons against
full frames: border pixels, partial glyphs, row-band boundaries, active and
inactive tabs, synchronized presentation and subsequent commit/reactivation.
Malformed rectangles leave capture usable. CLI PNG bytes match the direct API.
All owned process groups exit naturally. The first fixture attempt incorrectly
used new-tab, which started the user's default shell instead of the fixture;
its failure and scoped forced cleanup are retained. Using Duplicate Session
corrected that test setup without changing production or pixel assertions.

The existing GDI/DirectX automation tests and visual bell test also pass on this
same local frontend. The full DirectX and GDI GIF workloads each pass nine
groups of checks, both tabs show all three colours through rectangle capture,
and cleanup is natural. These separately hosted results do not establish memory
acceptance of a future single executable. Raw logs, manifests, observations,
screenshots and source hashes are in [the validation record](cropped-capture-validation.json).

Complete [core](https://github.com/xiongnemo/nemoterm/actions/runs/43622372607)
and [single-image](https://github.com/xiongnemo/nemoterm/actions/runs/43622372605)
CI are pending. The new rectangle fixture is mandatory in both workflows.
