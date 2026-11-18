# User-approved frontend memory policy

The current acceptance limits apply to the frontend's peak sampled private
working set. MB is decimal; select the limit from the observed renderer.

| Observed renderer | Private working set |
| --- | --- |
| GDI | Strictly below 20,000,000 bytes |
| DirectX | At most 30,000,000 bytes (inclusive) |
| Optional OpenGL | Existing user-approved exception; still record counters |

The native renderer property selects the limit, including fallback to GDI.
Private commitment and total working set remain separate counters; roughly
50 MB total working set remains a GDI target. No working-set trimming is added.
Historical runs retain their original limits and outcomes.

GitHub Actions run `44277391833` tested `ba91594` (EXE SHA-256 `c4963dba443aa810a3274d9cfcef92c1fb685f262e1573e37de629dfa6f48620`). All [six 160×48 DirectX workloads](ba91594-directx-memory-receipt.zip) passed. Plain text peaked at **26,079,232 bytes**; dense Unicode plus Kitty graphics peaked at **28,856,320 bytes**, leaving **1,143,680 bytes** below the 30 MB limit. The latter also recorded 71,958,528 bytes total working set and 32,468,992 private committed bytes. These are frontend-only samples without injection. The original GitHub receipt (artifact `14416816247`, SHA-256 `3d85a7b04e6248baceb2af1d38cf0a7e2d359252791ee0a3b4c5c3b2030e6a77`) includes all six per-workload sample traces and process cleanup results.

On the same image all [six GDI workloads](ba91594-gdi-memory-receipt.zip) passed as well. The highest private working set was **19,140,608 bytes** (`full-grid-unicode-kitty-gdi`). Original GitHub receipt: `14416512219`, SHA-256 `e27dfc1f4457bf2ccba5624594377cb94fa8bfc55c697526d100ab8cf854c82f`.

For the quieter case of a single completed Codex reply, see the [same-runner pterm, default tab and standalone GDI comparison](pterm-findings.md#同一台-runner-上的真实-codex-对照). It reports steady medians; the acceptance limits above apply to sampled peaks.

### Default grid with real clients

On `ba91594`, the [six original default-window receipts](real-agent-default-grid-ba91594.zip) from run `44293961012` all passed on GitHub-hosted Windows. The launch supplied **no width or height override**. Each run verified the actual 160×48 grid, actual GDI or DirectX renderer, Sarasa Light face, a real Shift-drag and system keyboard clipboard, exact text at the local provider and natural process cleanup. A background sampler observed the frontend from discovery through submission without attaching to it. The table takes the highest private working set among the periodic observations and five named milestones per run; these are sampled maxima, not an OS lifetime high-water mark. The client and separate console host are excluded.

| Real client | GDI private working set (bytes) | DirectX private working set (bytes) | GDI / DX periodic samples |
| --- | ---: | ---: | ---: |
| Codex | 11,411,456 | 17,518,592 | 30 / 29 |
| OpenCode | 13,897,728 | 12,480,512 | 88 / 80 |
| Claude Code | 11,612,160 | 17,575,936 | 38 / 40 |

Each phase lasted 3.3–9.9 seconds from first to last periodic sample, with 305 periodic observations in total. The original GitHub receipt is artifact `14423380725`, SHA-256 `65120ec08e7f5a3fdc7169119b826c70607e062b70e8f2dd21a1267c95dc066c`; it retains the exact traces, milestone readings, client identities and provider receipts. These are interactive workloads, not a benchmark of model inference or the dense Unicode/graphics stress cases.

### Smaller 100×30 interaction samples

On the same EXE, [20 real-client desktop selection cases and their original observations](real-agent-frontend-ba91594.zip) ran at **100×30**, on the `SarasaTermSC Nerd Light` Windows face. Each sampled only the frontend at five milestones: startup, first reply, copy, composer, and submission. These are the highest of those five readings across the cases, **not** continuous process high-water marks or total memory for the client and its shell.

| Real client | GDI private working set (bytes) | DirectX private working set (bytes) | Runs per renderer |
| --- | ---: | ---: | ---: |
| Codex | 6,086,656 | 8,933,376 | 3 |
| OpenCode | 6,189,056 | 9,011,200 | 3 |
| Claude Code | 6,406,144 | 9,195,520 | 4 |

The 100 readings are from GitHub run `44286244961`, artifact `14419238081`, original SHA-256 `885bc0007951ec29808c48210a93e190b1c995aca3672629f07b851827a412c0`. Each case verified the actual renderer, native keyboard/mouse, provider receipt and process cleanup. Separate image-paste failures in that run remain failures. The results above do not estimate a default-sized interactive window.

The [November 18 DirectX replay](directx-30mb.md) records the change from
25 MB to 30 MB. In the [six 160x48 workloads for preview `1b24e72`](selection-history.md#candidate-1b24e72),
DirectX peaked at 28,545,024 bytes, leaving 1,454,976 bytes below its limit.
GDI peaked at 18,894,848 bytes. The [earlier `85fe9b1` measurements](interaction-85fe9b1.md#memory-of-this-executable)
remain available for that executable.

In the independently built `163b3ea` executable from [full run 44238887555](https://github.com/xiongnemo/nemoterm/actions/runs/44238887555), the completed DirectX memory group also passed all six workloads. Its largest sampled frontend private working set was **29,446,144 bytes** (Unicode Kitty); total working set was 74,690,560 bytes and private commit was 32,808,960 bytes for that workload. This leaves 553,856 bytes under the DirectX limit. The executable SHA-256 was `c896d59bcc90136b4985637d5398d5ffa9b5e09679d20cc5492e72cd789e4ad5`. [Original memory artifact](https://github.com/xiongnemo/nemoterm/actions/runs/44238887555/artifacts/14398649827), ZIP SHA-256 `f015fa78c100b2faf1206a0dd8be3e571f4437afc7c5d7c1a17443132799c0f4`. This result covers the DirectX memory group only.

## Historical November 14 policy and results

Source `3f68d9c644ae049d981288920fcfb579ac456441` changes policy, documentation
and test reporting, not product source. Its
[core workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43453467534)
passes Windows and ASan/UBSan checks. The four policy tests cover strict GDI
and inclusive DirectX boundaries, OpenGL's exception and invalid observations.
They also pass in the
[single-image workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43453467235).

Attempt 1 of that single-image workflow fails before the GPU settings driver
reports ready: its 20-second wait expires, leaving an empty UI report. Earlier
shutdown, geometry and resize checks pass. This is not an observed memory-limit
failure, but that first attempt does not complete acceptance. The
[retained failure record](memory-budget-evidence/single-gpu-lifecycle-attempt-1.json)
identifies its exact EXE and forced cleanup. No assertion or deadline was relaxed.

Attempt 2 passes all **57** single-image groups, including the GPU lifecycle
fixture and the 25 MB tab-host check. Its [artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43453467235/artifacts/14054661905)
contains exactly one 4,371,456-byte EXE, SHA-256
`52d2c11b4a6575c074260f5f1fed3f03954bed4c4578c2249a863479841ac7a1`.
The README now points to this verified snapshot. A successful repeat does not
explain every earlier helper/close timeout. The
[manifest](memory-budget-validation.json) binds the downloaded binary and
retained results; the accepted local executable was not replaced and no local
runtime tests were executed.

## Development workload acceptance

Development source `7fc3c9c1a0493aa11257c40bf7b96d7c3d9e7b9d` separately passes
[85 single-image groups](https://github.com/xiongnemo/nemoterm/actions/runs/43453719414),
including real Codex default/inline and tabbed checks, pixel comparisons,
configured colours, guarded areas, shared renderer lifetime, and the normal
uninstrumented tab workloads under the newly approved policy.

| Two-tab workload | Frontend private WS peak | Frontend total WS peak | Private commitment peak |
| --- | ---: | ---: | ---: |
| GDI | 10,981,376 | 40,300,544 | 12,603,392 |
| DirectX | 21,970,944 | 59,580,416 | 24,432,640 |

Both private-working-set gates pass. DirectX total working set remains above
the approximate 50 MB target. The full sampled process tree records the frontend,
hosts and clients separately; these frontend figures are not whole-tree totals.
Both workload jobs drain naturally. The 4,437,504-byte development image has
SHA-256 `5ac65874e49ea7b08077b44aa62ebb55524c01e0da88213702a161dc21ec25d1`.
All raw memory samples are retained losslessly as compressed JSON.

The development [MinGW comparison](https://github.com/xiongnemo/nemoterm/actions/runs/43453719351)
still fails on a mixed-profile close timeout, while its ASan/UBSan and MSVC
diagnostic jobs pass. This development snapshot is therefore not substituted
for the main download. Later attribute-reset changes have their own validation;
this passing image predates those corrections.

The [six workloads per renderer on `b5d4514`](interaction-b5d4514-50.json) all passed. The dense Unicode and Kitty image case had the highest sampled frontend private working set on each renderer: **29,462,528 bytes on DirectX** (537,472 bytes below the limit) and **19,017,728 bytes on GDI**. These measurements apply to that EXE only.
