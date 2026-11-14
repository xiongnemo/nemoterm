# Protocol coverage and remaining gaps

This is an audited inventory of the current development sources, not a claim
of complete xterm compatibility. The accepted `dist/nemoterm.exe` on `main`
has an older source identity; consult the artifact records in `research/`.

The published product checkpoint at `f079f80` passes both full workflows,
including 99 single-image groups. Its [manifest](../research/relative-cursor-validation.json)
identifies the exact EXE, relative-cursor/DECALN replies and pixels, and local
acceptance limits. GDI passes at 16.13 MB in the Sarasa 160x48 workload. DirectX's
first run fails the temporary-tab resource-count gate; the cause remains unproven.
A separate unmodified full-workload run passes nine functional groups and drains
naturally, but reaches 30.63 MB private working set, above the 25 MB limit. Both
failures are retained separately.
The earlier sidecar reply-order issue was resolved by building the same host
source and overlay for compiler comparison. Local native testing is currently
paused at the user's request; remote CI continues. The later graphics/charset
integration `26f50c8` passes both full workflows and 119 single-image groups;
its smaller CI grids do not resolve local DirectX failures. See the
[integration record](../research/graphics-charsets-integration.md).
The preceding [overline checkpoint](../research/overline.md) includes local checks
of its downloaded image under all three renderers; CI's OpenGL request used GDI fallback.

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
| C0 BEL | Partial; core and remote API checks | Sound/disabled/visual policy, OSC terminator distinction and bounded overload accounting pass core tests. Remote native checks observe real MessageBeep dispatch for sound and no calls for disabled/visual modes. Audible speaker output, visual pixels and custom WAV/PC-speaker modes remain unverified. See [bell evidence](../research/font-zoom-and-bell.md). |
| C0 BS, CR, LF, VT, FF | Tested | `margins`, `terminal`; BS follows explicit reverse-wrap modes 45/1045, with physical-cell counting and pending-wrap cases. Default BS stays on the current line. |
| C0 HT; ESC H (HTS) | Tested | `state_control`, 108 tabulation oracle comparisons and native ConPTY replies. |
| C0 ENQ | Source only | Configured answerback path. |
| C0 SI/SO | Partial | G0/G1 bank selection is covered by presentation-state reports; full ISO 2022 combinations remain unverified. |
| C0 CAN/SUB/ESC cancellation | Partial | Numerous query/OSC/DCS recovery cases; complete state-machine matrix remains open. |
| ESC D/E/M (IND/NEL/RI) | Tested | `margins`, including partial horizontal scroll regions. |
| ESC 7/8 (DECSC/DECRC) | Partial | `state_control` covers cursor/rendition/alternate-screen state. All supported G0–G3 designations and both GL/GR selectors have 44 independently matched XTerm cases plus native four-bank pixel restoration; see [cursor charset checkpoint](../research/cursor-charset-save.md). The supported charset repertoire remains limited. |
| ESC = / ESC > | Tested | `modes`, `keyboard`, application/numeric keypad state. |
| ESC Z (DECID) | Source only | Shares configured primary DA response; not separately covered by identity oracle. |
| ESC c (RIS) | Tested | `state_control`, `grapheme_terminal`, `sixel_terminal`. |
| ESC #3/#4/#5/#6 | Partial | Output, cursor movement, pending wraps, wide/combining text and cluster growth checked; see `double-size-lines.md`. The three tabulation failures are fixed. Row-size-specific editing/resize combinations remain open. |
| ESC #8 (DECALN) | Partial | [State/image fix](../research/alignment-reset.md): 13 exact XTerm query cases, direct RGB policy, cell/selection/history assertions and 12 native pixel checks per renderer. Both full CI workflows and downloaded-image actual GDI/OpenGL/DirectX checks pass. Current RGB keeps valid encoding instead of XTerm's packed-index report after reset. |
| ESC ( / ) / * / + and ESC - / . / / | Partial | Development [parser integration](../research/iso2022-parser.md) adds mapped national/DEC/ISO sets and 94/96 designations. [Input/native follow-up](../research/iso2022-input.md) and [UPSS](../research/iso2022-upss.md) add independent paste and actual GDI/OpenGL/DirectX pixel checks. The broader lower-level output matrix remains open. Accepted EXE unchanged. |
| ESC % G / ESC % @, DEC mode 42 | Partial | Development DOCS override/cache and NRC decoding match the isolated state matrix. Encoding is global across cursor/alternate saves. NRC paste conversion and the temporary UTF-8 keyboard shortcut are covered by the [input checkpoint](../research/iso2022-input.md); all encoding combinations remain open. |
| ESC N/O (SS2/SS3), ESC n/o and GR locking shifts | Partial | Extended bank invocation passes the real-parser Unicode-cell and transition matrix. Native SS2 pixels match directly printed Unicode on three actual renderers; extended legacy checksums remain unverified. |
| ESC SP F/G (S7C1T/S8C1T) | Tested | Selectable generated reply/key framing; 141 exact XTerm streams, two native code-page variants, reset/level lifetimes. See [C1 transmission](../research/c1-controls.md). Input-parser conformance remains separate. |
| ESC SP L/M/N (ANSI conformance levels) | Missing | No handlers. |
| ESC 6/9 (DECBI/DECFI) | Tested | `margins`, native `horizontal`: VT420 gate, inside/outside margins, edge scrolling and pending wrap. Text, full cell payloads, shell marks and Sixel pixels move together. |
| ESC V/W (SPA/EPA) | Tested | ISO guarded writes, ordinary/DEC erasure, queries, reset and family transitions: 63 independent XTerm matches, core assertions and single-image native text/Sixel pixels. See [guarded areas](../research/guarded-areas.md) for the upstream sidecar limitation. Legacy raw C1 dispatch retains the configured codepage policy. |
| Raw C1 bytes and UTF-8 encoded C1 | Partial | Existing codepage-sensitive parser; exhaustive byte/state conformance is still open. Do not assume UTF-8 text is reprocessed as controls. |
| SOS/PM/APC strings | Partial | String consumption/recovery only; no application payload support. |

## CSI cursor, editing, status and window functions

| Wire function | Status | Evidence or limitation |
| --- | --- | --- |
| A/B/C/D (CUU/CUD/CUF/CUB) | Tested | `margins`, `terminal`; origin and scroll-region boundaries. CUB shares reverse-wrap handling with BS, including bounded large counts and extended cycles. |
| E/F (CNL/CPL) | Partial | Cursor-report streams match the 848-sequence [movement audit](../research/cursor-movement-audit.md), including origin/margins/defaults and pending wrap. Full pixel/scrolling/resize behavior remains unverified. |
| G and backtick (CHA/HPA); d (VPA); H/f (CUP/HVP) | Tested | `margins`, `queries`, origin-relative positioning. |
| a/e (HPR/VPR) | Partial | The [correction](../research/relative-cursor.md) matches all 848 independent XTerm streams, fixing the audit's 47 differences. Separate origin clipping, bounded logical double-row columns, tiny-grid sanitizer assertions and native pixels pass both complete CI workflows and downloaded-image actual GDI/OpenGL/DirectX checks. |
| I/Z (CHT/CBT) | Tested | `state_control`, defaults/counts, custom stops, margins and pending wrap; native oracle replay. |
| g, parameters 0/3 (TBC) | Tested | Tabulation oracle, including extra parameters using the first value. |
| ?W, parameters default/0/5 (DECST8C) | Tested | Tabulation oracle; VT510 compatibility capability required. |
| @/P (ICH/DCH) | Tested | `margins`, `rectangle`, `reflow`, wide/combining boundaries. |
| L/M (IL/DL) | Tested | `margins`, `sixel_terminal`, partial-region lifetimes. |
| J/K/X (ED/EL/ECH) | Tested | `terminal`, `selective_erase`, `rectangle` and Sixel checks; ISO protection is covered by the 63-case guarded-area reference matrix and single-image native erasure/pixel checks. |
| J parameter 3 (saved-line erase) | Gated | Local remote-clear-scrollback setting; active screen is separate. |
| ?J/?K (DECSED/DECSEL) | Tested | Protected text/image checks include shared ISO family, empty whole-display retirement and wrap/drawn-span handling in the guarded-area core and single-image native fixtures. |
| S/T (SU/SD) | Tested | `margins`, `sixel_terminal`; T also has mouse highlight syntax. Pending wrap is preserved, independently checked by XTerm and native cell/cursor replies. |
| ^ (SD alias), SP @ / SP A (SL/SR) | Tested | `margins`, native `horizontal`: counts, margins, outside-region behavior, wide/double-size rows, origin and pending wrap. See [horizontal editing](../research/horizontal-editing.md). |
| ' } / ' ~ (DECIC/DECDC) | Tested | VT420 column insertion/deletion over vertical margins from the cursor column. Full cell lifetimes and bounded Sixel views are checked separately from the 198-case XTerm matrix. |
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
| ?n (DEC-specific DSR, including extended CPR) | Tested | `queries`, native `dec_status`: 5/6/15/25/26/55/56/62/63/75/85, level-dependent report formats, origin/margins/resize and explicit unavailable devices. UDK download, DEC locator and macros themselves remain missing. See `dec-status.md`. |
| ?9001;id n (Nemoterm internal cursor synchronization) | Tested | Same-image host transaction IDs and viewport-absolute coordinates; separate from application CPR and Win32 input mode 9001. Native ordering, stale replies and console-API positions are checked. |
| x (DECREQTPARM) | Source only | Legacy fixed serial characteristics response. |
| "p (DECSCL) | Partial | Levels 61–65, soft-reset effects, Pc control selection and DECRQSS `"p` use the [C1 reference capture](../research/c1-controls.md). PuTTY extensions remain; exhaustive reset/charset interactions remain open. |
| "q (DECSCA) | Tested | `selective_erase` checks independence from SGR resets. ISO/DEC transitions and the family-sensitive DECRQSS response pass the guarded-area reference/core/native matrix. |
| $z / ${ (DECERA/DECSERA) | Tested | `selective_erase` rectangles, with ISO/combined-family distinctions covered by the guarded-area reference/core/native matrix. |
| $x / $v (DECFRA/DECCRA) | Tested | `rectangle`, fill/copy, overlap, wide/combining characters and page handling. |
| $r / $t / *x (DECCARA/DECRARA/DECSACE) | Tested | `rectangle`, stream/rectangle attribute extent. |
| *y (DECRQCRA); #y (XTCHECKSUM) | Gated / Partial | Off by default; `queries` and native `checksum`: 364 exact XTerm cases, 8 retained-cell expectations, attributes/blank modes/origin/resize/reset. Unicode normalization and legacy charSeen differences are explicit; see [checksum record](../research/rectangle-checksums.md). |
| $w (DECRQPSR); DCS 1/2 $t (DECRSPS) | Partial | Cursor/tab reports and replay: 142 exact XTerm cases and 10 direct cases in `queries` and native `presentation_state`. Bounded streaming tab restoration, offscreen stops, valid-prefix cursor restoration and protection-family semantics. Charset restoration is limited to the supported banks/sets; see [presentation-state record](../research/presentation-state.md). |
| "v (DECRQDE) | Tested | Active rows/columns, single page, operating-level gate, origin-independent and resized native reports. |
| $u (terminal state request) | Missing | Complete terminal-state serialization/restoration is separate from presentation-state reports. |
| #\| (XTREPORTSGR), #{ / #} and #p / #q (SGR stack) | Tested | `queries`, native `sgr_stack`: 193 exact XTerm captures and 14 modern-underline expectations. Ten retained frames, bounded overflow, selective attributes/colors, origin-relative intersections, reset/alternate-screen retention and read-only queries. Six XTerm cases ignore modern underline styles and are documented separately; see [SGR stack record](../research/sgr-stack.md). |
| #P/#Q/#R (palette stack) | Tested | Ten lazy snapshots of the implemented indexed/default palette; indexed access, zero/omitted arguments, high-water reports, reset/alternate-screen retention, invalidation and synchronized pixels. See [palette stacks](../research/palette-stacks.md); unsupported OSC color namespaces remain separate. |
| #S (title-stack position query) | Tested | Logical depth and ten retained slots; fixes the former depth clamp. The combined palette/title oracle has 101 exact XTerm cases through core and all three native renderers. |
| t, operations 1–9, 11, 13–16, 18–23 and line count >=24 | Partial | `queries`, `titles`, `window_resize`; native movement, size and title policies apply. Other window operations remain missing. |
| >t / >T (title modes) | Tested | `titles`, independent raw-byte title-mode oracle. |
| *\| / $\| (DECSNLS/DECSCPP) | Gated | `queries`, `window_resize`; remote resizing setting and monitor work-area clamp. |
| i / ?i (media copy) | Source only | Configured printer start/stop subset; not a full screen-to-printer implementation. |
| DEC locator 'w/'z/'{/'\| controls | Missing | Xterm mouse tracking is implemented separately; DEC locator is not. |

## Rendition, modes, input and graphics

| Wire function | Status | Evidence or limitation |
| --- | --- | --- |
| SGR 0,1,2,3,4,5,7,8,9,21–25,27–29 | Tested | `sgr`, `queries`; bold/dim/italic/underline/blink/inverse/conceal/strike and resets. |
| SGR 4:0–5; 58/59 | Tested | Underline styles/colours and reset, native pixels and query round trips. |
| SGR 30–37/40–47/90–97/100–107/39/49 | Tested | Indexed/default foreground/background and configuration policy. |
| SGR 38/48/58, indexed or RGB, semicolon/colon forms | Tested | `sgr`, `queries`; supported forms and malformed input recovery. |
| SGR 53/55 (overline) | Tested | ECMA-48 state/reset/query, history/reflow and native GDI/OpenGL/DirectX pixels; both complete CI workflows pass. Selective SGR-stack selector 53 is a Nemoterm extension. See [overline](../research/overline.md); RTF export does not encode the style. |
| SGR font-selection, framed/encircled and ideogram attributes | Missing | Legacy SCO font controls do not satisfy these families. |
| ANSI modes 4/12/20/34 | Tested | `modes`, `state_control`; insertion, echo, newline and legacy cursor mode. |
| DEC modes 1/2/3/5/6/7/8/12/25/66 | Partial | `modes`, `state_control`; corresponding legacy behavior and configuration gates. Full VT52 and 80/132 transition coverage remains open. |
| DEC modes 47/1047/1048/1049 | Tested | Alternate screen and cursor state, `state_control`, `margins`, `grapheme_terminal`. |
| DEC mode 69 | Tested | Horizontal margin state and edits, `margins`. |
| DEC modes 45/1045 | Tested | Normal/extended reverse wrap: 567 exact XTerm cases, 13 direct boundary cases, private save/restore, reset, alternate-screen state, pending wrap, wide/double-size cells and margin scrolling. Cursor stays in the viewport where ten reference cases leave it; see [reverse-wrap record](../research/reverse-wrap.md). |
| DEC modes 9/1000/1001/1002/1003 | Tested | X10, press/release, highlight, button/all motion; `mouse`, `highlight`, native HWND fixtures. |
| DEC modes 1005/1006/1015/1016 | Tested | UTF-8/SGR/urxvt/pixel mouse encodings and bounded coordinates. |
| DEC modes 1004/1007 | Tested | Focus reports and alternate-screen wheel behavior. |
| DEC mode 2004 | Gated | Bracketed paste protocol tested; local real clipboard acceptance remains unavailable, mandatory CI gate retained. |
| DEC modes 80/1070/8452 | Tested | Sixel display/palette/cursor-scroll behavior, `sixel_terminal`. |
| DEC modes 2026/2027 | Partial | Synchronized frames and opt-in grapheme widths tested; see `sync`, `grapheme_terminal`, `graphemes.md`. Color-font/emoji policy and long workloads remain open. |
| DEC mode 9001 | Gated | Windows input records, `win32_input`, user setting and native fixture. |
| Other DEC modes, including 1042/1043 bell focus | Missing | Not in the current mode handler; DECRQM returns unknown rather than advertising support. |
| >m/>n/?m; >f/?g/>g (modifyOtherKeys family) | Partial | `mok`, native key tests and independent reference; supported resource is modifyOtherKeys, not all xterm key resources. |
| ?u/=u/>u/<u (kitty keyboard flags/stack) | Tested | `keyboard`, progressive flags and stack; platform-specific physical-layout coverage remains open. |
| DCS $q ... ST (DECRQSS) | Partial | `queries`: m, r, s, *x, "p, "q, SP q, $\|, *\|, >4m, >4f and title modes; unknown requests fail explicitly. |
| DCS Ps !u Pt ST; CSI &u (DECAUPSS / DECRQUPSS) | Partial | Development [UPSS checkpoint](../research/iso2022-upss.md): 112 independent streams, 5,376 output cells and 28 selection captures; reset, DOCS and saved-cursor state; actual three-renderer pixels and ConPTY transport. Full checkpoint CI and complete encoding/malformed-input combinations remain open. |
| DCS +q ... ST (XTGETTCAP) | Partial | `tcap`; named colour/identity/key and rendition whitelist. `smul/rmul`, `sitm/ritm`, `smxx/rmxx`, `Smol/Rmol`, plus `us/ue/ZH/ZR` aliases. `Smulx`/`Setulc` programs pass independent ncurses expansion, both complete workflows at `37ef26d`, and local discovery/state replay using that exact downloaded image. Requests remain bounded to 2,047 bytes; replies have a 22 KiB ceiling. Not arbitrary terminfo access; `Su` and `Setulc1` remain unknown. These protocol checks do not resolve the separately retained DX acceptance failures. See [underline query evidence](../research/underline-capabilities.md). |
| DCS +p ... ST (XTSETTCAP), user-defined keys and full terminal-state restoration | Missing | Query-only termcap support; presentation-state restoration is listed separately. |
| DCS ... q ... ST (Sixel) | Tested | `sixel`, `sixel_terminal`, native render/scroll/erase/font-resize cases. Resource bounds are part of the implementation. |
| CSI ? Pi ; Pa ; Pv S (XTSMGRAPHICS) | Tested | `queries`, `sixel`, `sixel_terminal`, native `graphics_query`: register count read/reset/set/max (2–256), current/max geometry, explicit invalid-item/action/failure replies. Geometry is read-only; 8192 per-axis limit remains subject to the shared 4 MiB raster budget. See `graphics-query.md`. |
| ReGIS; Tektronix 4014 | Missing | No decoders/renderers. |
| APC G (kitty graphics) | Missing | APC is consumed; no kitty graphics transport or placement implementation. |
| OSC 1337 inline images: File / MultipartFile / FilePart / FileEnd | Partial; integration candidate | PNG/JPEG/BMP and animated GIF use streaming transport, Windows WIC and the shared bounded raster lifetime. This candidate passes 32 static and 36 animation scenes on each actual GDI/OpenGL/DirectX backend. File downloading and full iTerm parity remain open; the accepted download is unchanged. See [integration evidence](../research/graphics-charsets-integration.md). |
| OSC 1337 Capabilities / ReportCellSize | Tested; remote CI | Live preference-aware feature codes and current DPI-scaled cell size. The ambiguous focus/file `F` and uncertified `Uw` codes are omitted; no `TERM_FEATURES` environment publication. Both full workflows pass at `5b2e6f1`, including 13 capability cases and 42 native geometry phases at 96 DPI; local native testing is paused. See [report policy and validation](../research/iterm-capability-reports.md). |

## OSC and modern shell metadata

| Wire function | Status | Evidence or limitation |
| --- | --- | --- |
| OSC 0/1/2/21 | Gated | `titles`, bounded title/icon strings, encoding modes and local title policies. |
| OSC 4 / 104 | Tested | `osc_colour`, indexed palette set/query/reset; multiple pairs and malformed data. The [25-case reset/reverse capture](../research/reset-palette.md) and native pixels cover RIS/DECSTR restoration and saved-palette retention. |
| OSC 10/11/12 and 110/111/112 | Tested | Default foreground/background/cursor colours and resets, including reversed foreground/background roles and stateful cursor following in the reset/reverse capture. |
| OSC colour names: pinned Xorg table | Tested | [782 X11 names](../research/x11-colours.md), including exact space aliases and numbered shades. Extended parser/protocol tests pass remotely; independent XTerm matches 1,574 name/case/rejection observations in 66 batches using separate setters and queries. Malformed combined-command recovery is distinct. Numeric `rgb:`/`#` semantics are unchanged; Xcms device-profile forms remain unsupported. |
| OSC 17/19, 117/119 | Partial | Selection foreground/background set/query/reset, palette stacks, display overlays and [saved defaults](../research/selection-settings.md). Independent capture matches 30 cases and retains 11 resource observations; core, native GDI/DirectX and settings checks pass remotely. Full XTerm highlight-resource pixel parity and actual OpenGL pixels remain open. See [selection colours](../research/selection-colours.md). |
| OSC 5/6, 105/106 and OSC 4/104 aliases 256–260 | Partial | [Attribute colours](../research/attribute-colours.md): special colours, modes, overlays, palette retention and [saved defaults/style settings](../research/attribute-colour-settings.md) pass remote core/native/settings checks. Independent replies match 37 cases, with two explicitly retained differences for overflow and selective reset; eight reference variants are recorded. Full reference pixel parity, documented mode 5 and actual OpenGL remain separate. |
| OSC 13–16/18, 113–116/118 | Missing | Pointer/Tektronix colour operations are not implemented. Chained dynamic commands preserve their parameter positions. |
| OSC 7 | Tested | `cwd`; validated working-directory URI metadata. |
| OSC 8 | Gated | `hyperlink`; bounded IDs/URIs and local link policy; mandatory native clipboard-related cases still await CI. |
| OSC 9;9 / OSC 633 P;Cwd= / OSC 1337 CurrentDir= | Partial | `cwd`; metadata subset only, not every operation in these namespaces. |
| OSC 133 / OSC 633 A/B/C/D | Partial | `shell_marks`; bounded prompt/command/output marks; not a complete VS Code terminal protocol. |
| OSC 52 | Gated | `osc52`; read/write permissions separate, bounded streaming base64. Actual clipboard integration remains a required CI gate. |
| OSC P / R (Linux palette legacy syntax) | Source only | Inherited handlers; separate from tested OSC 4 parsing. |
| OSC 3/22/30/31/46/50/60/61/62 and remaining xterm OSC commands | Missing | X properties, pointer/font/log/resource operations are not implemented. |

## Work queue from this audit

1. Add remaining presentation/terminal-state reports and extend checksum charset coverage;
   extend the implemented DEC status queries when UDK/locator/macro support exists.
2. Audit C0/C1 and character-set state transitions; expand individual mode and
   unlisted CSI entries instead of treating this first inventory as exhaustive.
3. Add remaining xterm report/stack operations and remaining mode families with
   independent reference cases and bounded storage.
4. Extend double-size row coverage to editing and resize combinations beyond
   the now-verified text output, cursor and grapheme behavior.
5. Preserve native clipboard, real-agent, physical IME, graphics lifetime and
   full process-tree memory acceptance as separate gates. Passing protocol unit
   tests does not close these requirements.
