# Direct2D bitmap lifetime experiment

**Not accepted: DirectX still exceeds 20,000,000 private-working-set bytes.**
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
Its result is pending at this checkpoint; compilation is not acceptance.
Local runtime tests remain paused; downloaded binaries are evidence only.
