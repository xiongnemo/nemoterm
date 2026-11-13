# Screen-alignment state audit

The initial `ESC # 8` (DECALN) audit below found that the inherited handler filled
the screen with `E` characters but omitted several state changes made by XTerm.
The [development fix and local validation](alignment-reset.md) now address the
state and visible-image lifetime findings; full remote CI for that fix is pending.
The control is listed in the [XTerm sequence reference](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html).

A private Xvfb/XTerm capture and a newly spawned native Nemoterm/ConPTY process
ran the same 14 authored sequences. XTerm identifies itself as `XTerm(412)`;
its executable SHA-256 is
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
The tested Windows image is the downloaded `6cbe05f` single-image artifact,
SHA-256 `53658a13e96e1d55f3f871f318912a8c7cd5c89ac63a05c6012d76c25f485f84`.
Its alignment handler is unchanged in current main. The manifest verifies the
current `terminal.c` identity against the audited source copy.

Each case independently resets to VT520 compatibility, sets up state, sends
DECALN, and queries cursor position, rendition, margins, origin mode,
left/right-margin mode and character protection. The native transport uses a
separate final status-string barrier. Both exact wire streams are retained in
the [manifest](alignment-audit-validation.json), along with scripts, source
snapshots, controller results and logs.

| Setup before DECALN | Observed Nemoterm result | Observed XTerm result |
| --- | --- | --- |
| Cursor at row 7, column 13 | Cursor remains 7,13 | Cursor becomes 1,1 |
| Vertical margins 4–17 | Margins remain 4–17 | Margins become 1–24 |
| Horizontal margins 8–67, mode 69 on | Bounds remain 8–67 | Bounds become 1–80; mode 69 stays on |
| Origin mode with both margins | Origin remains on | Origin turns off |
| Pending wrap at column 80, then DECALN and `Q` | Cursor becomes 2,2 | Cursor becomes 1,2 |
| Styled rendition and explicit colours | Prior styles and underline colour remain | Styles clear; colour handling has separate details |

Thirteen combined reply streams differ; the double-width-row case matches.
This is not thirteen independent bugs. Several cases exercise the same missing
cursor reset. Protection replies themselves match even where cursor replies
differ. In the RGB case XTerm reports packed RGB integers using indexed-colour
syntax after DECALN; Nemoterm still reports RGB syntax. That reference encoding
must be investigated separately, rather than copied as an assumed requirement.
The style case also demonstrates XTerm's bold/bright colour interaction, so a
future fix must distinguish style reset from blindly resetting all colours.

The native comparison collects every reply before checking differences, exits
nonzero, and records `completed: false` and `compatibility_passed: false`.
Its transport completed and all five controller/job processes drained naturally;
no observer was injected and no process was force-terminated. The first local
wrapper read an incorrect result filename after transport completion. Its
original failure is retained; the corrected wrapper reports the actual
comparison failure instead.

Next work is to implement and test the missing state transitions, then extend
the cell/image lifecycle checks. This audit does not establish full-screen
character/colour parity, Sixel retirement, selection invalidation, scrollback,
or resize behavior. The existing hyperlink unit check verifies that replacement
cells lose old hyperlink IDs; it does not cover those remaining requirements.
No product code or accepted executable changed in this audit.
