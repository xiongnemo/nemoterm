# Relative cursor positioning

The [independent audit](cursor-movement-audit.md) found that HPR (`CSI a`)
and VPR (`CSI e`) incorrectly shared CUF/CUD's scrolling-boundary rules.
The development correction gives them position-relative movement with CUP's
origin policy: origin disabled permits crossing scrolling margins; origin
enabled confines both coordinates to the origin region. CNL/CPL and CUF/CUD
retain their existing behavior.

HPR keeps its logical column within the allocated physical grid. On a
double-width row it can therefore report a column beyond the visible half-row,
matching XTerm. The existing writer ignores positive-width text there; it does
not receive an index beyond the allocated line. No allocation or runtime
dependency is added.

The generated oracle reproduces all 848 retained XTerm query streams, including
the 47 originally differing streams. It verifies each captured input/reply and
the compressed reference's decoded hash, with no excluded cases or substituted
expectations. Core assertions also check writes across scrolling margins,
origin clipping, preserved unrelated cells, no spurious scrollback, saturated
counts and tiny grids with UTF-8, combining text, hyperlinks and protection.

The margin, state-control and Sixel terminal suites pass locally in MinGW and
Linux ASan/UBSan with leak detection. Native tests replay all 848 streams and
compare eight pixel states: absolute versus relative placement outside margins,
origin-clipped placement, ignored writes beyond a double-width row, and the
same bounds after resizing. These development runs do not establish a final
single-image artifact or memory acceptance. Full remote CI remains pending.

All three native runs use the actual requested GDI/OpenGL/DirectX renderer,
resize from 80x24 to 93x24 and drain their five owned processes naturally.
The DirectX screenshot was visually inspected. GPU captures use the existing
owned-process observer and are excluded from memory acceptance.

The tested MinGW frontend is 3,873,566 bytes, SHA-256
`1c975954cb0e9ddcc754004aa79a40fe4126b4b7d26b605bfa25292f490ea291`.
It uses the unchanged source-built host from `37ef26d`, SHA-256
`d0a95950e45f77c541f7ae524d20003e56caf57fe7e9b3480d8102385dab9d6a`.
The [manifest](relative-cursor-validation.json) retains exact source/binary
identities, all replies, pixel hashes/screenshots, natural cleanup and sanitizer
logs. This is a development sidecar build; the accepted local EXE is unchanged.

The subsequent development merge includes the [DECALN correction](alignment-reset.md)
and its UTF-8 generator fix. The merged margin, state-control and Sixel suites
pass on MinGW and Linux ASan/UBSan. Those separate source hashes/build logs are
retained without relabeling the earlier native captures as a merged-image test.
The combined single-image workflow now expects 99 functional groups; its full
remote and downloaded-image validation is pending.
