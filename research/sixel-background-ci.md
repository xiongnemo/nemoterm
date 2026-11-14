# Sixel background CI image: functional checks pass, DX acceptance incomplete

Source `0bea5c7ef9ea3901ef770ec8e69c1e4e64a1f49e` passes both full workflows:
[core/build](https://github.com/xiongnemo/nemoterm/actions/runs/43557539166) and
[single executable](https://github.com/xiongnemo/nemoterm/actions/runs/43557539161).
The single-image manifest records 108 checks. The
[artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43557539161/artifacts/14099891298)
is 4,451,328 bytes, SHA-256
`2e89ff8d5acd472a14f8b3697ee14ba46b6e896608548461481e6f541e445cfe`.
The downloaded bytes match that manifest. This candidate is not promoted over
the previously accepted `e436ecd` distribution.

The exact downloaded EXE passes all 22 background and all 16 original palette
phases locally in each actual renderer, GDI/OpenGL/DirectX (IDs 0/1/2), using
fresh owned jobs and the public automation interface. All six jobs exit
naturally and remove their unique registry profiles. CI's requested OpenGL
background run instead falls back to GDI; the separate local actual-OpenGL
run supplies that backend coverage.

The unchanged GDI Sarasa 160x48 full workload passes nine groups and 469 memory
samples, with peaks of 16,330,752 bytes private working set, 43,106,304 total
working set and 19,144,704 private commit. All 56 inner / 58 outer processes
exit naturally. Sampling precedes capture-helper injection.

The DirectX workload fails on the second post-close resource sample, before
the history/frame workload: handles 489 -> 540 (allowance +6), GDI 37 -> 38
(+3), USER 41 -> 54 (+2), with both tracked I/O workers signaled. Its 57 early
samples are not full memory acceptance. The failing inner fixture terminates
its five remaining owned processes; the outer controller finds no survivors.
Neither this failure nor previous resource failures is turned into a pass.

Independent resource investigation has observed delayed process-wide input
method UI initialization with a matching handle jump, plus a separate transient
USER-object increase after switching tabs. This image's failure was not itself
instrumented, so those observations are a diagnostic lead, not attribution of
every object in this run. The tests retain their original numerical thresholds.

The [manifest](sixel-background-ci-validation.json) records CI metadata, exact
image identity, native pixels/replies and the original memory/resource failure
and cleanup, with verified decompressed hashes. These records do not establish
long-session, physical-input or complete Sixel compatibility.
