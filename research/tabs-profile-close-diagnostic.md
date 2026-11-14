# Mixed-profile close timeout, source 683f8c3

The [ordinary build](https://github.com/xiongnemo/nemoterm/actions/runs/43638850813)
passed. The [single-executable run](https://github.com/xiongnemo/nemoterm/actions/runs/43638850751)
failed after all seven mixed-profile functional checks: the frontend did not exit
within 15 seconds of posting WM_CLOSE. All seven owned processes were still live
when the fixture cleaned up its private job. No close-message return value or
thread/window failure metadata was recorded by that fixture. This is an unresolved
failure, not proof of either a product deadlock or a lost close message.

The unverified failed image is SHA256
`105181fc0b1c369f906bb3bb1536dc08b371956fa453f5737a100f8cad297035`.
It has not replaced the accepted local `97d6025` image, SHA256
`07c8d279c526b13eb75586afe1a2b980d21253adf125e3d11f68574572e8e9d6`.

The diagnostic fixture now records the owned host's process/thread identity,
checks PostMessageW's result, and collects read-only process, thread and window
metadata before failure cleanup. Its 15-second close threshold and functional
assertions are unchanged. On this PC, three fresh executions of the exact failed
image with CI's Consolas setting passed all checks and exited naturally. Each
private job contained seven processes, all drained without forced termination.
These local passes do not resolve an intermittent runner failure.

`tabs-close-replay.yml` accepts an explicit failed run, full source commit and
executable hash, checks unchanged production sources, and retains three independent
runner observations. It is diagnostic only and cannot promote this image.

The compressed raw records and their hashes are listed in
`tabs-profile-close-validation.json`. They retain the failed run alongside the
successful local repetitions; the conclusions above never substitute for either.
