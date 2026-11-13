# DEC status reports and ConPTY cursor synchronization

The terminal now handles DEC-specific DSR requests 5, 6, 15, 25, 26, 55, 56,
62, 63, 75 and 85. Extended CPR follows origin mode and both scrolling margins,
and includes page 1 at VT330/VT400-compatible levels. Keyboard reply fields and
device-query availability follow the selected compatibility level. DECSCL 63
and 64 now select distinct VT300 and VT400 masks instead of enabling every
later VT feature. RIS retains these masks, as before and as in the reference.

Replies describe the implementation rather than implying hardware or protocol
support that does not exist:

* An unconfigured printer reports absent (13); a configured printer without an
  open job reports not ready (11). Queries do not open printers or start jobs.
* Downloadable user-defined keys report unavailable (23), following the status
  used by Microsoft's terminal adapter. UDK downloading remains unimplemented.
* DEC Locator reports absent/unknown (53 and 57;0). Ordinary mouse support is
  separate from that protocol.
* Macro space and the checksum of the empty macro store are zero. This does
  not read process memory or implement screen-area checksum requests.
* Data integrity reports ready; DEC multi-session control reports unconfigured.
  Native tabs are separate from DEC's session protocol.

Keyboard identity is the emulated DEC keyboard dialect, not a probe of the
physical Windows layout. Existing configured DA identity strings remain
independent of the operating compatibility mask. DECSCL's complete reset
semantics and 7/8-bit response selection are still open; this change does not
claim full DECSCL conformance.

## Independent evidence

`dec-status-xterm.json` captures 79 cases from pinned XTerm 412 on private Xvfb,
using `-ti vt525`. Every case explicitly selects level 65 with 7-bit replies
before its reset. The reference executable SHA256 is
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
Seventy-seven cases compare exactly in the core and native fixtures. They cover
normal/private requests, parameter boundaries, ignored arguments, malformed
colon input, cancellation, margins, wide and combining text, pending wraps,
double-size rows, alternate screens and levels 61 through 65.

Two deliberate differences retain the original captured replies: xterm reports
UDKs unlocked (20), while Nemoterm reports unavailable (23); an explicitly empty
checksum identifier is zero here rather than xterm's sentinel 65535. Oversized
nonempty identifiers clamp to 65535. Direct checks cover both policies.

The first core run failed because there was no private DSR handler. After the
implementation, the Unicode case exposed an ISO-8859-1 mock setup; selecting
UTF-8 to match the reference/native fixtures resolved that fixture mismatch.
Both failed logs are retained in `dec-status-validation.json`.

## Native failure and host fix

The first local single image, SHA256
`cb4b9fc41962602162a74c9cfb828ae4a3537088d8f2b38478e37af026c2d0f5`, failed
before reaching the new private-query cases. In the ordinary CPR case the
application received the subsequent marker before its cursor reply:
`ESC P 0 $ r ST`, then `ESC [ 1 ; 1 R`.

The pinned host marks its cursor dirty after an unknown output sequence.
`GetConsoleScreenBufferInfo` then sends its own ordinary `CSI 6 n` and consumes
the next ordinary CPR. If an application's earlier CPR is pending, the host
can consume that reply and let its own later reply reach the application. The
fixture's size query and DECSCL output reproduced this ordering failure.

The source overlay now separates the same-image host's synchronization from
application reports. Internal requests use `CSI ? 9001 ; id n`; replies use
`CSI ? 9001 ; id ; row ; column R`. The bounded, nonzero identifier is matched
by the host. These coordinates are absolute within the viewport, including
under origin mode. Late internal replies are consumed without becoming app
input. Ordinary and DEC CPR replies remain application input. This is a
Nemoterm host/frontend extension, not an xterm feature or an authentication
mechanism. The final single image contains both sides of the protocol.

All five changed host files match a fresh complete preparation from pinned
Microsoft Terminal `f6de9e0618015def1c9dda5b82f9d3abf03eb799`. The native test
also uses a version-query barrier that works at VT100 compatibility level;
the prior unknown-DECRQSS marker depends on VT220 support. Reply order is
still checked exactly; no sleeps or reordered comparisons mask the race.

## Final validation

The corrected single image passed 77 native reference cases, direct unavailable
UDK/empty-identifier/stale-internal-reply cases, resize/origin checks and 80
rounds of simultaneous application reports and host cursor synchronization.
Each round checks both exact application bytes and the actual console API's
absolute cursor position. Query-only output leaves captured terminal pixels
unchanged. The owned job drains naturally with zero active processes.

All 35 MSVC core/offscreen suites passed after the final source changes.
Queries, modes and margins passed MinGW. Queries, state controls and margins
passed Linux ASan/UBSan with leak detection. An initial Linux command named the
Windows-only `test_modes` target; it failed before execution and was corrected
to the available state-control suite, without being counted as a test pass.

Thirteen other local native groups passed on the same image: existing queries,
UTF-8 stream reads, Unicode console records, input-method interfaces, mouse,
PowerShell environment, shell selection, delegated console lifetime, single-file
isolation, application resize, Sixel queries, tabulation and double-size rows.
The keyboard group stopped at its clipboard-access step and is not counted as
passed. It was not retried; clipboard and real-agent gates remain mandatory in
CI. Synthetic IME/interface checks do not establish physical IME acceptance.

Image: `build/local-dec-status-sync-check/dist/nemoterm.exe`, 4,419,072 bytes,
SHA256 `ce20294d310095b69354c653a8f7af5460eba43b0525e8fbe93ea46af356786b`.
The validation JSON records source/overlay hashes, initial failures and exact
native reports. The accepted main distribution is unchanged.

The new native DEC group is required by the single-EXE workflow, which builds
the patched host. The legacy portable/sidecar workflow's unmodified upstream
runtime does not include the synchronization fix; it checks the core fixtures
but is not claimed as passing this new integration matrix. GitHub's billing
startup failure remains a separate CI blocker, not a successful cloud result.

References: [pinned xterm controls](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.txt),
[xterm DSR implementation](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/charproc.c),
[Microsoft status replies](https://github.com/microsoft/terminal/blob/f6de9e0618015def1c9dda5b82f9d3abf03eb799/src/terminal/adapter/adaptDispatch.cpp),
[host synchronization](https://github.com/microsoft/terminal/blob/f6de9e0618015def1c9dda5b82f9d3abf03eb799/src/host/screenInfo.cpp).
