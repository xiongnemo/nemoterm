# Explicit artifact replay sources

The main integration `683f8c3` triggered two historical diagnostic workflows:
[font zoom/bell 43638850816](https://github.com/xiongnemo/nemoterm/actions/runs/43638850816)
and [rectangle capture 43638850791](https://github.com/xiongnemo/nemoterm/actions/runs/43638850791).
Both failed before running their fixtures because their hardcoded source
commits (`9bef907` and `f6b3d64`) differ from the integrated production source.
The identity guards correctly prevented testing a stale executable as if it
represented the current source. Complete failure logs and run metadata are
retained in [the validation manifest](replay-workflow-validation.json).

These workflows now run only through explicit `workflow_dispatch`, with
required `source_commit` and `source_run` inputs. Before downloading, they
validate input syntax, require a successful completed source workflow whose
head SHA matches the requested source, and compare all vendored/native sources
and the build recipes. The downloaded manifest must still match the source,
actual executable size and SHA-256. A mismatch remains a hard failure; no
fixture is allowed to claim a different image's result.

For the current implementation, a suitable independent source-host artifact
comes from commit `97d60254e3bae94fbba9803ff15e1abfce5373f8`, core run
`43633479250`. Its executable hash is `355d0e83a9153dee3b2e6193cfcc215b931fbce93785d7e9d23a456256051429`;
it is separate from the accepted formal single-executable hash `07c8d279`.
These replays diagnose fixture behavior and do not perform a new build or
replace full CI or exact-product local memory acceptance.

Regular core and single-image workflows already include zoom, bell and
rectangle checks. They retain their normal push triggers; only the two
historical artifact replays require an explicit artifact selection.

## Corrected executions

Both explicit replays pass at fixture commit
`4b3cf8ad34063636a54310e9e5d99e4ac6a6d4b1`:
[font zoom/bell 43639226136](https://github.com/xiongnemo/nemoterm/actions/runs/43639226136)
and [rectangle capture 43639229046](https://github.com/xiongnemo/nemoterm/actions/runs/43639229046).
Both source/run guards pass, and both downloaded identity records name the
expected `97d6025` source and `355d0e83` executable. The font replay completes
zoom pixels/input, sibling tabs/settings, audible-bell API and visual-bell
checks; rectangle replay completes cropped/frozen-tab and GDI/DirectX full-frame
checks. Their 24 evidence files, complete logs and artifact/run metadata are
retained in the validation manifest alongside the original failures.

Local PowerShell parsing succeeded for all modified workflow blocks. The
production comparison accepts `97d6025` and still rejects both historical
fixed source commits. These workflow-only changes leave the accepted local
`07c8d279` executable unchanged and do not cancel the full `683f8c3` workflows.
