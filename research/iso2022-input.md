# ISO 2022 selection input and native validation

Development checkpoint on top of parser commit `9abf3396520b858e637d521de4616a6c664c68ca`.
The accepted root executable is unchanged. Raw reference captures, test logs,
build identities and native observations are retained in the
[evidence manifest](iso2022-input-validation.json).

## Input behavior

With DECNRCM enabled, pasted Unicode is converted through the active GL and GR
national sets. The conversion uses the explicit reverse mappings in XTerm 412,
including its French-Canadian alias exception and unmappable-character fallback.
The input mask table adds 960 read-only bytes on x64 and no heap allocation.
Normal Unicode typing keeps its configured input encoding; it is separate from
selection conversion. Temporary DOCS UTF-8 selection now also applies to the
keyboard's same-codepage shortcut.

This legacy conversion is intentionally lossy: XTerm masks unmappable characters
to seven bits, which can produce control bytes. It is not a Unicode-safe paste
mode. Outside NRC mode, byte-output selection data applies the existing
paste-control policy to C1 bytes after locale conversion. In a UTF-8 locale this
can remove bytes from a multibyte sequence, matching the captured reference's
byte-output selection behavior. Normal UTF-8 output/paste is unaffected.

## Independent reference and core tests

The pinned XTerm 412 executable is SHA-256
`089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c`.
Each selection case uses a fresh private Xvfb/XTerm process and X11 PRIMARY
selection; the Windows clipboard and desktop input are not used.

- 53 reference selections cover 586 Unicode codepoints, 40 designations,
  UTF-8/NRC transitions, GL invocation, level-2 DEC supplemental and level-3 JIS
  input. Captured bytes, including embedded NULs, are compared by length and value.
- The real terminal's long-paste callback path matches every capture. Authored
  regressions separately preserve Unicode typing and check ISO-8859-1 keyboard
  input under temporary UTF-8 mode.
- Eight Linux suites pass normally and under ASan/UBSan with leak detection;
  eight MSVC suites pass. The standalone mapping component also passes MSVC
  `/W4 /WX` and all 15,360 previously captured output cells.
- The initial xdotool keyboard captures were inconsistent and are retained only
  as exploratory evidence. They are not used to claim independent keyboard parity.

## Actual Windows rendering and transport

The local integrated single executable is 4,524,544 bytes, SHA-256
`7563afb9d23fbd44cffe7543da950a51c970693848dbbcbbb47d8fd69c1e3f24`.
It uses the current frontend with cached source-host link inputs; the manifest
records their hashes. It is not claimed to be identical to a future CI artifact.

Fresh owned ConPTY windows use 160 x 48 cells and SarasaTermSC Nerd Font Light.
Actual GDI, OpenGL and DirectX each pass four logical-text and pixel comparisons:
German, Portuguese, Greek 96-set and SS2. Each is compared with directly printed
Unicode, and each Unicode baseline must differ from a blank frame. Public API
paste of German NRC text reaches the child as `5b5c5d7e`; Unicode input reaches
it as `c384c396c39cc39f`. These tests do not exercise the system clipboard.
All owned processes close naturally; no focus changes or injected capture code
are used.

The new native fixture is registered in both CI paths. CI uses 80 x 24 Consolas
and records any GDI hardware fallback explicitly. Local acceptance requires
actual OpenGL and DirectX. The CI settings also passed locally on all three
actual renderers.

## Memory comparison

Four sequential runs use unchanged fixtures from `6ab186d`, the actual 160 x 48
Sarasa grid and the same tab/history/Sixel workload. Sampling runs without
compilation, screenshot requests or injected code. Figures below are frontend
peak bytes, not total memory of every shell/host process.

| Image / renderer | Samples | Private working set | Total working set | Private commit |
| --- | ---: | ---: | ---: | ---: |
| Accepted / GDI | 531 | 16,478,208 | 43,184,128 | 19,378,176 |
| Candidate / GDI | 521 | 16,293,888 | 42,930,176 | 19,017,728 |
| Accepted / DirectX | 504 | 23,863,296 | 63,275,008 | 87,756,800 |
| Candidate / DirectX | 528 | 24,195,072 | 63,713,280 | 87,257,088 |

All four runs pass their existing nine check groups, unchanged resource gates
and natural process cleanup. Candidate GDI stays below 20,000,000 bytes and
DirectX below 25,000,000 bytes in this finite workload. This is not proof of a
memory optimization or of every real-agent workload; DirectX total working set
still exceeds the approximate 50 MB target.

## Retained failures and remaining scope

The evidence includes the missing-xclip first capture, inconsistent exploratory
keyboard data, a test callback-queue ordering failure, the first integrated link
with incorrect archive paths, and a CI-fixture print-variable error. Their fixes
and subsequent runs are retained separately; no failed measurement is replaced.

UPSS reassignment, the lower-level output matrix, extended legacy DEC checksums,
all encoding combinations and complete ISO 2022 conformance remain open. The
previous native tab-close access violation is unresolved and is unrelated to
these fixture fixes.

Parser commit `9abf339` passed [core CI](https://github.com/xiongnemo/nemoterm/actions/runs/43588399701)
and [single-executable CI](https://github.com/xiongnemo/nemoterm/actions/runs/43588399714).
Those runs predate this input change. Full CI for the input checkpoint is pending.

Subsequent UPSS assignment, invocation and state-lifetime work is recorded in the
[UPSS checkpoint](iso2022-upss.md); this input checkpoint's original evidence is unchanged.
