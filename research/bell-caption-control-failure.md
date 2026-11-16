# Caption fallback exposes a native DirectX exit

The four [ordinary focus comparisons](bell-focus-029bfac.md) pass, but they
do not exercise synchronized caption fallback: all delayed activations settle
at the queue barrier. A separate control refuses only the Python controller's
initial SetForegroundWindow request. It leaves the owned terminal processes,
native caption hit testing, SendInput, foreground observations and all 74 bell
assertions unchanged. It does not inject a hook into the standalone cover
terminal; the pre-existing Frida bell probe observes the separate tab host.

Two hosted runs stop after 47 checks in the third profile, DirectX without
AlwaysOnTop. GDI's normal and topmost profiles complete first. Rapid caption
clicks are observed to change the cover window from its normal rectangle to
`[-8,-8,1032,728]`, consistent with maximization. The helper also selects a
caption point at y=-2, outside this runner's visible screen. These are concrete
preparation defects to address, but they do not establish why the process exits.

* [Run 43782567735](https://github.com/xiongnemo/nemoterm/actions/runs/43782567735),
  fixture `8e0c1c7`, records a focus timeout followed by a nonzero-exit assertion;
  the original fixture did not retain the numeric process exit code.
* [Run 43782963283](https://github.com/xiongnemo/nemoterm/actions/runs/43782963283),
  fixture `23acf07`, adds process-lifetime evidence without changing foreground
  preparation. The standalone cover process exits **3221226525 / 0xC000041D**
  before cleanup; its last cooperative client snapshot has no reported error.
  The tab host exits zero after the normal stop request. The capture retains
  the initial focus timeout instead of masking it with the cleanup assertion.

Both runs use the exact original single EXE, SHA-256
`64a493391747c27afd44074a4fea3f3efc21724139baef6d35d13955d0d05f5d`.
The original artifact ZIPs, logs and per-run validation manifests are retained
as `bell-caption-control-{8e0c1c7,23acf07}-failure*`. Server digests, every member
hash, image identity and fixture source are checked. Application-scoped WER
capture produced no dump or application-error event in the second run; that
absence does not negate the observed native exit.

The next diagnostic attaches the previously controlled external exception
observer only to this newly spawned, private-job cover process. It checks
observer exception sensitivity and target survival first, retains exception
addresses and dumps, and leaves the original action order intact. Debugger
attachment changes scheduling and exception dispatch, so its outcome will be
reported separately. No production source has been changed or promoted.

Complete ordinary and single-image CI at `8a6bd2b` remain useful regressions,
but even a pass cannot close this newly exposed native-exit case. Exact-product
acceptance and any promotion must wait for this failure to be understood.

The external observer subsequently reproduces the same 47-check failure and
captures the original write exception and a dump. A production staging-strip
bounds defect and its before/after regression are described in
[the DirectX allocation correction](d3d11-discarded-reservations.md). Fixed-image
native replay is still required before treating this case as resolved.
