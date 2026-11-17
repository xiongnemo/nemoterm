# Translation settings layout

Product source: `47dad363c81022b35e796c0eafdddee51bd9c3b5`.
Single executable: 4,556,288 bytes, SHA-256
`c726ecd7a57575f8183efc0e07b04daa1dba2cf0b2992fff348b6e01cdccae71`.

The Translation page combined encoding, width options and five Windows line
drawing choices. Its final checkboxes overlapped the Save and Apply footer.
The earlier seven-page DPI suite did not include Translation.

Line drawing now has its own `Window / Translation / Line drawing` page.
The original configuration keys, handlers and values are unchanged. The main
Translation page retains character encoding, CJK/grapheme width and Cyrillic
Caps Lock options. This page controls terminal character encoding, not UI
language; the English/Chinese catalogs remain `draft-not-integrated`.

The [fresh-build DPI workflow](https://github.com/xiongnemo/nemoterm/actions/runs/44002995333)
passed. It compiled the single executable, verified its artifact hash and ran
both real and synthetic DPI checks against that image. In standalone and tab
hosts, all five real scales (100%, 125%, 150%, 175%, 200%) passed cold starts
and live transitions with settings open. All 198 page inspections passed,
including 22 each for Translation and Line drawing. The five line drawing
radio buttons and both final checkboxes were visible, inside the dialog and
clear of the footer. Representative 100% and 200% screenshots of both pages
were visually inspected.

- [Single executable and provenance](https://github.com/xiongnemo/nemoterm/actions/runs/44002995333/artifacts/14293341440)
- [DPI measurements, logs and screenshots](https://github.com/xiongnemo/nemoterm/actions/runs/44002995333/artifacts/14292583852)
- [Repository evidence archive](translation-layout-ci-47dad36.zip)

The native UIA helper compiled locally without warnings; Python and PowerShell
syntax checks passed, and the draft language catalogs have 290 matching keys.
The existing startup settings fixture was adjusted for the new child page;
the targeted `scope=dpi` run exercises live settings and does not claim to run
the full profile, protocol, sanitizer or renderer suites. No local GUI tests
or local display-setting changes were made.
