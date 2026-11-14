# Combined Sixel, enclosure and resource-lifetime checkpoint

Local merge `4e4bbc7` combines the Sixel background branch `9f9cdbb`, SGR
enclosure branch `87b7bd5` and menu/resource-observation branch `f2f7dbc`.
The merge is clean. This is an integration candidate, not the accepted download.
The earlier individual branch failures remain in their original records.

The locally linked single executable is 4,511,744 bytes, SHA-256
`3b3358a758c95caac15108202db7778d613c6ac4e9fe70bffd4ddd5525ff0300`.
It uses freshly compiled MSVC frontend libraries and previously validated
OpenConsole host objects. The manifest retains all link input hashes and changed
source hashes; it is not represented as a fresh full-source CI artifact.

## Combined verification

`test_sixel`, `test_sixel_terminal`, `test_sgr`, `test_queries`,
`test_state_control` and `test_rectangle` pass ordinary Linux, ASan/UBSan with
leak detection, and MSVC builds. The generated SGR reply fixture is consistent,
and the resource-timing unit tests pass. The standalone strict C99 decoder test
also passes, including its bounded fuzz workload. Its first compile command
omitted the header include directory; that command/error is retained alongside
the corrected strict compile and run. The other passed tests were not rerun.

All following native checks use the same executable hash, fresh private jobs
and SarasaTermSC Nerd Font Light:

* Eighteen renderer scenes pass in each actual GDI, OpenGL and DirectX backend,
  including framed/encircled text, wide and double-size cells, conceal/inverse
  handling, Sixel and synchronized-frame retention.
* Twenty-two Sixel background scenes and sixteen palette scenes pass in each
  actual backend. These cover implicit register 3, register-0 opaque fill,
  transparent holes, shared/private palette ownership, cancellation and resets.
* All 239 ConPTY reply cases pass: 193 unchanged XTerm references plus 46
  explicit extension cases. Extension cases are not claimed as XTerm behavior.
* The existing Sixel resize/history/partial-scroll and erasure suite passes.
* GDI and DirectX both complete the full nine-group 160x48 tab workload, including
  twelve create/close cycles, menu ownership, renderer transfer and sibling
  lifetime. The bounded resource-return method is documented separately in
  [resource-settle.md](resource-settle.md); numeric allowances are unchanged.

| Full workload | Samples | Private WS peak | Total WS peak | Private commit peak |
| --- | ---: | ---: | ---: | ---: |
| GDI | 540 | 16,523,264 | 43,315,200 | 19,300,352 |
| DirectX | 507 | 23,621,632 | 63,086,592 | 92,676,096 |

All values are bytes. Both private-working-set requirements pass. These are
individual observed peaks, not an attribution of the difference from another
run to a particular feature. DirectX total working set remains above the user's
approximate 50 MB target. Startup and resource-wait samples are included in the
memory maximum; no working-set trimming is used. The full memory sampler stops
before later independent pixel-helper instrumentation.

Each full workload drains all 56 inner / 58 outer processes naturally. Every
other native controller also reports natural completion and no remaining owned
processes. No existing user terminal is attached or controlled.

The [manifest](sixel-enclosure-integration-validation.json) verifies 398 compressed
records (1,195,201 bytes): compiler commands/results, the failed strict command,
native pixels/replies, all memory samples, executable provenance and cleanup.
These are local observations, not REA-server Evidence. Full integration CI and
downloaded-artifact verification remain required before merging to main or
replacing the accepted executable. This checkpoint does not complete physical
IME/multi-monitor, long real-agent sessions, remaining SGR/graphics or exhaustive
xterm compatibility work.
