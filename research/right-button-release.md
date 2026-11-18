# Right-click after copying a terminal selection

A local copy consumes the right-button press. If its release goes to another window, the terminal never sees that release. Previously the next right-click in a mouse-tracking application inherited the old local flag: the application received a press but no release, and the terminal could retain mouse capture. `f628d89` clears the stale flag when a new right press is routed through the application's normal input path. Default copy, optional copy-and-paste and the context menu still consume their own gestures.

The before image is `ba91594` (`c4963dba443aa810a3274d9cfcef92c1fb685f262e1573e37de629dfa6f48620`). The fixed 4,859,904-byte executable from run `44298297621` is `bce43b16e14965bf54dc5797e098eb8e26bf8924b20870e61ad4301525bff5a2` (source artifact `14424658437`). All runs used disposable GitHub-hosted Windows desktops.

| Same sequence of Win32 messages delivered to the terminal | Before | After |
| --- | --- | --- |
| Shift-select the five cells `LOCAL`, then copy by shortcut and right click | `LOCAL` both times | `LOCAL` both times |
| Bytes forwarded to the application by the local copy | None | None |
| Right-click in the application at column 8, row 5 | `CSI <2;8;5M` only | `CSI <2;8;5M`, then `CSI <2;8;5m` |

GDI and DirectX independently showed these same bytes, bounded by device status replies in the child process. The controlled window-message runs on the old (`44298913494`) and fixed (`44298969162`) images used identical fixtures. An earlier physical test (`44298204216`) timed out preparing a selection; during the following runs the physical fixture verified the five selected cells and exact clipboard, but did not establish the recipient of the external release. Their original failures remain in the archive.

The final physical comparison confirmed the OS sending `WM_RBUTTONUP` to a second foreground window owned by the test. It checked that the mouse was physically held, the second window owned capture and that its actual queue received the release. After returning to the terminal the peer cleared the selection and requested SGR mouse tracking. On the [old run](https://github.com/xiongnemo/nemoterm/actions/runs/44300752614) the right press arrived alone and the terminal retained capture. On the [fixed run](https://github.com/xiongnemo/nemoterm/actions/runs/44300752889) the peer received both edges and capture was released. The entire selection group passed **4/4** on the fixed image. The physical test uses GDI without injected hooks; the separate addressed-message cases cover both renderers.

The [original comparison evidence](right-button-release-evidence.zip) contains all nine unmodified selection archives, including the earlier fixture failures. `index.json` lists the originating run, artifact ID, size and SHA-256 of each; its last two entries contain the verified physical comparison and screenshots.

On the fixed image, all six [real-client default-grid checks](right-release-agents-grid-f628d89.zip) passed: Codex, Claude Code and OpenCode at 160×48 with the verified Sarasa Light face, using actual Shift-drag, system copy/paste and a local provider. The highest sampled frontend private working set across these interactions was 11,997,184 bytes on GDI and 17,653,760 on DirectX. Artifact `14425123375`, archive SHA-256 `f9bafba305401040c3043826220e692175d76ecacaa575d15960f7c5fadf52ad`. These are interactive readings, not full-grid graphics stress results.

All [30 other real-client interactions](right-release-agents-f628d89.zip) in the same run also passed with natural cleanup (receipt `14424839394`, SHA-256 `246fa94c853f9cc465dbd84d638bf513d05954dd15af3ff7c5a43805f7efc253`). They include the early and ready Codex image gestures, OpenCode image gestures and all three clients’ two right-click actions. Together with the default-grid group this is 36 distinct agent cases. The earlier [Codex startup timing failures](agent-unicode-boundary.md) are still relevant: the mouse fix did not change image paste or Codex’s startup input handler.

The six [160×48 DirectX stress workloads](right-release-memory-directx-f628d89.zip) passed on this same executable. Dense Unicode and Kitty images reached a peak sampled private working set of **29,515,776 bytes**, 484,224 below the 30 MB limit. The original receipt is `14426470622` (SHA-256 `1de90dfadbc57831bb3e122bb28439b7ed78c8badf2e21525ad0dd4a5d1ce16a`).
