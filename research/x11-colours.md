# X11 named colours: source and build checkpoint

## Current remote verification (2026-11-14 Sydney)

The extended `test_colour` and `test_osc_colour` suites pass in the remote
Windows core and Linux sanitizer jobs at `d2aa14a`; their workflow later fails
the separate upstream-host guarded-area check. The
[retained validation](reset-palette-validation.json) records that failure and
the successful 88-group single-image run. This establishes product parser
coverage. The subsequent [independent run 43468632067](https://github.com/xiongnemo/nemoterm/actions/runs/43468632067)
matches all 66 batches: 782 table names, 782 case variants and ten rejected
names. The [manifest and raw captures](x11-colours-reference-validation.json)
identify XTerm(412) and the installed X11 libraries/server. No local runtime
test was needed for this checkpoint. The remaining sections preserve the
initial source/build checkpoint.

The first capture failed because a query was placed in the same OSC 4 command
after an invalid name. The pinned XTerm
[`ChangeAnsiColorRequest`](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/misc.c#L2815-L2860)
stops processing that command on a colour-allocation error, so it omits the
query. The follow-up uses separate set and query commands to observe the old
sentinel colour after rejection. The original 66-batch capture is retained;
this correction does not claim malformed combined-command recovery parity.

## Implementation

The shared OSC colour parser now contains all 782 names from the pinned Xorg
server 21.1.16 `os/oscolor.c` table, replacing the eight-name whitelist. This
includes grey ramps, numbered shades, case-insensitive matching and the exact
space-separated aliases present upstream. For example, `gray50` is `(127,127,127)`,
`gray` is `(190,190,190)`, and `WebGray` is `(128,128,128)`. It does not apply CSS
colour meanings or silently remove arbitrary whitespace.

The original source, exact download/content hashes and notices are retained
under [tools/x11/xorg-server-21.1.16](../tools/x11/xorg-server-21.1.16/README.md).
The offline generator validates every offset against the corresponding source
name, RGB ranges, unique case-folded names and sort order. Builds consume
committed generated data; CI checks that it regenerates without differences.
No X server implementation is compiled, and no X11 runtime dependency is added.

## Storage and parser boundaries

The product uses binary search over immutable data with 16-bit name offsets.
The MSVC object contains 7,615 string bytes and 4,692 table bytes in `.rdata`,
with zero relocations in either data section: 12,307 bytes total before linker
alignment. There are no per-terminal fields, caches, allocations or locale
lookups. The final image's colour strings are in its non-writable `.rdata`.
These static sizes are **not** a working-set measurement or memory acceptance.

Input remains an exact bounded byte slice, with a 22-byte upper bound determined
by the longest upstream name. Failure leaves the output colour untouched.
The established numeric semantics are unchanged: `rgb:f/f/f` is white while
legacy `#fff` is `(240,240,240)`. `rgbi:` and other Xcms device-profile colour
spaces remain unsupported. This fixed table does not claim to emulate arbitrary
Xlib client databases, server modifications or user resources.

The shared parser supplies indexed OSC 4 colours, default OSC 10/11/12 colours
and the development branch's OSC 17/19 selection colours. Their existing reset
and palette-stack behaviour is unchanged by this patch. Selection-colour
runtime verification is still pending separately.

## Prepared checks; runtime remains paused

`test_colour` now checks all 782 names with four case variants, exact allocated
slices without terminators, embedded NULs, extra suffixes and unchanged failure
outputs. Explicit cases distinguish X11 from web colour meanings, invalid
spaces and out-of-range numbered shades. Existing exhaustive numeric checks
remain. `test_osc_colour` adds all names through byte-fragmented OSC 4 with
alternating BEL/ST terminators and representative default/selection operations.

These are source-derived expectations, **not captured XTerm results**. The
prepared `tests/xterm_x11_colour_oracle.py` separately captures 66 batches covering
1,574 spelling/invalid-input cases, retains raw replies, and only then compares
them with the pinned source expectations. It has not been run. Any XTerm/Xlib
resource or parsing differences must be investigated when execution resumes.

The [build manifest](x11-colours-build-validation.json) binds source hashes,
raw logs and the unverified image. MSVC built the frontend and both extended
test targets; Linux compiled and linked both test targets with ASan/UBSan;
the existing source-integrated OpenConsole overlay linked the single EXE.
Only its licence resource was refreshed; the overlay was not regenerated.
Python syntax compilation, generator freshness, PowerShell AST parsing and
Git whitespace checks passed. Static image inspection confirms the complete
updated licence resource, including the original Open Group and DEC notices.
An initial LF-only byte search did not match the Windows CRLF resource; the
follow-up checked the exact resource bytes and CRLF notice, without running
the image. The portable comparison build also copies the notice alongside
its other licences, and the pending single-file runtime fixture checks it.

**No new binary, unit test, sanitizer test, XTerm session or desktop fixture
was executed.** The candidate is staged separately under
`build/local-x11-colours-unverified/dist/nemoterm.exe`; accepted main and the
last native-tested palette-stack image retain their prior hashes. Run the
core suites and independent reference capture first after testing resumes,
then native protocol/regression and uninstrumented GDI memory checks. Prior
runtime passes do not transfer to this image.
