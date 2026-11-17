# ReGIS terminal input integration under development

The development branch now accepts ReGIS through the actual `terminal.c` DCS
state machine. The adapter owns one lazy decoder per terminal, buffers at
most 256 KiB of a complete DCS body and parses it at ST. It handles string
cancellation, resize cancellation, separate main/alternate page banks and
reset/closure cleanup. No ReGIS capability is advertised.

The same 4 MiB image budget counts retained raster images, pending Sixel,
iTerm, Kitty and ReGIS resources. ReGIS reservations include its wrapper,
decoder, page storage, alphabet data, both old and new input buffers during
growth, and 65 KiB for the native font provider and transient DIB pixels.
This is logical resource accounting, not a process working-set measurement:
OS-managed GDI allocations are measured separately by native memory tests.

The Windows callback lazily creates the GDI provider using the profile font
face and weight. Font changes, terminal reset and closure release it. The
unchanged native font test covers 573 Sarasa masks, padding, multiple owners,
lookup failure and recovery, native decoder text and GDI handle lifetime.

## Original failed integration run

[Run 44112460346](https://github.com/xiongnemo/nemoterm/actions/runs/44112460346)
at `c3d263142fdaf5f948ce774c8366a76b329a9a78` compiled GCC, Clang and MSVC,
including the Windows frontend. Component comparisons, ownership, native
fonts, DCS framing, Sixel/Kitty and cancellation regressions passed. The real
terminal replay failed `address-range` and `address-offset` on all compilers.
GCC/Clang ASan identified an out-of-bounds tile-directory access: ReGIS `S(A)`
changed the actual dimensions without resizing the directory allocated for
the initial dimensions. The whole-write comparison failed before the
bytewise command could run; the latter is not recorded as passing.

The terminal fixture also configured a maximum of 8192x8192, whereas the
unchanged upstream reference configured both initial and maximum dimensions
to 160x120. The internal resource setter now specifies both pairs explicitly.
The expected frames, replies and input streams were not changed.

## Storage fix and validation scope

Commit `3a7d6d5` uses a two-level sparse directory covering the configured
maximum range, with rows allocated only when used. Small pages avoid a full
8192-square pointer grid, and address changes retain valid indexing. Uniform
backgrounds retain their extent: newly exposed space stays transparent, and
clearing a smaller extent preserves hidden ink outside it. The added real
terminal checks cover growth, shrink/clear/re-expansion, shared accounting
and return to zero resources after RIS.

The workflow retains the core replay binary, compiler/build logs and binary
hashes; the Windows job also retains the built frontend. Whole-write and
bytewise comparisons are separate steps, so a failure does not suppress the
other transport's evidence. Each compares the original 37-scene / 70-frame
projection against the pinned XTerm reference with independent Xft masks.

[Run 44114538710](https://github.com/xiongnemo/nemoterm/actions/runs/44114538710)
at `3a7d6d5` passes both Linux compiler jobs. The Windows build also compiles,
but artifact collection asks for the old `pterm.exe` filename instead of the
configured `nemoterm.exe`. This keeps the job failed and skips its ordinary
ownership/native-font steps, even though the separately scheduled terminal
replays pass. The CI-only correction is `eb94a48`; the failed run is retained.

[Run 44115314078](https://github.com/xiongnemo/nemoterm/actions/runs/44115314078)
at **`eb94a48130e5b0d1915d5c365d20ea316fd13aea` passes all four jobs**:
independent font capture, GCC, Clang and MSVC. Each compiler passes the
original 70 component frames plus **70 whole-write and 70 bytewise frames
through the real terminal parser**, with zero pixel or reply mismatches.
GCC/Clang use ASan and UBSan. Framing/resource checks, Sixel/Kitty regression
and cancellation (254 streams in each transport and 64 lifetime cycles) pass.
The Windows font check again reports 573 comparisons, zero mismatches,
196 foreground pixels in its native text frame and GDI handles 0 to 0.

The retained core replay executable hashes are:

| Compiler | SHA-256 |
| --- | --- |
| GCC | `85d5b65cf9eb9aa0ebc590c78f625a66fbd0e24aa64d6d33ff3a73b7102f41d0` |
| Clang | `05e11e5a5803707a71017a9d29e8db2cb2434bba011bab51856bc73a570bfeab` |
| MSVC | `ae6961b7d295466c45264739ccf9c0a941662c9ab4cce3166d4d317ce1f74b5d` |

The comparison records' hashes match the binaries retained in the artifacts.
The Windows frontend compile artifact is 3,857,920 bytes, SHA-256
`b60bb29a93d02e7201cdce59640591be1f5d80c20ea95f2e7dfaa84216e97db0`.
This job does not assemble or certify the single-file release package.

[The evidence archive](regis-terminal-input-evidence.zip) retains all three
runs' metadata, original artifact ZIPs, receipts and logs, plus analysis and
a per-entry manifest: **38 entries, 37,333,009 bytes**, SHA-256
`9d09a8582b46c7767bc2b04801ff522f4ae7c13538b70384cc6043cb0c9aa71f`.
Archive entries were read back and verified against that manifest. The
original failed results remain unchanged.

## Remaining work

This checkpoint's replay reads pixels from the decoder, not a terminal window.
Subsequent [image-view integration](regis-image-views.md) connects retained
graphics to the Windows drawing path and adds a 60-scene / 131-frame lifecycle
comparison, which remains failed. Native-window acceptance, partial margins,
scrollback, eviction pressure and scheduling remain open. Twenty-four of the
61 original scenes remain explicit exclusions from this older 37-scene
projection; the newer view gate is separate and does not erase those limits.

Further arithmetic and parser-progress review and wider font/alphabet/curve
coverage are needed. Tektronix remains unimplemented. No new frontend memory
or complete-product acceptance is inferred from these component/core tests,
and `dist` is unchanged. Builds and all runtime checks run only on hosted
GitHub Actions runners.
