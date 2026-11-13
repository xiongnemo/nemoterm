# Native CI fixture recovery and development checkpoint

Recorded 2026-11-14 (Australia/Sydney). Local runtime testing remains paused.
All runtime observations below came from GitHub-hosted Windows jobs. The local
accepted executable was not replaced. The [manifest](ci-fixture-validation.json)
binds the retained original JSON files and log excerpt to their jobs and images.

## Development single-image result

The [single-image run at d4dfb30](https://github.com/xiongnemo/nemoterm/actions/runs/43426865236)
completed its functional fixtures before failing the final DirectX workload
memory gate. The diagnostic artifact is **not an accepted distribution**.
Its downloaded EXE is 4,436,992 bytes, SHA-256
`bb2a9acf9e934645d7c4990a6dbbfe70e492a4e80da55282e3afe255e7a3d138`;
this matches the native records retained under `ci-fixture-evidence/single-d4dfb30`.

The passing checks include:

* Attribute colours: 70 wire cases and eight pixel checks in GDI and actual
  DirectX; the configured GDI variant has 32 wire cases and nine pixel checks.
  Requested OpenGL fell back to GDI on this runner, so that variant does not
  establish hardware OpenGL behaviour.
* ISO guarded areas: 76 recorded wire phases and 11 pixel captures, including
  protected text/Sixel, erase, synchronized presentation and 1,000 state cycles.
  These are authored/source expectations, not a new independent XTerm capture.
* Standalone and tab-host settings: five attribute-colour query phases each,
  saved configuration, live reconfiguration, and startup/live hyperlink pages.
* All four tab-bar positions and the tab regression matrix, including overflow,
  mixed profiles, geometry, resize, input-method fixtures and selection.
* Four pinned real Codex client fixtures: standalone/tab-host and default/inline
  UI, with local response fixtures, Unicode input, resize and exact copy/paste.
  These are bounded hosted-runner scenarios, not physical IME or arbitrary
  long-running agent acceptance.

The workload sampler ran before pixel instrumentation, without working-set
trimming. The font was Consolas. Host and client processes remain separate
from the frontend gate; summing process working sets can double-count shared pages.

| Renderer | Frontend private WS peak | Frontend total WS peak | Samples / duration | Result |
| --- | ---: | ---: | --- | --- |
| GDI | 11,530,240 bytes | 42,917,888 bytes | 317 / 32.609 s | Pass |
| Actual DirectX | 23,580,672 bytes | 63,578,112 bytes | 227 / 23.594 s | Fail |

The DirectX fixture completed its nine functional groups before the memory
assertion. Its limit remains **20,000,000 bytes**. Neither that gate nor the
process-count assertions were relaxed. The single-image workload validates
same-image host accounting; the corrected sidecar classifier still needs a
completed native sidecar workload, because that job failed earlier.

## Rectangle mailbox read

The [main comparison repeat](https://github.com/xiongnemo/nemoterm/actions/runs/43427249103)
failed at `rectangle_window_smoke.py` while recording resized dimensions:
`KeyError: 'columns'`. Each phase already waited for a matching reply snapshot,
but discarded it and later performed an unchecked mailbox read. The mailbox
reader can return `{}` during replacement/read contention.

Commit `34ca37b` retains the acknowledged snapshot, requires positive dimensions,
and uses that same object for the resize record. All existing pixel, clipboard,
geometry and memory assertions remain intact. Static syntax and assertion
preservation checks passed; remote validation is tracked separately in the manifest.

## Startup caret observer lifetime

The [single-image run at 41a6cc5](https://github.com/xiongnemo/nemoterm/actions/runs/43422849935)
hit the 45-minute job deadline. Repeated Python stack dumps locate the controller
inside `frida.Session.detach` in the caret fixture's `finally` block. The original
fixture wrote evidence only after that block, so this does **not** establish
whether an earlier assertion had failed or whether the terminal itself stalled.

Commit `7f7166e` detaches the startup/focus observer while the frontend is still
alive, then requests normal shutdown. Frida attach/load/RPC/detach operations
use a 15-second cancellable scope. Atomic stage records and a 120-second CI
watchdog preserve failure evidence; expiration remains a failure. Cleanup still
drains only the fixture's private job. Existing assertions remain, with added
checks that the frontend exits successfully. The separate shutdown observer
continues to cover destruction ordering.

## Sidecar protocol mismatch remains open

The [d4dfb30 MinGW comparison](https://github.com/xiongnemo/nemoterm/actions/runs/43426865243)
passed 58 guarded-area wire cases, then timed out in `pending-wrap-K`. Its final
snapshot contains the expected two cursor reports separated by the identity
barrier, rather than both reports preceding it. The raw snapshot is retained;
the byte-order assertion has not been weakened or bypassed.

The source-linked single-image run passed this same case. That contrast is
consistent with different console-host handling but is not a complete causal
trace of the sidecar mismatch. Do not call the entire comparison CI green.

DirectX allocation ownership, historical close stalls, physical IME/multi-monitor
behaviour, the requested local Sarasa workload and the remaining protocol ledger
are still open. This checkpoint does not complete the terminal goal.
