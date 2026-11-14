# Bounded Kitty zlib compression: implementation checkpoint

The compression branch implements `o=z` for direct RGB, RGBA and PNG images.
The accepted downloadable `97d6025` executable predates this work. A new single
executable, full CI and GDI/DirectX memory acceptance are still required before
replacing it. This record does not claim those checks have passed.

## Independent behavior

[Upstream capture 43640064559](https://github.com/xiongnemo/nemoterm/actions/runs/43640064559)
used compiled, unmodified Kitty `8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f`
under REA. Its own image/PNG tests passed. The retained process exited naturally
with code 0, its owned process group was drained, and its temporary root removed.
The 26 cases contain 36 states, wire replies and native decoded image bytes.
The full raw capture has SHA256
`6e6cb02704aaa748749759a7b991c67d39908ec12ab89acb6bfa536438c86321`;
all original records are indexed by `kitty-compression-reference-validation.json`.
The failed first observer run is retained alongside the corrected capture.

Nemoterm's real terminal parser replays every captured input byte. Tests compare
successful/quiet replies, error codes and image identities, cursor positions,
dimensions, every decoded pixel and the shared graphics budget. Error prose is
implementation-specific. Upstream's empty internal image slots after invalid
loads are recorded in the raw capture and are not mistaken for decoded images.

The reference establishes stored/fixed/dynamic DEFLATE blocks, compressed raw
pixels and PNG, padded intermediate chunks, empty final chunks, queries and
quiet replies, exact PNG `S`, malformed data recovery, cancellation and replacement.
Kitty accepts trailing bytes and concatenated streams by using the first complete
stream; Nemoterm follows that observed behavior.

## Implementation and limits

The codec statically compiles the small `puff` decoder from zlib v1.3.1, preserving
its license and original source hashes. Marked adaptations make fixed Huffman
tables per-call, bound back-references by the RFC 1950 window and propagate
truncated input with explicit return codes instead of CRT nonlocal jumps. The wrapper
checks header fields, rejects preset dictionaries, validates Adler-32 and requires
exact output length. It does not allocate output or attempt an unbounded size scan.
The full notice is embedded by the single-image build. No Kitty GPL implementation
is copied into the product and no codec DLL is added.

Raw RGB expands backwards inside its final RGBA allocation. Compressed PNG needs
an exact, nonzero `S`; its encoded PNG buffer is counted together with decoded
pixels and metadata during admission. Existing transport (2 MiB), shared graphics
(4 MiB), image/placement and dimension limits are unchanged. Failed queries cannot
evict images, and decode failure releases temporary storage. Read-only cache
inspection does not change eviction order.

`test_zlib` checks all three block types using independently captured byte pairs,
every truncated prefix and smaller output size, neighbor canaries, checksums,
invalid headers, empty streams and first-stream handling: 528,446 checks locally.
Cache tests add overlapping PNG-buffer budgets, failed-decode cleanup, read-only
query preservation and non-mutating peek; the complete cache suite has 1,667 checks.
Transport (2,111,798 assertions), placements (2,719 checks), and the full terminal
Sixel/image parser suite also pass locally with GCC. Strict GCC compilation passes.
MSVC, Linux sanitizers and the source-built single image remain CI gates.

## Native development build, not accepted single image

The local GCC frontend is SHA256
`6abf7efdc4b84f8d5b8d7e821ad1fc3fb75f645c89c264ad3da48635abbc8c72`.
This development execution uses separate OpenConsole/conpty files; their hashes
are retained in each observation. GDI, actual OpenGL and actual DirectX each pass
29 exact pixel stages through the public image API. A separate GDI run reads the
presented client DC and passes the same 29 stages. Each owned job exits naturally.

The tests include native PNG decoding, all DEFLATE block types, partial uploads,
malformed data followed by recovery, alpha compositing, deletion and reset.
The complete observations, PNG/BMP frames and source hashes are retained in
`kitty-compression-local-validation.json` and `kitty-compression-local-evidence/`.
They establish functional pixels, not memory usage or a finished single executable.

Both ordinary and single-image CI include these pixel tests and an additional
compressed-PNG two-tab workload with unchanged strict GDI/DirectX memory policies.
The original uncompressed workload remains. File/shared-memory transport, animation,
relative placements and Unicode placeholders remain separate unfinished work.

## Rejected truncated-input path

The first local decoder used upstream setjmp/longjmp. Its size-optimized tests
and native pixels passed, but the separate O2 executable later exited with
`0xc0000005`. GDB observed a truncated-input call in Windows stack unwinding
through the CRT nonlocal-jump path; a subsequent debugger execution exited normally.
This does not establish a defect in a particular compiler or runtime. The adaptation
now propagates short-input errors explicitly through each bit/code reader, preserving
the public failure result. Optimization and boundary tests are unchanged.

The fixed O2 boundary executable passes all 528,446 checks in three separate
processes. The size-optimized frontend was rebuilt; all core tests and all four
29-stage native captures were repeated against its new hash above. The earlier
functional evidence remains under `kitty-compression-before-truncation-fix-validation.json`,
and failure metadata remains alongside the new records. No failing test result
is treated as success based solely on the shell controller exiting zero.

## First cross-compiler run

[Component run 43643569388](https://github.com/xiongnemo/nemoterm/actions/runs/43643569388)
on `1877f94` passed GCC and Clang, including ASan/UBSan and the terminal replay.
MSVC stopped at four `C4244` narrowing warnings promoted to errors before runtime
tests. The follow-up uses explicit casts only after existing symbol/literal/length
bounds; `/W4 /WX` remains enabled. Complete original results are retained in
`kitty-compression-ci-validation.json`. This first run is a failed run, and the
MSVC fix still needs its own completed CI result.
