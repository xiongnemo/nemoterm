# DirectX 30 MB policy and exact-image hosted replay

On 2026-11-18 Sydney, the user changed the DirectX frontend private-working-set
allowance to **30,000,000 bytes, inclusive**. GDI remains strictly below
20,000,000 bytes, with approximately 50 MB total working set. Optional OpenGL
keeps its exception. The limit follows the actual renderer, including fallback.

The shared Python policy, its boundary tests, the PowerShell counter helper and
current requirement documentation are updated in `f0b76f5`. The hosted
interaction entry now runs the policy boundary tests as well. No production
memory optimization or working-set trimming is part of this change.

## Completed replay

[Run 44100194466](https://github.com/xiongnemo/nemoterm/actions/runs/44100194466)
**passes all six full-grid DirectX workloads**, plus its orchestration and
memory-policy tests. Fixture commit is
`c7d037c0a29e536b79b943909d209332bd219388` on `test/dx-30mb-20261118`.
This fixture branch applies the policy change to the last production-equivalent
tree, without the subsequent unwired ReGIS component. The existing source
comparison gate was not weakened.

The exact product comes from source
`329019d65618bc547f9f52e8b7277f1800341184`, full run `44083541137`:
**4,800,000 bytes**, SHA-256
`b4ed0f124b3e17d165b6c0d31c9a02a083477d556dd34ecbdb37d6d9db3458d7`.
The replay verifies the successful source-host job, unchanged production paths,
manifest, executable size and hash before running. Its fixture checkout is clean.

All six cases use actual DirectX, the actual `SarasaTermSC Nerd Light` font,
and an unclamped **160x48** grid. Memory samples are uninjected and contain no
sampling errors. These are frontend peaks in bytes; host and client records
remain separate in the original evidence.

| Workload | Private WS | Total WS | Private commit |
| --- | ---: | ---: | ---: |
| Text/history | 26,218,496 | 70,189,056 | 28,848,128 |
| Inline PNG | 27,103,232 | 71,966,720 | 30,220,288 |
| Animated GIF | 27,492,352 | 72,634,368 | 30,097,408 |
| Kitty PNG | 27,488,256 | 72,392,704 | 30,359,552 |
| Compressed Kitty | 27,557,888 | 72,421,376 | 30,154,752 |
| Unicode Kitty cells | 29,421,568 | 74,665,984 | 32,657,408 |

The highest private working set is **29.421568 MB / 28.058594 MiB**. Every
record identifies the new 30,000,000-byte inclusive limit and passes it.
Post-memory functional checks complete. Every private job drains naturally:
zero active processes and no forced cleanup after any case.

The original full run remains **21/22 under its recorded 25 MB policy**.
This separate replay closes that memory failure for the same image under the
new user-approved policy; it does not rewrite the original run as 22/22 or
certify the unintegrated ReGIS component. The earlier GDI, single-image,
interaction and DPI results keep their exact identities in the
[full regression record](terminfo-product-regression.md).

## Evidence

[The retained archive](directx-30mb-evidence.zip) contains nine entries: final
run/job/artifact metadata, the complete original memory artifact ZIP and its
receipt, full run logs, the fixture-branch identity, read-only analysis and a
per-file SHA-256 manifest. It is **301,232 bytes**, SHA-256
`83a268498b259bc3ce6341b87e8b2e217ddec877beb54b04ee957b435f2ba397`.

The [original memory artifact](https://github.com/xiongnemo/nemoterm/actions/runs/44100194466/artifacts/14335099876)
is 286,101 bytes, SHA-256
`83dfce615b727c4befdbec5f84f40eb117b06a9f3ef9874ab6cb825ef3a9776a`.
All builds and runtime checks ran on GitHub-hosted runners; local work only
edited source and inspected downloaded records.
