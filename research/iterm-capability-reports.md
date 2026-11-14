# iTerm capability and cell-size reports

Development branch based on `26f50c8796b6ba4ee5e941490a1dbd63021383f4`.
Local native testing remains paused at the user's request. This checkpoint
contains implementation and fixtures, not a claim that those fixtures passed.
Remote CI status is recorded separately. The accepted `dist/nemoterm.exe`
remains source `8ff214feb549c2b79bb57960467c1d6963eab47e`, SHA-256
`c110843b1fd5a551d654df094fa716c1ea1c48383d90e642b964d7dfb3d15e26`.

## Source basis

The [feature-reporting specification](https://iterm2.com/feature-reporting/)
defines `OSC 1337 ; Capabilities ST` and concatenated feature codes.
The [escape-code documentation](https://iterm2.com/documentation-escape-codes.html)
defines `ReportCellSize` as height, width and scale. Both use the OSC 1337
namespace; neither is an xterm-defined query.

Source inspection pinned iTerm2 to
`b3010f0d41a1ee9b0bebbc751b1342d428616cc2`:

* [VT100Terminal.m](https://github.com/gnachman/iTerm2/blob/b3010f0d41a1ee9b0bebbc751b1342d428616cc2/sources/VT100/VT100Terminal.m): dispatch and logical cell-size response.
* [VT100Output.m](https://github.com/gnachman/iTerm2/blob/b3010f0d41a1ee9b0bebbc751b1342d428616cc2/sources/VT100/VT100Output.m): feature code encoder.
* [PTYSession.m](https://github.com/gnachman/iTerm2/blob/b3010f0d41a1ee9b0bebbc751b1342d428616cc2/sources/PTYSession/PTYSession.m): feature values and local clipboard policy.

This is source/specification analysis, not an iTerm2 runtime capture. No upstream
implementation was copied. Reference hashes are retained in the companion JSON.

## Report policy

| Code | Nemoterm meaning and condition |
| --- | --- |
| T1 | Semicolon true-colour form, when true-colour rendering is enabled. Colon forms remain implemented but the complete spec's extension-parameter matrix is not certified by this report. |
| Cw | OSC 52 writes allowed and the frontend has a clipboard writer. Querying never writes the clipboard. |
| Lr | Left/right margins. |
| M | Mouse reporting is not disabled by local settings. |
| Sc3 | Cursor modes 1–6. Mode 0 means blinking block, so the reset-to-preference bit is absent. |
| U / Aw | Current UTF-8 decoding; ambiguous-wide only while UTF-8 and the setting are active. |
| Ts3 | Title setting and stacks, when remote title changes are allowed. |
| B | Bracketed paste is not disabled. |
| Gs / Go | Strikethrough and overline. |
| Sy | Frontend provides synchronized-update support. |
| H | OSC 8 hyperlinks are allowed. |
| Sx | Bounded Sixel decoding/rendering. |

The published specification **and the pinned iTerm2 encoder** assign `F` to
both focus reporting and file transfers. Nemoterm omits this ambiguous code.
Focus reporting remains discoverable through DECRQM 1004. Inline image display
is implemented, but file downloading is not, so this checkpoint does not
advertise complete `FILE` support. `Uw` is omitted because a single Unicode
width version has not been independently certified across the configurable
width and grapheme policies. Notifications and progress reporting are absent.
The optional `TERM_FEATURES` environment publication is not added; the OSC
query reflects current settings and encoding instead of a startup snapshot.

Cell size reuses the same current geometry snapshot as XTWINOPS. Windows supplies
the window's current DPI; unscaled frontends default to 96. Height and width use
logical units (`pixels * 96 / dpi`), scale is `dpi / 96`, each rounded to three
decimal places. Integer formatting avoids locale-dependent decimal separators.
Invalid cell dimensions do not produce a misleading report. This convention
means multiplying a logical dimension by scale recovers physical pixels within
the documented rounding precision.

Queries require an exact command name; echoed reports, suffixes, cancelled and
overflowed strings do not trigger another reply. BEL and ST terminate requests;
replies use ST and the existing selected C1 framing. Queries have bounded stack
buffers, no retained state, no codec creation and no new third-party dependency.
Pending multipart images remain independent of query handling.

## Validation scope

* `test_queries` includes live preference changes, frontend availability, UTF-8
  transitions, explicit DPI examples, missing geometry, cancellation, overflows,
  echoed-report suppression and raw/UTF-8 C1 response framing.
* `test_sixel_terminal` interleaves both queries into multipart image transport.
* `iterm_reports_window_smoke.py` has 13 exact console-host cases across two
  isolated profiles, including restrictive preferences and reset lifetimes.
  These are specification/policy assertions, not an independent XTerm oracle.
* The existing native geometry fixture now compares `ReportCellSize` with
  independently measured cell pixels and Win32 DPI throughout move, resize,
  minimize/restore and synchronized-update phases. Both full workflows include
  it; requested OpenGL may use GDI fallback on CI and must be reported as such.

Static Python parsing and `git diff --check` passed before submission. The first
remote sanitizer run on `1f4a23a` failed in the new fixture: CAN/SUB ends an OSC,
so its trailing BEL is a normal bell, but the mock had no bell callback. The
follow-up supplies that mock callback and asserts two bells; production code is
unchanged. The original log is retained, not classified as a passing run.
The corrected behavioral checks are **pending remote execution**. No native process,
clipboard operation, input injection, renderer or memory workload was run
locally for this checkpoint. The earlier integrated DX close-cycle failure and
unrun DX PNG/GIF memory cases remain unresolved; green protocol CI would not
resolve them or justify replacing the accepted executable.
