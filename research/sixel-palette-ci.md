# Downloaded Sixel palette image checkpoint

Source `e436ecdad1a81e570e409c2bc856d77f4d098c45` passes both full workflows:
[core/build](https://github.com/xiongnemo/nemoterm/actions/runs/43554488252)
and [single executable](https://github.com/xiongnemo/nemoterm/actions/runs/43554488270).
The latter records 105 checks and a directory containing only `nemoterm.exe`.
The [downloaded artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43554488270/artifacts/14097908470)
expires on 2026-12-14 at 04:26:17 UTC. Its exact EXE is 4,451,328 bytes,
SHA-256 `aa11c5398c102feef624764dda1a09ba96afadc33151358166c02e1eaf998bba`.
The downloaded bytes match the CI validation manifest.

This version adds the [register identity/shared lifetime fix](sixel-palette.md)
to the previously integrated renderer, automation and lifecycle corrections.
It does not include the independent Sixel implicit-background or SGR enclosure
branches. Complete protocol compatibility remains open.

## Native artifact verification

Fresh local owned jobs run the downloaded bytes. All 16 palette scenarios pass
for each actual renderer ID 0 (GDI), 1 (OpenGL) and 2 (DirectX), using the public
automation interface and real ConPTY output. Captures, sent bytes, DSR replies,
color positions/counts and cleanup are retained. No injection, global input,
clipboard access or existing-terminal attachment is used by this fixture.
Each palette job exits naturally: three inner and five outer processes.

CI's GDI and DirectX palette runs also report their requested renderers, but its
OpenGL request falls back to GDI. CI success therefore does not establish
OpenGL rendering; the separate local actual-OpenGL run supplies that coverage.

The unchanged full tab workload verifies SarasaTermSC Nerd Font Light and
actual 160x48 grids. Both modes pass nine functional groups and all original
memory/resource limits. Each closes 56 inner / 58 outer processes naturally.

| Frontend peak, decimal bytes | GDI | DirectX |
| --- | ---: | ---: |
| Private working set | 16,568,320 | 22,818,816 |
| Total working set | 43,401,216 | 58,470,400 |
| Private commit | 19,677,184 | 85,254,144 |
| Samples | 478 | 455 |

Memory sampling precedes pixel-helper injection. There is no working-set trim,
raised threshold or instrumentation-based memory acceptance. These observations
meet the GDI <20 MB and DX <=25 MB private-working-set targets. DX total working
set remains above the approximate 50 MB target. Differences from previous
observations are not established performance improvements.

Earlier late-initialization/USER-resource failures remain unresolved; a passing
artifact run does not erase those failures or establish long-session behavior.
Startup and automation's earlier exact-image local evidence remains identified
as `9c22311` in [its checkpoint](d3d11-ci.md), rather than being reassigned to
these new bytes. CI covers the current full suite.

The [manifest](sixel-palette-ci-validation.json) retains CI run/artifact metadata,
the 105-check validation, palette coverage, downloaded-image identity and
original local samples/captures/cleanup. Each archive's decompressed length
and SHA-256 is checked. These are local/API/CI records, not REA-server Evidence.
