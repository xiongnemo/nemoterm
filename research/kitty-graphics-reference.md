# Independent kitty graphics reference

The `kitty-graphics` family in the manually dispatched `protocol-reference.yml`
workflow builds upstream commit `8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f`
using its own CI build recipe on a disposable Linux runner. No upstream source
is patched and no local terminal or desktop is used. The pinned REA 6.8.0
`capture-process` recorder owns a single `kitty +runpy` process, with a 60-second
deadline and two-second termination grace period. The input scenario and full
Evidence, executable/extension hashes, package lock, raw observations and build
log are uploaded even when a stage fails.

The fixture runs four upstream graphics tests, then records 29 scenarios and
54 states using the actual compiled kitty parser, screen and graphics manager.
Each state retains input/reply bytes, cursor position, native layer coordinates,
derived pixel rectangles and image count. Inputs cover natural/explicit/aspect
dimensions, crop, pixel offsets, cursor movement, edge wrapping, text erasure,
screen reset, placement identity/deletion, layer order and scroll-region edges.
The captured model has no OS window; it does **not** establish GPU pixels or
an end-to-end visible application result. Raw model values are the observations;
the fixture does not implement a second layout algorithm to produce answers.

Success requires every upstream test to pass without skips, all observations
to finish, natural process exit, verified ownership cleanup, no truncated capture,
and an observation-file digest matching REA's after snapshot.

The [first run](https://github.com/xiongnemo/nemoterm/actions/runs/43612847484)
passed at fixture commit `d6386912f90742d8c69dc3a776fba29e2eea751f`.
All four upstream tests passed without skips, and all 29 scenarios / 54 states
completed. Source and fixture hashes were independently checked after download.
REA Evidence
`ev_6c70bc690dc2df51c9be97da3c80ec0a62fd301149e839dc66651e1c460e8ce3`
records natural exit code zero, verified owned-process cleanup and removal of its
temporary root. Twelve complete raw records are retained with hashes in the
[validation record](kitty-graphics-reference-validation.json).

## Observed model behavior

The cells are 10 by 20 pixels and the screen is 12 columns by 8 rows. Coordinates
below are zero-based; native floating-point rectangle values remain in the raw
record rather than being silently rounded into an exact compatibility claim.

| Input / case | Observed result |
| --- | --- |
| Natural 10 by 20 image at origin | Cursor moves to (1, 0), not the next row. |
| Natural 20 by 60 at (2, 1) | Cursor moves to (4, 3), adding effective rows minus one. |
| 40 by 20 source, `c=2,r=3` | Destination is approximately 20 by 60: ordinary placement fills both requested axes rather than letterboxing. |
| Same family with only one requested axis | Aspect ratio is preserved; `c=3` for a 20 by 40 source produces 30 by 60 pixels. |
| `c=3,r=2,X=3,Y=5` at (1, 1) | Starts at (13, 25), ends at (40, 60); the offset reduces the available explicit rectangle. |
| `C=1` | Preserves the starting cursor. |
| Text overwrite, EL, EL2, ED0, ED1 | The existing image/layer remains. |
| ED2, ED3 with empty history, RIS | The tested visible image is removed. ED3 needs further history-state coverage. |
| Same nonzero image/placement pair | Moves/replaces the previous placement; a different placement id adds another view. |
| Delete last placement with uppercase `I` | Releases that image's data; lowercase `a` retains reusable data. |
| Scroll region with image wholly inside | Moves/clips source and destination at the region edge. Images crossing the top or bottom boundary remain unchanged in these cases. |

These captures resolve the two documentation/source differences for the pinned
ordinary-placement path. The future adapter should follow these observed values
and retain the discrepancy in its compatibility notes. Unicode placeholder
fitting is a separate path and has not been measured here. Layer records are
sorted by the observed z values, but this fixture does not isolate the client-id
tie-breaker: its `same-z-lower-id` label actually sends id 4 after id 3. Do not
treat that label as evidence of lower-id ordering.

REA also reports sampling and identity limits: the executable hash is a
prelaunch sample, process trees may omit short-lived descendants, file snapshots
are not syscall traces, and inherited environment variables are not fully
recorded. The source/extension hashes supplement those observations; they do not
remove those limits.

This reference informs the [image cache notes](kitty-image-cache.md). It does not connect the cache
to Nemoterm, advertise kitty graphics support, or close local memory acceptance.
