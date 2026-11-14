# Binding-test mailbox observation fix

Main source `57171fac07e6ce69d9d6e457d45f27d4abb3c7c3` failed its
[single-executable CI](https://github.com/xiongnemo/nemoterm/actions/runs/43566479649)
in `bindings_window_smoke.py`, with `KeyError: 'hex'` immediately after custom
copy. The final retained child report contains phase `alt-rectangle-False` and
the expected DSR bytes `1b5b306e`. Earlier integration source `9e7549b` passed
all 108 groups and exact-artifact acceptance; this later failure is retained
independently rather than being replaced by the earlier success.

`fixture_io.read_snapshot` returns `{}` after a missing file, sharing-denied read
or invalid JSON. The binding test indexed a fresh, single read without handling
that documented transient. The CI failure does not identify which underlying
read exception occurred; no particular Windows sharing violation is claimed.

The test now polls the report with the existing bounded `wait_snapshot`, fails
immediately on child errors/early exit, and requests a second DSR barrier after
each custom-copy action without resetting the input stream. It asserts exactly
two DSR replies and no forwarded key/mouse bytes. This both tolerates unavailable
snapshots and prevents a too-early read from missing unexpected queued input.
Clipboard text and all existing binding expectations remain exact. No product
source, resource threshold or arbitrary sleep was changed.

The failed CI image is 4,451,840 bytes, SHA-256
`16d15ab4928b421e3ef281153ec54c9e35ad8e4694213ab89c0066bb40738f21`.
It remains an unverified diagnostic artifact. Fresh owned local jobs checked:

* Original fixture plus one controlled empty report read after clipboard access:
  reproduces `KeyError: 'hex'` at the same assertion.
* Fixed fixture with ordinary reads: all five binding groups pass.
* Fixed fixture with an empty read after each of the two copy checks: both
  injected empty reads are consumed, all five groups and exact DSR bytes pass.
* Fixed ordinary fixture on the accepted `9e7549b` image, SHA-256
  `c239b4af83eb3ae341309c81f59afd7e7af8039f0c058a990eb7a9a5ac1cda84`:
  all five groups pass.

The controlled fault changes only the test's Python report reader. It does not
alter terminal behavior or returned console bytes. Each job drains all five
processes naturally without survivors; clipboard contents are restored by the
existing saved-clipboard guard. Only fresh owned windows receive injected input.

The [manifest](bindings-observation-validation.json) retains original CI metadata,
the failed log/final child report, old/fixed fixtures, the reproducible fault
driver, exact-image identity, positive results and cleanup. These are local/CI
observations, not REA-server Evidence. Full CI must run again with the fixture
fix. The accepted download remains the independently verified integration image.
