# Independent Kitty feature-query reference

At the reference-only checkpoint, terminal dispatch still replied
`ENOTSUP:feature query`. The subsequent [development implementation](kitty-feature-implementation.md)
passes core/native replay. The accepted `6e05bd1` single image has a separate
[product checkpoint](kitty-feature-product.md).
The independent source capture below remains unchanged.

Kitty's [feature-query specification](https://sw.kovidgoyal.net/kitty/graphics-protocol/#querying-support-for-protocol-features)
defines a non-mutating query for each action and value. An implementation should
report the capabilities it actually supports; unsupported actions omit `e`, and
unsupported values omit their keys. The query ignores payload and preserves an
unfinished image transfer. It cannot stand in for attempting a real transfer.

The new `kitty-features` option in `protocol-reference.yml` builds unchanged
upstream commit `8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f`, runs its own image/query
test, and uses REA 6.8.0 to capture `tests/kitty_features_oracle.py`. The observer
contains 84 input cases and 176 states: supported and unknown actions, per-action
keys, formats/media/compression, flags, zero and limit values, deletion selectors,
identity and quiet handling, malformed/duplicate fields, ignored payloads,
bytewise input, and four queries interleaved with pending image transfers.

Each case begins with a real image placement. Input/reply bytes, native cursor,
image count and native layer geometry are retained after every step. The fixture
does not synthesize expected replies or copy upstream implementation into the
product. It creates no OS window and does not establish rendered GPU pixels.
Completion requires the upstream test without skips, all states, natural process
exit, verified REA cleanup and an exact observation-file digest in the capture.

The [first capture run 43648565834](https://github.com/xiongnemo/nemoterm/actions/runs/43648565834)
completed all 84 cases and 176 states, passed the upstream test and exited
naturally with verified cleanup. It nevertheless failed the untruncated-evidence
gate: REA retained all 4,850 raw PTY bytes and hashed the complete 194,123-byte
observation file, but omitted 19 of 98 cumulative rendered terminal frames after
the 262,144-byte output budget filled. The observation SHA256 is
`cffa489fa0c80ffb31b6b24c62492d4098868e94189fd36691cab48a4febe0d5`.
The original failure is retained in `kitty-feature-query-validation.json`.

The follow-up declares a 524,288-byte terminal-record budget specifically for
this larger reference family. Inputs, observations, process deadlines, file
capture bounds and the no-truncation gate are unchanged.

[Follow-up run 43649195027](https://github.com/xiongnemo/nemoterm/actions/runs/43649195027)
at `6ba7345` passed. REA retained all 97 rendered frames (374,752 cumulative bytes),
reported no truncation, and verified natural exit and cleanup. The full observation
file is 194,123 bytes, SHA256
`d3e775257cfcf70308d88030f2b0bbee5f81a860b15eae4d9911a4ea2dc227ac`,
bound to Evidence
`ev_94e4121d9aaa143279c6944e6ac364598b44df00762d37eb8e3f9e45e984de75`.
Fixture/source hashes and all 176 input/reply/model states match the first run.
The validation index retains 27 raw records across both runs, including the
original failed recorder evidence.

The observations establish several details for the next implementation:

- Unknown requested actions return `OK` without an `e` capability key.
- Explicit `f=32` and `t=d` can appear in replies even though they are ordinary
  transfer defaults; zero numeric fields are omitted. Keys depend on the action.
- Successful quiet queries suppress replies. All four interleaved queries leave
  the pending upload usable, including a feature query carrying `m=1`.
- Ignored payload includes invalid base64 and a payload larger than an ordinary
  chunk. The observed query leaves the existing image, cursor and layers intact.
- Missing/zero query IDs and parser-rejected media/compression values produce no
  reply. Simultaneous nonzero `i` and `I` produces an identity error.
- In the explicit non-query control, upstream ignores `e` and performs the normal
  image transmission. That case is recorded separately from non-mutating queries.

The implementation derives its reported capabilities from its own supported
actions, formats and limits, while preserving the observed query/lifecycle behavior.
Its explicit unsupported-key projections retain the original replies. Unicode
placeholders, animation and the remaining graphics/protocol scope remain required
work; feature discovery is not a substitute for implementing those capabilities.
