# ReGIS native single-image checkpoint

[Full run 44127238943](https://github.com/xiongnemo/nemoterm/actions/runs/44127238943)
builds source `a0c35e600bf428ee5716dd6050545b4fd506896b` into one executable:
**4,852,224 bytes**, SHA-256
`4d5fcd1e6ac47dfcd15c1731eb11e0b612b1d0a16915d0106c3846c7dd5baf04`.
Its source-host build and all four ReGIS native-window jobs passed. The
aggregate run was still active when this checkpoint was retained; it already
contains the unchanged failing historical ReGIS frame comparisons. This
document does not claim a successful full regression or replace `dist`. The
aggregate subsequently finished with three failed historical comparison jobs
(GCC, Clang, MSVC) and a cancelled single-EXE job. Its native test step succeeded; the job
reached its one-hour limit while uploading the executable. The six memory workloads
per renderer completed on this image: private working set peaked at 19,218,432
bytes on GDI (artifact `14349154556`) and 28,790,784 bytes on DirectX
(`14350915219`), both on the Unicode Kitty workload at 160×48.

An expanded [screen-edge replay](regis-screen-edges.md) subsequently fails
alternate-screen restoration on this same executable. The 30-check results
below remain a finite historical checkpoint; they are not full acceptance.

## Native results

Each job verifies the source-host manifest, exact EXE size and hash, unchanged
production code, and the pinned Sarasa Light font. It starts an owned terminal
job and sends real application output through the embedded console host.
No local execution or desktop interaction was used.

| Requested mode / capture | Actual renderer | Exact checks | Result |
| --- | --- | ---: | --- |
| GDI / public image API | GDI | 30 | Pass |
| DirectX / public image API | DirectX, fallback forbidden | 30 | Pass |
| GDI / visible client DC | GDI | 30 | Pass |
| OpenGL / public image API | **GDI fallback** | 30 | Fallback passes; OpenGL unverified |

The presented GDI probe uses `GetDC(owned HWND)` and `BitBlt`, without the
image API or `WM_PRINTCLIENT`. It temporarily raises only the owned window
without activation. Thus its checks observe already presented output rather
than asking the terminal to redraw into a capture surface. The GPU image API
observes the retained active renderer surface, not the physical compositor.

The checks compare every pixel in a 160x120 graphic region, with independent
line/rectangle geometry and exact RGB values. They cover two lines and a
position reply, exposure, line/display erasure and subsequent exposure,
forward/reverse scrolling, remapping after scrolling, hidden/displayed pages,
main/alternate screen restoration, both directions of shared ReGIS/Sixel
palette updates, and hard reset. All expected replies match. Representative
original PNGs were also visually inspected, including presented GDI and
DirectX after erasure, scrolling and palette updates.

All four jobs exit naturally: each owned job reports three total processes,
zero active processes and zero terminated processes. No forced cleanup was
needed. The actual renderer identity remains stable throughout each case.

## Limits

These explicit geometry and lifecycle checks are separate from the original
XTerm comparison. The same aggregate run repeats its **9 failed frames out
of 131**, on GCC, Clang and MSVC, in both whole-write and bytewise input.
The original 37-scene / 70-frame parser comparisons and new two-way palette
comparisons still pass. The independent presented-versus-exposed upstream
investigation is retained in [the image-view record](regis-image-views.md).
No gate or expected historical image was changed to obtain this checkpoint.

This window suite does not cover every protocol operation, all client pixels,
native vector text/curves, partial margins, font zoom, resize/scrollback,
eviction under pressure or delay scheduling. OpenGL hardware execution remains
unverified on this hosted runner. Process memory is measured by the separate
full-grid workload jobs; these captures do not establish the 20/30 MB targets.
Tektronix remains unimplemented, and ReGIS is not advertised as supported.

## Evidence

[regis-native-window-evidence.zip](regis-native-window-evidence.zip) contains
the original source-host ZIP (including the exact executable), all four
original window artifact ZIPs, receipts, complete logs for those five jobs,
run/job/artifact snapshots, analysis and a per-entry hash manifest. It has
**20 entries, 2,824,759 bytes**, SHA-256
`c5a10c3f1812964c03f99a2445fcbac8a803b391518cb595e9d883bbef40bbb4`.
All archive entries were read back and verified. The stored aggregate
snapshot is explicitly live, not rewritten as a final successful result.

The source artifact is `14349191560`. Window artifacts are GDI `14349520954`,
DirectX `14348043167`, presented GDI `14348107903`, and OpenGL-request/fallback
`14348827474`. Each contains the same EXE identity and its original PNG/BMP
captures, input sequences, replies, pixel differences and cleanup records.
