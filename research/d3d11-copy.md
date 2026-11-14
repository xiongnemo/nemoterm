# Direct3D 11 copy-compositor experiments

None of these candidates is accepted. The final bounded diagnostic records
**26,058,752 private-working-set bytes**, still above 25,000,000, and retains a
failed resource-count assertion. Main's production renderer and accepted
`dist/nemoterm.exe` are unchanged. These are local experimental builds, not new
CI artifacts or a replacement for the [99-group checkpoint](relative-cursor.md).

The follow-up [handle lifetime investigation](handle-lifetime.md) attributes six
short-lived tab handles to frontend workers and NVIDIA driver paths, with
observed closes. A persistent Event/IoCompletion pair remains unattributed;
the original resource failures and memory rejection remain in force.

The final prototype is preserved on
[`experiment/d3d11-copy-20261114`](https://github.com/xiongnemo/nemoterm/tree/0382062763ffa8198c72fae155c7bd9c6f4796f6).
Its four exact source variants, build/link records, modified diagnostic fixtures,
raw samples, screenshots and cleanup records are in the
[manifest](d3d11-copy-validation.json). The unfinished settings label, existing
Direct2D-specific fault tests, device recovery and full CI have not been adapted;
this branch must not be treated as production-ready.

## Implementation and hypothesis

The starting source is `e70ddf7`. Each image uses newly compiled MSVC `/MT`
frontend libraries linked against the same retained OpenConsole objects. The
host overlay and entry source are unchanged from their `37ef26d` checkpoint.
The retained linker response files and input hashes identify that reuse. This
is an incremental local build, not a fresh remote source-host rebuild.

The control keeps Direct2D. The candidates dynamically load system `d3d11.dll`
and request a hardware-only D3D11 device, with single-threaded and BGRA support
flags, feature levels 11.0/10.1/10.0. Creation failure retains the frontend's GDI
fallback. Tests require the requested renderer; fallback cannot pass these runs.
No shader compiler or extra runtime distribution file is added by the candidate.
The GPU child class changes to `NemotermDirect3D11` in the copied tab fixtures.

Text still uses the existing GDI rasterizer. Sixel, text strips, cursor overlays,
borders, readback, resize, attachment to another tab and retained presentation
are implemented through the existing renderer interface. The GPU operations
are texture copies, rather than Direct2D bitmap/brush rendering.

| Variant | Upload and retained frame |
| --- | --- |
| Copy | One writable staging texture, mapped for each run; separate retained GPU frame and discard swap chain |
| Dynamic | Changes the upload to a dynamic texture with `WRITE_DISCARD`; otherwise the same copy path |
| Batched | Packs GDI output into the existing bounded DIB and queues up to 512 rectangle copies per staging upload; no additional full CPU frame |
| Sequential | Keeps batching, uses a one-buffer sequential swap chain as the retained frame and removes the separate full GPU texture |

Readback uses 512x64 tiles. The DIB/upload bounds remain 4 MiB and the frame
bound 128 MiB, independent of the much smaller acceptance target. The batch
flushes before presentation, overlay reads and captures. Resize discards pending
old-size content and redraws the frame. None of these bounds accounts for driver
allocation overhead.

Microsoft documents [copy-region behavior](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-copysubresourceregion),
[dynamic resource mapping](https://learn.microsoft.com/en-us/windows/win32/direct3d11/how-to--use-dynamic-resources)
and [single-buffer sequential presentation](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ns-dxgi-dxgi_swap_chain_desc).
The dynamic control follows the API contract but has unacceptable observed
memory usage; API validity does not establish a memory benefit.

## Exact images and pixel checks

| Local image | Bytes | SHA-256 |
| --- | ---: | --- |
| Control | 4,507,136 | `9cad8acac2395ec06945ff55b5f89446d65d48bbd78c60b4b7195ef5f2c81bac` |
| Copy | 4,505,600 | `4cfcafe6af3ba6000b17e52ced5434a155085ddbe33763280af1bf3a147e55c0` |
| Dynamic | 4,505,600 | `bda0eb0bfc75043a82c810a8628ad433379b6e1b5c97222f07049dc1ef6747d8` |
| Batched | 4,507,136 | `db74e009672b39c27a51d070fa07624f09deadc799bf98e9c9cfb5a196d997b3` |
| Sequential | 4,507,136 | `bb73edd96408c84a8e00d6e321ff4f99fc54d894b91fcf5444a72b907760cd3c` |

All four candidates pass the existing GDI/OpenGL/DirectX pixel suite under actual
requested modes, including text styles, Sixel, cursor overlays, cache-eviction
scenes, expose, resize and synchronized output. Each 11-member owned job drains
naturally. These captures use the existing injected GPU readback helper and are
excluded from memory acceptance. The initial copy variant's text screenshot was
also visually inspected. This validates retained pixels, not every physical
display/compositor configuration.

## Unchanged resource assertions and bounded diagnostics

Every workload requests and obtains SarasaTermSC Nerd Font Light at 160x48 with
two retained tabs. History, images, 24 redraw/resize transitions, workload input
and numerical memory/resource limits remain unchanged. No working-set trimming,
global input or target injection is used during memory sampling.

The control completes all nine functional groups, drains its 56 inner and 58
outer job members naturally, then fails the 25 MB memory assertion at
**30,949,376** private bytes (72,130,560 total; 97,095,680 commit), across 253
samples over 27.415 seconds.

Each candidate's first tab run fails the unchanged resource assertion before
the full workload. The copy variant records 556 handles at baseline and 564 at
failure; dynamic records 557 to 565; batched and sequential record 559 to 567.
The allowed increase remains six. Each initial failure requires forced cleanup
of five remaining inner-job processes. The outer controller then sees zero
active processes; that does not make inner cleanup natural. The dynamic arm's
startup-only sampled peak is already **405,295,104 private bytes**, so it is
rejected without another full-workload attempt.

Separate copied diagnostic fixtures retain each violating sample and defer the
same original assertions until after the workload and normal close. They omit
the successful resource-group label when a violation exists, keep
`completed=false`, and mark `memory_acceptance=false`. They enumerate only the
owned frontend's window classes/PIDs/threads at baseline and after each cycle,
with a bounded message-window walk. They install no event hook or target code.
This added observation and deferred failure make them diagnostic fixtures;
their results cannot replace the original failures.

| Diagnostic | Private WS peak | Total WS peak | Private commit peak | Outcome |
| --- | ---: | ---: | ---: | --- |
| Copy | 25,260,032 | 65,003,520 | 104,300,544 | 180-second controller deadline; no final fixture result |
| Batched | 26,525,696 | 66,183,168 | 103,419,904 | 8 functional groups, original deferred resource assertion fails |
| Sequential | 26,058,752 | 65,687,552 | 94,613,504 | 8 functional groups, original deferred resource assertion fails |

The copy diagnostic retains 1,649 samples through a `settled` phase over
179.521 seconds, but lacks a final functional result and natural cleanup. Its
outer job terminates seven remaining members at the deadline. It is incomplete
evidence, not a completed memory acceptance run.

Batched and sequential complete the full workload and all remaining eight tab
groups, then drain 56 inner and 58 outer members naturally. Their traces contain
430 samples over 46.686 seconds and 428 over 46.422 seconds, respectively. Their
memory policy calculation is false; the final memory assertion itself is not
reached because the retained resource assertion fails first. The initial failures
and these later diagnostics are distinct records.

In the two completed diagnostics the owned window sets stay unchanged through
the resource cycles, although handles rise from 559 to 567 and USER objects from
57 to 58. The copy diagnostic also shows counts later falling below its baseline.
These observations do not prove a per-tab leak, identify the additional handle
types, or resolve the production Direct2D failure's different 492-to-549 jump.

The experiments narrow the next work: classify the actual added handles and
account for the remaining private resident pages, rather than relaxing limits
or replacing failures with a passing repeat. The sequential path remains over
budget and slower than the control in these single observations; no statistical
performance conclusion or full compatibility claim is made.

One initial batched build failed because a local type name collided with Win32's
`CopyRect`. The corrected `NemoCopyRect` build completed before any test used that
candidate; the failed log is retained. No stale executable was run after that
compile failure. The manifest retains 337 compressed records with compressed
and decoded hashes, including all failed attempts and modified fixture sources.

The subsequent [internal-threading experiment](d3d11-threading.md) observes
23.65–23.78 MB private working set in full diagnostic workloads, with fewer
frontend threads than its same-session control. Its original resource gate
still fails. The renderer remains experimental and is not promoted by these
memory observations.
