# Bell foreground preparation at 029bfac

The [single-image workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43776658192)
failed while preparing foreground focus for the fourth bell-window profile:
DirectX with AlwaysOnTop enabled. It stopped at the initial `focus(other)`
before this profile emitted a bell. The preceding three profiles produced
55 check records. This is a failed complete product checkpoint, not evidence
that all bell checks passed or that the terminal's bell implementation failed.

The original image is retained unchanged, 4,549,120 bytes, SHA-256
`64a493391747c27afd44074a4fea3f3efc21724139baef6d35d13955d0d05f5d`.
`bell-focus-029bfac-failed-single-evidence.zip` and
`bell-focus-029bfac-failed-unverified-product.zip` are original GitHub artifact
ZIPs. The failure manifest verifies their server digests, sizes, member sets
and every expanded member against the original download receipts. The original
workflow log is retained separately. There is no successful single-image
receipt, and the local acceptance controller stopped before launching a product.

The original fixture appended focus actions only after successful return,
so the failing action has no detailed record. Only three profile cleanup
records survived. No claim is made about natural fourth-profile cleanup.
The last successful actions include an accepted SetForegroundWindow followed
by a caption click because the immediate foreground check was still different.
That observation is consistent with asynchronous activation; it does not
identify the exact cause of the failed fourth preparation.

## Queue synchronization and diagnostic scope

[Microsoft documents asynchronous cross-queue activation](https://devblogs.microsoft.com/oldnewthing/20161118-00/?p=94745):
an accepted SetForegroundWindow need not have activated the window at return.
A bounded WM_NULL SendMessageTimeout waits for the target queue before deciding
whether the owned-caption fallback is required. An unresponsive target fails.
[SendInput reports insertion into the input stream](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput),
so the fallback now observes foreground activation and released left button
before restoring its temporary cursor position and topmost state. Its existing
post-restoration foreground assertion is retained. No input queues are joined,
foreground-lock policy changed, or synthetic focus messages sent.

Six deterministic controls model deferred activation, deferred click delivery,
the old ordering as a negative control, an unresponsive target, foreign owner
rejection and an already-focused window. All desktop calls are replaced in
these controls; passing them establishes ordering under the model, not the
cause of the original Windows failure.

The hosted comparison runs the same failed image with legacy and synchronized
preparation, twice each, on separate disposable Windows runners. Both paths
retain failed actions, bounded foreground/PID transitions and error cleanup.
The legacy path preserves the original action order but has additional
observation overhead; it is not timing-identical to the original failed run.
All bell, tab, focus-report, stacking and cleanup assertions are unchanged.
No terminal production code or image is modified.

## Hosted results

[Run 43781694405](https://github.com/xiongnemo/nemoterm/actions/runs/43781694405)
passes all four diagnostic jobs. Every replay preserves the same 74 bell-state
assertions, records 56 successful focus preparations and closes 48 owned
processes naturally. Both actual GDI and DirectX renderers pass, with normal
and topmost windows. The four original artifact ZIPs, workflow log and
`bell-focus-029bfac-hosted-validation.json` retain exact fixture/image identity,
server digests and member hashes.

| Preparation | Repetition | Caption clicks | Accepted but initially not foreground | Native checks |
|---|---:|---:|---:|---:|
| Legacy | 1 | 32 | 32 | 74 |
| Legacy | 2 | 30 | 30 | 74 |
| Synchronized | 1 | 0 | 36 | 74 |
| Synchronized | 2 | 0 | 36 | 74 |

All 72 delayed activations in the synchronized runs complete at the queue
barrier, without fallback input. This establishes a concrete improvement to
foreground preparation. The real caption fallback itself is covered by the
deferred-input model here; these synchronized native runs never needed it.
Neither legacy replay reproduces the original failure, so its exact cause
remains unconfirmed. A successful replay does not turn the failed complete
workflow into a successful checkpoint or explain the unrelated historical
MSVC tab callback crash. Full product CI and exact-image local acceptance
remain separate gates.

A subsequent [forced caption control](bell-caption-control-failure.md) exposes
a native DirectX process exit during window-state changes. Its two failed
runs are retained separately. Queue synchronization's passing direct-activation
path does not close this new failure or certify the real fallback path.
