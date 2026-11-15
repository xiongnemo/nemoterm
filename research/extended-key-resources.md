# Keypad, modifier and special-key resource negotiation

Applications can now negotiate xterm resources 3 (keypad), 6 (modifier keys)
and 7 (other special keys), alongside the existing resources 1, 2 and 4.
Level 4 emits the observed Unicode/PUA key identity in either extended format.
Levels 0–3 and disabled mode retain the legacy translator. Queries, format
selection, DECRQSS and terminal resets use the shared resource machinery.
Kitty input and configured local bindings retain priority; explicit xterm
negotiation takes priority over optional Win32 input transport.

The Windows mapping distinguishes keypad navigation from dedicated extended
navigation keys, Num Lock digits, keypad Enter and arithmetic operators.
Modifier presses use the state before that press, including another held key
for the same modifier. Releases are consumed without generating protocol bytes.
Shift+Tab uses the observed ISO_Left_Tab identity. Pause and Scroll Lock use
scalar values 19 and 20 rather than the generic PUA mapping.

The added resource state is 24 bytes per terminal. Encoding uses a bounded
stack buffer and introduces no library or renderer dependency. This is a source
size statement, not a new working-set measurement or full-product acceptance.

## Independent reference

The capture uses unmodified XTerm 412, source
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f`, executable SHA256
`fabe97acf7dc1d7b5e4786d797f77be94edf11d43ccbd1322cbfad7e52120688`.
XTest events run on an isolated Xvfb display with TCP disabled. Literal controls
run before the matrix. XKB records the actual symbol and modifier state before
each event, so expected identities do not depend only on the requested key name.
Lock state is normalized on that private server. Missing keypad symbols are
assigned unused private keycodes; the Windows keyboard and clipboard are untouched.

`extended-key-resources-reference.tar.gz` and its validation manifest retain
107 cases / 312 steps, upstream source, versions, raw bytes and exact fixtures.
The generator verifies the archive digest and projects unchanged replies:

* 283 steps match core replay, both whole and bytewise.
* 243 steps additionally match the Windows mapper, including release events.
* 235 steps match owned-HWND messages through the native frontend and ConPTY.

Twenty-six legacy-output observations are retained outside extended-encoder
parity. Forty remaining core steps lack an unambiguous Windows mapping in this
fixture; eight mapped combinations are reserved for local copy/paste or scroll
bindings and are covered at the core/mapper layers. Three reset-all observations
remain separate: Nemoterm keeps its documented all-resource reset contract,
whereas this XTerm capture leaves the selected resources unchanged.

## Validation and limits

MinGW and GCC/Clang with ASan, UBSan and leak checking pass the new replay and
the existing keyboard, UDK, query, state-control and Win32-input suites. Tests
also cover bounded output capacity, invalid scalars and eight-bit C1 output.
The first mapping attempt incorrectly assigned PUA values to Pause/Scroll Lock;
the independent replies exposed 48 mismatches across whole/bytewise replay.
That failed mapping and log are retained, alongside the corrected source.

The native negative comparison uses the previous `8655aae` production source:
it fails the first new resource query. The fixed portable image passes all 235
native streams, and all three owned processes exit naturally. The negative
fixture's forced cleanup is retained and is not a passing shutdown test.
`extended-key-resources-fix.tar.gz` and its validation manifest retain both
images, source-built host sidecars, exact fixtures, source hashes, compiler
logs, raw native replies and cleanup records. All archive members are rehashed
after compression.

The [component workflow at 77ec984](https://github.com/xiongnemo/nemoterm/actions/runs/43772008360)
passes GCC/Clang ASan/UBSan and MSVC, including the 283-step replay in both
fragmentation modes and the 243-step Windows mapper replay. Original logs,
artifact receipts and source hashes are retained in
`extended-key-resources-ci.tar.gz` and its validation manifest. Source hashes
match the exact Git content; four existing `.inc` files have separately verified
CRLF variants in the Windows checkout. The new native check is included in
ordinary and single-image CI. Both complete workflows now pass at `77ec984`:
[ordinary run 43772008320](https://github.com/xiongnemo/nemoterm/actions/runs/43772008320)
passes all four jobs, and
[single-image run 43772008256](https://github.com/xiongnemo/nemoterm/actions/runs/43772008256)
passes **166 groups**. The product contains only a 4,547,072-byte EXE, SHA256
`7378ca16a2d229bea46721eabf65be0dbc30c588f2a0ef78d916ba77d5ddb1cf`.
Original product/core/single evidence ZIPs and all artifact/member checks are
retained as `extended-key-resources-product-ci-*` and the validation manifest.

Physical keyboard/IME behavior, Print/Menu/Help,
Ctrl+Pause/Break and keypad Tab/Space/Equal remain outside native acceptance.
Resource 0 is covered by the later [legacy modifier implementation](legacy-modifiers.md);
remaining keyboard/application scope stays open. The separate
[`8655aae` MSVC tab-selection access violation](tab-select-msvc-8655aae.md) also remains unresolved; passing
keyboard checks do not resolve it. No accepted executable is replaced.
