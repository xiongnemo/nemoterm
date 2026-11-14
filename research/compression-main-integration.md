# Compression integration CI: retained success and two separate failures

Source `2f478e7` integrates the accepted compression implementation without
changing its product source. Its [single-image run 43652684796](https://github.com/xiongnemo/nemoterm/actions/runs/43652684796)
passed all **137 check groups**. The resulting 4,515,328-byte image has SHA256
`4a1ea84c11f10ae3e984dd040a78da9a6262fb3ab40dbed3fa59c4492297d19f`
and artifact ID `14137487501`. This is a different build from the accepted
`b3e03bb` artifact; it has not replaced the locally accepted executable.

The [ordinary run 43652684756](https://github.com/xiongnemo/nemoterm/actions/runs/43652684756)
failed. Its source-host and ASan/UBSan jobs passed, while two other jobs had
different outcomes:

- The MSVC tab fixture recorded an access violation after probe detachment.
  The exact failed sidecar-host image passed six unchanged local replays, two
  local boundary-observer runs and three hosted diagnostic replays. The cause
  remains unproven; see [the full failure record](tab-probe-detach.md).
- The Windows native suite reached the whole-job **30-minute ceiling** during
  `Test compressed Kitty PNG with mandatory tab memory limits`. GitHub's check
  annotation explicitly reports the maximum execution time, and the job began
  at `23:24:04Z` with the active step cancelled at `23:54:04Z`. The final group is
  incomplete, so this run does not pass the full memory gate or publish a portable
  artifact. The prior successful `48a0263` Windows job took 25 minutes 23 seconds.

The workflow's outer Windows-job budget is now 40 minutes for the expanded native
suites and ten memory workloads. Individual fixture deadlines, resource checks,
private-working-set limits and exact pixel/reply assertions are unchanged. The
MSVC diagnostics retain opt-in procedure-entry/liveness snapshots around the
existing probes; that observation does not claim to fix the original crash.
The updated complete ordinary workflow still needs to finish successfully.

`compression-main-integration-validation.json` indexes **3,395 original files**
in five deterministic tar/gzip archives, including run logs, artifact identities,
the timeout annotation, complete single-image evidence and incomplete ordinary
evidence. Every encoded record was verified against its raw SHA256. Helper and
product binaries remain CI artifacts. The accepted local `b3e03bb` hash, its
measured memory results and the original full-goal scope remain unchanged.
