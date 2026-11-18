# Real-client clipboard boundaries on the ba91594 Windows executable

All observations here use hosted Windows runners. The executable is 4,859,904 bytes, SHA-256 `c4963dba443aa810a3274d9cfcef92c1fb685f262e1573e37de629dfa6f48620`.

## Where a combining accent changes spelling

With mouse tracking active, the real Claude Code UI drew the generated reply using `e` followed by U+0301. On GDI and DirectX, system Shift-drag selected the visible cells and Ctrl+Shift+C replaced an image-only clipboard with the original string, including the original accent, Chinese text and both private-use characters. On the same image the Messages request, after Ctrl+Shift+V and Enter, contained a precomposed U+00E9. The original byte-identical HTTP test failed on both renderers: [application output, screens, requests and first failure](claude-submit-0b32187.zip), run `44280466475`.

[Independent hosted controls](claude-independent-unicode.zip), run `44285499650`, artifact `14418797924`, SHA-256 `97555c76b216fe811964f87c354d1edfb31801130b860f88f8e9b4f1bd70344c`:

| Input path | Receiver | Exact observation |
| --- | --- | --- |
| Nemoterm GDI, system Ctrl+Shift+V | Native console input reader | Bracketed paste contains the original UTF-8 `65 CC 81` |
| Nemoterm DirectX, same gesture | Native console input reader | Same bytes, with the same Chinese and private-use characters |
| Windows ConPTY, directly written bracketed UTF-8, no Nemoterm | Pinned Claude Code and loopback Messages API | U+00E9; one complete matching user part; no tools |
| WinPTY, same direct input, no Nemoterm | Same Claude executable and API | Identical independently observed user part |

The Claude executable SHA-256 was `345996b4bdbae21d817f750fae2f34cbf8d81224a5444c78136091d121beb298`. Each independent driver recorded its own input; no user clipboard was involved. All four processes closed naturally. The first [minimal launcher](claude-system-conpty-first.zip), [handshake](claude-system-conpty-handshake.zip) and [explicit-handle](claude-system-conpty-explicit.zip) trials did not reach an interactive client; they are not client-reference evidence. The successful control uses a hash-pinned pywinpty wheel on the runner only. It adds no dependency to Nemoterm.

The client-specific test binds its expected HTTP spelling to both observed reference hosts, the exact client hash, and the original user part. Clipboard and native input remain byte-exact. Additional `q` + U+0301 cases use a combining sequence with no precomposed equivalent: the keyboard shortcut and both right-click policies must reproduce the same bytes at the HTTP boundary. All other clients keep their exact original-text gate.

In [exact-image run 44286244961](claude-gestures-1e677b2.zip) all eight real Claude cases passed. On each renderer, the `e` + combining accent case matched the two independent native client references; the `q` + combining accent reached the provider byte-for-byte using the keyboard shortcut, default right-click copy followed by paste, and optional right-click copy-and-paste. All eight required an exact system clipboard, pixel checks at both selection boundaries, exactly one expected user part and natural process cleanup. The agent group was **26/28**: the two outstanding failures were Codex image-paste via the window API and via system input. This group is not a successful full-suite result.

## Image paste and shell regression

Run `44283406122` [tested both a real system keyboard and the window API](agent-image-system-625bb73.zip). OpenCode submitted the exact generated 32×16 checkerboard using both Ctrl+V and Ctrl+Shift+V, via both input paths. Codex did not paint an image after Ctrl+V in either path; these fixtures stopped before Ctrl+Shift+V. The independent PowerShell reader retrieved clipboard image data in the failed system-input case. [Selected Codex log query records](codex-image-client-logs.zip) did not contain a clipboard diagnostic. Subsequent fixtures keep the raw application output at the gesture and continue to the other shortcut in a fresh isolated client while still failing the original case.

In the original full run `44277391833`, **55 of 58** interactions were verified; two Claude HTTP cases and the Codex image case failed. The single-executable suite also stopped at the Codex image case. This is why this image is a preview. The shell lifetime fixture initially failed during preparation because it required a CLI argument for an unrelated client. After fixing preparation, [the exact-image shell replay](ba91594-shell-checkpoints.zip) (`44281108834`) ran all 24 Git Bash duplicate/close cases (12 ordinary, 12 observed) with natural cleanup, and all six late-client controls passed. The original failures remain recorded.
