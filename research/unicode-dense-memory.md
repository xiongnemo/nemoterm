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
