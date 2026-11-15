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

## Unix conversion follow-up

The first [component CI](https://github.com/xiongnemo/nemoterm/actions/runs/43755825392)
at `23c90fe` passes MSVC but fails the unchanged query suite on both GCC and
Clang with `FATAL ERROR: Out of memory`. The binary answerback test exposes a
second inherited defect in the Unix locale converter: it appends the converted
NUL repeatedly because it uses the zero return value as the consumed byte count.
For NUL, zero is the conversion result rather than a byte count; this distinction
is specified in [C draft N1570, section 7.29.6.3.2](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf).

The converter now advances through the NUL byte within the provided input
length, including any preceding shift sequence. The regression still requires
the NUL and all following bytes; it is not removed or changed to truncate the
answerback. The Windows conversion implementation is unaffected.

Local GCC and Clang ASan/UBSan builds each pass the unchanged query, keyboard,
state-control and ANSI suites. The ANSI suite checks all 243 retained streams
whole and bytewise. Full CI for the combined source remains pending.
`answerback-nul-unix.tar.gz` and its validation manifest retain the original
failed component logs, passing MSVC result, local configure/build/test records,
controller scripts, exact source and hashes. Initial local setup failures are
retained separately from the product failure; no assertion was relaxed.
