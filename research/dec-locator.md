# DEC Locator reference and integration boundary

DEC Locator remains a missing Nemoterm feature. The new independent reference
establishes behavior before implementing its parser, pointer query and native
mouse integration. It is separate from the existing xterm tracking protocols.
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

## Implementation work still required

Add bounded per-terminal locator state, integrate the four CSI commands and
capability/status reports, and share the existing raw-mouse mode arbitration.
The Windows pointer snapshot must query the current position and held buttons,
with cell coordinates and physical pixels measured from their appropriate
origins. A last-mouse-event cache cannot satisfy explicit position requests.
Preserve Shift selection and configured local bindings, including cancellation
of captured gestures and transitions between locator and xterm tracking.

Replay the retained protocol observations through the real terminal parser,
separating upstream frontend bindings from delivered protocol events. Then
verify the actual Windows/ConPTY path, resizing and pointer boundaries in
remote CI. No implementation, native parity or new local Sarasa acceptance is
claimed by the upstream capture alone. This work adds no renderer dependency
and does not resume DX memory optimization.
