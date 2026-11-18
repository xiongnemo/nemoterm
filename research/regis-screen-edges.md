# ReGIS alternate-screen and scroll-margin corrections

The first [native checkpoint](regis-native-window.md) passes 30 checks on
the `a0c35e6` single image. Expanding the native fixture found a real missing
case: continuing an existing ReGIS context on the alternate screen, then
returning to the main screen without another ReGIS request, loses the main
graphic. Passing the earlier finite fixture did not establish this behavior.

## Reproduction and upstream comparison

[Exact-image replay 44130072554](https://github.com/xiongnemo/nemoterm/actions/runs/44130072554)
uses fixture `7041ae6282af64576efc386f1c7171cc2dd1fe7c` and the unchanged
4,852,224-byte image, SHA-256
`4d5fcd1e6ac47dfcd15c1731eb11e0b612b1d0a16915d0106c3846c7dd5baf04`.
All four jobs fail `continued-alternate-restore`, after 32 preceding checks
pass. The actual GDI API, actual DirectX API and directly presented GDI
surface agree; the OpenGL-request job falls back to GDI. Processes still
exit naturally. The later scroll-margin checks do not execute after this
failure and must not be counted as tested by this run.

[Independent reference run 44129966537](https://github.com/xiongnemo/nemoterm/actions/runs/44129966537)
at `63790cd83c5b3ac1bb875bf9bc59407739a31a6d` retains 65 scenes on the pinned,
unmodified XTerm. It confirms that upstream also returns a blank main screen
until another ReGIS request remaps the page. Full Expose alone does not fix
it. A separate scroll-margin scene shows that the immediately presented
pixels and the pixels after full Expose disagree. These are observations,
not new expected product images.

The product invariant is that switching terminal screens preserves each
screen's retained graphic visibility, and scrolling a bounded text region
preserves pixels outside that region. This intentionally avoids the observed
upstream display-state inconsistencies. The historical comparison remains
unchanged and failed; the invariant does not waive that gate or establish
complete XTerm compatibility.

## Source changes

Commit `f8faa722699b447daef5e4656af3aaf5c4d7157f` detaches the current ReGIS
page pointers when switching screen banks. Coordinates and selected page
numbers survive, while the next mapping cannot mark a graphic in the bank
we just left as hidden. Main and alternate visibility remain independent.

[Core run 44130567116](https://github.com/xiongnemo/nemoterm/actions/runs/44130567116)
passes the new visibility/ownership check, original 70-frame projections,
shared-palette comparisons, Sixel/Kitty, cancellation and native glyph checks
on GCC, Clang and MSVC. The overall run is still failed: the unchanged view
comparison now reports **10** frames rather than 9. The additional difference
is `alternate-page-ownership` step 3, where entering/resetting the alternate
screen now erases its visible graphic rather than retaining a hidden one.
The failed frames remain available for further compatibility review.

Commit `e08e53b` limits partial-region scrolling to the intersection of the
graphic and the active character rectangle. It copies indexed pixels in
overlap-safe order, leaves outside pixels unchanged, and clears newly exposed
pixels to holes. Full-window scrolling retains the existing character-origin
path. The operation uses existing sparse tiles, per-request work limits and
the shared image budget. Core checks cover vertical margins, a restricted
column strip in both directions, exact outside pixels and release after RIS.

[Margin core run 44131050416](https://github.com/xiongnemo/nemoterm/actions/runs/44131050416)
passes the new region checks. On GCC, Clang and MSVC the unchanged historical
comparison still has 10 differing frames out of 131, both whole and bytewise.

[Native run 44131192187](https://github.com/xiongnemo/nemoterm/actions/runs/44131192187)
built `d817161f32a3ef0699927da1c0739764dcd5c3dd`: 4,853,248 bytes, SHA-256
`34ae5cc92ab681e253955435b462f04b8b7c66db87b2c3f49bdc7debe55bf2a6`.
The source-host artifact is `14349384062`. All 37 checks passed on actual GDI
(`14348989979`), actual DirectX (`14349987450`) and directly presented GDI
(`14350701091`), including alternate-screen restoration without another DCS,
the subsequent repaint, and clipping to the scroll margins before/after repaint.
The OpenGL request (`14350277175`) fell back to GDI. All four jobs closed
naturally. These window checks do not measure private working set.

## Original evidence

[regis-screen-edge-evidence.zip](regis-screen-edge-evidence.zip) preserves
the failed native replay and successful independent upstream capture, with
their original artifact ZIPs, final metadata, receipts, complete job logs
and per-entry hash manifest. It has **27 entries, 2,510,755 bytes**, SHA-256
`03bf21001751f257f5a6f29f1f646a9dd3b6197a1fc0224e69a5bcff6c4f743a`.
All entries were read back and verified. The original upstream artifact is
`14348329052`, 2,672,037 bytes, SHA-256
`459d824dd0957c13e1c55f567715323e31a91c3e755bc20671f7554f7468c357`.
