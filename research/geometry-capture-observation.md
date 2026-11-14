# Geometry capture and lifecycle failure evidence

The geometry and application-resize fixtures now obtain GPU pixels from the
opt-in local automation interface. GDI still uses independent PrintWindow.
Win32 rectangles, ConPTY replies, retained pixels after minimize/restore,
synchronized frames, resize policies, actual-renderer requirements and the
10-second exit deadline remain unchanged. The default geometry/resize paths
use no injection; the explicit geometry `--observe` diagnostic still does.
Successful cases also require the private process job to drain naturally.

Three earlier CI failures remain unresolved:

- [e126 single-image run](https://github.com/xiongnemo/nemoterm/actions/runs/43575722079)
  reached all 42 normal DirectX resize checks with left-side tabs, then returned
  a nonzero process exit. The old assertion discarded its value. Capture had
  detached before stop. The retained application-event list is empty.
- [GIF core run](https://github.com/xiongnemo/nemoterm/actions/runs/43576229677)
  exceeded the geometry process-close deadline with bottom-side tabs, followed
  by a Frida-detach timeout. Its failed portable image was not uploaded; the
  separately passing single-image artifact is not the same executable.
- [a6 single-image run](https://github.com/xiongnemo/nemoterm/actions/runs/43575726430)
  failed to find the requested OpenGL window within eight seconds, before
  attaching Frida. No actual renderer or pre-cleanup exit code was retained;
  its application-event list is empty.

The fixtures now retain exit codes, close duration, natural/forced job cleanup
and failure-time process status. When the owned process is still alive, a
read-only observer records thread start metadata and owned window classes.
It reads no stacks or window text and performs no suspension or injection.
Observation errors are separate from the original failure. Explicit observer
detachment is bounded and cannot replace an already-raised primary exception.
The startup deadline and zero-exit requirements have not been relaxed.

## Finite local comparison

The failed e126 image (`3ee59aa8...f78f`) passes both an original-fixture replay
and the new left-tab resize fixture on actual GDI, OpenGL and DirectX, including
the three additional GDI resize policies. The accepted default image
(`c110843b...5e26`) passes the new standalone resize and geometry tests.
The separately successful GIF single-image artifact (`73c13e96...d406`) passes
the new bottom-tab geometry test on all three actual backends. These four
updated geometry/resize runs complete 326 checks in 18 owned terminal
processes; every process exits zero in 0.0732-0.3131 seconds and drains naturally.

The failed a6 image (`200f0025...873`) passes all six original and all six updated
shutdown cases. The existing lifetime probe and its callback-order assertions
are retained. Each updated case records a zero exit and natural job drainage.
These passing replays do not establish the cause of the earlier failures.

A separate negative canary deliberately withholds the new fixture's window-
ready result. It fails at the original eight-second deadline before injection,
records the live owned terminal window and thread metadata, and records forced
cleanup of exactly its three private-job members. Its failure is expected
diagnostic validation, not a product pass.

The [manifest](geometry-capture-validation.json) retains full image identities,
original/new fixtures, failed CI logs, local results, screenshots and the canary.
No product source or accepted default executable changes in this checkpoint.
