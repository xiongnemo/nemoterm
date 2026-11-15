# Legacy enquiry and device replies

This bounded audit replaces source-only assumptions for ENQ, DECID and
DECREQTPARM with original wire captures. It does not establish complete xterm
compatibility or acceptance of the executable used for diagnosis.

The reference is a fresh build of pinned XTerm source
`5c75ead9a75d4b2e666ca06fa94503b5766ed93f` (XTerm 412), with an empty tracked-source
diff. Each profile runs on a private Xvfb display. The retained bundle includes
the full source archive, build/configure logs, compiler identity and exact ELF.
Two VT525 answerback profiles capture 188 streams each; a separate VT100 profile
captures 136 parameter streams, for 512 reference streams in total.

The exact `d914972` single image, SHA256
`9f15af510a028880153e7cda4c261c7525583edb8714a1a76fae280d8dff24b0`,
captures all 376 corresponding native streams with natural cleanup. This is
the unverified image retained from cancelled run `43748775754`, not a promoted
product. Its production source is unchanged at the later `5f5e80c` fixture fix.

- 284 replies match the VT525 reference exactly after the explicitly recorded
  Windows input-codepage representation of C1 controls. Both original byte
  streams remain intact. This includes 38 ENQ cases using explicit empty/ASCII
  answerback settings and two VT52 device-identification cases.
- 64 identity observations check DECID and primary DA as aliases in each
  product, including reset, alternate-screen, charset and 7/8-bit reply states.
  The products' numeric capability identities differ and are not rewritten.
- 28 parameter replies differ from VT525: Nemoterm's inherited handler answers
  valid requests with fixed baud codes `112`, whereas XTerm only implements
  this report for VT100-class identities. The separate VT100 capture returns
  baud codes `128`. Its 24 replies also include ten colon-parameter streams
  that the audited Nemoterm image ignores. The syntax fix below addresses
  those ten streams; the identity and baud-code differences remain explicit.

The first native capture used the older portable comparison runtime. It timed
out on an enquiry embedded in a cursor query. A separate ordinary cursor query
also exposed reply reordering after reset. The bounded frontend pipe trace
records the old OpenConsole's untagged internal `CSI 6 n`: it can consume an
application CPR and expose the later response. The current source-built single
image preserves the original enquiry/cursor stream and subsequent marker in
the correct order. No parser or host code was changed during this audit.

`legacy-reply-reference.tar.gz` retains those original failures, partial
captures, the diagnostic trace, complete later captures and both reference
profiles. Its adjacent validation manifest hashes every record. The probe's
generic log line saying cases "passed" means capture completed; actual equality
is determined by the separate comparison JSON and the distinctions above.
Unicode answerback settings, control-notation configuration, every simulated
identity and the full malformed-input matrix remain unverified. No clipboard
or physical desktop input is used, and the instrumented trace is not a memory
measurement.

The reference's model-dependent parameter behavior is documented in its
[pinned control-sequence source](https://github.com/ThomasDickey/xterm-snapshots/blob/5c75ead9a75d4b2e666ca06fa94503b5766ed93f/ctlseqs.ms).

## Parameter syntax follow-up

The DECREQTPARM handler now follows the retained VT100 reference's treatment
of colon subparameters: discard the parameter list and use request zero.
This applies only to unprefixed `CSI x`; unrelated commands and overflowing
sequences keep their existing rejection rules. Nemoterm's inherited fixed
baud codes `112` and model-independent reply policy are unchanged.

`scripts/generate-legacy-parameter-reference.py` verifies the original archive
hash and projects its 136 unchanged request streams into core and native
regressions. The original replies remain alongside the expectations. Only the
documented baud codes and level-5 S8C1T framing differ from the VT100 oracle.

The core suite replays all streams whole and bytewise: the original source
fails 20 checks (ten streams in both modes), and the fix passes the entire
query suite. A native baseline using the current patched source host fails
the first colon request. The fixed portable frontend then passes all 136
streams with each Windows input code page, 28591 and 65001 (272 comparisons),
and both jobs exit naturally. This includes exact no-reply checks, private
prefixes, invalid arguments and recovery before the following marker.

`legacy-parameter-fix.tar.gz` and its validation manifest retain the original
failures, fixed reports, exact frontends, source-built host, fixtures and
changed parser source. These are bounded portable diagnostics, not acceptance
of a final single executable or a claim of full xterm identity parity.
The generated data and native replay are also included in CI.
