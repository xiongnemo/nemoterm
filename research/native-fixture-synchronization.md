# Native fixture input synchronization

The first CI pass for `21e0c368aab4aae16b96fa004e64140bc4eb71b6`
exposed two test-harness issues after the rectangle implementation:

* [Single executable run 43163829459](https://github.com/xiongnemo/nemoterm/actions/runs/43163829459)
  failed the hyperlink capture-cancellation assertion. Its error message already
  contained the required `CSI <35;4;2 M` motion report. The assertion and its
  error argument called `data()` separately, each using a fixed 60 ms delay.
  `SendMessage` completion only establishes frontend dispatch; the ConPTY reader
  and JSON publisher can still be behind it.
* [Test/build run 43163829429](https://github.com/xiongnemo/nemoterm/actions/runs/43163829429)
  completed every rectangle assertion, then failed while printing its Unicode
  copy result to a cp1252 stdout pipe. The saved JSON had already been written.

`mouse_fixture.py` now accepts an optional, unique `input_barrier` token without
changing the phase, clearing input or resetting mouse modes. It emits a status
query (`CSI 5 n`) and acknowledges the token only after its reply (`CSI 0 n`)
arrives through the same ordered ConPTY input path. Hyperlink assertions wait
for that acknowledgement and inspect one captured byte string. Required reports
and forbidden button reports are still checked; there is no retry of the mouse
action or relaxation of those assertions. Fixtures that do not request this
barrier retain their existing behavior.

The rectangle success log uses JSON escaping, preserving the Unicode value in
the evidence while making console output independent of the pipeline encoding.

Local validation used rectangle executable SHA256
`203ad359ea9eebe5bfa6288a291b444525ba15b85dec3c7d0a9ecc4bf75a69b8`:

* The entire hyperlink fixture passed with its ordinary 40 ms publication loop.
* A separate isolated copy passed with publication slowed to 150 ms, longer than
  the former 60 ms assumption. This delay is only in the local experiment copy.
* The complete rectangle fixture passed with `PYTHONIOENCODING=cp1252`.

These changes address the observed input-snapshot race and log encoding failure.
Earlier intermittent local hover-refresh and URI-launch timeouts have a
different symptom and remain unproven; this result does not claim to fix them.
