# ReGIS image views and shared palette integration

Development source now connects ReGIS graphics to the terminal's retained
image list and the Windows renderer's existing row-composition path. This
was initially checked only through core row composition. The subsequent
[native-window checkpoint](regis-native-window.md) passes 30 finite checks on
actual GDI and DirectX plus presented GDI. The later [screen-edge replay and
fix](regis-screen-edges.md) expands that window suite to 37 checks. Full
acceptance remains open; the distributed executable has not been replaced. The original
full comparison remains failed.

## Ownership and drawing

Commit `77a05d9` replaces the fixed page slots with stable graphic identities
in creation order. Matching includes page, main/alternate screen, character
origin and actual dimensions, following the pinned XTerm source. Scrolling
or an address-size change can therefore retain more than one graphic with
the same page number. Hidden pages remain owned but are not displayed.

Terminal image views refer to the live indexed graphic. They do not make a
second pixel bitmap or use the raster-only row/mask arrays. Text erasure
changes the underlying pixels and invalidates the terminal surface, including
cells whose text was already blank. Removal releases the graphic only after
its last view; allocation admission protects active decoder views. All
metadata, sparse tiles, fonts and pending input remain in the existing shared
4 MiB image budget. This is logical accounting, not a new working-set result.

## Original-frame comparisons

The original reference ZIP, input streams, replies and expected images from
run `44093439244` remain unchanged. The component's 37-scene / 70-frame
projection and both real-parser transports continue to pass on GCC, Clang
and MSVC. GCC and Clang use ASan and UBSan. The separate Windows font check
passes 573 Sarasa comparisons with no leaked GDI handles.

The added view comparison composites the terminal's retained images using
the same row accessors as Windows. An independent X11 font probe supplies
the 6x13 fixed-grid text inputs. It does not capture a Nemoterm window.

| Hosted run | Commit | View cases / frames | Failing frames per transport/compiler |
| --- | --- | --- | --- |
| [44118346451](https://github.com/xiongnemo/nemoterm/actions/runs/44118346451) | `77a05d9` | 59 / 128 | 8 |
| [44121588424](https://github.com/xiongnemo/nemoterm/actions/runs/44121588424) | `a158da8` | 60 / 131 | 6 |
| [44123411341](https://github.com/xiongnemo/nemoterm/actions/runs/44123411341) | `c150a8f` | 60 / 131 | 4 |
| [44125106179](https://github.com/xiongnemo/nemoterm/actions/runs/44125106179) | `ae48602` | 60 / 131 | 9 |

The fixture corrections added the upstream VT340 register count and actual
fixed-font glyph inputs. The shared-bank correction also makes the fixture's
initial black registers opaque, matching the public row API contract. SUB in
VT340 mode produces U+2426, which the reference's ISO8859-1 face lacks.
XTerm draws a dashed missing-glyph box rather than XDrawString16's default
question mark. The final independent probe follows `util.c:xtermDrawMissing`
and `xterm.h:setXtermLineAttributes`; its 19 ink pixels match the reference.
No expected terminal image was used as font input.

At `c150a8f`, the four failures are scroll-up step 2 (101 pixels), scroll-down
steps 1 and 2 (101 and 303), and newline-scroll step 2 (202). All replies
match. The only excluded view scene is the capability identity control;
ReGIS is not advertised yet. Exclusion does not count as a pass.

## Independent repaint investigation

Runs [44119855217](https://github.com/xiongnemo/nemoterm/actions/runs/44119855217)
and [44123420797](https://github.com/xiongnemo/nemoterm/actions/runs/44123420797)
build the same unmodified upstream commit
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f`. The collector records both the
ordinary presented frame and a new frame after XClearArea with Expose and a
status-reply barrier. It retains both; the latter never replaces an older
golden image. Subsequent steps in this new run follow the full repaint, so
their presentation history is explicitly different from the original run.

The 61-scene capture passes transport, ordinary text and natural-exit
controls. The later capture adds two palette scenes and passes the same
controls over 63 scenes / 126 reference processes. Both transports show:

* An erased line can reappear on Expose because the upstream line-erasure
  path changes the presented window but not the retained graphic pixels.
* The final scroll-up and newline-scroll frames lose stale pixels on Expose.
  Reverse scrolling can instead restore the original unmoved graphic rows.
* A shared ReGIS palette change can recolor an older Sixel only after Expose.
  Upstream `set_shared_color_register` checks `color_registers_used[ii]`
  using the graphic slot index rather than the changed colour index when
  deciding whether to mark that graphic dirty.

These source and frame observations explain why a full recomposition and
the historically presented window need not agree. They do not waive the
failing legacy comparison or certify Nemoterm's scroll/erase policy.

The older palette-only Sixel stream ended immediately after its final RGB
number. Upstream `parse_sixel_finished` does not flush that pending colour
parameter. The added `shared-palette-sixel-terminated` scene explicitly ends
the definition with another selector before ST. The reference then changes
the existing ReGIS line from green to red. The opposite scene changes a
Sixel from green to red after a ReGIS definition and full repaint. This
demonstrates that the two protocols really share one upstream register bank.

The complete later reference artifact is committed unchanged as
[regis-repaint-reference.zip](regis-repaint-reference.zip), 2,650,557 bytes,
SHA-256 `ca9165f9d14cb8ef67840a3c46063fde3d4f9dc104ac58086bc9b125c79fac4f`.
It contains original streams, presented and exposed frames, process records,
build identity, and the pinned relevant source files.

## Shared palette correction

Commit `ae48602` binds the ReGIS owner to the existing terminal-owned Sixel
ARGB bank. New shared graphics read its live bytes; private graphics retain
their own colours. Mode switches do not rebind existing graphics. ReGIS
imports colour percentages for parser operations at each request and writes
changes back to that same bank; display reads preserve exact ARGB values.
The caller's bank outlives the decoders and is not cleared by decoder reset.
No additional shared bitmap or palette allocation is introduced.

The added hosted comparison uses the two independently captured palette
scenes and their full-repaint frames, with whole and bytewise terminal input.
It is an additional gate, separate from the unchanged historical-frame gate.
Core checks also cover both update directions, private isolation, completed
colour definitions followed by CAN, terminal isolation, exact byte readback,
invalid bank sizes and release after RIS.

[Run 44125106179](https://github.com/xiongnemo/nemoterm/actions/runs/44125106179)
at `ae486028f501a1ba459e379fbc1f1e704610f254` passes this additional comparison:
**2 scenes / 5 frames with zero pixel or reply differences**, in both transports
on all three compilers. Ownership, framing, Sixel/Kitty, cancellation and the
573 native glyph checks pass as well. The original 70-frame projection and
both original terminal parser projections also still pass.

The overall run remains **failed**. Connecting the bank exposes five more
differences against the older presented-frame captures, for **9 failing frames
out of 131** in each transport/compiler. The additional failures are
`sixel-palette-False` steps 1 and 2, `regis-palette-False` step 1, and
`sixel-defined-palette-False` steps 1 and 2. Nemoterm recolors the retained
pixels red. The old XTerm frames remain black or green. Four involve the
unterminated final Sixel colour parameter described above; the ReGIS-to-Sixel
case changes on the independent Expose capture. These differences remain
reported as failures. Passing the new full-repaint scenes does not replace,
waive or relabel any historical gate.

Retained terminal replay executable SHA-256 values are:

| Compiler | SHA-256 |
| --- | --- |
| GCC | `f94e418dc75c2499de7ef34b474a112f54f76ad2c61c68321694b96ccb2a3ba8` |
| Clang | `1455e0085a261e6930e6226b5df7103ffdf06a8dc6cb1bc8b37941ef23ec52cb` |
| MSVC | `e1e9ae141bf11520f675ae2f1101aed4d9aa35043c02240cb5a938702eab89ca` |

Every comparison's executable identity matches its original retained binary.

## Retention and remaining work

[The initial evidence archive](regis-views-initial-evidence.zip) retains runs
`44118346451`, `44119855217` and `44121588424`, including all original
artifact ZIPs, receipts, logs, run/job metadata, analysis and a per-entry
manifest. It has 32 entries and 34,740,022 bytes, SHA-256
`2d8f9e6ffa8e092e40925e48e2b657fc50551960d4a910e72c6d83c0bdccd8a3`.
Every archived entry was read back and its identity checked.

[The follow-up evidence archive](regis-views-shared-evidence.zip) retains
`44123411341`, `44123420797` and `44125106179` with the same original-record
and per-entry identity checks. It has 32 entries and 34,873,088 bytes, SHA-256
`a9620980c041c1553e2d1bf585e38957d950d07f125c6d3a22b5eb46cb699d68`.

The [native-window checkpoint](regis-native-window.md) now covers finite GDI
and DirectX geometry and presented-GDI invalidation on one exact single image.
The [expanded fixture](regis-screen-edges.md) also checks scroll-margin clipping
and screen restoration. OpenGL execution, scrollback/resize/eviction pressure,
delay scheduling, broader arithmetic/parser-progress review and full
single-image CI remain open. No new frontend memory claim follows from
these core tests. The accepted DirectX limit remains 30,000,000 bytes and
GDI remains strictly below 20,000,000 bytes. Tektronix is still unimplemented.

The [shared register terminator investigation](shared-register-terminator.md) compares the four previously failing palette-only frames and a separately drawn Sixel readback. It tracks six remaining historical mismatches.
