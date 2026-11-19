# Protocol coverage and remaining gaps

Fresh shared Sixel/ReGIS colours, including private, RIS and DECSTR controls: the [pinned XTerm and presented GDI comparison](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/shared-bank-start.md) improves from 2/7 to 7/7 on the `6bed777` candidate. This covers first-use colour registers, not the remaining historical ReGIS presentation differences.

## Windows preview `42232a2d`

For `TERM=xterm` and `TERM=xterm-256color`, the [hosted application captures](../research/xterm-clients-42232a2d.zip) cover real Vim, Vim under tmux, and the separate colour and Sixel checks on this executable. The [scrollback and selection captures](../research/scrollback-modes.md) verify independent output/key scrolling and preservation of the visible rectangular highlight as history fills, plus 46 checks of highlight geometry, clipboard contents and child input when a TUI scrolls part of its screen. The earlier [wide-glyph margin report](../research/column-edge-integrity.md) pairs actual GDI/DirectX selection and clipboard observations with the three cells that still differ from XTerm 412. [ReGIS presentation differences](../research/regis-presented-pairs.md) are tracked separately. The [current preview and interaction results](../README.md#下载) identify the downloadable file; older checkpoints below apply only to the builds named.

## Current verification policy (2026-11-17)

All automated builds and tests run on GitHub-hosted runners. The
[remote migration checkpoint](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/remote-test-migration.md) at `2312edd`
passes 19/19 jobs, including 169 single-image groups, 26 interaction cases and
24 real bilingual DPI cases. Later full-grid Sarasa checks expose failures
that the earlier screen-clamped grids did not cover; see the
[full-grid record](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/full-grid-memory-ci.md).

Candidate `6247818` passes all six full-grid GDI workloads, but its full run is
19/21 because DirectX exceeds 25 MB and Git Bash sometimes survives closure.
The [closed-console correction](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/closed-console-connections.md) at
`8084338` passes 24 hosted Git Bash lifetimes and six native closure controls;
its complete aggregate is 21/22, with only full-grid DirectX memory failing.
All 169 single-image groups, the MinGW suite, 26 interactions, 24 DPI cases and
six full-grid GDI workloads pass; see the [final regression](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/closed-console-regression.md).
The later [Terminfo product](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/terminfo-product-regression.md) at
`329019d` also completes 21/22: 170 single-image groups, the complete MinGW
suite, 26 interactions, 24 bilingual DPI cases and six full-grid GDI workloads
pass; only the then-current DirectX memory gate fails. The user subsequently
raised DirectX's limit to 30 MB; the same image passes all six workloads in
[replay 44100194466](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/directx-30mb.md), with a 29.42 MB peak.
These finite checks do not turn
the partial or missing protocol families below into complete xterm support.

The dated product checkpoints below retain their original scope. Statements
about pending local acceptance or permission to use the development desktop
are historical; they do not override the remote-only policy above.

## Earlier product checkpoints

This is an audited inventory of the current development sources, not a claim
of complete xterm compatibility. The accepted `dist/nemoterm.exe` on `main`
has an older source identity; consult the artifact records in `research/`.

The accepted product is source `752f3be`, with all four ordinary CI jobs,
143 single-image groups and 39 local groups passing. Its
[exact-product record](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/kitty-query-transaction-product.md) identifies
the executable hash and ten uninjected Sarasa 160x48 two-tab workloads. Frontend
private working-set peaks are 17.32 MB for GDI and 24.11 MB for DirectX; DirectX's
59.69 MB total working set is recorded separately. The user has accepted current
DX memory and clarified that the approximate 50 MB total target is for GDI. Earlier
resource, shutdown and access-violation failures remain recorded; later passes
do not establish their causes.

The later `8655aae` development MSVC job has a separate
[tab-selection access violation](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/tab-select-msvc-8655aae.md).
The exact failed image passes six local and twelve hosted diagnostic replays,
but the cause remains unconfirmed. New keyboard checks do not resolve it.
An additional [controlled probe comparison](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/tab-probe-lifetime-8655aae.md)
passes six local and six hosted lifetimes, comparing three unload timings with
read-only code snapshots. It captures asynchronous cleanup but no crash or
different outcome between variants; the original failure remains open.

The `029bfac` keyboard development checkpoint has a separate
[single-image CI failure during bell focus preparation](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/bell-focus-029bfac.md).
Four exact-image diagnostic replays pass 74 checks each, and synchronized
preparation avoids unnecessary caption clicks. The original failure was not
reproduced. This is not a successful complete-product checkpoint; the updated
harness still requires full CI and exact-image local acceptance.

The subsequent [DirectX strip-reservation fix](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/d3d11-discarded-reservations.md)
passes both complete workflows at the exact product source `f3b5b65`: all four
ordinary jobs and 167 single-image checks. Its generated single EXE remains a
development candidate. The densest hosted GDI Unicode/Kitty workload peaks at
14,065,664 bytes private and 44,990,464 bytes total working set for the frontend.
The distinct MSVC tab-selection access violation above and exact-image local
acceptance remain open; main's accepted image is unchanged.

The development branch adds Kitty relative placements and Unicode placeholders.
The lazy cell index passes all three component compilers and ordinary full CI at
`f01927a`, including twelve memory groups and 25,048 post-memory cell-centre
checks. The single-image run at `fd0c253` fails a mixed-profile close timeout;
twelve exact-image replays pass without explaining it. See the
[dense-image record](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/unicode-dense-memory.md) and
[profile failure record](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/unicode-single-profile-close.md).
The later [single-image checkpoint at `056fe87`](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/kitty-unicode-ci.md)
passes all 154 groups, twelve memory workloads and 25,048 post-memory pixel
checks with the same production source as the green ordinary CI. This does not
explain the earlier intermittent failure.
The [pointer-shape checkpoint](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/pointer-shapes.md#complete-single-image-checkpoint)
also passes complete ordinary CI and all 154 single-image groups, including
twelve memory workloads. Its first external PowerShell parser timeout remains
unexplained after exact-image replays and the complete retry pass.
The user resumed local native testing. The latest portable
[display-cache correction](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/gdi-image-cache.md) completes the local
160x48 Sarasa dense-image workload at 18.48 MB private / 39.97 MB total WS,
with 29,072 image cells and ten lifecycle checks passing. It also passes 185
native pixel stages, including actual OpenGL/DirectX and presented GDI captures.
Both full workflows for this correction pass, with 160 single-image groups.
Exact combined-product local acceptance is separate and remains in progress; the local
clipboard preflight is denied before any selection assertion. The accepted
distribution is unchanged.

Reference: [official xterm control sequences](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
(page identifies patch 411); independent captures use the pinned
[XTerm 412 source](https://github.com/ThomasDickey/xterm-snapshots/tree/5c75ead9a75d4b2e666ca06fa94503b5766ed93f).
Modern extensions are tracked separately below. Xterm itself has optional,
platform-specific and build-dependent functions.

Status vocabulary:

* **Tested**: concrete assertions exist for the listed behavior. This does not
  imply every parameter combination or real application has been verified.
* **Partial**: an implementation and tests exist, with an explicit limitation.
* **Gated**: a local setting controls the operation. Protocol unit tests are
  distinct from permission and native integration acceptance.
* **Source only**: a handler exists, but this audit has not established adequate
  behavioral evidence.
* **Missing**: no implementation was found in the current dispatch path.

Test names below refer to `vendor/putty-0.85/test/test_<name>.c` unless noted.
The main parser is `vendor/putty-0.85/terminal/terminal.c`; modern helpers are
`terminal/nemo_*.c`. The inventory is organized by wire function, not by the
number of passing executables. Unlisted private extensions remain **unverified**.

## Controls and character sets

| Wire function | Status | Evidence or limitation |
| --- | --- | --- |
| C0 BEL | Partial; sound and renderer-surface checks | Sound/disabled/visual policy, OSC terminator distinction and bounded overload accounting pass core tests. The user confirmed audible output for the identified `69cd5a4` image; its actual GDI/OpenGL/DirectX surfaces also show the flash and restoration. That listening observation does not certify later image hashes. Physical desktop flash, custom WAV and PC-speaker modes remain unverified. See [bell evidence](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/font-zoom-and-bell.md). |
| C0 BS, CR, LF, VT, FF | Tested | `margins`, `terminal`; BS follows explicit reverse-wrap modes 45/1045, with physical-cell counting and pending-wrap cases. Default BS stays on the current line. |
| C0 HT; ESC H (HTS) | Tested | `state_control`, 108 tabulation oracle comparisons and native ConPTY replies. |
| C0 ENQ | Partial; native comparison and configuration checks | [Legacy enquiry audit](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/legacy-replies.md): 38 exact XTerm/native cases with explicit empty/ASCII answerback settings, including reset, C1 framing, CSI/OSC context and VT52. [Configuration recovery](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/answerback-config.md) fixes unsupported caret escapes and adds 160 native direct comparisons for literal/control/numeric/empty settings, including NUL. Unicode configuration and complete syntax coverage remain unverified; this is not full product acceptance. |
| C0 SI/SO | Partial | G0/G1 bank selection is covered by presentation-state reports; full ISO 2022 combinations remain unverified. |
| C0 CAN/SUB/ESC cancellation | Partial; development | [CAN/SUB](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/control-cancellation.md): 254 unchanged XTerm streams match GCC/Clang sanitizers and MSVC whole/bytewise, with 64 payload lifetime cycles. SUB displays the byte/UTF-8 error character, including pending single shifts and wrapping. The 236-stream UTF-8-transportable native projection and three GDI pixel pairs pass both complete workflows at the documented source-equivalent checkpoints. Broader ESC recovery, older hardware identities and complete state coverage remain open; local acceptance is unchanged. |
| ESC D/E/M (IND/NEL/RI) | Tested | `margins`, including partial horizontal scroll regions. |
| ESC 7/8 (DECSC/DECRC) | Partial | `state_control` covers cursor/rendition/alternate-screen state. All supported G0–G3 designations and both GL/GR selectors have 44 independently matched XTerm cases plus native four-bank pixel restoration; see [cursor charset checkpoint](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/cursor-charset-save.md). The supported charset repertoire remains limited. |
| ESC = / ESC > | Tested | `modes`, `keyboard`, application/numeric keypad state. |
| ESC Z (DECID) | Partial; native comparison | [Legacy enquiry audit](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/legacy-replies.md): 64 DECID/DA alias observations across two profiles plus two exact VT52 replies. Numeric capability identities are product-specific; complete terminal-identity coverage remains open. |
| ESC c (RIS) | Tested | `state_control`, `grapheme_terminal`, `sixel_terminal`. |
| ESC #3/#4/#5/#6 | Partial | Output, cursor movement, pending wraps, wide/combining text and cluster growth checked; see `double-size-lines.md`. The three tabulation failures are fixed. Row-size-specific editing/resize combinations remain open. |
| ESC #8 (DECALN) | Partial | [State/image fix](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/alignment-reset.md): 13 exact XTerm query cases, direct RGB policy, cell/selection/history assertions and 12 native pixel checks per renderer. Both full CI workflows and downloaded-image actual GDI/OpenGL/DirectX checks pass. Current RGB keeps valid encoding instead of XTerm's packed-index report after reset. |
| ESC ( / ) / * / + and ESC - / . / / | Partial | Development [parser integration](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/iso2022-parser.md) adds mapped national/DEC/ISO sets and 94/96 designations. [Input/native follow-up](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/iso2022-input.md) and [UPSS](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/iso2022-upss.md) add independent paste and actual GDI/OpenGL/DirectX pixel checks. The broader lower-level output matrix remains open. Accepted EXE unchanged. |
| ESC % G / ESC % @, DEC mode 42 | Partial | Development DOCS override/cache and NRC decoding match the isolated state matrix. Encoding is global across cursor/alternate saves. NRC paste conversion and the temporary UTF-8 keyboard shortcut are covered by the [input checkpoint](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/iso2022-input.md); all encoding combinations remain open. |
| ESC N/O (SS2/SS3), ESC n/o and GR locking shifts | Partial | Extended bank invocation passes the real-parser Unicode-cell and transition matrix. Native SS2 pixels match directly printed Unicode on three actual renderers. The [legacy checksum matrix](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/iso2022-checksums.md) matches 172 mapping streams and 33,024 cell sums, with four explicit lifecycle differences; it is not an all-level/all-encoding proof. |
| ESC SP F/G (S7C1T/S8C1T) | Tested | Selectable generated reply/key framing; 141 exact XTerm streams, two native code-page variants, reset/level lifetimes. See [C1 transmission](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/c1-controls.md). Input-parser conformance remains separate. |
| ESC SP L/M/N (ANSI conformance levels) | Partial; development | [ANSI conformance](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/ansi-conformance.md): one byte of terminal state gates extended locking shifts while preserving pending SS2/SS3 and invoked banks. GCC/Clang sanitizers and MSVC match all 243 unchanged XTerm streams whole and bytewise after the SUB fix. Resets, alternate screens, DEC levels and VT52 return are covered. The 177-stream native projection passes both complete workflows in the [cancellation checkpoint](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/control-cancellation.md). Local acceptance remains pending. |
| ESC 6/9 (DECBI/DECFI) | Tested | `margins`, native `horizontal`: VT420 gate, inside/outside margins, edge scrolling and pending wrap. Text, full cell payloads, shell marks and Sixel pixels move together. |
| ESC V/W (SPA/EPA) | Tested | ISO guarded writes, ordinary/DEC erasure, queries, reset and family transitions: 63 independent XTerm matches, core assertions and single-image native text/Sixel pixels. See [guarded areas](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/guarded-areas.md) for the upstream sidecar limitation. Legacy raw C1 dispatch retains the configured codepage policy. |
| Raw C1 bytes and UTF-8 encoded C1 | Partial | Existing codepage-sensitive parser; exhaustive byte/state conformance is still open. Do not assume UTF-8 text is reprocessed as controls. |
| SOS/PM and other APC strings | Partial | String consumption/recovery; Kitty APC G has its own implemented handler and is listed below. Other application payloads remain unimplemented. |

## CSI cursor, editing, status and window functions

| Wire function | Status | Evidence or limitation |
| --- | --- | --- |
| A/B/C/D (CUU/CUD/CUF/CUB) | Tested | `margins`, `terminal`; origin and scroll-region boundaries. CUB shares reverse-wrap handling with BS, including bounded large counts and extended cycles. |
| E/F (CNL/CPL) | Partial | Cursor-report streams match the 848-sequence [movement audit](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/cursor-movement-audit.md), including origin/margins/defaults and pending wrap. Full pixel/scrolling/resize behavior remains unverified. |
| G and backtick (CHA/HPA); d (VPA); H/f (CUP/HVP) | Tested | `margins`, `queries`, origin-relative positioning. |
| a/e (HPR/VPR) | Partial | The [correction](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/relative-cursor.md) matches all 848 independent XTerm streams, fixing the audit's 47 differences. Separate origin clipping, bounded logical double-row columns, tiny-grid sanitizer assertions and native pixels pass both complete CI workflows and downloaded-image actual GDI/OpenGL/DirectX checks. |
| I/Z (CHT/CBT) | Tested | `state_control`, defaults/counts, custom stops, margins and pending wrap; native oracle replay. |
| g, parameters 0/3 (TBC) | Tested | Tabulation oracle, including extra parameters using the first value. |
| ?W, parameters default/0/5 (DECST8C) | Tested | Tabulation oracle; VT510 compatibility capability required. |
| @/P (ICH/DCH) | Partial | `margins`, `rectangle`, `reflow`; [held selection and 728 upstream cell observations](../research/selection-column-edits.md). One DCH margin case retains `V` where XTerm 412 reports a space; [72 additional rows distinguish complete glyphs from literal upstream checksum parity](../research/column-edge-integrity.md). |
| L/M (IL/DL) | Tested | `margins`, `sixel_terminal`, partial-region lifetimes. |
| J/K/X (ED/EL/ECH) | Tested | `terminal`, `selective_erase`, `rectangle` and Sixel checks; ISO protection is covered by the 63-case guarded-area reference matrix and single-image native erasure/pixel checks. |
| J parameter 3 (saved-line erase) | Gated | Local remote-clear-scrollback setting; active screen is separate. |
| ?J/?K (DECSED/DECSEL) | Tested | Protected text/image checks include shared ISO family, empty whole-display retirement and wrap/drawn-span handling in the guarded-area core and single-image native fixtures. |
| S/T (SU/SD) | Tested | `margins`, `sixel_terminal`; T also has mouse highlight syntax. Pending wrap is preserved, independently checked by XTerm and native cell/cursor replies. |
| ^ (SD alias), SP @ / SP A (SL/SR) | Partial | `margins`, native `horizontal`: counts, margins, outside-region behavior, wide/double-size rows, origin and pending wrap. See [horizontal editing](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/horizontal-editing.md) and the [SL wide-row difference](../research/column-edge-integrity.md). |
| ' } / ' ~ (DECIC/DECDC) | Partial | VT420 column insertion/deletion over vertical margins from the cursor column. Full cell lifetimes and bounded Sixel views are checked separately from the 198-case XTerm matrix; [the DECDC wide-row difference](../research/column-edge-integrity.md) remains. |
| b (REP) | Tested | `terminal`, `grapheme_terminal`; bounded repeats and optional whole clusters. |
| r (DECSTBM); s with mode 69 (DECSLRM) | Tested | `margins`, independent xterm oracle. |
| s/u without mode 69 | Tested | `state_control`; ANSI cursor save/restore aliases, including the supported-bank cache in the 44-case independent charset matrix and native restoration checks. |
| !p (DECSTR) | Tested | `state_control`, soft reset retention and mode reset semantics. |
| $p / ?$p (DECRQM) | Tested | `modes`; reports implemented state, local restrictions and unknown modes. |
| ?s / ?r (XTSAVE/XTRESTORE) | Partial | `state_control`, `margins`; bounded explicit list of supported private modes, not arbitrary modes. |
| SP q (DECSCUSR) | Tested | `queries`, cursor shape and blink readback. |
| c / >c / =c (DA/DA2/DA3) | Tested | `queries`, `identity-queries.md`; compatibility identity is not a feature-completeness claim. |
| >q (XTVERSION) | Tested | `queries`; reports Nemoterm/PuTTY lineage. |
| n parameters 5/6 (DSR/CPR) | Tested | `queries`, `margins`, tabulation oracle. |
| ?n (DEC-specific DSR, including extended CPR) | Tested including UDK status update | `queries`, native `dec_status`: 5/6/15/25/26/55/56/62/63/75/85, level-dependent report formats, origin/margins/resize and explicit unavailable devices. Enabled Locator status/type pass the [Locator native checkpoint](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/dec-locator.md). The [UDK development implementation](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/dec-udk.md) now reports unlocked and passes the original query in core and native replay; macros remain missing. See `dec-status.md`. |
| ?9001;id n (Nemoterm internal cursor synchronization) | Tested | Same-image host transaction IDs and viewport-absolute coordinates; separate from application CPR and Win32 input mode 9001. Native ordering, stale replies and console-API positions are checked. |
| x (DECREQTPARM) | Partial; syntax replay and explicit policy differences | [Legacy parameter audit and fix](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/legacy-replies.md): 136 retained VT100 streams replayed whole/bytewise and through native ConPTY at input CP 28591/65001; ten previously ignored colon streams now follow the reference's default-request treatment. Inherited baud codes `112`, model-independent replies and level-5 S8C1T differ explicitly from the VT100 reference. Final single-image acceptance and complete identity parity remain open. |
| "p (DECSCL) | Partial | Levels 61–65, soft-reset effects, Pc control selection and DECRQSS `"p` use the [C1 reference capture](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/c1-controls.md). PuTTY extensions remain; exhaustive reset/charset interactions remain open. |
| "q (DECSCA) | Tested | `selective_erase` checks independence from SGR resets. ISO/DEC transitions and the family-sensitive DECRQSS response pass the guarded-area reference/core/native matrix. |
| $z / ${ (DECERA/DECSERA) | Tested | `selective_erase` rectangles, with ISO/combined-family distinctions covered by the guarded-area reference/core/native matrix. |
| $x / $v (DECFRA/DECCRA) | Tested | `rectangle`, fill/copy, overlap, wide/combining characters and page handling. |
| $r / $t / *x (DECCARA/DECRARA/DECSACE) | Tested | `rectangle`, stream/rectangle attribute extent. |
| *y (DECRQCRA); #y (XTCHECKSUM) | Gated / Partial | Off by default; `queries` and native `checksum`: 364 exact XTerm cases, 8 retained-cell expectations, attributes/blank modes/origin/resize/reset. Unicode normalization and legacy charSeen differences are explicit; see [checksum record](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/rectangle-checksums.md). |
| $w (DECRQPSR); DCS 1/2 $t (DECRSPS) | Partial | Cursor/tab reports and replay: 142 exact XTerm cases and 10 direct cases in `queries` and native `presentation_state`. Bounded streaming tab restoration, offscreen stops, valid-prefix cursor restoration and protection-family semantics. Charset restoration is limited to the supported banks/sets; see [presentation-state record](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/presentation-state.md). |
| "v (DECRQDE) | Tested | Active rows/columns, single page, operating-level gate, origin-independent and resized native reports. |
| $u (terminal state request) | Missing | Complete terminal-state serialization/restoration is separate from presentation-state reports. |
| #\| (XTREPORTSGR), #{ / #} and #p / #q (SGR stack) | Tested | `queries`, native `sgr_stack`: 193 exact XTerm captures and 14 modern-underline expectations. Ten retained frames, bounded overflow, selective attributes/colors, origin-relative intersections, reset/alternate-screen retention and read-only queries. Six XTerm cases ignore modern underline styles and are documented separately; see [SGR stack record](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/sgr-stack.md). |
| #P/#Q/#R (palette stack) | Tested | Ten lazy snapshots of the implemented indexed/default palette; indexed access, zero/omitted arguments, high-water reports, reset/alternate-screen retention, invalidation and synchronized pixels. See [palette stacks](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/palette-stacks.md); unsupported OSC color namespaces remain separate. |
| #S (title-stack position query) | Tested | Logical depth and ten retained slots; fixes the former depth clamp. The combined palette/title oracle has 101 exact XTerm cases through core and all three native renderers. |
| t, operations 1–9, 11, 13–16, 18–23 and line count >=24 | Partial | `queries`, `titles`, `window_resize`; native movement, size and title policies apply. Other window operations remain missing. |
| t, operation 10 (`FullscreenWin`) | Development | Enter, leave and toggle native fullscreen on the active resizable Windows terminal. `suite=fullscreen` compares the real monitor, frame and restored placement in both host modes. [Original failure and replay](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/xtwinops-fullscreen.md). |
| >t / >T (title modes) | Tested | `titles`, independent raw-byte title-mode oracle. |
| *\| / $\| (DECSNLS/DECSCPP) | Gated | `queries`, `window_resize`; remote resizing setting and monitor work-area clamp. |
| i / ?i (media copy) | Source only | Configured printer start/stop subset; not a full screen-to-printer implementation. |
| DEC locator 'w/'z/'{/'\| controls | Core, native and full CI checkpoints pass | [Independent DEC Locator comparison](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/dec-locator.md): 102 fresh-XTerm cases and 429 unchanged reply streams pass GCC/Clang sanitizers and MSVC, whole and bytewise. Four default frontend interceptions are explicit. A source-built single image passes 27 actual Windows/ConPTY phases, including live pointer/button queries, Shift selection pixels and resize. Complete ordinary and 156-group single-image checkpoints pass; local acceptance remains paused. |

## Rendition, modes, input and graphics

| Wire function | Status | Evidence or limitation |
| --- | --- | --- |
| SGR 0,1,2,3,4,5,7,8,9,21–25,27–29 | Tested | `sgr`, `queries`; bold/dim/italic/underline/blink/inverse/conceal/strike and resets. |
| SGR 4:0–5; 58/59 | Tested | Underline styles/colours and reset, native pixels and query round trips. |
| SGR 30–37/40–47/90–97/100–107/39/49 | Tested | Indexed/default foreground/background and configuration policy. |
| SGR 38/48/58, indexed or RGB, semicolon/colon forms | Tested | `sgr`, `queries`; supported forms and malformed input recovery. |
| SGR 53/55 (overline) | Tested | ECMA-48 state/reset/query, history/reflow and native GDI/OpenGL/DirectX pixels; both complete CI workflows pass. Selective SGR-stack selector 53 is a Nemoterm extension. See [overline](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/overline.md); RTF export does not encode the style. |
| SGR 51/52/54 (framed/encircled) | Tested | Independent text/style replies and native pixels on all three actual renderers; font/window geometry, history and reset checks. The [enclosure checkpoint](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/sgr-enclosure-ci.md) retains its original separate resource failure. These attributes are included in the later accepted product. |
| SGR 60–65 (ideogram decorations) | Partial | Five decorations and independent reset use existing cell storage. Twenty renderer scenes per actual backend and 283 protocol cases pass in the [accepted ideogram checkpoint](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/sgr-ideogram-ci.md). Horizontal geometry is an explicit project policy, not vertical-writing or full XTerm pixel parity. |
| SGR font-selection attributes | Missing | Legacy SCO font controls do not satisfy the full font-selection family. |
| ANSI modes 4/12/20/34 | Tested | `modes`, `state_control`; insertion, echo, newline and legacy cursor mode. |
| DEC modes 1/2/3/5/6/7/8/12/25/66 | Partial | `modes`, `state_control`; corresponding legacy behavior and configuration gates. Full VT52 and 80/132 transition coverage remains open. |
| DEC modes 47/1047/1048/1049 | Tested | Alternate screen and cursor state, `state_control`, `margins`, `grapheme_terminal`. |
| DEC mode 69 | Tested | Horizontal margin state and edits, `margins`. |
| DEC modes 45/1045 | Tested | Normal/extended reverse wrap: 567 exact XTerm cases, 13 direct boundary cases, private save/restore, reset, alternate-screen state, pending wrap, wide/double-size cells and margin scrolling. Cursor stays in the viewport where ten reference cases leave it; see [reverse-wrap record](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/reverse-wrap.md). |
| DEC modes 9/1000/1001/1002/1003 | Tested | X10, press/release, highlight, button/all motion; `mouse`, `highlight`, native HWND fixtures. |
| DEC modes 1005/1006/1015/1016 | Tested | UTF-8/SGR/urxvt/pixel mouse encodings and bounded coordinates. |
| DEC modes 1004/1007 | Tested | Focus reports and alternate-screen wheel behavior. |
| DEC private modes 1010/1011 (rxvt scroll on output / keypress) | Implemented on the development branch | Independent set, reset, query, save and restore. The initial values come from the profile; changing a mode affects only the running terminal. [Original XTerm 412 replies](../testdata/upstream/xterm412-scrollback-modes.zip) and [Windows preview before implementation](../research/scrollback-modes-before-b3274ed.zip). |
| DEC mode 2004 | Gated | Bracketed paste framing and local settings are tested. Native clipboard and real-client checks are retained in [input validation](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/automation-input.md) and full CI; physical gestures, all applications and sustained sessions remain separate. |
| DEC private modes 2004/2006 (bracket framing / literal paste LF) | Verified on `476a2c76` | [Actual XTerm clipboard bytes](../testdata/upstream/xterm412-paste-lines.zip) and [Windows `ReadConsoleW` results](../research/paste-lines-476a2c76.zip) agree in all 68 comparisons. Includes native CRLF and standalone LF, empty lines, multibyte characters, physical Enter after paste, independent mode restore, alternate screen, DECSTR and RIS. Does not implement quote-each-byte mode 2005. |
| DEC modes 80/1070/8452 | Tested | Sixel display/palette/cursor-scroll behavior, `sixel_terminal`. |
| DEC modes 2026/2027 | Partial | Synchronized frames and opt-in grapheme widths tested; see `sync`, `grapheme_terminal`, `graphemes.md`. Color-font/emoji policy and long workloads remain open. |
| DEC mode 9001 | Gated | Windows input records, `win32_input`, user setting and native fixture. |
| DEC 1042/1043 bell attention and raising | Development; both complete CI workflows passed | Independent 112-case/192-step XTerm capture and full three-compiler component regressions pass. Separate defaults and save/restore are implemented. Corrected native replay preserves every reply and passes actual focus/Z-order and final topmost checks. All 38 GDI/DirectX state checks pass, including minimized windows, multiple notifying tabs, closure and real reactivation with exact focus reports. Complete ordinary CI and the production-equivalent 159-group single image pass; visible taskbar and local acceptance remain open. [Scope and platform policies](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/bell-modes.md). |
| Other unlisted DEC modes | Missing | Unimplemented modes continue to return unknown to DECRQM. |
| >m/>n/?m; >f/?g/>g (modified-key resources) | Partial | Resources 1/2/4: `mok` replays 394 unchanged cursor/function observations whole and bytewise; 378 owned-HWND/ConPTY streams pass. Sixteen local shortcut combinations remain core-only. [Resources 3/6/7](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/extended-key-resources.md) additionally pass 283 core steps whole/bytewise, 243 Windows mapper steps and 235 native streams. [Resource 0 and legacy/VT220 profiles](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/legacy-modifiers.md) now pass 2,704 native streams and 112 startup-equivalence checks, with independent XTerm references and three-compiler regressions. Reset/numeric-policy differences and unmapped hardware observations are retained separately. Complete single-image CI stopped later in bell focus preparation; physical-keyboard and exact-product acceptance remain open. |
| ?u/=u/>u/<u (kitty keyboard flags/stack) | Tested | `keyboard`, progressive flags and stack; platform-specific physical-layout coverage remains open. |
| DCS $q ... ST (DECRQSS) | Partial | `queries`: m, r, s, *x, "p, "q, SP q, $\|, *\|, >4m, >4f and title modes; unknown requests fail explicitly. |
| DCS Ps !u Pt ST; CSI &u (DECAUPSS / DECRQUPSS) | Partial | Development [UPSS checkpoint](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/iso2022-upss.md): 112 independent streams, 5,376 output cells and 28 selection captures; reset, DOCS and saved-cursor state; actual three-renderer pixels and ConPTY transport. Full checkpoint CI and complete encoding/malformed-input combinations remain open. |
| DCS +q ... ST (XTGETTCAP) | Partial | `tcap`; named colour/identity/key and rendition whitelist. `smul/rmul`, `sitm/ritm`, `smxx/rmxx`, `Smol/Rmol`, plus `us/ue/ZH/ZR` aliases. `Smulx`/`Setulc` programs pass independent ncurses expansion, both complete workflows at `37ef26d`, and local discovery/state replay using that exact downloaded image. Requests remain bounded to 2,047 bytes; replies have a 22 KiB ceiling. Not arbitrary terminfo access; `Su` and `Setulc1` remain unknown. These protocol checks do not resolve the separately retained DX acceptance failures. See [underline query evidence](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/underline-capabilities.md). |
| DCS Ps;Pl \| key/hex;... ST (DECUDK) | Development; both complete CI workflows passed | [91 independent XTerm cases / 238 steps](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/dec-udk.md), including physical F1-F20 input, binary payloads, reset/cancellation and keyboard-profile differences. GCC/Clang sanitizers and MSVC match every reply whole and bytewise; input/aggregate budgets and lazy storage checked. 89 physical-key cases / 232 native streams pass within all four ordinary CI jobs and the later [159-group bell single image](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/bell-modes.md). Two raw byte cases remain core-only; local acceptance is pending. |
| DCS +p ... ST (XTSETTCAP) | Tested in bounded scope | Optional Terminfo keyboard backed by the immutable pinned ncurses database, independent SetTcap/GetTcap gates (set off/get on by default), bounded 31-byte name, profile startup-name persistence and shared key/query lookup. Production API passes 622,172 combinations; component replay passes 2,180 individual queries and 1,378 startup steps, with 45 explicit startup-TN policy comparisons. Exact single and MinGW images at `329019d` each pass 1,293 native streams with zero mismatches. All four permissions, 24 bilingual DPI cases and six full-grid GDI workloads pass within the completed 21/22 aggregate; DirectX memory remains failed. See [exact identities and original failures](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/terminfo-database.md). This does not implement arbitrary terminal-state restoration or copy the upstream setter lifetime bug. |
| DCS ... q ... ST (Sixel) | Tested | `sixel`, `sixel_terminal`, native render/scroll/erase/font-resize cases. Resource bounds are part of the implementation. |
| CSI ? Pi ; Pa ; Pv S (XTSMGRAPHICS) | Tested | `queries`, `sixel`, `sixel_terminal`, native `graphics_query`: register count read/reset/set/max (2–256), current/max geometry, explicit invalid-item/action/failure replies. Geometry is read-only; 8192 per-axis limit remains subject to the shared 4 MiB raster budget. See `graphics-query.md`. [ReGIS item 3](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-discovery.md) reads the configured page independently of Sixel/window geometry; its reset, set and read-maximum actions report status 3, as on the ReGIS-enabled reference. |
| ReGIS | Partial | The [native ReGIS component](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-native-component.md) passes its 37-scene / 70-frame projection on three compilers. [Live image views](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-image-views.md) and shared palettes are connected. The unchanged 60-scene / 131-frame historical comparison has [five remaining frame differences](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-six-frames.md) after the page-remap and scroll-origin fixes. The [first native checkpoint](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-native-window.md) passed 30 steps; the [screen and margin fixes](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-screen-edges.md) passed 37, [saved-line clearing](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-history-clear.md) brought that to 49, and [window-height and temporary-history tests](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-resize.md) passed all 59 on actual GDI, DirectX and directly presented GDI. Requested OpenGL fell back to GDI. [Bounded history](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/regis-history-limit.md) adds 12 checks of retained and evicted pixels in the native window. The historical frame differences remain open. |
| Tektronix 4014 | Missing | No product emulation. |
| APC G (kitty graphics) | Partial; runtime implemented | The accepted `752f3be` supports direct RGB/RGBA/PNG, `o=z` compression, chunks, feature/image queries, placement/deletion, crop/scale, transparency and layered rendering. [Product validation](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/kitty-query-transaction-product.md) covers actual GDI/OpenGL/DirectX and separate presented GDI pixels. The development branch adds [relative/Unicode placements](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/kitty-unicode-placeholders.md), with 238 relative and 728 Unicode states and bounded lazy indexing; new exact-product local acceptance remains open. File/shared-memory transport and Kitty animation remain missing. |
| OSC 1337 inline images: File / MultipartFile / FilePart / FileEnd | Partial; accepted runtime subset | PNG/JPEG/BMP and animated GIF use streaming transport, Windows WIC and the shared bounded raster lifetime. The accepted image passes 32 static and 36 animation stages on each actual GDI/OpenGL/DirectX backend, separate presented GDI stages and 160x48 memory workloads. File downloading and full iTerm parity remain open. See [product validation](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/kitty-query-transaction-product.md). |
| OSC 1337 Capabilities / ReportCellSize | Tested; remote CI | Live preference-aware feature codes and current DPI-scaled cell size. The ambiguous focus/file `F` and uncertified `Uw` codes are omitted; no `TERM_FEATURES` environment publication. Both full workflows pass at `5b2e6f1`, including 13 capability cases and 42 native geometry phases at 96 DPI; local native testing is paused. See [report policy and validation](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/iterm-capability-reports.md). |

## OSC and modern shell metadata

| Wire function | Status | Evidence or limitation |
| --- | --- | --- |
| OSC 0/1/2/21 | Gated | `titles`, bounded title/icon strings, encoding modes and local title policies. |
| OSC 4 / 104 | Tested | `osc_colour`, indexed palette set/query/reset; multiple pairs and malformed data. The [25-case reset/reverse capture](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/reset-palette.md) and native pixels cover RIS/DECSTR restoration and saved-palette retention. |
| OSC 4/5 chained colour rejection | Core, local native and complete CI passed | [64 unchanged independent streams](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/osc-colour-sequences.md) pass whole and bytewise on GCC/Clang sanitizers and MSVC, and through local native ConPTY. Invalid specifications stop the current indexed/attribute command without undoing earlier effects; dynamic colours retain separate continuation semantics. Eight Xlib accepted-prefix syntax differences are retained separately. At 31747b9 all four ordinary CI jobs and 164 single-image groups pass; local full-product acceptance remains separate. |
| OSC 10/11/12 and 110/111/112 | Tested | Default foreground/background/cursor colours and resets, including reversed foreground/background roles and stateful cursor following in the reset/reverse capture. |
| OSC colour names: pinned Xorg table | Tested | [782 X11 names](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/x11-colours.md), including exact space aliases and numbered shades. Extended parser/protocol tests pass remotely; independent XTerm matches 1,574 name/case/rejection observations in 66 batches using separate setters and queries. Malformed combined-command recovery is distinct. Numeric `rgb:`/`#` semantics are unchanged; Xcms device-profile forms remain unsupported. |
| OSC 17/19, 117/119 | Partial | Selection foreground/background set/query/reset, palette stacks, display overlays and [saved defaults](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-settings.md). Independent capture matches 30 cases and retains 11 resource observations; core, native GDI/DirectX and settings checks pass remotely. Full XTerm highlight-resource pixel parity and actual OpenGL pixels remain open. See [selection colours](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/selection-colours.md). |
| OSC 5/6, 105/106 and OSC 4/104 aliases 256–260 | Partial | [Attribute colours](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/attribute-colours.md): special colours, modes, overlays, palette retention and [saved defaults/style settings](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/attribute-colour-settings.md) pass remote core/native/settings checks. Independent replies match 37 cases, with two explicitly retained differences for overflow and selective reset; eight reference variants are recorded. Full reference pixel parity, documented mode 5 and actual OpenGL remain separate. |
| OSC 13/14, 113/114 | Development | [Mouse pointer colour evidence](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/pointer-colours.md). 31 pinned XTerm stages, exact Windows cursor inks, reverse video, palette/reset semantics and active/hidden tab checks pass on `57217fd`. The OS theme is restored when both overrides are reset. XTerm resource profiles with special colour permissions are reference-only. |
| OSC 15/16/18, 115/116/118 | Missing | Tektronix colour slots are not implemented. Chained dynamic commands preserve their positions. |
| OSC 7 | Tested | `cwd`; validated working-directory URI metadata. |
| OSC 8 | Gated | `hyperlink`; bounded IDs/URIs and local link policy. Native hover, activation, copy and synchronization checks run in full CI; physical input and all URI handlers remain separate. See the detailed scope in [the protocol ledger](PROTOCOLS.md). |
| OSC 22 pointer shapes | Partial; development | [Pointer checkpoint](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/pointer-shapes.md): all 30 Kitty shapes, bounded per-screen stacks, queries and resets; 555 upstream stages replayed whole and bytewise with three named cancellation differences. Corrected-source GCC/Clang/MSVC checks and 53 actual Windows cursor checks pass, including Shift/selection, links and tab isolation. Complete ordinary CI and 154 single-image groups pass with twelve memory workloads; the first external shell-parser timeout remains unexplained. Local 160×48 Sarasa, physical DPI and original XTerm unknown-name semantics remain separate. Accepted EXE unchanged. |
| OSC 9;9 / OSC 633 P;Cwd= / OSC 1337 CurrentDir= | Partial | `cwd`; metadata subset only, not every operation in these namespaces. |
| OSC 133 / OSC 633 A/B/C/D | Partial | `shell_marks`; bounded prompt/command/output marks; not a complete VS Code terminal protocol. |
| OSC 52 | Gated | `osc52`; read/write permissions separate, bounded streaming base64. Full CI covers native Unicode clipboard text, selection retention, synchronized output, lock contention and delayed rendering. Read permission defaults off; these checks do not establish X11 ownership semantics or every application. See [the protocol ledger](PROTOCOLS.md). |
| OSC P / R (Linux palette legacy syntax) | Source only | Inherited handlers; separate from tested OSC 4 parsing. |
| OSC 60/61/62 feature-policy reports | Partial; both complete CI workflows passed | GCC/Clang ASan+UBSan and MSVC pass 1,780 unchanged XTerm formatter replies from the 20-profile / 2,100-stream capture, 36 native-policy parser cases whole and bytewise, and actual permission gates. Local native GDI/ConPTY and both full CI products each pass 72 cases across three profiles; the single image passes 160 groups. Native settings use independent restrictions, not XTerm master overrides; ESC restart is a named parser difference. Local exact-product Sarasa acceptance remains pending. [Mapping, reference and scope](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/feature-policy.md). |
| OSC 50 font query/change | Partial | The Windows frontend implements a per-view scalable font family and independent profile permissions for reading and changing it. Windows uses its installed fonts; there is no X11 bitmap font menu or XLFD lookup. [Independent XTerm 412, original Windows failures and exact-image checks](https://github.com/xiongnemo/nemoterm/blob/fca0e61388f99dd460811c231950d5d7c19a775e/research/osc-font-operations.md). |
| OSC 3/30/31/46 and remaining xterm OSC commands | Missing | X properties and unlisted log/resource operations are not implemented. |

## Work queue from this audit

1. Add remaining presentation/terminal-state reports and extend checksum charset coverage;
   extend the implemented DEC status queries when the remaining macro support exists.
2. Audit C0/C1 and character-set state transitions; expand individual mode and
   unlisted CSI entries instead of treating this first inventory as exhaustive.
3. Add remaining xterm report/stack operations and remaining mode families with
   independent reference cases and bounded storage.
4. Extend double-size row coverage to editing and resize combinations beyond
   the now-verified text output, cursor and grapheme behavior.
5. Preserve native clipboard, real-agent, physical IME, graphics lifetime and
   full process-tree memory acceptance as separate gates. Passing protocol unit
   tests does not close these requirements.
