# Dense Unicode-image display-cache follow-up

The user keeps the strict GDI private-working-set target below 20,000,000 bytes;
the accepted DirectX policy is unchanged. The local Sarasa 160x48 two-tab
[portable and successful single-image baselines](feature-policy-sarasa.md)
peak at 20,746,240 and 20,623,360 bytes respectively. Those failures remain
retained. The later feature-policy product passes both complete CI workflows,
but those smaller remote Consolas grids do not close this local gate.

## Redundant displayed-text storage

Kitty Unicode placeholders carry positional combining marks in the terminal's
original text. The text painter already renders a blank instead of that PUA
character and omits its marks; the image compositor reads the original text.
However, the last-painted-text cache still copied the invisible mark chains.

`12ee33b` normalizes only the painted cache entry to a zero-extension character.
Original screen/history characters, image placement metadata, clipboard source,
ordinary combining text and frontends without Kitty support are unchanged.
No capacity, history size, grid, font or memory threshold is reduced. There is
no working-set trimming, renderer replacement or new persistent allocation.

The regression paints 7,268 marked placeholders at 160x48. It fails against
the prior production source with **737,408 bytes** of displayed character
storage and 7,268 extension-bearing cells. The corrected source uses **245,760
bytes**, exactly the base grid, saving **491,648 bytes per tab** in this case.
The test also checks the live mark chains after repeated paints, ordinary
accent rendering and a frontend without Kitty support. These are actual cache
allocations, not process-working-set measurements.

Local MinGW grapheme, Sixel/Kitty, reflow, resize, mouse and hyperlink suites
pass. The image suite includes all 728 unchanged independent Unicode states
and 32 exact core clipboard copies. `gdi-image-cache-core.tar.gz` retains the
original failing regression, corrected logs, source and build configuration;
its manifest is `gdi-image-cache-core-validation.json`. GCC/Clang ASan+UBSan
and MSVC all pass this regression in component run `43736421112`, including
728 unchanged Unicode-image states and 32 exact core copies per compiler.
The recorded display-cache sizes are 307,200 bytes on the Linux ABI (40-byte
terminal cells) and 245,760 bytes on Windows (32-byte cells), with no cached
positional chains. `gdi-image-cache-components.tar.gz` retains 80 original
records, verified source hashes and artifact receipts; its separate manifest
does not infer full-product or native process-memory acceptance.

## Local portable acceptance

The local portable candidate is 4,026,766 bytes, SHA256
`ddf4ccfdedf6d6406884d27e24d0b8be87a022f65ae01c5041700bd05fa26452`.
It passes the unchanged two-tab workload with Sarasa, 160x48 and the strict GDI
limit. The existing bounded child option is set to 1,800 seconds,
because the older single image completed all 29,072 pixels just before its
900-second child expired, leaving no time for the later lifecycle scenes.
Per-reply, shutdown and memory assertions remain unchanged.

The complete run records **18,481,152 bytes private working set**, **39,968,768
bytes total working set**, and **21,385,216 bytes private commit**. All 2,670
uninstrumented samples over 290.015 seconds are retained, with the peaks
independently recomputed. All **29,072** post-sampling image-cell centres match,
all ten tab/lifecycle checks pass, and all 56 owned processes drain naturally
without forced termination. This closes the portable candidate's dense GDI
budget failure; it does not measure the forthcoming combined CI executable.

The same frontend also passes **185 native pixel stages**: 32 Unicode-image
checks on each of GDI, actual OpenGL and actual DirectX, another 32 from the
visible GDI client DC, and 19 resize/font/history stages on each actual backend.
The presented capture uses `GetDC(owned HWND) + BitBlt`, without `WM_PRINTCLIENT`
or the image API. Each run checks natural process cleanup. Original observations,
BMP/PNG captures, exact executable/runtime files, source fixtures and controller
logs are retained in `gdi-image-cache-local.tar.gz`; the separate validation
manifest verifies their hashes and all twelve dense-image pixel strips.

The first local native selection attempt fails in `SavedClipboard` before any
selection or copy assertion. A separate non-mutating `OpenClipboard(NULL)`
probe also returns Windows error 5 (access denied), with no reported open-window
handle. No existing clipboard contents were read or changed. The
failure is not a selection pass and is not yet attributed to product code.
The independent memory run does not use the clipboard. The original failure,
natural cleanup, external error-5 observation and exact test sources are in
`gdi-image-cache-clipboard-preflight.tar.gz`, with a separate failure manifest.

A later external `OpenClipboard(NULL)` succeeds and closes normally, allowing
one unchanged-fixture retry. That retry again fails at the initial clipboard
backup; a subsequent independent call again returns error 5. The retry retains
zero selection assertions and natural cleanup, without changing clipboard
contents. Current process window-station access includes clipboard access and
its job reports no UI restrictions; the cause remains unconfirmed. A NULL
`GetOpenClipboardWindow` result does **not** exclude a lock opened without a
window handle, as [Microsoft documents](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getopenclipboardwindow).
The original failed retry and surrounding observations are retained separately
in `gdi-image-cache-clipboard-retry.tar.gz`; no clipboard pass is claimed.

## Complete CI and exact-product acceptance

All three compiler components and both complete source `12ee33b` workflows now
pass: [ordinary](https://github.com/xiongnemo/nemoterm/actions/runs/43736421054),
[single image](https://github.com/xiongnemo/nemoterm/actions/runs/43736421137),
and [graphics components](https://github.com/xiongnemo/nemoterm/actions/runs/43736421112).
The ordinary workflow passes all four jobs; the single image passes **160
groups**. Each full workflow passes twelve uninjected memory workloads and
25,048 dense image-cell comparisons. Retainers also verify the unchanged 413
ANSI/C0 streams, 232 UDK streams, 27 Locator phases, 192 bell streams, 38 bell
window states and 72 feature-policy cases against their exact expectations.

The [single executable artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43736421137/artifacts/14172342252)
is **4,544,000 bytes**, SHA256
`64195969a8f2e6653f854d598f169810107ee808d66eaa1088cf9e3ced6b259f`,
and expires at `2026-12-15T17:22:32Z`. The isolated runtime contains only
`nemoterm.exe`. The ordinary compiler-comparison frontend is a distinct
3,961,838-byte image, SHA256
`d445b06e7de8dfc2169d5d6c00ec526f50423b8b7be43c9736b053d9b17bf74a`;
its source-built console host remains a separate file.

| Complete workflow | Dense GDI private / total WS (B) | Dense DirectX private / total WS (B) |
| --- | ---: | ---: |
| Ordinary | 14,176,256 / 45,166,592 | 17,637,376 / 54,329,344 |
| Single image | 14,258,176 / 46,653,440 | 18,026,496 / 55,267,328 |

These cloud Consolas workloads use smaller grids and do not substitute for
local Sarasa acceptance. DirectX total WS remains recorded under the user's
accepted policy. `gdi-image-cache-ordinary.tar.gz` retains 4,634 records;
`gdi-image-cache-single.tar.gz` retains 4,605. Their manifests verify artifact
receipts, source identities, archived record hashes and all listed assertions.

The exact downloaded single image has started a separate **39-command** local
acceptance run. Shutdown and startup-size groups pass; the 160x48 Sarasa dense
GDI workload is running. The remaining groups cover all available shells, tab
positions and previews, session lifetime, font zoom, input translation, local
automation, native image pixels, twelve memory workloads, bindings and file/
clipboard input. Each command preserves its own observations before shared
filenames can be reused. Clipboard access remains an outstanding local concern.
No accepted executable or main-branch promotion has occurred.
