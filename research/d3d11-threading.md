# Direct3D 11 internal-threading experiment

The sequential [copy compositor](d3d11-copy.md) was already above the local
25,000,000-byte private-working-set limit and failed its resource gate. This
experiment changes only its device-creation flags by adding
`D3D11_CREATE_DEVICE_PREVENT_INTERNAL_THREADING_OPTIMIZATIONS`.
Microsoft documents this as a request to the runtime and driver to avoid extra
threads, principally for profiling/debugging; it is not a general performance
recommendation. See the [device flag contract](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_create_device_flag).

The candidate remains an experimental local single image, SHA-256
`f4b7cc47a4278b578b775bb2fdb1d0012b75306bd1bd8580deace9dc12599940`,
4,507,136 bytes. It reuses the previously recorded source-built host objects;
the exact link inputs, patch, compiler log and image identity are retained in
the [manifest](d3d11-threading-validation.json). It adds no distribution file.

The unchanged pixel suite passes under actual GDI, OpenGL and DirectX modes,
including text, Sixel, synchronized output, resize, palette, cursor, eviction
and overline scenes. Its 11-member owned job drains naturally. Those GPU
captures are instrumented and excluded from memory acceptance.

The original candidate workload fails the resource assertion on cycle 10:
540 handles at baseline, 548 at failure, with the allowed increase still six.
Its startup-only peak is 19,197,952 private bytes; it does not reach the full
workload and requires five-member inner cleanup. The outer job then has no
active members. Neither fact makes this a successful acceptance run.

Separate copied diagnostic fixtures retain all violations and defer the same
original assertions until after the unchanged full workload and normal close.
They keep `completed=false` and `memory_acceptance=false`. Each obtains Sarasa
Term SC Nerd Font Light (family `SarasaTermSC Nerd Font Light`) at 160x48,
retains both histories and images, and performs all 24 redraw/resize transitions.
No injection, working-set trimming or global desktop input is used. All three
full diagnostics complete the remaining eight functional groups and drain
56 inner / 58 outer processes naturally, then fail the retained resource assertion.

| Full diagnostic | Private WS peak | Total WS peak | Private commit peak | Settled frontend threads |
| --- | ---: | ---: | ---: | ---: |
| Candidate, first observation | 23,654,400 | 63,111,168 | 86,548,480 | Not collected |
| Same-session sequential control | 25,956,352 | 65,613,824 | 94,248,960 | 32 |
| Same-session candidate repeat | 23,777,280 | 63,299,584 | 86,970,368 | 29 |

The paired diagnostics preserve the frontend thread count from the existing
Toolhelp process snapshot. They add no extra process snapshot or target code;
only the owned process tree's metadata is retained. Thread counts and resident
bytes are not an atomic snapshot. These observations support further study of
the device option; they do not identify which allocation belongs to a thread,
prove a statistical saving or establish acceptable latency on other drivers.

The candidate's memory calculation is below 25 MB in both full observations,
but resource growth remains 540 to 548. The control repeats 559 to 567.
The retained assertions fail before the final memory assertion, and neither
candidate diagnostic is an acceptance pass. The existing unexplained persistent
handle pair and asynchronous handle cleanup remain separate questions.
Renderer recovery, complete integration/CI and final unmodified acceptance are
still open. This experiment is not merged into the product; the accepted local
executable is unchanged. The manifest verifies 133 compressed evidence records.

## I/O shutdown fix follow-up

The independent [pipe-shutdown fix](https://github.com/xiongnemo/nemoterm/blob/ea381ac/research/io-lifetime.md)
was applied to this experimental branch at `ab6e678`. Its seven-case MSVC
lifetime regression passes; the relinked single image is 4,508,160 bytes,
SHA-256 `00f9a30d6a4660efc020cfebef5bddc51146a460ebd0308a15b6ee50cc26fe49`.
The original renderer suite again passes all 16 groups for each actual renderer,
with 11 owned processes exiting naturally.

The original full-grid workload still fails at zero-based cycle 10, with 540
handles at baseline and 548 at failure. Only the experimental child-window class
name is adapted in the copied fixture; its numerical checks, sequencing and
resource samples are unchanged. It stops before the full memory workload and
forces five remaining inner processes. The outer 31-process job then drains.
This does not establish that the earlier growth was caused by the I/O bug.

A separate diagnostic enables the public automation API and reads its counters
only after the original resource comparison has already failed. It retains that
pre-query sample and still executes the original failing assertion afterwards.
Its baseline is 547 handles and pre-query failure is 555. Four subsequent
snapshots, 0.130 through 1.001 seconds later, report two input and two output
contexts, zero closing contexts, 28 creations and 24 destructions. Post-query
OS handle samples remain 551. These observations confirm no retired stream
context remains at the query times, but do not reveal the exact state at the
earlier failing sample or identify the remaining OS handles. Request processing
can change scheduling; this diagnostic is not memory or resource acceptance.
Its five remaining inner processes require cleanup; the outer job drains.

The manifest now verifies 217 records and preserves both original failures and
this follow-up. The experimental renderer remains unmerged and the accepted
local executable remains unchanged.
