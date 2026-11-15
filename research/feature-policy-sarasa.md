# Local Sarasa preflight for the feature-policy candidate

The user resumed local testing on 2026-11-16. These observations use the
MinGW frontend at `846b525bd0c7cbeacf71d12596d0a264d82eb5c6` with the pinned
packaged ConPTY runtime. They do not certify the combined single executable or
replace its pending full CI and local acceptance. The accepted EXE is unchanged.

The installed face resolves to `SarasaTermSC Nerd Font Light`, including a
native CJK glyph. The independent OS mapper result and the first startup sample
are in `feature-policy-sarasa-startup-observed.json`. The updated startup
fixture explicitly requests GDI, accepts `--font`, verifies the actual backend,
and requires natural owned-job cleanup. Its successful rerun is retained in
`feature-policy-sarasa-startup-owned-observed.json`:

* The default is 160x48 characters, with 8x20 cells on this machine.
* A 1000x1000 request at 24 points is clamped to 117x24 characters with 16x40
  cells, inside the 1920x1040 monitor work area.
* Both processes and their children exit naturally. Startup memory is a
  point-in-time private-working-set observation, not the dense workload gate.

## First dense Unicode workload: incomplete

The first 160x48 two-tab GDI run completes all 24 resize frames and samples
291.227 seconds. Its observed frontend peaks are **19,857,408 private working
set**, **41,963,520 total working set** and **22,917,120 private commit** bytes.
No observer is injected during these samples. The GDI private threshold remains
strictly below 20,000,000 bytes; the DX policy is unchanged.

The run subsequently fails during inactive-tab pixel verification with
`session no longer exists`. The fixture child has a hardcoded 300-second
lifetime, leaving insufficient time for the large local workload and its
post-sampling pixel checks. Cleanup terminates the remaining frontend, so this
run is **not accepted**, despite the sampled private peak being below the limit.
`feature-policy-sarasa-first.tar.gz` retains 11 original records / 7,388,484
bytes, including memory samples, partial pixels, failure/cleanup and the original
fixture source. Its manifest is `feature-policy-sarasa-first-validation.json`.

The tab fixture now accepts an explicit bounded `--session-seconds` option,
passed to each child. Its default remains 300 seconds. The local repeat will
use 900 seconds with the identical executable, font, grid, workload and memory
threshold. Individual reply waits and shutdown deadlines are unchanged. Passing
that repeat, including all pixels and natural cleanup, is still required.
