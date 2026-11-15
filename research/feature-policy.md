# XTerm feature-policy query reference

OSC 60 (XTQALLOWED), 61 (XTQDISALLOWED) and 62 (XTQALLOWABLE) are implemented
on the development branch. The reference below was captured before the handler
was written. This checkpoint does not change the accepted executable or the
rendering/memory targets. The user resumed local testing on 2026-11-16.

[Reference run 43727943696](https://github.com/xiongnemo/nemoterm/actions/runs/43727943696)
at fixture `1a77a76efff0f95408085f700bce983be69ee6ae` passes on unmodified
XTerm(412), commit `5c75ead9a75d4b2e666ca06fa94503b5766ed93f`. Each of 20 resource
profiles has 105 authored requests, yielding **2,100 original reply streams**.
All 20 XTerm/child pairs exit naturally with zero status and no stderr.
Three literal controls confirm the empty category list, all seven categories,
and an unknown subcategory table. A private Xvfb display has no TCP listener.

`feature-policy-reference.tar.gz` retains 85 records / 426,909 bytes, indexed by
`feature-policy-reference-validation.json`. It includes original per-profile
captures, input and reply bytes with barriers, compiler configuration, upstream
source files/hashes, fixture source, run metadata and artifact provenance. The
raw aggregate SHA256 is
`84990aadc68e758f926f703f279ceb52d039ed94f96d307465e46b6ac3b4e865`.
The retainer verifies every barrier, identical inputs across profiles, natural
cleanup, fixture identity and archive records without rewriting any reply.

## Observed contract

The [official control-sequence specification](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
defines category and subcategory queries. The actual capture additionally shows:

* OSC 60 accepts a missing or empty payload. An extra `?` or other nonempty
  payload is ignored. With no enabled categories, its reply has no semicolon.
* OSC 61 reads configured restriction lists, even when the corresponding master
  category is currently enabled. It is not a flattened list of every operation
  currently denied by the terminal. Changing a category's master boolean alone
  leaves its restriction report unchanged.
* OSC 62 lists compiled subcategory names in table order, independently of
  category enablement and the configured restriction list. Its window table
  differs in ordering from the numeric restriction table reported by OSC 61.
* `allowWinOps` aliases `allowWindowOps`. Names are case-insensitive, but leading
  and trailing spaces are not stripped. Unknown nonempty names produce an empty
  OSC 61/62 response; absent/empty payloads produce no response.
* XTerm reports `allowTitleOps` in OSC 60, but has no corresponding OSC 61/62
  subcategory table. This source-specific asymmetry remains in the raw capture.
* BEL/ST response endings follow the request. Eight-bit output produces C1 OSC
  and ST bytes. Malformed input, cancellation, reset, alternate screens and
  return from VT52 are recorded separately, including no-reply outcomes.

Default XTerm permits colour, font, mouse, termcap and title categories; paste
controls and the window master override are off. Its default window restrictions
include title reads, X properties, selection access and checksums. Explicit
all-on/all-off, one-enabled/one-disabled and custom/empty restriction profiles
distinguish these booleans from the restriction tables.

## Implementation boundary

Nemoterm already has mouse, paste-control, title, window-size, clipboard and
checksum settings, but these do not reproduce XTerm's entire resource model.
The implementation must distinguish a supported operation, a master permission,
and a configured restriction. It must not advertise X properties, font switching,
termcap mutation or other unimplemented operations as available merely to copy
an upstream response. Preserve the complete upstream capture and name any
platform differences in the eventual component/native replay.

## Native policy mapping

Nemoterm has independent permissions rather than XTerm's master overrides.
OSC 60 therefore lists a category when all its supported operations are allowed;
OSC 61 reports current local restrictions; OSC 62 lists supported operations.
Queries never change these permissions. The snapshot is derived at query time,
uses fixed stack buffers, and adds no persistent per-terminal or per-cell state.

* Colour operations and XTGETTCAP are available. OSC font switching/querying,
  XTSETTCAP, X properties, fullscreen XTWINOPS and status-line operations are not
  advertised. Optional frontend callbacks determine Locator and window support.
* Disabling mouse reports restricts tracking and focus reporting. Coordinate
  encoding selection and alternate-screen wheel-to-key conversion remain
  available, matching their existing behavior.
* With paste controls disabled, C0 bytes except BS, HT, LF and CR are restricted.
  DEL remains allowed; no STTY filter is advertised. Existing newline conversion
  and bracketed-paste terminator filtering remain independent of this report.
* Remote resize, title writes, title reads, OSC 52 read/write and checksum gates
  remain independent. TITLE_EMPTY is reported as restricted title disclosure,
  even though a query still returns an empty title. Primary selection/cut buffers
  are supported without a system clipboard callback.
* Like the reference, the title category has no OSC 61/62 subcategory table.

## Validation boundaries

`generate-feature-policy-reference.py` projects **1,780 unchanged single-query
reply streams** from the 2,100-stream archive. Its 20 policy fixtures are authored
from the pinned upstream operation enums, default resources and explicit profile
inputs, not inferred from expected replies. `test_feature_policy` checks exact
bytes, unchanged permissions, exact-size writes and undersized-buffer rejection.

Separately authored native-policy parser cases cover 36 requests both whole and
bytewise, framing, invalid UTF-8, embedded NUL, cancellation, overflow, reset,
alternate screens and VT52 return. Actual resize, title, focus, paste, checksum
flags and cut-buffer operations are checked across reconfiguration and independent
read/write permissions. These pass locally with MinGW, along with OSC 52, query,
mouse and capability/keyboard regressions. The first local failure log is retained:
independent fixtures initially inherited the previous VT52 compatibility level;
they now explicitly establish their VT525 baseline, because RIS preserves that
selection.

One parser difference is explicit: an ESC inside an unfinished OSC can begin
another sequence in the existing PuTTY-derived parser. XTerm's captured
`escape-restart` case emits no reply, while Nemo answers the second OSC 60.
The raw upstream result remains unchanged; the native case names this difference.
This change does not claim complete parser equivalence or implement missing
underlying operations.

`feature_policy_window_smoke.py` adds 72 native ConPTY cases across three isolated
profiles, without physical input or system clipboard access. It and the
GCC/Clang sanitizer/MSVC checks are wired into CI; their results are pending.
Full product and local 160x48 Sarasa acceptance remain separate gates.
