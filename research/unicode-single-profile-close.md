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

[Exact-image run 43690036549](https://github.com/xiongnemo/nemoterm/actions/runs/43690036549)
at fixture `af03e5a` passes the three helper controls and all twelve profile
lifetimes. Every lifetime passes seven functional groups, returns exit zero and
naturally drains seven owned processes. The post-failure helper is never invoked
against Nemoterm, so there is no terminal dump. The original timeout remains
unexplained; finite successful replays do not change its result.

`unicode-single-profile-replays.json` indexes 47 records, including the fixture
identity and native helper controls, in `single-profile-exact-replays.tar.gz`.
Both complete workflows now prepare this validated helper and pass its absolute
path through `NEMOTERM_PROFILE_FAILURE_DUMP`. The profile fixture only captures
after an actual failure and before private-job cleanup. Successful execution,
the Frida version, the 15-second exit limit and all memory limits are unchanged.
This retains an original failure directly if it recurs during the long suite;
it is an observation change, not a production close-path fix.

The exact-image workflow also offers `profiles-api`, an uninjected diagnostic
arm of the same seven-group fixture. It enables the existing `--automation`
interface, uses its renderer BMP snapshots and sends the existing next-tab
bindings through its key operation. All three saved configurations, font checks,
input isolation, 36 renderer switches, frozen-frame checks, resource thresholds
and the 15-second close deadline remain. This arm does not import or install
Frida. It uses the same failed artifact and ownership-checked post-failure dump
helper; it does not replace the original injected checks or establish memory
acceptance. Passing it cannot by itself identify the cause of the timeout.
