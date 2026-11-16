# Exact single-image local checkpoint

The single EXE from successful run 43796089119 (source `f3b5b65`) passes six
local groups on 2026-11-16: startup size, command-line profile, dense GDI
Unicode/Kitty tabs, special keys, extended keys and legacy modifiers. Its
4,549,120-byte image has SHA-256
`de2f9e105e9186cb99fd925f8824e0573ae144ff62954b63ab3cda7c15ff0d28`.

The OS font mapper resolves `SarasaTermSC Nerd Font Light` and a native Chinese
glyph. The normal startup is 160 x 48 with 8 x 20 cells; the oversized-font
control reduces the grid to 117 x 24 within the 1920 x 1040 work area.

The actual 160 x 48, two-tab GDI dense-image workload records frontend peaks of
19,947,520 bytes private working set, 47,030,272 total working set and
23,318,528 private commit. The strict 20,000,000-byte private-working-set gate
passes with only 52,480 bytes of headroom. This finite result does not establish
an arbitrary-workload bound. There is no sampler error, injection or working-set
trimming during sampling. The later 29,072 image-cell checks and all ten tab
checks pass, including inactive previews, synchronized rendering, fullscreen,
resize and close. All 56 owned processes exit naturally. Special/extended/legacy
input tests retain their source reference records; the legacy replay passes
2,704 exact streams and 112 separately counted startup equivalence checks.

## Interrupted foreground acceptance

A fresh interaction stage planned eight existing native desktop/clipboard
groups and isolated Codex 0.167.0/OpenCode 1.19.3 image-paste checks. Three test
fixtures were extended to honor the explicitly requested test font; their exact
overrides are archived, and the product image was unchanged.

The first `input-byte` group exited during foreground preparation, before
input assertions: `No exposed owned caption`. The recorded foreground PID
28984 was independently identified as `Windows Default Lock Screen`. The
desktop had been unlocked when local testing started, but was locked by the
time foreground acceptance began. The remaining nine groups did not run.
The test left no Nemoterm processes running. This is not a passed input test
or evidence of a terminal input defect. Retain the failure and use a fresh
stage after the desktop is available.

The Computer Use tool separately failed three connection attempts, including
a session reset, with `Computer Use native pipe is unavailable` / error 2.
Physical mouse/keyboard, live IME candidate selection and physical DPI testing
therefore remain unverified. The native fixture suite cannot stand in for them.

`d3d11-local-f3b5b65.zip` retains 64 records: controllers, executable/fixture
identity, logs, font records, observations and per-case receipts, including the
failed foreground attempt. `d3d11-local-f3b5b65-validation.json` records archive
and member hashes, checked after compression. Complete ordinary and single-EXE
CI remain documented in [the renderer fix](d3d11-discarded-reservations.md).
This is a development checkpoint; final interaction acceptance and the separate
historical MSVC tab-selection failure remain open.
