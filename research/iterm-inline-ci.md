# Static inline image CI artifact: local acceptance incomplete

Source `3187ec51acb703adebf006fd637c1ad80fba8b43` passed all four jobs in
[core CI 43571162940](https://github.com/xiongnemo/nemoterm/actions/runs/43571162940)
and [single-image CI 43571162963](https://github.com/xiongnemo/nemoterm/actions/runs/43571162963).
The single-image validation manifest records 113 checks and exactly one runtime
file. The [CI artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43571162963/artifacts/14104948635)
is 4,459,520 bytes, SHA-256
`8e52b517787fb508937611b15eb48855ab0e73521978f579d853cf48d9748585`,
and expires on 2026-12-14 at 07:58:08 UTC.

**This artifact has not replaced the accepted default executable.** The exact
downloaded image exceeded the local DirectX private-working-set limit with
inline images. The successful hosted run uses a smaller Consolas grid and does
not override that failure.

## Downloaded image observations

The 31 inline-image pixel scenes passed on actual GDI, OpenGL and DirectX. The
Sixel lifecycle fixture also passed. The first renderer comparison stopped in
the Frida capture RPC with `access violation accessing 0x0` after OpenGL resize.
A finite unchanged-fixture replay and an API-capture comparison subsequently
passed all 20 scenes per renderer; this does not establish the original RPC
error's cause. The API-capture comparison retains the separate focus injection.

Memory tests used actual 160x48 SarasaTermSC Nerd Font Light terminals, the same
two retained histories and 24 redraw/resize transitions as the local source
build checkpoint. Sampling precedes capture, hover and fault injection. The
following are separate retained runs, not a minimum selected from retries:

| Run | Samples | Peak private WS (bytes) | Outcome |
|---|---:|---:|---|
| GDI baseline | 582 | 16,224,256 | Full fixture passed |
| GDI inline images | 657 | 17,235,968 | Full fixture passed |
| DirectX baseline, initial | 523 | 24,043,520 | Memory passed; later hover preview timed out |
| DirectX baseline, message observation | recorded in manifest | 23,986,176 | Full fixture passed |
| DirectX inline images, message observation | 671 | 25,337,856 | Memory failed; later hover preview also timed out |

The inline-image peak is 337,856 bytes over the unchanged 25,000,000-byte limit;
it occurred at `frame-18` before instrumentation. No working-set trim or limit
change was used. DirectX total working set also remains above the approximate
50 MB target. The earlier local link's 24,907,776-byte passing peak is not a
substitute for this downloaded artifact's measurement.

The failed preview trace contains the fixture's `(96,14)` hover message,
followed by repeated `(137,452)` mouse messages and no preview timer callback.
The later coordinates replace the intended hover target. This identifies a
pointer-model conflict in this run; it does not explain the separate earlier
CI close timeouts. A scoped virtual-pointer fixture and a controlled queued
interference canary are being validated separately. Failed preview runs required
private-job cleanup of five remaining processes; the passing baseline drained
naturally. All forced cleanups remain failures, even when the outer controller
subsequently drained.

The [manifest](iterm-inline-ci-validation.json) retains run identities, CI logs,
the success manifest, exact downloaded-image test results, screenshots, full
memory samples, failure logs, diagnostic fixture and cleanup records. Image
memory optimization, complete local acceptance and default-image promotion
remain unfinished.
