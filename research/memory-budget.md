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
