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
passed. That job then exceeded its 20-minute limit inside the native shutdown
step. GitHub records the job as cancelled and explicitly annotates the timeout;
no finer failure location was retained. It is not a pass.

The [single-image job at ed78f2b](https://github.com/xiongnemo/nemoterm/actions/runs/43420356998)
completed the new selection/attribute colour wire and pixel checks, configured
colour defaults, presentation-state restoration and guarded areas. Its image
SHA-256 is `225af471ec20deadc72373bbc2c2385245cf7580d1fa681d6f32276ebf291231`.
Colour comparisons exercised actual GDI and DirectX; requested OpenGL fell back
to GDI. These are the recorded authored/source-derived cases, not new independent
XTerm captures. Configured-default fixtures are not substitutes for settings UI
save/load acceptance.

The same image passed the two-tab GDI workload at 11,227,136 peak private WS
bytes, but actual DirectX failed at 23,994,368 bytes. Its workflow therefore
failed before the later settings, tab-regression and Codex groups. The candidate
is diagnostic only; no new accepted EXE was published. The DirectX memory gate,
longer lifetime checks and local Sarasa/IME/multiple-monitor acceptance remain
open.

The [manifest](ci-public-recovery-validation.json) binds retained logs and JSON
records to their source commits and individual jobs. Local checks consisted
only of generation, static inspection and compilation/linking.

## In-flight shutdown diagnosis

The development MinGW job remained inside the shutdown fixture beyond its
bounded window/child waits. Frida attachment, script loading, synchronous RPC
and detach have no fixture-level timeout, so the current observation does not
identify whether the terminal or instrumentation is blocked.

The fixture now writes an atomic evidence checkpoint before each stage and
logs observer-installation progress. CI enables Python watchdog stack dumps;
the shutdown fixture has a 120-second CI-only deadline, with a three-minute
step limit in the MinGW workflow. A watchdog expiration is a failure, not a
pass. Private kill-on-close job handles still bound the owned descendants if
the Python controller exits immediately. The partial JSON is uploaded even
when the fixture does not reach normal cleanup. The single-image matrix runs
the same shutdown assertions earlier without dropping any fixture.

Python/JavaScript/PowerShell syntax and preservation of the assertion/fixture
sets were checked statically. The new diagnostics have not been executed
locally and are not yet evidence of a product fix.

## Settings accelerator defect

The [Windows MinGW job at 41a6cc5](https://github.com/xiongnemo/nemoterm/actions/runs/43422849774/job/131876855657)
passed all six instrumented shutdown cases, native renderer/grapheme checks,
session checks and the four tab-bar orientations. This repeat has diagnostic
changes but the same product source as `ed78f2b`; one successful repeat does not
explain the previous shutdown stall.

It then failed while opening the attribute-colour settings page. The test's
missing-selector error was secondary: the retained native dialog text reports
`controls.c:1207`, `!dp->shortcuts[s]`. The new attribute selector used Alt+A,
which belongs to the global About button at startup and Apply during live
reconfiguration. Source inspection found the same conflict on the custom-URI
checkbox. The selector now uses Alt+T and the URI checkbox Alt+R. The shortcut
uniqueness assertion is retained.

The existing settings fixture still verifies attribute control geometry,
save/load, configured queries and live application; it additionally opens the
hyperlink page at startup and during live reconfiguration. MSVC frontend
compilation and source-linked single-image linking pass. The corrected settings
have not been run locally; their remote native acceptance is pending.
