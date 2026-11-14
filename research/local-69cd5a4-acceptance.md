# Resumed local acceptance of the downloaded 69cd5a4 image

The user resumed native testing on November 15, Sydney time. The tested artifact
is the 4,486,144-byte single EXE from run `43609279193`, artifact `14121125045`,
SHA-256 `e9251226d91972e137db9e84ad74bf3ead4fa5564fd38298ca6152525012eba6`.
It remains isolated under `build`; the accepted executable has not changed.

Local Sarasa font zoom on actual GDI/OpenGL/DirectX, all three bell API profiles
and mixed-font/rendering tabs pass, as recorded in [font and bell validation](font-zoom-and-bell.md).
Full native memory acceptance is **not complete**.

All DirectX workloads below use the actual 160 by 48 SarasaTermSC Nerd Font Light
grid. Memory sampling is external, with no injected observer, capture requests
or working-set trimming during the sampling interval. Raw peaks were recomputed
from every retained frontend sample. Host and workload-client memory is separate.

| Workload | Samples | Private WS peak | Total WS peak | Private commit peak | Outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| Baseline | 572 | 23,412,736 | 62,439,424 | 92,274,688 | Nine groups and memory pass, natural cleanup |
| PNG | 697 | 24,424,448 | 63,881,216 | 93,790,208 | Nine groups and memory pass, natural cleanup |
| GIF, original run | 619 | 24,674,304 | 64,045,056 | 92,553,216 | Post-sampling animation check fails; not acceptance |
| GIF, capture-timing diagnostic | 653 | 25,133,056 | 65,474,560 | 88,690,688 | Nine functional groups pass; 25 MB gate fails |

The original GIF check observes red and green but no blue in 14 captures over
3.07 seconds. Its failure cleanup terminates five remaining owned processes and
confirms zero afterward. The timing diagnostic preserves the original workload,
3-second assertion, PNG writes and executable, adding only controller-side API
timestamps. Both tabs show all three colours in that diagnostic and all processes
exit naturally, but the memory assertion fails by 133,056 bytes. Neither failed
run is discarded or promoted to a pass.

Two narrower diagnostics on the same executable pass 36 GIF codec/lifetime pixel
checks and nine large-image colour checks at 160 by 48. In the latter, 42 image
requests take a median of about 11 ms. Dense-workload image requests instead
include 111–185 ms calls, longer than the animation's 100 ms frame interval, and
writing each newly seen PNG adds further delay. Sampling aliasing is a plausible
explanation for the first failure; these comparisons do not isolate causality or
prove every original frame was displayed. The independent small/large tests are
not substitutes for the failed full workload.

The preceding `26f50c8` resource-count failure is also unresolved. Successful
resource cycles on this artifact do not establish its cause. The approximate
50 MB total working-set target is not met by these DirectX observations.
Fresh GDI memory acceptance and a more reliable margin below the unchanged
25,000,000-byte DirectX ceiling remain to be completed. Logs, raw samples,
diagnostic scripts, observations and original failure images are retained with
hashes in [the validation record](local-69cd5a4-validation.json).
