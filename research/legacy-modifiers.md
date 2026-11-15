# Legacy XTerm modifier masks

Resource 0 (`modifyKeyboard`) now controls modifier parameters for the legacy
XTerm and VT220 keyboard profiles: bit 1 selects numeric keypad keys, bit 2
cursor/editing keys, bit 4 numbered function keys, and bit 8 miscellaneous
function keys. Modern XTerm input is unaffected by this mask. Nonzero
`modifyOtherKeys` and the corresponding level-4 extended resource retain their
precedence. The mask, format, queries, disable operation and lifecycle state
are implemented alongside resources 1, 2, 3, 4, 6 and 7.

Settings add **Xterm legacy (X11R5)** without renumbering saved profiles. This
profile uses numbered F1–F4 sequences and DEL for Delete. Legacy/VT220 Ctrl+Fn
advances the function number by 12 before encoding remaining modifiers. VT220
Shift user-defined keys retain priority, except for level-4 extended encoding.
The retained XTerm source and capture preserve UDK even with mask bit 4 set,
despite the manual's statement that the bit overrides UDK.

The Windows translator preserves numeric-keypad identity until the mask is
applied, handles application-keypad and Num Lock state, and supports Help/Menu.
The new legacy profile also handles these keys before an application negotiates
any resource. XTGETTCAP uses the matching negotiated keypad encoder. Configured
local copy/paste and scrolling keep priority. This does not change the default
modern XTerm profile or the user-selected optional Win32 transport policy.

Each modifier record is now 12 bytes to retain resource 0's 16-bit values.
The complete inline modifier state grows by **36 bytes** relative to `77ec984`;
encoding uses bounded stack buffers and adds no library or allocation. The
existing Windows key tracker is shared and allocated on demand for negotiation
or the explicitly selected legacy profile. These sizes are implementation
facts, not a new working-set acceptance result.

## Independent reference and deliberate differences

The unmodified XTerm 412 reference is commit
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f`, executable SHA256
`fabe97acf7dc1d7b5e4786d797f77be94edf11d43ccbd1322cbfad7e52120688`.
Its private Xvfb/XTest keyboard capture contains **98 cases / 2,895 steps**.
The archive retains observed XKB key identities and state, original bytes,
fixtures, source and literal mechanism controls. It uses no Windows input.
`legacy-modifiers-reference.tar.gz` has SHA256
`6af81cb1535135c42c75e48a91369dd3bccf2660e18bfb1c654c93c0074f85d3`.

The generator projects **2,872 unchanged input/reply steps**. The remaining
23 complete state observations are separately retained and not claimed as
matching reference steps. Every one includes `DECRQSS >0f`: XTerm 412's
`misc.c` `FMT_FMT_FKEYS` emits an `m` suffix, which restores the wrong resource.
Nemoterm keeps its existing, restorable `f` response. It also keeps the
documented all-resource reset behavior and restorable `65535` disabled value
instead of the reference's signed DECRQSS `-1`. Dedicated policy checks cover
these differences, format restoration, values, resize/reconfiguration, screen
and cursor preservation, RIS, DECSTR and DECSCL. See the upstream
[control specification](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
and [manual](https://invisible-island.net/xterm/manpage/xterm.html).

## Validation status

MinGW and GCC/Clang with ASan, UBSan and leak checking pass eight suites:
modified keys, Kitty keyboard, UDK, queries, state control, Win32 input,
XTGETTCAP and configuration. The new core replay passes both whole and
bytewise. Windows unit checks also cover legacy input before negotiation.

Broader configuration checking exposed an existing Unix Unicode conversion
path calling `strlen(NULL)` when the optional replacement string is omitted.
It now uses the charset layer's default replacement. The original GCC/Clang
UBSan failures and passing reruns are retained in the fix archive below.
The saved-profile checks now include VT220 and the new legacy profile.

The first native fixture misclassified Shift+Alt+Insert as application input;
the actual local paste binding consumed it. Corrected classification follows
the frontend's Shift/Ctrl mask regardless of Alt, and the fixture explicitly
disables its clipboard setting. That setup failure is not product acceptance,
and its hardcoded no-clipboard flag is not proof that no API was attempted.
The corrected intermediate image passes **2,704 exact native streams**, with
168 local-binding steps covered by the core. All three profile jobs exit
naturally. The previous `77ec984` image passes the F1 mechanism control and
fails the first new resource-0 query, as expected.

The final image includes startup-path and capability-query consistency fixes.
It passes **2,704 exact native streams** and **112 separate mask-zero startup
equivalence checks**. All nine owned processes across the three profiles drain
naturally. Those 112 checks reuse the observed key bytes with the
reset default instead of an explicit setter; they are not additional raw
XTerm input-stream captures. `legacy-modifiers-fix.tar.gz` (SHA256
`e3ca11f9afb7a4253b6e542073845712357a01fe027eafefd32bc69e696c92a7`)
retains exact old/new images, source-built host sidecars, all three native
attempts, original failures, compiler logs, source snapshots and cleanup.
Every archived member was rehashed after compression.

The [component workflow at 029bfac](https://github.com/xiongnemo/nemoterm/actions/runs/43776658169)
passes GCC/Clang ASan/UBSan and MSVC, including the unchanged replay, startup
mapper, configuration and capability regressions. `legacy-modifiers-ci.tar.gz`
and its manifest retain original logs and artifact receipts; all source hashes
match the exact Git content, with separately verified Windows CRLF checkout
variants for four existing `.inc` files. Ordinary and single-image CI include
the native fixture; those complete workflows remain pending. The outer
portable CI job budget accounts for the roughly eight-minute new replay;
existing product tests, deadlines and memory gates are unchanged.

Physical keyboard/IME/agent behavior, full keypad hardware coverage and the
remaining protocol ledger stay open. No accepted distribution is replaced.
The separate [MSVC tab-selection crash](tab-select-msvc-8655aae.md) remains
unresolved, and no memory limit is waived or transferred to this image.
