# Kitty feature-query implementation checkpoint

The development branch now answers `a=q,e=<action>` without loading an image,
changing placements or advancing the cursor. The accepted `b3e03bb` single EXE
still predates this change and remains in `dist`; new single-image CI and local
product acceptance are required before replacing it.

Replies describe existing Nemoterm behavior: direct RGB/RGBA/PNG, zlib compression,
ordinary placement and the implemented deletion selectors. Unsupported actions
omit `e`; unsupported keys/values are omitted. File/shared-memory media, indexed
formats, animation, Unicode/relative placements, file offsets and transient-use
hints are not advertised. Axis and encoded-size values respect the existing
8192 / 2 MiB bounds. Discovery does not promise that a later image allocation
will fit the shared budget or that a combination of supported keys is valid.

The transport preserves unfinished uploads across feature queries, including
`m=1`, ignores their payload, and lets the owner suppress queries without an ID.
The selector on ordinary transmissions is ignored, matching the observed
non-query control. Reply construction uses bounded stack storage; feature
dispatch does not construct the image cache or placement owner.

## Independent replay and deliberate differences

The [independent reference](kitty-feature-queries.md) retains all original
84 cases / 176 states and their upstream source identity. The generator keeps
the original reply next to the product expectation. For 22 cases it explicitly
removes named unsupported capabilities from the captured reply; it never adds
capability fields. The original state records are unchanged.

Eight states during unfinished uploads contain an empty internal upstream image
slot. The comparison retains that original count separately and excludes the
unfinished slot from Nemoterm's complete-image count. Cursor, placement geometry,
wire replies and the completed upload remain checked. Exploratory failures from
before this distinction and before the implementation corrections are retained;
their changing fixture snapshot is not claimed as independently pinned evidence.

The real terminal-core replay passes all 176 states, along with the existing
101 terminal states and 36 compression states. Additional checks cover the
8192/8193 and 2 MiB boundaries and 1,000 repeated queries without graphics-owner
memory growth or construction of an image cache. Transport, cache, layout and
placement suites also pass locally.

## Native development frontend

The MinGW development frontend is 3,983,001 bytes, SHA256
`847240905f74f4abfdd124efe3a9616905e0e2d1ad44430e71ebb52c8688105a`.
It uses the separately identified bundled ConPTY DLL/host, not the accepted
single-image packaging. Through the actual ConPTY input/output path, all
176 stages pass on each actual GDI/OpenGL/DirectX backend (**528 API stages**).
A separate owned visible GDI client-DC capture passes another **176 stages**.
Each stage checks exact reply bytes, including the input barrier, plus retained
seed pixels and successful completion of interleaved uploads. All four owned
process groups exit naturally. The fixture requests SarasaTermSC Nerd Font Light.

`kitty-feature-implementation-validation.json` indexes 1,439 byte-verified
original records in a deterministic tar/gzip archive, source and fixture hashes,
renderer identities and cleanup. This is not physical-input, full-grid memory,
single-image or complete terminal-protocol acceptance. The original remaining
graphics and real-application requirements remain open.

The full/component CI workflows now check the generated fixtures; ordinary and
single-image native suites include the new query replay.
[Component CI 43653882971](https://github.com/xiongnemo/nemoterm/actions/runs/43653882971)
passes all three strict GCC/Clang/MSVC jobs at `6e05bd1`, including real-core replay
and GCC/Clang ASan/UBSan. Its original logs and artifact identities are retained
in the validation manifest. Full ordinary/single-image CI is still running.
A separate integration run on unchanged
compression product source (`2f478e7`, run `43652684756`) recorded an MSVC native
tab-fixture access violation after hover-probe detachment; that failure remains
under investigation and is not erased by these query passes.
