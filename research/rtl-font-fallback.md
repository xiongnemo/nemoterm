# RTL cell fallback and bounded bidi cache

This is development-branch evidence, not single-executable release acceptance.
The local MinGW frontend SHA-256 is
`f255a10e2f436cab0bfa4053ac394d6a15d082e3c8771c62eb5d7fb6a6254fdd`.
It was tested with the pinned ConPTY DLL and accepted OpenConsole sidecar.
The accepted main `dist/nemoterm.exe` has not been replaced.

## Reproduced rendering defects

The preceding single-image artifact (`6def9f241239165bf6a0f7ca37c80594793425b820016fd23051a421d61207ad`)
fails the new Hebrew glyph-presence test: Alef is blank. See
[the negative result](rtl-before-observed.json). Comparing two renderers that
both omit the same letters had previously missed this defect.

PuTTY has already established visual order and Arabic contextual forms before
the Windows frontend paints an RTL run. Its glyph-index output path cannot
obtain glyphs absent from the selected font. Consolas and the installed Sarasa
face lack the tested Hebrew and Arabic glyphs. The frontend now checks missing
BMP RTL glyphs and sends each missing cell through the existing DirectWrite
cluster rasterizer. Neighboring cells, the terminal's visual order and its
pre-shaped Arabic forms are preserved. There is no additional font package or
rendering library.

The rasterizer can preserve destination pixels for a transparent fallback cell,
including shadow-bold drawing. Its opaque whole-cluster behavior is unchanged.
The Courier bitmap-font case also exposed a separate format creation failure:
GDI's `FW_DONTCARE` weight is zero. The DirectWrite fallback format now converts
that value to normal weight. An offscreen Courier test failed before this fix.

The first implementation repeatedly created a layout for every missing cell.
The 5,000-repaint lifetime case outlived both its original 60-second child and a
300-second diagnostic child (3,860 repaints completed in the latter). A bounded
cache now retains at most 32 immutable single-character layouts per renderer,
cleared on font changes and destruction. Colors, pixels, geometry, shadow bold
and multi-character cluster layouts are not retained in this cache. A native
regression compares reused layouts against a fresh renderer after cache turnover
and changes in cell geometry, offset and scale.

Caching layouts alone was insufficient: that version reached 4,738 repaints
before the 300-second child deadline. The opaque-run path also unnecessarily
read window pixels back for every fallback cell, although the run had already
erased its background. Opaque cells now fill their own background; combining
and shadow passes still preserve earlier ink. With both changes, the same
5,000-repaint loop completed in 41.30 seconds, with private commit falling from
7,290,880 to 7,135,232 bytes. The complete font case also checks 32 resize cycles
and 6,144 distinct symbols. This is a local repeat-paint result, not a general
terminal throughput benchmark. [300-second baseline](rtl-font-lifetime-300-before-cache.json),
[layout-cache-only result](rtl-font-lifetime-layout-cache-only.json),
[completed final case](rtl-font-lifetime-observed.json).
The [Courier repeat-paint case](rtl-courier-lifetime-observed.json) also passed
all 5,000 iterations in 42.66 seconds and exited normally, with no private-commit
growth. Its glyph rasterization uses the corrected bitmap-primary font weight.

API references: [GetGlyphIndicesW](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-getglyphindicesw),
[ExtTextOutW](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-exttextoutw).

## Retained memory

The dense two-tab scene now includes Hebrew and Arabic as well as Latin, CJK and
extended grapheme clusters. Retaining every transformed row exceeded the memory
target. Exact before/after cell copies and permutation maps now have a 64 KiB
LRU budget per terminal. Evicted rows are recomputed for paint, cursor and mouse
lookups. This trades some repeated bidi processing for bounded retained memory;
there is no lossy hash comparison or shared row ownership. One row larger than
the budget is allowed by itself so that unusually wide terminals remain correct.
The limit counts row data and maps, not allocator or cache-index overhead.

Local measurements use decimal MB, frontend only, before capture instrumentation.
The dense tests keep two tabs, create and close another tab twelve times, and
sample before hover-preview capture. They are not process-tree or universal
worst-case memory bounds.

| Dense scene | Peak private working set | Peak total working set |
| --- | ---: | ---: |
| DirectX, unbounded RTL row cache | 21.18 MB | see raw record |
| DirectX, intermediate 256 KiB budget | 20.49 MB | see raw record |
| DirectX, 64 KiB before layout-cache optimization | 18.89 MB | 53.82 MB |
| DirectX, final build | 19.80 MB | 54.81 MB |
| GDI, final build | 9.51 MB | 29.98 MB |

Raw records: [unbounded](rtl-directx-dense-before-observed.json),
[256 KiB](rtl-directx-256k-cache-observed.json),
[before layout cache](rtl-directx-before-layout-cache.json),
[final DirectX](rtl-directx-dense-observed.json), [final GDI](rtl-gdi-dense-observed.json).
The separate renderer scene reached 19.00 MB private / 57.47 MB total on DirectX.
DirectX's dense-case margin below 20 MB is small; this sample does not establish
that every driver, font or workload stays below the target.
OpenGL remains an explicitly permitted exception to the private-memory target.

## Local verification

- Thirty-five Windows core/offscreen test executables passed, including 853
  official grapheme vectors. The native renderer test covers six distinct RTL
  letters, transparent background preservation, Courier, clipping, double-height
  cells and renderer lifetime.
- Sixteen terminal suites passed under GCC 14.2 ASan and UBSan in Debian WSL1,
  with leak detection and halt-on-undefined-behavior enabled. The bidi regression
  covers 48 distinct dense rows, repeated eviction, cursor and mouse remapping,
  two individually oversized 2,048-column rows, reconfiguration and resizing.
  [Source hashes and test results](rtl-core-validation.json).
- Native [Consolas](rtl-consolas-observed.json),
  [Sarasa](rtl-sarasa-observed.json) and [Courier](rtl-courier-observed.json)
  cases passed on actual GDI, OpenGL and DirectX. They check distinct nonblank
  glyphs, right-aligned RTL paragraphs, Hebrew ordering, Arabic contextual
  forms, neighboring Latin cells, combining marks, synchronized updates and
  font resizing. [Sarasa capture](rtl-sarasa.png).
- Existing [renderer parity](rtl-renderer-observed.json),
  [grapheme grid](rtl-grapheme-observed.json) and
  [grapheme font resize](rtl-grapheme-font-observed.json) suites passed on all
  three compositors. Dense GDI and DirectX tab tests passed all nine groups,
  including hover previews, original-tab closure and owned-process cleanup.
  The Sarasa RTL capture and all three text-scene captures have identical PNG
  hashes before and after layout caching and opaque-cell optimization;
  [comparison](rtl-layout-cache-pixel-parity.json).
- The extended font lifetime case passed. Its original 60-second child lifetime
  was independently reproduced closing normally at 60.37 seconds with exit code
  zero, during repaint 496. The bounded child lifetime is now 300 seconds;
  the 5,000-repaint and memory assertions remain.
  [Original failure](rtl-font-lifetime-first-failure.json),
  [timed reproduction](rtl-font-lifetime-60-observed.json).

## Remaining acceptance work

Local clipboard access is unavailable, so these runs do not validate clipboard
contents. CI retains real clipboard assertions, including logical Hebrew order.
Windows CI and the exact single-image validation script now include the RTL
fixture and its bitmap-primary Courier variant.

GitHub Actions has refused recent jobs before executing steps because of account
billing or spending-limit restrictions. This change therefore still needs MSVC
and exact single-image CI validation. The preceding branch's real Codex paste
fixture fix also awaits CI. The earlier isolated tab-close access violation and
transient DirectX handle growth remain unexplained; successful local reruns do
not establish their causes or fixes. No accepted release artifact is promoted
by this branch.
