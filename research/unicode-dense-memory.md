# Dense Unicode image workload: incomplete native observation

[Single-image run 43683916414](https://github.com/xiongnemo/nemoterm/actions/runs/43683916414)
at `eae896846561f73fa1c444808ca3f7319707857a` is cancelled by its 45-minute
whole-job deadline. The native step starts at 06:11:46 UTC. The ten earlier
memory groups finish by 06:46:14; the new dense Unicode GDI workload starts
next. Repeated Python tracebacks from 06:47 through 06:51 put its controller
in the synchronous `MoveWindow` call in `tab_workload_memory.exercise`.
The external process-tree sampler continues on another thread.

These stacks identify the waiting controller, not the frontend's cause.
There is no retained native stack, completed dense-memory observation or
final single-file validation manifest. They cannot establish whether the
frontend is blocked or simply spending too long processing/painting the
dense scene. The existing job limit and memory limits remain unchanged.

Before that incomplete group, the same executable passes all ten earlier
two-tab memory groups and three requested-renderer Unicode selection runs:
16 cases per run, each with exact shortcut and right-click copy (96 copies
total). Requested OpenGL falls back to actual GDI. These are synthetic,
instrumented input checks, not physical input acceptance. Memory sampling
is uninjected and uses the retained remote Consolas grids.

The observations record executable SHA256
`68bd5992457ecd06632f9e05099e119a5439ae0760e3df59b14bc2f57c2686e8`.
Artifact `14150517760` contains evidence only. Neither executable upload ran:
the product required success, and the failed-image condition excluded a
cancelled job. Future failed/cancelled runs retain their unverified images.
This does not recover the old executable or make an exact-image replay
possible. `unicode-dense-memory-validation.json` indexes 31 retained original
records and their hashes in `dense-memory-timeout-eae8968.tar.gz`.

The subsequent [lazy cell index](kitty-cell-performance.md) removes repeated
placement lookup/insertion scans and passes its complete component checks.
Native rendering still walks placements for each text run and makes small
row-composition calls; these are potential remaining costs, not a diagnosed
cause of the wait. Full native CI is checking the indexed version. An external
controller checkpoint now records the last phase, input and memory sample
before/after each resize, explicitly marked incomplete. No new local native
test has run while desktop testing is paused, and the accepted executable
remains unchanged.

The opt-in source diagnostic runs the same dense workload with small external
process dumps if a synchronous resize remains outstanding for 30 and 60 seconds.
The dump's thread information includes CPU times. Capture validates the inherited private-job
and process handles, and its existing three controls cover target survival,
thread context, wrong-job rejection and an exited target. The diagnostic retains
the ordinary 180-second diagnostic watchdog and exits separately from acceptance.
No dump helper is added to the production binary or ordinary memory runs.

The first dispatch, `43688160693` at fixture `09dd518`, fails before launching
Nemoterm because the older diagnostic branch referenced `faulthandler` without
importing it. The fixture now imports it explicitly. That setup failure is not
a resize reproduction; its runtime identity, control results and error remain
in the original CI artifacts.

The corrected [indexed-source diagnostic](https://github.com/xiongnemo/nemoterm/actions/runs/43688463026)
at fixture `84e6f80` completes in both requested renderers. Each rebuilt frontend
uses production source `f01927a`, which includes the lazy index, and the matching
source-host artifact. Both complete all 24 resize calls, reseed both final grids,
and naturally drain all 31 owned processes. Neither call sequence reaches the
30-second dump threshold; no application dump is taken.

| Requested renderer | Actual grid | Median / longest observed resize (s) |
| --- | --- | --- |
| GDI | 109x34 | 0.899 / 1.110 |
| DirectX | 88x35 | 0.367 / 0.531 |

These intervals include external before/after thread-snapshot overhead. They
are not frame latency, and different grids/runners prevent a renderer ranking.
The runs explicitly disable memory acceptance and stop before post-memory pixel
verification; they do not replace the ordinary dense-image gate. The rebuilt
executables also differ from the missing original single-file image.

`unicode-resize-diagnostic-validation.json` indexes 152 retained observations,
logs and controls in `indexed-native-resize.tar.gz`. Downloaded runtime/helper
binaries are listed by hash and remain in the identified local/CI artifact
folders rather than being embedded in this archive. The earlier setup failure
is included. The rebuilt pre-index source diagnostic below locates a slow path;
these finite indexed passes alone do not establish the original missing image's
timeout cause. Full local-grid acceptance remains pending.

## Pre-index source reproduction

[Run 43688973897](https://github.com/xiongnemo/nemoterm/actions/runs/43688973897)
uses the same `84e6f80` diagnostic fixture with production source `eae8968`.
Both GDI and DirectX remain in the first resize when the existing 180-second
diagnostic watchdog terminates their controllers. Each retains two successful
external captures, at 30 and 60 seconds; the helper leaves its target alive.
The first scene's grid, cell count, input byte count and hash match the indexed
diagnostic for each renderer exactly. The only changed production file between
`eae8968` and `f01927a` is `nemo_kitty_placements.c`.

The GDI thread is captured at `by_sequence+0xd` and `by_sequence+0x12` and adds
27.453 CPU seconds between snapshots. DirectX is captured at `by_sequence+0xd`
and `nemo_kitty_placement_view+0x13`, adding 29.594 CPU seconds. Disassembly of the
retained rebuilt image confirms those `by_sequence` addresses are in the linked
list search. These direct instruction and CPU observations demonstrate active
placement lookup in the source reproduction, rather than a waiting thread.

Raw stack words also point into `visible`, `nemo_kitty_paint`, text drawing and
painting callbacks; these are explicitly recorded as pointer candidates, not
an unwound call chain. Source inspection connects each per-text-run placement
walk to a fresh linear prototype lookup for each view. The lazy sequence index
removes that inner list search without changing the raster, cell cap or budget.
Different runners and rebuilt images prevent an exact latency comparison or a
claim that the missing original single-file failure has been replayed.

`unicode-preindex-stall-validation.json` indexes 82 original records in
`preindex-native-resize-stall.tar.gz`, including all four dumps, rebuilt runtime
images, symbol lists, helper controls, disassembly and offline parser. Neither
baseline controller reaches memory acceptance or ordinary cleanup; the existing
watchdog bounds the diagnostic lifetime.

## Completed indexed ordinary CI

[Run 43686454496](https://github.com/xiongnemo/nemoterm/actions/runs/43686454496)
at `f01927a` passes all four jobs, including the complete Windows native sequence
and all twelve uninjected two-tab memory groups. The dense Unicode groups pass
their unchanged strict GDI 20 MB / inclusive DirectX 25 MB private-WS gates:

| Renderer | Actual Consolas grid | Peak private WS | Peak total WS |
| --- | --- | ---: | ---: |
| GDI | 109x34 | 14,405,632 bytes | 45,400,064 bytes |
| DirectX | 88x35 | 18,411,520 bytes | 54,407,168 bytes |

After sampling stops, all 25,048 expected cell centres match across active and
inactive reads of both tabs (260 row strips total). The same frontend also
passes 153 Unicode cell/geometry stages and 96 exact clipboard copies. Requested
OpenGL again falls back to GDI. All memory fixture jobs drain naturally.

`unicode-indexed-core-validation.json` indexes 78 workflow, memory, native and
retained strip records in `indexed-full-core-f01927a.tar.gz`. The portable MinGW
frontend SHA256 is
`9fa94d82fac744a2dbed3fda8bd78f6a75e8b2b01207f8670938513cdfc267e3`.
It uses separate ConPTY/console-host files; the single-file workflow remains
independent. This is remote-grid acceptance, not local 160x48 Sarasa validation.
DirectX total WS still exceeds the approximate 50 MB target. No distribution
binary is promoted, and local desktop testing remains paused. The separate
indexed single-image run subsequently fails its
[mixed-profile close check](unicode-single-profile-close.md) before memory
acceptance; its exact executable is retained for diagnosis.
