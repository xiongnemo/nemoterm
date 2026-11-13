# OpenGL context failure cleanup

Source review on 2026-11-13 found a cleanup defect in `nemo_gl.c`:
`nemo_gl_free` called `nemo_gl_clear_cache`, but the latter returned immediately
when `wglMakeCurrent` failed. The cache's CPU `strbuf` keys were then abandoned
when the renderer was freed. Destruction also proceeded with GL deletion calls
even though the context had not been made current. Preview readback ignored
the binding result, and tab attachment reported success after cache invalidation
had marked the renderer failed.

The patch:

- Releases every CPU cache key and clears cache accounting regardless of whether
  the context can be bound, including partial initialization without a context.
- Deletes GL textures/framebuffers only after a successful context binding.
  When binding fails, context destruction owns the remaining GL resource cleanup.
- Preserves the failed state, reports failed attachment, and returns before
  preview readback or GL error queries on a known-failed renderer.
- Adds no renderer fields, allocations, runtime dependencies or per-cell storage.

Microsoft's [wglMakeCurrent contract](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-wglmakecurrent)
states that a failed call leaves the calling thread without a current context.
The [wglDeleteContext contract](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-wgldeletecontext)
allows destruction when the context is not current on another thread.
Nemoterm owns these contexts on its UI thread. This finding does not establish
deletion from an unrelated current context, and does not explain the earlier
GDI tab-close access violation described in
[the renderer follow-up](cluster-renderer-followup.md).

## Prepared regression checks

`tests/test_gl_lifetime.c` compiles the real implementation with injected WGL/GL,
parenting and preview-copy functions. Its cases cover full 256-entry cache
destruction, binding success/failure combinations, repeated invalidation,
partial initialization, failed and successful preview readback, and tab
attachment failures. Assertions count every CPU key release exactly once,
reject GL operations without the owned context, check texture deletion and
context destruction order, and retain failure state across attempted recovery.
No real window, driver context, clipboard or global input is used by the cases.

The target is included in both MSVC and MinGW CI and in `scripts/test.ps1`.
CI logs retain the mock test output separately from hardware/native evidence.
Real GPU device failure, tab preview pixels and long-lived resource behavior
still require native verification.

## Build-only validation

Local runtime testing remains paused at the user's request. No product or test
executable was run for this patch, including the mocked checks. MSVC frontend
and mock test compilation, MinGW mock test compilation, and the source-linked
single EXE build passed. The initial test link missed the console
`modalfatalbox` implementation; the fixture now provides it, and the failed
attempt is retained alongside the successful build logs.

The candidate is kept under `build/local-gl-lifetime-unverified/dist/`.
The accepted main `dist/nemoterm.exe` was not replaced.
Exact hashes and commands are recorded in
[the build manifest](opengl-context-build-validation.json).
Compilation is not runtime acceptance; existing memory and lifecycle gates
remain open.
