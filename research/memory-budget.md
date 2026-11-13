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
failure, but the overall run has not completed acceptance. The
[retained failure record](memory-budget-evidence/single-gpu-lifecycle-attempt-1.json)
identifies its exact EXE and forced cleanup. A fresh attempt of the same source
is running; no assertion or deadline was relaxed. The README's fixed verified
download and accepted local executable remain unchanged. No local runtime
tests were executed.
