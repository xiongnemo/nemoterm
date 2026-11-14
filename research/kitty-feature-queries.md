# Kitty feature-query reference preparation

The current terminal transport recognizes `a=q,e=<action>` and preserves a
pending image upload, but terminal dispatch replies `ENOTSUP:feature query`.
Supporting the transport does not establish that feature discovery is implemented.
This checkpoint adds an independent observer only; product source stays frozen
while compression's formal single-image acceptance runs.

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
capture bounds and the no-truncation gate are unchanged. A complete accepted
capture is still pending. Its results must be reviewed before deriving
Nemoterm's supported subset and regression expectations. Unicode placeholders,
animation and the remaining graphics/protocol scope remain required work; feature
discovery is not a substitute for implementing those capabilities.
