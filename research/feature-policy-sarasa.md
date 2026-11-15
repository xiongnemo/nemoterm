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
threshold. Individual reply waits and shutdown deadlines are unchanged.

The first attempt with the longer lifetime did not reach the workload: the
session wrapper accepted 900 seconds, but the underlying `mouse_fixture.py`
still rejected values above 300. That guard mismatch is retained separately in
`feature-policy-sarasa-lifetime-rejected.tar.gz` with its original source and
failure metadata. Both layers now use the same 1–1800-second bound; ordinary
mouse/session defaults remain 60/300 seconds. No product code changed.

## Completed repeat: GDI memory gate fails

The repeat with the 900-second child lifetime finishes all **29,072 image-cell
checks**, all ten tab/lifecycle checks, and natural cleanup (56 total owned
processes, zero remaining or terminated; host exit code zero). Its 2,874
uninstrumented samples span 310.009 seconds. The peaks are **20,746,240 private
working set**, **42,950,656 total working set**, and **23,064,576 private commit**
bytes. It therefore **fails** the unchanged strict 20,000,000-byte GDI gate.
Neither the lower first run nor a conversion to MiB makes this result a pass.

`feature-policy-sarasa-budget.tar.gz` retains the original samples, all four
active/inactive pixel observations, twelve representative pixel strips, fixture
source, original failure and natural cleanup. Its manifest independently
recomputes the three peaks and verifies the saved strip pixels. The successful
bell single-image product is being measured with the same local workload to
distinguish a portable compiler/runtime effect from the shipping-image budget.
That comparison is not acceptance of the newer feature-policy product.

## Exact successful bell single-image comparison

The `9d636e9` single image also exceeds the GDI gate: **20,623,360 private WS**,
**44,183,552 total WS**, and **23,658,496 private commit** bytes over 3,976
uninstrumented samples / 431.678 seconds. Thus the overrun is not specific to
the portable MinGW build. All 29,072 post-sampling image cells match, but the
900-second child lifetime is exhausted before the subsequent lifecycle scenes;
the next fixture mailbox wait fails. The job drains naturally, yet neither
the memory gate nor the complete functional run passes.

`bell-single-sarasa-budget.tar.gz` retains the original measurements, pixels,
later timeout, cleanup, runtime identity and exact fixture sources. A separate
read-only region map was taken after sampling; it is not a peak attribution.
Future local dense runs use the existing bounded 1,800-second child option;
individual reply deadlines and memory thresholds remain unchanged.
