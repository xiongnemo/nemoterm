# Complete pinned terminfo key database

This is upstream research for XTSETTCAP. Nemoterm still does not implement that
setter, and no production executable contains this new database yet. Export,
compilation and runtime reference capture run only on GitHub-hosted Actions.
Local work only edits source or reads downloaded records.

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
`xterm-256color`. All arrays are `static const`; selection can eventually use a
small per-terminal profile index without allocating thousands of key strings.
This is a storage design, not evidence of runtime working-set usage.

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
Before production integration, retain the notices in the repository, portable
package and the single executable's existing embedded notice resource. The
export does not add a runtime ncurses dependency.

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
semantics, so they are not an exhaustive query check. Integration still needs
bounded setter parsing, permission/profile persistence, key/query mapping and
native product regression, followed by GDI memory verification of the exact
new executable. XTSETTCAP remains absent from supported-feature advertisements.

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
