# Dense-image fixture lifetime investigation

[Single-image run 43754577320](https://github.com/xiongnemo/nemoterm/actions/runs/43754577320)
at `69496bb` failed the GDI Unicode-image tab workload while waiting for five
live owned processes during repeated shortcut-driven tab closes. At failure,
the frontend had exited with code 0 and all 41 processes created so far had
exited. This was not an observed crash or memory-limit failure.

The original image is 4,544,512 bytes, SHA256
`4a50a382545ef40ffe06d2950e75bd71ff57a06558f3a6d518fd5653ba48319a`,
from artifact `14179329039`. Its uninstrumented GDI memory phase retained 1,708
samples over 179.156 seconds, peaking at 13,561,856 bytes private working set.
The runner clamped the requested 160x48 grid to 109x34; these numbers cannot
stand in for the separate local 160x48 memory workload. All four post-sampling
Unicode pixel checks matched, covering 13,696 cells.

The synthetic client has a fixed 300-second lifetime. A later periodic Python
stack still places the controller in `frida.attach`; the subsequent failure is
in the close-cycle process-count wait. An expired client lifetime is a plausible
explanation, but the original test did not record an exit reason. Wall-clock
log output and frontend exit code alone do not establish that cause.

The following [single-image run 43755825357](https://github.com/xiongnemo/nemoterm/actions/runs/43755825357)
at `23c90fe` passes all 163 groups. The same GDI workload also completes at
109x34 with the original 300-second client lifetime, peaking at 13,971,456 bytes
private working set. Its image SHA256 is
`3c7cd5be5fbf134dd52be085fb9476698dc9868389684d6f8467fe7d334cfc27`.
This different-source passing image is comparison evidence, not a replay that
fixes the earlier failure. That revision's ordinary workflow also failed its
Unix NUL regression and a separate portable callback test.

The diagnostic adds per-client receipts for deadline, requested-stop and
exception exits, plus timestamps around the existing probe attachment. It
records these files before removing the private fixture directory. Abruptly
terminated clients may leave no receipt; absence is not an exit classification.
The 300-second lifetime, memory gates, workloads, native waits and teardown
assertions are unchanged.

Two local controls using the exact failed image verify a two-second deadline
receipt and an explicit stop before a 30-second deadline. Both frontend exits
are zero and both three-process jobs drain naturally. These controls verify
the observer; they do not establish the original CI failure's cause.

The focused workflow's `tabs-unicode` mode reuses the identified failed single
EXE with the original requested grid, font, workload and Frida 17.24.3. It
preserves the existing failed-run, source-difference and executable-hash guards.

[The exact-image replay](https://github.com/xiongnemo/nemoterm/actions/runs/43760193865)
passes all ten groups in 295.469 seconds. Probe attachment starts at 292.140
seconds and finishes at 292.484; all 56 owned processes drain naturally. No
client writes an exit receipt, as they are retired by the terminal during the
normal close checks. This successful run leaves about four seconds of fixture
lifetime and demonstrates insufficient headroom, without proving the earlier
failure's cause.

`session-lifetime-diagnostic.tar.gz` and its validation manifest retain the
failed run, local receipt controls, later 163-group single-image comparison,
and exact-image hosted replay (artifact `14179234849`).

Only the Unicode-image workload invocations in ordinary and single-image CI
now request a 900-second client lifetime. The default remains 300 seconds;
other tests, memory ceilings, operation waits and normal shutdown bounds are
unchanged. The focused `tabs-unicode-900s` mode allows the same failed image to
exercise this setup change without rebuilding or changing production code.

[The 900-second replay](https://github.com/xiongnemo/nemoterm/actions/runs/43760974443)
uses the same failed EXE and passes all ten groups in 302.172 seconds, with 56
naturally drained processes and no forced cleanup. The GDI private working-set
peak is 14,528,512 bytes on the same 109x34 grid. All four post-sampling image
checks report 13,696 matched cells. The setup change preserves the original
memory threshold and operation/close assertions. The earlier failure remains
retained with its unproven cause.

`session-lifetime-900.tar.gz` and its validation manifest retain artifact
`14180351718`, exact runtime identity, fixture observation and controller logs.
This focused workflow does not upload the replay's full raw memory sample file
or PNGs, so it is not an independent re-analysis of those pixels or a local
160x48 product acceptance. The full CI and local acceptance paths retain those
additional files separately.
