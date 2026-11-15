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
its manifest is `gdi-image-cache-core-validation.json`. GCC/Clang sanitizers
and MSVC now also run this paint-cache regression in the component workflow.

## Native acceptance in progress

The local portable candidate is 4,026,766 bytes, SHA256
`ddf4ccfdedf6d6406884d27e24d0b8be87a022f65ae01c5041700bd05fa26452`.
It is being measured with the unchanged two-tab workload, Sarasa, 160x48 and
strict GDI limit. The existing bounded child option is set to 1,800 seconds,
because the older single image completed all 29,072 pixels just before its
900-second child expired, leaving no time for the later lifecycle scenes.
Per-reply, shutdown and memory assertions remain unchanged.

The first local native selection attempt fails in `SavedClipboard` before any
selection or copy assertion. A separate non-mutating `OpenClipboard(NULL)`
probe also returns Windows error 5 (access denied), with no window holding the
clipboard open. No existing clipboard contents were read or changed. The
failure is not a selection pass and is not yet attributed to product code.
The independent memory run does not use the clipboard.

Current source workflows: [ordinary](https://github.com/xiongnemo/nemoterm/actions/runs/43736421054),
[single image](https://github.com/xiongnemo/nemoterm/actions/runs/43736421137),
and [graphics components](https://github.com/xiongnemo/nemoterm/actions/runs/43736421112).
All were still running when this record was created. No distribution or main
branch promotion follows from the narrower cache regression.
