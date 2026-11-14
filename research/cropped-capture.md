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

The original [core run](https://github.com/xiongnemo/nemoterm/actions/runs/43622372607)
failed after 48 successful pixel comparisons: the child report `PID.json` and
parent command `PID.control` both used `PID.tmp` for atomic replacement. Their
writers collided during the final stop command. The failed MinGW image hash,
log and forced cleanup are retained. Fixture `72754a3` gives commands a distinct
stem (`PID-control.json`), with no production or pixel assertion changes.

The corrected fixture passes all 72 comparisons and natural cleanup on the
same local development EXE. A separate
[focused replay](https://github.com/xiongnemo/nemoterm/actions/runs/43624369253)
passes rectangle and existing GDI/DirectX automation checks against the original
source-built MSVC host, SHA-256
`bdc2cb95528fbeae999da672c0c9d655df5bae92c7668020fff717eafb3cbb44`.
This is the same production source, not the failed MinGW executable. On the
runner, the OpenGL request falls back to GDI; actual local OpenGL passed above.

The original [single-image run](https://github.com/xiongnemo/nemoterm/actions/runs/43622372605)
passes all 124 mandatory checks, including the original rectangle fixture.
Its downloaded 4,487,168-byte EXE has SHA-256
`820f36f4e455d43bdce5403be503c160d5610eb141d8b46f9c84d2410072541b`,
matching its validation and rectangle records. That success does not erase the
core fixture race or establish local memory acceptance for this single image.
Complete corrected-fixture
[core](https://github.com/xiongnemo/nemoterm/actions/runs/43624369125) and
[single-image](https://github.com/xiongnemo/nemoterm/actions/runs/43624369106)
workflows both pass at `72754a3`, including all 124 mandatory single-image
checks. The downloaded 4,487,168-byte single image has SHA-256
`e271b9be8788e4de25a999910559ba7fadc319da8b27a2ee6bca498f057f98ce`.
Its validation, rectangle, renderer, zoom, visual-bell and tab-profile records
match that exact image. The separate MinGW core image also passes all 72
rectangle comparisons with natural cleanup. On both runners, OpenGL requests
fall back to GDI. Complete workflow logs, artifact metadata and sanitizer logs
are retained. These results do not substitute for local memory measurement of
this newer executable. The accepted executable remains unchanged.

The formal single image `820f36f` also passes both local GIF workload runs with
fixture `b95c406`, at 160 by 48 cells in SarasaTermSC Nerd Font Light. Each run
passes nine check groups and exits naturally. DirectX has 528 samples and peaks
at 24,080,384 bytes private working set, 60,387,328 total working set and
92,676,096 private commit. GDI has 512 samples and peaks at 16,719,872,
39,428,096 and 19,558,400 bytes respectively. Memory sampling is uninstrumented
and ends before image capture. All three colours appear on both tabs within the
unchanged three-second observation limit. These runs meet the private-working-
set limits; DirectX total working set remains above the approximate 50 MB target.
They do not retroactively resolve earlier failed images or establish complete
application acceptance. The exact image identity, observations, samples, logs
and bounded screenshots are retained in the validation record.
