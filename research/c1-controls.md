# C1 transmission and operating level

S7C1T/S8C1T now select the framing of generated CSI, SS3, DCS, OSC and ST
records. Defaults and RIS use seven-bit framing. Literal text, UTF-8 input,
configured answerback and the private ConPTY 9001 transport remain separate.
One boolean and stack buffers implement the conversion; it adds no cache or
runtime dependency.

DECSCL levels 61–65 perform the soft reset and select the operating level.
At levels 62–65, Pc 0/2 selects eight-bit framing and Pc 1 selects seven-bit.
Level 61 and invalid Pc values preserve the existing transmission selection;
S7C1T/S8C1T are ignored at level 61. DECRQSS `"p` reports the current level and
control selection above level 61. Existing PuTTY compatibility extensions remain.

The independent capture uses XTerm 412, executable SHA-256
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
It retains 144 raw byte streams. The generated exact comparison covers 141;
two default-palette observations and one title-policy observation are retained
but excluded from equality because those resources differ. Deterministic colour
set/query assertions separately verify OSC framing and BEL/ST termination.
The oracle covers mode changes, omitted/invalid parameters, resets, save/restore,
alternate screens, DOCS, representative replies and DECSCL state effects.

ConPTY consumes UTF-8 characters, so its generated C1 controls are encoded as
U+0080–U+009F on that pipe. Console clients read the resulting characters through
their selected code page: ISO-8859-1 yields original C1 octets; UTF-8 yields
two-byte encodings. Windows DOCS changes the console code page itself; the
fixture checks this behavior explicitly. Other backends retain raw C1 octets.
The fixture changes only its own console, restores its initial code page and
sends messages only to its owned HWND.

Development validation passes eight MinGW core suites and seven Linux
ASan/UBSan suites with leak detection (the Linux build has no mouse target).
Both native code-page variants pass all 141 queries plus CSI/SS3 keys,
modifyOtherKeys, Kitty text and literal-text checks and exit naturally. Final
CI and downloaded single-image validation are recorded separately when complete.

Initial failures are retained: an oracle barrier that attempted S7C1T at level
61; raw C1 rejection by the UTF-8 ConPTY pipe; DOCS changing the fixture's input
code page; and a new modifyOtherKeys assertion missing its explicit `;1`
modifier. The latter was corrected from the existing independent keyboard
contract, not by relaxing equality. Review also caught the legacy `ESC % 8`
alias adjacent to the new parser cases; a regression assertion preserves its
UTF-8 designation without changing C1 transmission.

This is bounded transmission coverage, not complete C0/C1 input-parser, VT52,
charset, keyboard-layout or XTerm conformance. Renderer memory and lifetime
acceptance remain independent.

The [validation manifest](c1-controls-validation.json) retains 210 compressed
records with decoded and compressed SHA-256 hashes, including every local
failed attempt. The final development frontend is
`960f1ea3e8ed9691ddff355b32c2ee2f83138238986e457565745e114ef87d0a`;
both code-page runs exit naturally. Its separate automation recheck passes all
nine interface groups, compares screenshots with zero differing channels and
drains all ten processes owned by the outer test job. Those small-window
observations are not the Sarasa 160x48 memory acceptance workload.

## Downloaded single-image checkpoint; compiler repeat pending

Source checkpoint `517124f30da646ff2d67b589226a5259002dd117` passes all 101 groups
in [single-image integration](https://github.com/xiongnemo/nemoterm/actions/runs/43534154789).
Artifact 14090051527 contains the 4,450,304-byte EXE, SHA-256
`4beee874e66f49981ad39b6887cb05852fd77d7afea19cb0eac5346f7823527f`.
Its two C1 code-page fixtures each pass 141 reference cases and five key/text
checks remotely and again locally. The downloaded image also passes all nine
automation groups locally with identical reference/API pixels and natural exit.

The unmodified local GDI workload obtains SarasaTermSC Nerd Font Light at
160x48, passes all nine groups, and drains 56 inner / 58 outer processes
naturally. Across 453 samples over 48.979 seconds, frontend peaks are
16,269,312 private-working-set bytes, 43,118,592 total-working-set bytes and
18,931,712 private-commit bytes. Sampling uses no target injection or trimming.
This is a GDI result; DirectX's outstanding limits are not closed by it.

The first [compiler/core/native run](https://github.com/xiongnemo/nemoterm/actions/runs/43534154821)
passes sanitizer, MSVC renderer and source-host jobs. The Windows job reaches
its overall 20-minute deadline during the final memory-workload step and is
cancelled, so the full workflow is not a pass. All preceding Windows steps
report success; partial results and the job log are retained. Commit `cb52a3c`
changes only the Windows whole-job deadline to 30 minutes; product and test
sources are identical. Its [full repeat](https://github.com/xiongnemo/nemoterm/actions/runs/43537297417)
is still pending and remains a merge gate. No numerical resource or memory
assertion or individual test timeout was relaxed.

The manifest now retains 303 compressed records. This branch is not yet merged;
the accepted local `dist/nemoterm.exe` remains unchanged.
