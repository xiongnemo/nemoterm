# Codex startup: late foreground and background colour replies

On the hosted Windows desktop, the first prompt submitted by real Codex on `b5d4514` sometimes contained the terminal's foreground and background colour replies. Selection had not started yet. On run `44275373394`, all three real GDI cases failed and all three DirectX cases passed. The [selected original failure records](agent-startup-5344f4e.zip) retain the client output, screen, generated prompt receipt and the distinct Claude startup failure from the same run. The model service ran only on loopback.

A separate native Windows console reader replayed the exact paint bytes saved from both renderer sessions, then requested OSC 10 and 11. For each renderer it also ran a no-paint control, both with and without a prequeued `k`. The timer ended when the application had read both replies through `ReadConsoleInputW`. These are observed timings, not a guarantee for every machine.

| Actual renderer, with captured paint | Original `b5d4514`, run `44275928298` | Candidate `ba91594`, run `44277391833` |
| --- | ---: | ---: |
| GDI, four cases | 690.60–724.34 ms | 33.08–37.97 ms |
| DirectX, four cases | 228.89–249.27 ms | 11.02–12.14 ms |

The no-paint controls were below 1 ms on both images. All 12 candidate cases met the 250 ms client deadline. In the original and candidate key records the two colours arrived exactly once, in sequence; the queued `k` was preserved when provided. Replaying the captured paint also produced a device-attributes reply, separate from the colour replies. Both copies of the native recordings include individual input events, process cleanup and executable identity: [original](console-colour-b5d4514-input.zip), [candidate](console-colour-ba91594-input.zip). Candidate EXE SHA-256: `c4963dba443aa810a3274d9cfcef92c1fb685f262e1573e37de629dfa6f48620`.

`ba91594` avoids taking a physical snapshot of the window when a complete buffered synchronized update only changes drawing attributes, places the cursor on its existing cell, or reasserts its current visibility. Real text, cursor movements, queries, split writes and ambiguous controls retain the original snapshot path. The native timing test, the real-client selection tests and the renderer memory tests are independent acceptance checks.

The actual Codex client then passed all six Windows desktop cases on the candidate in run `44277391833`: GDI and DirectX each passed Shift-drag with Ctrl+Shift+C/V, default right-click copy, and opt-in right-click copy and paste. The client asked for mouse tracking; the provider recorded the selected Unicode text exactly once in each submitted request. [Six receipts, screenshots, and two separate Claude startup failures](codex-ba91594-selection.zip).
