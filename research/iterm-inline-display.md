# OSC 1337 static inline image integration

The development branch now connects the existing streaming transport to the
terminal and native renderers. This is a local validation checkpoint, not a
replacement for the accepted main executable or a claim of full iTerm2 parity.

## Implemented behavior

`File=inline=1:...` and `MultipartFile` / `FilePart` / `FileEnd` stream through
the terminal parser without enlarging its ordinary OSC string buffer. BEL,
7-bit ST, ordinary OSC cancellation and fragmented input retain their framing.
CAN/SUB now release an active inline transfer in the parser's common early
cancellation path. Unrelated OSC commands may occur between multipart pieces.
Resize, font-cell changes, RIS and destruction release pending transfers.

The Windows frontend uses WIC's Microsoft codecs for PNG, JPEG, BMP and
single-frame GIF. It accepts no filename authority from OSC, writes no download,
and releases all decoder/stream interfaces before returning to the parser.
The input buffer remains owned throughout the synchronous borrowed stream.
WIC is a Windows component; no separate codec DLL is added to the distribution.
The source overlay links `windowscodecs.lib`, including the single-EXE build.
References: [WIC memory-stream lifetime](https://learn.microsoft.com/en-us/windows/win32/api/wincodec/nf-wincodec-iwicstream-initializefrommemory)
and [the iTerm2 protocol](https://iterm2.com/documentation-images.html).

Natural raster pixels and display dimensions are stored separately. Cell,
pixel, percentage and auto dimensions resolve before allocating retained
metadata; aspect preservation fits inside the specified dimensions. Auto/auto
fits the viewport width when necessary. Zero or over-limit dimensions are
rejected. Nearest-neighbor sampling does not allocate another full image.
Placement uses the current cursor on completion and advances to the final image
row, preserving its column. This explicit placement policy has not been
compared against a running macOS iTerm2 instance.

Generic raster sources share Sixel's reference-counted ownership, erase masks,
partial scrolling, history and alternate-screen lifetime. Retained sources,
pending Sixel and iTerm transfers, growth overlap, raster pixels and metadata
share the existing 4 MiB per-terminal image budget. Oldest retained views are
evicted when necessary. Input files are limited to 2 MiB, FilePart base64 to
1 MiB, headers to 4,096 bytes, and dimensions to 8,192 pixels. WIC's internal
codec workspace and allocator overhead are not claimed to be covered by that
accounting; process memory must be measured separately.

Opaque spans keep the existing direct row path. Partial alpha uses a lazy
one-row DIB, premultiplication and source-over composition. OpenGL and DirectX
reuse the existing bounded overlay readback/upload path. Visible translucent
images invalidate the grid for the current paint, preventing repeated cursor
repaints from accumulating opacity. This favors correctness and bounded CPU
storage; it is not a shader-based GPU alpha pipeline. Off-screen translucent
history does not force that grid repaint.

## Local validation

The candidate single executable is 4,518,912 bytes with SHA-256
`6c1bfae51422477abe5a87c3a2e44bb0843ba2d27d75d33cea68cba3ae97711b`.
It was linked against the existing source-built console host; the link response
and every concrete input hash are retained. It has not been promoted to `dist`.

Real ConPTY output and public automation captures check 31 scenes in each of
GDI, OpenGL and DirectX: PNG/JPEG/BMP/static GIF; BEL/ST; multipart boundaries
inside base64 quartets; cell/pixel/percentage sizes; aspect preservation;
transparent and partial-alpha pixels; repeated repaint; changed background;
image-over-image composition; reset/erase; alternate screens; upward/downward
scroll; malformed transport and codec recovery; cancellation; excessive image
dimensions and decoded-raster budget rejection. The requested GPU backends
must actually run; fallback cannot turn these checks green. Jobs and profiles
are private to the fixture, ordinary API IO does not focus windows or access
the clipboard, and cleanup records distinguish natural exit from forced cleanup.

The portable transport suite adds dimension and arithmetic-boundary tests.
The shared graphics core suite adds mock-codec tests for framing, pixels,
placement, multipart/Sixel interleaving, cancellation, resize, unsupported
frontends, retained-source eviction and combined pending budgets. Ordinary
Linux and ASan/UBSan with leak detection pass the transport, graphics lifecycle,
OSC 52 and SGR suites. MSVC transport, decoder, terminal and graphics tests
also pass. Native renderer and Sixel regressions are checked against the same
final executable. All nine final local controller runs completed with natural
process cleanup. Each memory run completed its nine functional/resource groups;
the 56 inner job processes and 58 outer job processes exited naturally.

The 160x48 full-grid workloads use `SarasaTermSC Nerd Font Light`, retain two
2,000-line histories, and perform 24 tab/resize/redraw transitions. The original
Sixel workload and an additional workload with 512x288 half-alpha PNG images
use identical memory/resource limits. No working-set trim, injected memory
observer or image-capture helper is used during the sampling phase.

| Workload | Samples | Peak private WS (bytes) | Peak total WS (bytes) | Peak private commit (bytes) |
|---|---:|---:|---:|---:|
| GDI baseline | 527 | 16,355,328 | 43,122,688 | 19,046,400 |
| GDI with inline images | 599 | 17,145,856 | 44,539,904 | 20,221,952 |
| DirectX baseline | 512 | 24,092,672 | 63,590,400 | 92,372,992 |
| DirectX with inline images | 642 | 24,907,776 | 64,991,232 | 89,448,448 |

These local measurements pass GDI `<20,000,000` and DirectX `<=25,000,000` bytes.
DirectX's margin is small and its total working set remains above the approximate
50 MB target. These are measured workloads, not a bound on arbitrary images or
all machines. Both baseline and image workloads are mandatory in the new CI.
The local workload fixture predates only the `inline-` output filename prefix;
its exact copy is retained with the observations.

The [display validation manifest](iterm-inline-validation.json) retains compiler
and sanitizer logs, final executable/link hashes, actual test fixtures, pixel
captures, memory samples, cleanup records and the earlier CI close failure.

## CI boundary and remaining work

The earlier transport-only source `3a60e4f` passed core CI
[43567290823](https://github.com/xiongnemo/nemoterm/actions/runs/43567290823).
Its single-image CI [43567290829](https://github.com/xiongnemo/nemoterm/actions/runs/43567290829)
failed while closing the bottom overflow-tab case after its five interaction
checks. One frontend remained alive at the 15-second close deadline; the owned
job forcibly cleaned it up. That is an unresolved failure, not a successful
validation or evidence about the new image decoder. Its log, failed-product
identity and cleanup record are retained. The failed product was not promoted.
Main `8264b27` has subsequently passed both
[core CI](https://github.com/xiongnemo/nemoterm/actions/runs/43568332401) and
[single-image CI](https://github.com/xiongnemo/nemoterm/actions/runs/43568332348);
that successful run does not establish the cause of the intermittent close failure.

The new 31-scene image fixture is registered for all three renderers in core
and single-EXE CI. Source `3187ec5` subsequently passed both full workflows, but
the downloaded artifact exceeded the local DirectX image-workload memory limit;
see the [CI artifact checkpoint](iterm-inline-ci.md). It remains unpromoted.
Animated GIF is explicitly rejected in this static checkpoint pending a bounded
frame scheduler. macOS-specific image
formats, feature reporting, file downloads, multiplexer passthrough, newer
iTerm image options and kitty graphics remain separate unfinished work.
