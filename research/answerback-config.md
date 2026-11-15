# Configured answerback escape recovery

The inherited `ctrlparse` helper promises to set its continuation pointer to
NULL for an unrecognized control-character escape. It did so for ordinary
text, a lone caret and malformed numeric forms, but omitted the assignment
for unsupported two-character forms such as `^!` or `^0`. A caller's previous
continuation could therefore survive a failed parse. The answerback loader
expects NULL so it can preserve the original text literally.

The product fix initializes the continuation to NULL on entry. Successful
caret, numeric and literal-caret escapes still set their original continuation
and byte. No new allocation, terminal state or dependency is introduced.

Core regression evidence covers 15 invalid vectors, 13 valid vectors, literal
ENQ replies in both C1 framing modes, and a binary answerback containing NUL.
The original code fails eight deterministic continuation assertions. The
regression stops before exercising the ambiguous continuation through the
terminal on that original source. After the fix, all checks and the existing
query suite pass.

The native fixture runs four configurations in input code pages 28591 and
65001. Its 160 exact comparisons cover reset, alternate screen, saved cursor,
DOCS encoding changes, conformance level 61, VT52, an enquiry inside CSI, and
an enquiry inside an OSC payload. Literal text, CR/LF, NUL, ESC, DEL, numeric
forms and the empty configuration survive the real source-built ConPTY host.
All eight jobs, containing 24 processes, exit naturally. There is no physical
input or clipboard access.

These expectations come from the PuTTY configuration contract, including its
documented `^C` and `^~` notation, not an XTerm oracle. The first successful
probe used a generic helper argument whose log misleadingly labelled the
cases as XTerm. That original output is retained; the final fixture explicitly
classifies the same expectations as direct configuration cases and passes
again. No original capture is rewritten.

`answerback-config.tar.gz` and its validation manifest retain both native
captures, the original core failure, fixed core result, source, fixtures,
exact frontend and source-host identity. The frontend SHA256 is
`2a53c4c46900cfe1083a323e592dc3b692e2c3ce1526f7699494d09c75d61c31`.
This portable diagnostic is not a final single-image acceptance. Unicode
configuration, exhaustive numeric syntax, and complete xterm compatibility
remain separate work. CI now includes the core and native regressions.
