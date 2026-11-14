# Accepted SGR ideogram CI artifact

Source `8ff214feb549c2b79bb57960467c1d6963eab47e` passed both complete workflows:
[core/compiler tests](https://github.com/xiongnemo/nemoterm/actions/runs/43565551238)
and [single executable](https://github.com/xiongnemo/nemoterm/actions/runs/43565551266).
All four core jobs passed. The single-executable record contains all 108 native
check groups, including the expanded renderer and SGR protocol fixtures.

The [downloaded artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43565551266/artifacts/14103002979)
contains one 4,452,864-byte `nemoterm.exe`, SHA-256
`c110843b1fd5a551d654df094fa716c1ea1c48383d90e642b964d7dfb3d15e26`.
It expires at 2026-12-14T06:43:51Z. Its hash matches the CI validation record.
All local checks below use this exact file, not the earlier development relink.

Twenty renderer scenes pass on each actual GDI, OpenGL and DirectX backend,
including both new ideogram scenes. All 283 protocol cases pass through ConPTY:
193 unchanged XTerm references and 90 explicit extensions. The auxiliary scene,
read-only and resize exercise adds 44 exchanges. This confirms the scope in
the [implementation checkpoint](sgr-ideograms.md), including its stated horizontal
geometry policy; it is not vertical-writing or exhaustive XTerm certification.

Both nine-group tab workloads use SarasaTermSC Nerd Font Light at actual 160x48:

| Renderer | Samples | Private WS peak | Total WS peak | Private commit peak |
| --- | ---: | ---: | ---: | ---: |
| GDI | 521 | 16,093,184 | 42,897,408 | 18,915,328 |
| DirectX | 515 | 23,494,656 | 63,029,248 | 86,257,664 |

Values are bytes. Both private-working-set limits pass; DirectX total remains
above the approximate 50 MB target. These are workload observations, not an
attribution of run-to-run differences to the feature. Startup and resource-wait
samples are included, with unchanged numeric limits and no working-set trimming.
Memory sampling ends before independent pixel-helper instrumentation. Each
workload drains all 56 inner / 58 outer processes naturally.

The strengthened [binding test](bindings-observation.md) from main source
`f2c4be6` was also run against this exact artifact: all five groups pass, with
the two ordered DSR replies and exact clipboard text. That fixture is retained
explicitly because it postdates source `8ff214f`. Renderer, wire and binding jobs
drain 11, 5 and 5 outer processes respectively, with no survivors.

The [manifest](sgr-ideogram-ci-validation.json) verifies 104 compressed records
(1,049,300 bytes): workflow/artifact metadata, exact-image CI validation, native
pixels and replies, all memory samples, the updated binding fixture and cleanup.
These are CI/local observations, not REA-server Evidence. Main's intervening
`57171fa` binding-fixture failure and its correction remain separately recorded.

This is the accepted development artifact. Its product code is unchanged by
the subsequent merge of main's documentation and binding-test correction.
The overall goal remains open, including remaining protocol/graphics support,
physical IME and multi-monitor behavior, long real-agent sessions and total
DirectX working-set optimization.
