# User-approved frontend memory policy

On 2026-11-14 the user approved DirectX private working set up to 25 MB, with
further optimization deferred. The acceptance policy uses decimal bytes:

| Observed renderer | Private working set |
| --- | --- |
| GDI | Strictly below 20,000,000 bytes |
| DirectX | At most 25,000,000 bytes |
| Optional OpenGL | Existing user-approved exception; still record counters |

The native renderer property selects the limit, including fallback to GDI.
Private commitment and total working set remain separate counters; roughly
50 MB total working set remains a target. No working-set trimming is added.
Historical runs retain their original limits and outcomes.

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
