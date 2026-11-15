# DEC Locator reference and integration boundary

DEC Locator is implemented on the development branch with passing parser and
mouse-dispatch comparisons and a passing focused Windows/ConPTY check. Complete
product acceptance remains pending. The independent reference establishes the
behavior separately from the existing xterm tracking protocols.
Local interactive testing remains paused; all captures below run on private
Xvfb displays in disposable Linux CI.

## Reference configuration and evidence

The pinned XTerm(412) revision is
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f`. Its
[build option](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/configure.in)
disables DEC Locator by default. The dedicated reference family adds
`--enable-dec-locator`; other reference families retain their existing build
configuration. Generated `xtermcfg.h`, six upstream source files and their
hashes are retained with the executable and fixture identities.

[Run 43711890883](https://github.com/xiongnemo/nemoterm/actions/runs/43711890883)
at `435d428` captures **100 cases and 421 steps**, with three literal controls
for disabled requests, an enabled cell-position request and left-button events.
Each case starts a fresh XTerm, using VT525 identity, an 80×24 grid, a measured
6×13 fixed font and two-pixel padding. XTest changes real pointer/button state
on the owned display; the fixture records those states, actual window geometry,
input bytes and complete replies. Every successful case exits naturally.

The merged capture SHA256 is
`bf0a4fe8b465b67adf4c89c79c2462421301582559e2520f5fe094d253fbe15a`.
`dec-locator-reference.tar.gz` retains 802 records (900,480 bytes), including
both failed harness iterations and this passing capture.
`dec-locator-reference-validation.json` indexes and hashes every record.

The first harness accepted a previous DSR marker before the next reply arrived,
then stalled while a local selection suspended XTerm's PTY processing. The
second counts both markers correctly but still waited between a press and
release after RIS disabled tracking. The passing fixture finishes such owned
gestures before requesting its trailing barrier and rejects late events. The
original failed captures are not replacement expectations for the successful
reference.

## Observed behavior

- `CSI Ps;Pu ' z` enables, disables or requests one report; coordinate units
  can be cells or pixels. Locator and xterm tracking modes share a mutually
  exclusive active mode. Even resetting a different xterm tracking mode can
  disable an active locator.
- `CSI Pm ' {` selects press/release reports. Requests with `CSI Ps ' |`
  obtain the current pointer position and button state, including when no
  recent terminal mouse event exists. Disabled or unavailable requests report
  event zero rather than a stale cached position.
- `CSI top;left;bottom;right ' w` defines a one-shot filter. Reversed bounds,
  omitted coordinates, out-of-window points and immediate outside reports
  have retained observations. A request or reported button event while a
  filter is active can disable locator reporting; leaving the rectangle by
  motion consumes the filter while retaining continuous reporting.
- RIS disables tracking. DECSTR, DECSCL and alternate-screen transitions
  preserve it in this reference. Locator commands also work at DEC levels 1
  and 2, while the locator-status/type queries require level 3 or above.
- Shift takes over locally. Default XTerm Ctrl bindings and wheel-button
  bindings can intercept events before its locator dispatcher. The stored
  observations include that distinction; they must not be treated as a
  blanket protocol rule to discard Ctrl or the fourth button.

The [upstream mouse dispatcher](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/button.c)
and [parser](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/charproc.c)
provide context for these independent observations. The supplementary
[run 43712495322](https://github.com/xiongnemo/nemoterm/actions/runs/43712495322)
at `bbddb98` passes **102 cases, 429 steps and five literal controls**. Named
explicit-binding profiles verify fourth-button and Ctrl+left dispatch with the
unmodified upstream protocol implementation. All 100 earlier input/action/reply
streams remain identical; the extra profiles distinguish protocol behavior
from XTerm's default wheel/menu bindings.

The supplemental capture SHA256 is
`fa3f3f13dd56847c093c8b638f8e658a8227bf29964485c63a07029bcb2fa96e`.
`dec-locator-binding-reference.tar.gz` retains 328 records (304,848 bytes),
indexed by `dec-locator-binding-reference-validation.json`. It includes the
explicit X resources, pointer states, replies, stderr and natural exit records.

## Implementation and component validation

`43f75a4` adds 24 bytes of per-terminal Locator state and an optional synchronous
pointer snapshot callback. It implements the four CSI controls and available /
unavailable status reports, sharing the existing raw-mouse mode group. Query
positions and held buttons come from the OS; event positions come from the
current window message, with button state from that message's input queue.
Pixel coordinates include viewport padding; cell coordinates use the text
origin. No per-cell storage, allocation or renderer dependency is added.

[Run 43713883091](https://github.com/xiongnemo/nemoterm/actions/runs/43713883091)
passes GCC/Clang ASan/UBSan and MSVC. Each compiler compares all **429 unchanged
reply streams** both whole and bytewise, spanning all 102 retained cases.
Four default XTerm frontend interceptions are modeled explicitly in the
projection; the named Ctrl/fourth-button profiles verify actual dispatch.
These are parser/input-dispatch comparisons, not proof of identical physical
event routing on Windows. Direct checks cover unavailable snapshots, reporting
disabled by local policy, and Shift cancelling a reported press before taking
over the selection. Existing cancellation, ANSI, selective-erasure, SGR,
XTGETTCAP, query, state, keyboard, clipboard and image regressions also pass.

`dec-locator-components.tar.gz` retains 85 records (370,102 bytes), including
exact source blobs and all compiler logs. The companion
`dec-locator-component-validation.json` verifies 36 recorded source hashes.

## Native integration checkpoint

The new `locator_window_smoke.py` is restricted to disposable CI desktops. It
checks live queries, physical buttons and their held-state masks, pixel units,
one-shot and filter behavior, Shift selection pixels, resized grids and outside
positions through the bundled host. A focused source-built single-image job
also runs the existing mouse, highlight, state and DEC-status fixtures.

[Run 43714776480](https://github.com/xiongnemo/nemoterm/actions/runs/43714776480)
at `33db228` passes **27 physical-input phases** and all four additional
regression fixtures. The measured initial cells are 9×16 pixels; the resized
grid is 73×28. Left, middle, right and X1 button presses/releases and held-state
queries return their expected masks. Shift sends no Locator events while
changing the GDI selection pixels, and subsequent queries still read the live
pointer. The owned terminal, host and child exit naturally with no forced
cleanup.

The diagnostic single EXE is 4,535,808 bytes, SHA256
`01f22a3c71f43cad0b23d09d5add844903fce86618a9be2599dc32cc6ec85d68`.
Its production and single-image build inputs match component checkpoint
`43f75a4`. `dec-locator-native.tar.gz` retains 40 records (2,919,989 bytes),
indexed by `dec-locator-native-validation.json`, including the image, logs,
observations and exact fixture/source blobs. This first fixture stores its
asserted expected replies plus the final raw snapshot; the subsequent full
product fixture also retains every actual wire including its barriers.

The older DEC-status oracle used an XTerm build without Locator. Its original
reply bytes are retained and its native replay now uses the equivalent disabled
mouse-reporting policy; the new Locator fixture separately checks enabled
status and type reports. DA1 retains the existing configurable terminal identity;
the verified Locator capability queries are DSR 55 and 56. Complete product
validation uses `8e8321c`: ordinary run 43715235781 now passes all four jobs;
single-image run 43715238255 remains in progress. The focused result does not
substitute for complete workflow acceptance.
No local Sarasa or hardware acceptance is renewed, and DX memory optimization
remains stopped.

## Complete ordinary checkpoint

[Run 43715235781](https://github.com/xiongnemo/nemoterm/actions/runs/43715235781)
passes all four jobs at `8e8321c336bac4e6c7c21327f0e4b7b646367043`. Its MinGW
frontend is 3,951,172 bytes, SHA256
`f63ae3051caa9d46598291779eb4140b2a1308038975e7ff6df3fc106e235db7`.
The separate OpenConsole host has verified source revision and overlay hashes.
This checkpoint predates DECUDK and is not the single-image distribution.

All 27 Locator phases retain actual received bytes, including both synchronization
barriers. Offline validation compares them to their expected query/event bytes
and confirms changed Shift-selection pixels and natural process cleanup. The
same package matches 413 ANSI/CAN/SUB streams and three GDI pixel pairs.

All twelve uninjected memory workloads pass their existing limits, with 25,048
post-memory image-cell comparisons. The dense remote Consolas GDI workload
(109x34) peaks at 14,635,008 private / 45,563,904 total working-set bytes; the DX
workload (88x35) peaks at 17,821,696 / 54,378,496. The approximate 50 MB total
target applies only to GDI. These remote grids do not renew local 160x48 Sarasa
acceptance. `dec-locator-ordinary.tar.gz` retains 4,586 records / 9,375,426 bytes,
indexed and hashed by `dec-locator-ordinary-validation.json`.
