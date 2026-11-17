# Complete pinned terminfo key database

This records the pinned upstream key database and the XTSETTCAP integration.
The setter and optional Terminfo keyboard are now implemented in source;
full native product acceptance is tracked below, separately from export and
component checks. Export, builds, tests and runtime reference capture run only
on GitHub-hosted Actions. Local work edits source or reads downloaded records.

## Source and transformation

The workflow pins ncurses to
`789942a72295ac37b53a8a167ba9a016325a9ef1` (v6_6_20261114) and XTerm to
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f` (412). Upstream `tic -x` compiles the
entire `terminfo.src`; the same build's libtinfo reads every compiled alias and
all 218 string names in the pinned XTerm key table. Identity/colour queries
(`name`, `colors`, `RGB`) are excluded from this key database. No escape strings
are generated from Nemoterm's encoders.

The exporter records setup failures, owns and releases each library terminal,
then interns strings and deduplicates complete key profiles. Profile zero is
`xterm-256color`. All arrays are `static const`; selection uses one per-terminal
profile index without allocating thousands of key strings. Array sizes alone
are not evidence of runtime working-set usage.

| Measurement | Result |
| --- | ---: |
| Compiled terminal aliases | 2,931 |
| Aliases accepted by upstream setupterm | 2,854 |
| Rejected aliases retained in the manifest | 77 |
| String capabilities | 218 |
| Distinct key profiles | 516 |
| Sparse profile/key records | 15,846 |
| String pool bytes | 37,801 |
| Total C array bytes | 192,401 |
| Maximum key string length | 7 bytes |

`COPYING.ncurses`, the original `terminfo.src`, build/configuration logs,
tool/library hashes and raw library observations accompany the generated data.
The notices are retained in the repository, portable package recipe and the
single executable's existing embedded notice resource. The database adds no
runtime ncurses dependency.

## Compiled-table verification

[Run 44072637041](https://github.com/xiongnemo/nemoterm/actions/runs/44072637041)
at fixture `3526ff1` passes the independent C reader and Python comparison.
The C reader checks bounds, string terminators, alias/capability ordering and
profile indices, then emits the values actually compiled into the executable.
The file comparator checks those records against the original libtinfo
observations, rather than rebuilding expected strings from the export tables.

All **622,172 alias/capability combinations** match: 83,656 present values and
538,516 absent values. The present set includes 18 empty strings, which are
kept distinct from absent capabilities. The generated header SHA-256 is
`809c721a29b66764ee109420be1ff18cde3e3248f3dde8f78e8474700d9eaadc`;
the original library-observation gzip SHA-256 is
`d49ff300c079fd559a8bcf8ff35bec4d39f327e6f97cd7873dd7e5c84eeadec1`.

The earlier [database-only run 44070871162](https://github.com/xiongnemo/nemoterm/actions/runs/44070871162)
already built the same header and measured its C array sizes. The initial
[run 44070383769](https://github.com/xiongnemo/nemoterm/actions/runs/44070383769)
failed because the workflow assumed `libtinfo.so`, while the pinned ncurses
configuration built `libtinfow.so`. Both upstream compilation and tic succeeded.
The fix resolves the actual single library file; the original failure remains
retained and is not counted as a passing export.

## Keyboard reference scope

The separate XTerm capture selects databases at startup. This avoids confusing
successful database keys with the independently observed upstream setter
[lifetime discrepancy](set-tcap-reference.md). XTerm is built unmodified with
termcap keys/queries enabled and uses the runner's libtinfo against the same
private compiled database. Its library/package identities are recorded; it is
not claimed to be linked against the exporter's newly built library.

Required names are `xterm-256color`, `linux`, `vt100`, `screen` and `tmux`.
The capture includes twenty keys, eight modifier combinations, resources 1/2/3,
cursor/keypad modes, soft/hard resets and alternate-screen transitions. Optional
startup cases record availability explicitly. Input uses only an owned private
Xvfb, with Num Lock/Caps Lock cleared per case and actual XKB key symbols
recorded. Literal controls require XTerm F1 `ESC O P`, Linux F1 `ESC [ [ A` and
Linux F5 `ESC [ [ E`. Existing barriers and completion/exit checks remain intact.

The initial [capture run 44071392571](https://github.com/xiongnemo/nemoterm/actions/runs/44071392571)
failed before its first case: the fixture passed the extended helper's second
argument to the older one-argument keyboard helper. Fixture `4f2c5b0` imports
the existing extended helper and observer. The zero-case failure is retained;
it does not establish any terminal behavior.

The corrected [run 44072174561](https://github.com/xiongnemo/nemoterm/actions/runs/44072174561)
at `4f2c5b0` passes **163 cases / 1,378 steps**. Every case completes and its
XTerm exits zero. Besides the five required names, `vt220`, `ansi`, `alacritty`,
`wezterm` and `foot` have startup captures; `rxvt-unicode-256color` and
`xterm-kitty` are explicitly recorded as unavailable in this database.
The unmodified reference executable SHA-256 is
`1295fa6711ff3f650190dfb852b0466786a2474d86b50b824e53eb0c382394a5`.

A file-only comparison of seventeen ordinary key names across the five
required databases finds seventy present library values; all seventy match
the corresponding unmodified real-key bytes exactly. Fifteen absent entries
have separately retained fallback observations. Database hits take precedence
over cursor/keypad mode formatting: XTerm's Up remains `ESC O A` in both cursor
modes, while Linux Up remains `ESC [ A`. Missing keys still follow ordinary
state: Linux keypad Enter changes from CR to `ESC O M` in application mode,
and VT100 Home changes from `ESC [ H` to `ESC O H`. The selected startup
database's Up/F1 output survives the captured soft/hard resets and alternate
screen round trip. This does not assert that the buggy upstream setter acquires
or retains a new database successfully.

These observations do not cover VT52, every keyboard layout or every physical
key on all 2,854 aliases. Combined XTGETTCAP requests retain XTerm's early-stop
semantics, so they are not an exhaustive query check. The subsequent independent
query capture below addresses that gap for the ten captured startup names.

## Source integration and component verification

`590fc9e` adds the immutable table and bounded setter, and `582803f` connects
the optional keyboard profile to Win32 input and bilingual settings. The
default keyboard remains unchanged. Choose **Terminal / Keyboard / Terminfo**
to configure the startup database and the independent request permissions;
select **Terminfo** on the parent keyboard page to use its key strings.
GetTcap defaults on and SetTcap defaults off. OSC 60/61/62 reports both gates.

The setter accepts one hex-encoded name of at most 31 decoded bytes. Invalid,
unknown, overlong or cancelled requests leave the selection unchanged. It
rejects embedded NUL instead of adopting XTerm's prefix acceptance. Successful
selection has no reply; errors use the existing bell policy. Resets and
unrelated reconfiguration preserve the live selection. Saving a profile stores
the configured startup name and permissions, not an application's temporary
selection. Changing the startup name explicitly applies the new selection.
An unknown configured startup name falls back to `xterm-256color`.

The allocation-free production lookup API passes all **622,172** upstream
alias/capability combinations under GCC ASan/UBSan in
[run 44076036172](https://github.com/xiongnemo/nemoterm/actions/runs/44076036172).
That run also regenerates the header from pinned upstream source and requires
an exact match to the vendored bytes. The original artifact ZIP is 1,050,732
bytes, SHA-256 `87e3c122065e8b168c6a463125ab24ca081b88d7b827e01587239d1b8cd16122`.

[Independent query run 44074397164](https://github.com/xiongnemo/nemoterm/actions/runs/44074397164)
captures all **2,180 individual queries** (218 names times ten terminals) and
three physical controls. Separate requests prevent early-stop gaps. Its
[retained original observations](tcap-query-reference.zip) have SHA-256
`6ebcafe5f675b49e24803369be4c51b5da9ac4914861e5ba45946e9188bb9e3d`.
The generated fixtures preserve original answers, normalizing only the case
of ASCII hex digits in capability values. Physical key bytes remain exact.

At `771f5a3`, [run 44078735638](https://github.com/xiongnemo/nemoterm/actions/runs/44078735638)
passes the capability/keyboard suite under GCC, Clang and MSVC: the 2,180
individual queries and all 1,378 startup steps, alongside setter/configuration
regressions. This is a **component result**, not an all-green run: its newly
added feature-policy tests fail because the preceding mock resize request was
never acknowledged. `904a240` completes that fixture handshake. The original
failure is retained.

The subsequent [component run 44080443304](https://github.com/xiongnemo/nemoterm/actions/runs/44080443304)
at fixture `baabe5e` passes **all three compiler jobs**, including the repaired
permission checks. GCC and Clang use ASan/UBSan; MSVC supplies an independent
Windows compiler check. This still does not validate settings-page lifetime or
native key routing, which the separate hosted product jobs exercise.

There are **45 explicit startup-identity comparisons**. Reference XTerm `-tn`
sets both TN and the startup keyboard database. Nemoterm's keyboard selector
preserves its emulator identity (`xterm-256color`), as does the upstream setter's
intended scope. Fixtures keep the full original response, assert Nemoterm's TN
separately, and compare all remaining original bytes. They do not claim complete
TN parity with `xterm -tn linux` or silently rewrite reference answers.

Two earlier failures are retained: [44076036326](https://github.com/xiongnemo/nemoterm/actions/runs/44076036326)
found 37 missing-Delete query mismatches (XTerm's synthetic query is empty while
the real key falls back to DEL). [44077432618](https://github.com/xiongnemo/nemoterm/actions/runs/44077432618)
exposed extended-mode priority and the startup TN comparison boundary. Explicit
modify*Keys level 4 now precedes raw database lookup; ordinary database hits
still precede cursor/keypad mode formatting.

The hosted native fixture projects **1,293** Windows-comparable streams. It
lists 45 F35 steps without a Win32 key equivalent and 40 Shift+PageUp/PageDown
steps reserved for local scroll; the core retains all 85. Injection targets
only the owned UI thread and restores its keyboard state. Actual key messages,
ConPTY bytes, barriers and natural process cleanup are checked. These injected
messages do not certify arbitrary physical keyboard layouts.

Initial full product [run 44079360773](https://github.com/xiongnemo/nemoterm/actions/runs/44079360773)
at `904a240` is **cancelled after a recorded DPI failure**, superseded by a source
fix. The twelve-page DPI matrix exposed the new text field passing an integer
instead of the edit handler's string-type descriptor, causing settings to exit
when opening Terminfo. Its source image is SHA-256
`114e62d4ce9f7673cca6073537bdfb498e920d8d42fd7888f18aaae5f950365f`.
All ten functional interaction groups, profile and shell-lifetime jobs passed
before cancellation, but the incomplete single-image, MinGW and memory jobs
are not accepted. The original DPI artifact is retained.

The same image's [native replay 44080437288](https://github.com/xiongnemo/nemoterm/actions/runs/44080437288)
fails at Shift+Insert: the disabled legacy clipboard action still swallowed the
key before the application encoder. It separately passes 75 existing policy
cases and all 28 new cases covering four independent SetTcap/GetTcap permission
combinations. These successes do not make the keyboard replay green.

`589faec` supplies the proper string descriptor and lets disabled Insert
clipboard combinations reach the application. Enabled local copy/paste actions
retain their existing dispatch. Its 4,800,000-byte source-built image has SHA-256
`ec927024b3ff77d74379857f0ee226e45677fcea80d4cc4ccdfa635836ab7315`.

On that exact image, [native replay 44082638389](https://github.com/xiongnemo/nemoterm/actions/runs/44082638389)
at fixture `928b34c` **passes all 1,293 native streams with zero mismatches**, the
75 existing policy cases and 28 independent termcap permission cases. All ten
keyboard profiles complete with natural owned-job cleanup; the 85 documented
native exclusions remain explicit. The fixture records complete key streams
even when one comparison fails, then fails the overall check if any mismatch
exists. It does not discard failures after completing a capture.

The same image's [full run 44081569049](https://github.com/xiongnemo/nemoterm/actions/runs/44081569049)
passes the real-DPI job: **24 cases, 528 page checks and 3,036 control checks**,
including Terminfo in both languages and both window modes. The 200% Chinese
Terminfo screenshot was also visually inspected. All ten functional interaction
groups, profile, shell-lifetime and compiler/sanitizer jobs pass. The aggregate
is **cancelled**, not a full acceptance: its remaining single-image, MinGW and
memory jobs were superseded by the subsequent UI-layout source change.

The retained keyboard screenshot also exposes truncated long keyboard-mode
radio labels. `329019d` lays them out in two columns and moves the AltGr options
to Keyboard/Extended, which joins the now **13-page** bilingual DPI matrix.
Full product [run 44083541137](https://github.com/xiongnemo/nemoterm/actions/runs/44083541137)
has completed on this final source candidate, with all gates unchanged:
**21 jobs pass; only full-grid DirectX memory fails**.
Its single image is **4,800,000 bytes**, SHA-256
`b4ed0f124b3e17d165b6c0d31c9a02a083477d556dd34ecbdb37d6d9db3458d7`.
The downloaded image matches its source-host manifest without local execution.

This exact image passes all **26 functional interaction cases**, with natural
process cleanup, and all **24 real bilingual DPI cases**: 44 frames, **572 page
checks and 3,344 control checks**. The English and Chinese 200% Keyboard,
Terminfo and Extended screenshots were visually inspected; the long radio
labels fit and the footer remains separate. Profile, shell-lifetime, MSVC
diagnostics and sanitizer jobs also pass.

All six full **160x48 Sarasa GDI** workloads pass, including their subsequent
pixel/lifetime checks and natural cleanup. The actual font is
`SarasaTermSC Nerd Light`, the requested grid is not clamped, and memory samples
are uninjected. Frontend peaks in bytes are:

| Workload | GDI private WS | GDI total WS | GDI private commit | DirectX private WS |
| --- | ---: | ---: | ---: | ---: |
| Text/history | 16,142,336 | 49,455,104 | 18,214,912 | 25,436,160 |
| Inline PNG | 17,408,000 | 52,043,776 | 19,963,904 | 27,004,928 |
| Animated GIF | 17,100,800 | 51,720,192 | 19,369,984 | 27,348,992 |
| Kitty PNG | 17,285,120 | 52,043,776 | 20,250,624 | 26,591,232 |
| Compressed Kitty | 17,051,648 | 51,716,096 | 19,390,464 | 26,759,168 |
| Unicode Kitty cells | 18,817,024 | 53,497,856 | 22,224,896 | 28,778,496 |

All six DirectX workloads fail the unchanged 25,000,000-byte private working-set
gate; their functional checks and natural cleanup complete. These failures are
retained, and the user's instruction to stop further DirectX memory tuning is
unchanged. GDI remains below 20 MB private WS and approximately 50 MB total WS.

The full single-image suite now passes **170 groups** and the complete MinGW
suite also passes. Each exact executable passes **1,293 native Terminfo streams
with zero mismatches**, retaining 85 named exclusions; permission combinations
and persisted profile settings also pass. This completed **21/22** aggregate
is not an all-green build, and `dist` has not been replaced. Exact downloads,
portable notice completion and scope are in the
[final product record](terminfo-product-regression.md).

## Integration evidence archive

[The integration archive](tcap-integration-evidence.zip) retains 179 entries,
including final metadata, original failed component/native ZIPs, successful
production-lookup and native-replay receipts, cancelled aggregate records,
complete DPI JSON/logs and selected 200% screenshots. It additionally retains
the explicitly named earlier in-progress `44083541137` snapshot, final metadata,
complete single-image/MinGW evidence, original interaction, GDI/DirectX memory,
profile and lifetime artifact ZIPs, and both notice-package replays. Original download hashes
remain in the receipt files; explicitly named `.selected.zip` files omit the
rest of the successful DPI screenshots. Source-host and package binaries are
omitted after file-only verification; package metadata and file hashes remain.
No downloaded program was run
on the development computer.

The archive is **20,689,733 bytes**, SHA-256
`c978c3c8ae0776184faa38190fda77f2aeaab7c5bcc5f35713dd9b5a9f32d8e9`.
It retains the completed component/native and full aggregate checkpoint,
including the failed DirectX memory gate.

## Retained evidence

[The archive](terminfo-database-evidence.zip) contains 21 records plus its
per-file hash manifest, including final run/job/artifact metadata for all five
runs, both complete failure logs, selected artifact ZIPs, raw observations,
generated data, analysis and file-only analysis scripts. Probe executables are
omitted; their hashes and the original downloaded ZIP hashes are retained.
The archive is **3,261,069 bytes**, SHA-256
`7e3270eadc8063fc85624e67dd3fae0ee26a654e8d82e37374c63199300d0df0`.
All four successful export stages produced the identical generated header,
including the run whose subsequent keyboard capture failed before its first case.
