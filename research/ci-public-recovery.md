# CI recovery after making the repository public

The repository became public at the user's request on 2026-11-13. Newly
dispatched jobs now start on runners. The prior zero-step billing rejections
do not describe these runs. Local product, mock-test and native-window
execution remain paused; validation below ran on GitHub-hosted machines.

## Public main artifact

Main commit `992faa37f53ba5583e343eff66ca82150db0a1e8` updates the README without
changing the previously accepted product source. Its
[single-image workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43418162604)
passed all 57 recorded groups, including the isolated image, native protocols,
tab regressions, settings and Codex fixtures. The
[downloadable artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43418162604/artifacts/14032799615)
contains only `nemoterm.exe`: 4,371,456 bytes, SHA-256
`252598a446ca5bb1555765bc7c959061889ebb05af70ea7286e67d3be00901e5`.
The downloaded file matches the test manifest. The local accepted EXE was not
replaced.

Main's separate MinGW/sidecar comparison job did **not** pass: in
[run 43418162840](https://github.com/xiongnemo/nemoterm/actions/runs/43418162840),
`tabs_profiles_window_smoke.py` timed out waiting 15 seconds for host close.
The same profile fixture completed in the source-linked single-image job.
This is an unresolved difference, not evidence that the timeout is harmless.

## Development build and fixture corrections

The first public development run at `356af21` exposed two portability failures:

- Windows Python used cp1252 for a generated UTF-8 fixture. The generators now
  specify UTF-8 on reads and writes. CI treats omitted-encoding warnings as
  errors in the generator step; all 16 check-mode generators passed locally.
- The packed X11 colour names formed a 7,614-byte concatenated string literal,
  exceeding the ISO C99 minimum required support under GCC's strict warning
  settings. The generator now emits character initializers. The packed data
  remains byte-for-byte identical, including its final sentinel: 7,615 bytes,
  SHA-256 `92e4964b1f632e255f01802a24540bfe6fd44def2430c701ef9521d9500fce9e`.
  Colour offsets, values and storage size are unchanged. Strict GCC compilation
  with `-Wall -Wextra -Werror -pedantic` passed without relaxing flags.

After these corrections, runtime checks exposed mistakes in the new colour
painting fixtures. They permitted drawing before `term_size`, when the grid
still used `-1` sentinels; used positional `pos` initializers as x/y although
the structure is y/x; and treated the invalidatable `disptext` cache as the
retained visible frame. Rapid DECSCNM on/off also starts a visual-bell timer,
which the no-timing fixture never expired.

The fixtures now wait for a valid grid, use designated coordinates, retain
actual draw callback attributes/colours, and advance the existing deterministic
test clock through the flash. Freeze assertions begin after DECSET 2026 has
flushed the preceding frame. The colour expectations and frozen-frame checks
remain in place; no product behaviour was changed to satisfy these failures.

## Verified development results

At `ed78f2b782ffd8d55c184f4957e1e88a9ba2f2af`, the complete
[Linux ASan/UBSan job](https://github.com/xiongnemo/nemoterm/actions/runs/43420357001/job/131868507166)
passed. This includes the 782-name X11 parser vectors, Unicode's 853 grapheme
vectors, terminal grapheme/image/history/input checks, state control, protected
erasure, rectangles, queries, titles, and the OSC colour suite. The newly
executed authored subsets include 30 selection-colour cases, 39 attribute-colour
cases, 44 cursor/charset cases and 63 guarded-area cases, with their associated
core rendering/state checks. Authored cases are not independent XTerm captures.

The [MSVC diagnostic job at 356af21](https://github.com/xiongnemo/nemoterm/actions/runs/43418418330/job/131862017842)
and its [repeat at ed78f2b](https://github.com/xiongnemo/nemoterm/actions/runs/43420357001/job/131868507503)
passed the mocked OpenGL context cleanup target, cluster rendering, pixel
comparisons, eight complete tab-close repetitions per job and hyperlink checks.
All eight tab runs requested OpenGL but actually used GDI; renderer comparisons
also exercised DirectX. These results do not verify hardware OpenGL behavior
or resolve the older GDI access violation. No application-error events were
recorded by that job.

The Windows MinGW core suite and grapheme/cluster checks at `ed78f2b` also
passed. Its native shutdown step and the single-image workflows are still
running at this checkpoint; the overall Windows job is not a pass. Native
verification of the newer colour,
charset and guarded-area changes, the DirectX memory gate, longer lifetime
checks and local Sarasa/IME/multiple-monitor acceptance remain open.

The [manifest](ci-public-recovery-validation.json) binds retained logs and JSON
records to their source commits and individual jobs. Local checks consisted
only of generation, static inspection and compilation/linking.
