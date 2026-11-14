# Tab capture and lifecycle failure observation

The tab fixture now obtains retained terminal pixels through the existing
opt-in local automation interface. It preserves the nine tab, shortcut,
resource-return, fault, preview, synchronized-frame, fullscreen, resize and
sibling-lifetime checks. Key/fault/preview probes still use instrumentation;
independent native screenshot parity remains in the automation/renderer suites.
This is an observation change, not a product crash fix.

The fixture starts its owned frontend with `--automation`. Workload memory
sampling includes that idle endpoint, but precedes both snapshot requests and
injected probes. Thresholds, sampling, resource allowances and deadlines are
unchanged. Phase, read-only process/thread/window metadata and host exit/time
are retained on failure. Probe detach has the existing bounded wait; secondary
detach failures do not replace an earlier error. CI will also retain the exact
failed MSVC frontend and its console sidecars for replay.

## Failed main CI remains unresolved

The `8a41ad7` branch workflows passed before integration. Its later main
[core run 43581417880](https://github.com/xiongnemo/nemoterm/actions/runs/43581417880)
fails repetition five of eight in the MSVC tab fixture. Requested OpenGL had
fallen back to GDI (`actual_renderer=1`). Eight groups passed; after closing the
original tab, the sibling HWND was gone. The first poll still saw a running
frontend, but private-job cleanup recorded frontend exit **0xC0000005**.
Four console/client processes remained live and cleanup was forced. Application
error events are empty; the workflow did not retain that exact MSVC image,
SHA-256 `df60002f650e651e69eb4bce9de53703cefdd8564e8fb63b7909a548dca0eeff`.
There is no stack or fault-address evidence to assign a cause.

The same-source [main single-executable run](https://github.com/xiongnemo/nemoterm/actions/runs/43581417881)
passes 108 groups. Its EXE SHA-256 is
`2e74be8f0d7f9c9a76520d307724e1c04258ce3c90e37c30b2fbbe9fadaa2b60`,
4,452,864 bytes, artifact 14109725146. That separate success neither reproduces
nor resolves the failed MSVC diagnostic image. The accepted default EXE stays
at source `8ff214f`, SHA-256 `c110843b...5e26`.

## Local comparison

The full-branch-CI `8a41ad7` single EXE
`4e25f1652d0d622c1b5a46658e9881f36dd3ecce4d7e22847a68d70a3f42d614`
supplies both old/new fixture comparisons. It is not the missing failed MSVC
artifact. Non-workload cases use 88x35 Consolas and actual requested backends.

| Case | Result |
|---|---|
| Old capture, OpenGL/right, first replay | All nine groups; natural cleanup |
| Old capture, OpenGL/right, second replay | Resource-return failure in cycle two, before injection/capture |
| API capture, GDI/top | All nine groups; natural cleanup |
| API capture, OpenGL/right | Resource-return failure in cycle two, before any API snapshot or injection |
| API capture, DirectX/left | All nine groups; natural cleanup |

Both resource failures end 40 handles, two GDI objects and 12 USER objects above
the two-tab baseline (11 USER objects above the preceding returned cycle).
The original six/three/two allowances correctly fail. Each failed fixture
forcibly closes its five remaining owned processes; an empty outer job does not
make those cases natural-cleanup passes. The complete comparison driver fails.

The new failure metadata contains IME windows and threads. A separate read-only
metadata diagnostic already sees these at baseline and completes all nine
groups. It is explicitly diagnostic, not replacement acceptance, and does not
establish that IME initialization caused the earlier count increase. No memory
payload, stack or object name is collected. The original CI crash also remains
distinct from these earlier resource-return failures.

The originally planned late-close negative canary was stopped by the same
resource gate before reaching its intended close. It is retained as an
inconclusive canary. A separate early canary copies the same close assertion
immediately after two-tab routing, deliberately closes only its owned host and
correctly records `sibling_alive=false`, phase `close-first-tab`, the failure-time
process metadata and natural drain of its five owned processes. It is an
expected failure, not a product pass or a resource-test replacement.

## Memory with the interface enabled

The accepted `c110843b...5e26` EXE is unchanged. Actual 160x48 SarasaTermSC Nerd
Font Light workloads include two histories, Sixel, redraw and resize, with no
concurrent compilation, memory trimming, snapshot or injected memory observer.

| Renderer | Samples | Peak private WS | Peak total WS | Peak private commit |
|---|---:|---:|---:|---:|
| GDI | 521 | 16,392,192 | 43,364,352 | 19,238,912 |
| DirectX | 478 | 23,633,920 | 63,430,656 | 87,261,184 |

Both pass their unchanged private-WS gates and all nine functional/resource
groups, naturally draining 56 inner / 58 outer processes. DirectX total WS
still exceeds the approximate 50 MB target. These are finite workloads with
the idle interface enabled, not all-load or sustained real-agent guarantees.

The [manifest](tab-api-observation-validation.json) retains each fixture,
source hashes, all failed/passed results, native screenshots, raw memory samples,
controller cleanup and the completed main CI records. New full branch CI is
pending; no default executable is replaced.
