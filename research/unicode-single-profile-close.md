# Indexed single-file build: mixed-profile close timeout

[Single-image run 43687495119](https://github.com/xiongnemo/nemoterm/actions/runs/43687495119)
at `fd0c2535314e4a3d0609eaff465962c1d96b2b14` fails the mixed-profile fixture.
Its seven functional groups finish, including font zoom, input isolation,
36 renderer switches and synchronized frames. The fixture closes its capture
helpers, detaches its key probe and successfully posts `WM_CLOSE` to the verified
owned host. The frontend does not exit within the unchanged 15-second limit.

Read-only failure metadata still finds the host, all three content windows and
the DirectX child surface. All seven owned processes remain alive; cleanup
terminates the private job. The record also contains retained Frida module and
thread metadata after detach, but no native stack. That presence alone does not
identify a cause. This timeout is distinct from the earlier `eae8968` MinGW
access violation in [the source-build failure record](unicode-profiles-close-failure.md).

This time the workflow preserves the exact unverified single EXE: 4,523,520 bytes,
SHA256 `992cabb4d424235e92f46586230c5282dab1ad3a92d1cef3bd7f1b63ff759115`,
artifact `14151996507`. Evidence artifact `14151548857` retains the earlier
153 Unicode geometry/pixel stages and 96 exact clipboard copies. They are
partial passes: the later memory groups are not reached and there is no final
single-file validation manifest or passed product artifact.

`unicode-single-profile-validation.json` indexes 23 original records, including
the failed executable, in `indexed-single-profile-timeout.tar.gz`. The accepted
local `752f3be` distribution is unchanged. The independently passed ordinary
MinGW/source-host CI does not make this single-image run pass.

The exact-image replay workflow now permits post-failure capture for the profile
fixture. It verifies the original artifact SHA256 and unchanged production
sources, runs the three existing external-dump controls, then repeats twelve
independently owned lifetimes. The helper is only invoked after a check has
already failed, before cleanup; it neither changes the 15-second limit nor turns
a failure into success. Replays use the original Frida 17.24.3 dependency. This
diagnostic runs on GitHub's disposable runner; local desktop testing stays paused.
