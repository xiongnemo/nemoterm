# Settings fixture window ownership

Portable CI 43318199252 at grapheme branch commit b421983 passed all four
tab-host cases, then failed at the settings fixture's terminal HWND lookup.
The child's exact keyboard-mode replies had already passed; the catch handler
reported that the owned frontend had exited with code zero. The old lookup
depended on `Process.MainWindowHandle`, and the child had a 60-second lifetime.
The retained log does not establish which condition caused the failure.

The fixture now enumerates only top-level windows belonging to the launched
PID. Tabbed lookup requires the `NemotermHost` class and a descendant carrying
`NemotermRenderer`; standalone lookup requires that renderer property directly.
Early process exit fails explicitly and prints the last child report. The
child's lifetime is 300 seconds for this multi-dialog fixture; each individual
wait retains its eight-second deadline, and normal shutdown remains required.

The updated tabbed fixture passed locally using the previously accepted
single EXE, SHA-256
`2470cbcb8fd3560496a74e8d7e08fee4a8ce173b9552a8cf72b1c00a22416adc`.
`settings-lookup-local-observed.json` includes save/reload of shell, Unicode
directory, bindings and tab position, exact child replies, and live switches
through actual GDI, OpenGL, DirectX and back to GDI. No global keyboard or mouse
input was used. The first isolated run lacked a copied Python test utility;
it was corrected before this successful run. This is fixture hardening, not
proof that the earlier CI exit was a terminal rendering defect.
