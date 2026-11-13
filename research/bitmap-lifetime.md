# Direct2D bitmap lifetime experiment

**Current policy:** on 2026-11-14 the user approved DirectX private working set
up to **25,000,000 bytes**, with further optimization deferred. GDI remains
strictly below 20,000,000 bytes; optional OpenGL keeps its exception. The
experiments below ran with the earlier 20,000,000-byte DirectX limit and their
original failure records are preserved. Fresh acceptance uses the new policy.
The [exact ETW stacks](virtual-memory-trace.md) attribute 5,009,408 newly
committed bytes in a selected graphics reservation to the text-run bitmap
creation path. This does not mean those pages are live bitmap contents or
guaranteed recoverable memory.

The first candidate reuses an evicted bitmap when its dimensions match the
new run, while retaining the 256-object/4-MiB pixel budget. It uses the
documented [CopyFromMemory ordering](https://learn.microsoft.com/en-us/windows/win32/api/d2d1/nf-d2d1-id2d1bitmap-copyfrommemory)
when the bitmap may still be referenced by pending draws. Other sizes follow
the existing release/create path. This differs from the previously rejected
fixed-atlas and smaller-cache experiments.

## First remote comparison

[Run 43448937817](https://github.com/xiongnemo/nemoterm/actions/runs/43448937817)
uses the unchanged `587965e` control image and source `95d06d0` candidate in
separate Windows 2025 jobs. Comparing production/build source confirms that
only `nemo_d2d.c` changed. Both have 160x48 left tabs, Consolas, identical
workload fixtures, and normal sampling without injection or ETW. Each runs
the renderer pixel test before new GDI and DirectX workload processes.

| Image / renderer | Private WS peak | Total WS peak | Samples | Memory gate |
| --- | ---: | ---: | ---: | --- |
| Control GDI | 11,153,408 | 41,144,320 | 339 | Pass |
| Candidate GDI | 10,936,320 | 43,106,304 | 279 | Pass |
| Control DirectX | 25,317,376 | 64,319,488 | 248 | Fail |
| Candidate DirectX | 23,642,112 | 65,208,320 | 225 | Fail |

Both renderer steps pass. All four workloads finish the nine functional
groups and drain owned processes naturally. Both DirectX jobs then fail the
unchanged memory gate. The 1,675,264-byte difference is one cross-runner
observation, not a proven stable saving. Neither image is promoted to main
or replaces the accepted local distribution.

The [manifest](bitmap-lifetime-validation.json) binds both executable hashes,
artifact IDs, all raw workload samples and logs. The first workflow mistakenly
packaged the tracked `renderer-printclient-observed.json` rather than the newly
written `renderer-observed.json`; that stale record is excluded. The step
status and renderer log support the first parity result. Subsequent runs retain
the correct JSON and scene PNGs.

## Follow-up under evaluation

Source `3f7a9fd` additionally invalidates content keys without destroying the
bounded bitmap pool on tab/font changes. Full frame destruction still releases
all resources, and a failed copy still takes the existing failure path. The
byte budget counts retained resources even when their keys are invalidated.

The renderer fixture now alternates 800 distinct two-cell coloured tiles,
then restores the original content. This exceeds cache capacity and compares
every scene to GDI using the existing pixel thresholds. It targets corruption
from updating a bitmap still referenced by the current draw batch, including
old content appearing in a newly assigned cache slot.

[Follow-up run 43450313623](https://github.com/xiongnemo/nemoterm/actions/runs/43450313623)
also fails the unchanged DirectX limit. Control private WS is **25,276,416**
bytes versus **22,409,216** for the candidate (total WS 63,746,048 versus
61,308,928). GDI is 11,227,136 versus 11,026,432 private bytes. Both images
complete all nine tab functional groups and exit naturally. All three new
cache-eviction scenes match GDI exactly for actual DirectX: zero changed
channels. OpenGL falls back to GDI on these runners, so this is not physical
OpenGL validation. The manifest's `follow_up` section retains exact identities;
compressed memory JSON files preserve every sample and the decompressed hashes.

The next candidate, `4422bd7`, keeps the bounded bitmap pool across compatible
target resizes as well, clearing its content keys. Device destruction still
releases everything. Microsoft's [resource-domain contract](https://learn.microsoft.com/en-us/windows/win32/direct2d/resources-and-resource-domains)
allows sharing resources with targets created as compatible with the same
parent. [Run 43451668160](https://github.com/xiongnemo/nemoterm/actions/runs/43451668160)
adds the existing device-failure/cleanup fixture alongside pixels and workloads.
That run finished all pixel, functional and device-failure/cleanup checks, but
the candidate private peak increased to **25,210,880** bytes versus control
**24,981,504**. It also exceeds the newly approved 25 MB ceiling. This resize
resource-pool change is rejected and restored to the `3f7a9fd` product source.
The earlier 22,409,216-byte candidate is retained for fresh validation under
the new policy; a historical 20 MB failure is not relabelled as a CI pass.
Local runtime tests remain paused; downloaded binaries are evidence only.

## Fresh acceptance under the approved 25 MB policy

[Single-image run 43453719414](https://github.com/xiongnemo/nemoterm/actions/runs/43453719414)
at `7fc3c9c` passes all **85** groups, including normal tab workloads after the
independent protocol, pixel, settings and Codex checks. DirectX frontend private
WS peaks at **21,970,944 bytes**, total WS at **59,580,416**, and private
commitment at **24,432,640**. GDI peaks at **10,981,376** private bytes. Both
workloads pass their renderer-specific gates and drain owned processes naturally.
The approximate 50 MB total-WS target is still exceeded by this DirectX workload.

The downloaded 4,437,504-byte EXE has SHA-256
`5ac65874e49ea7b08077b44aa62ebb55524c01e0da88213702a161dc21ec25d1`.
The [main-branch evidence manifest](https://github.com/xiongnemo/nemoterm/blob/main/research/memory-budget-validation.json)
retains the exact artifact IDs, functional results and lossless raw memory
samples. This is fresh validation, not relabelling the earlier 20 MB failures.
The separate MinGW comparison still fails on a mixed-profile close timeout;
the development image therefore does not replace the main verified download.
