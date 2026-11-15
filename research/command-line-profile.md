# Command-line options and loaded profiles

Explicit frontend options now override a saved profile regardless of whether
they appear before or after `-load`. Previously, `--tabs -load NAME` could open
a standalone window, and earlier font, size, tab-position, scrollback and
right-click options could be silently replaced by the profile. Shell and
directory overrides already used the deferred behavior.

The frontend now remembers each explicitly supplied option and applies it after
profile loading and PuTTY's saved command-line options. The last occurrence of
each frontend option wins. Unspecified font properties come from the loaded
profile. Parsing bounds and the `-e` command boundary are unchanged; the fix
adds no per-terminal or per-cell state.

The new owned-window regression runs five cases: profile only, all overrides
after the profile, all overrides before it, options split across the profile,
and repeated values. It observes the actual root-window class, view/host
relationship, grid, client dimensions and left-tab offset through the public
API and Win32. It sends no physical input and does not use the clipboard.

The exact `12ee33b` CI single image fails the three cases with overrides before
the profile; profile-only and after-profile controls pass. The local corrected
MinGW candidate passes all five, with natural cleanup for every process group.
Original failing and successful observations are retained separately. This
portable candidate is not a replacement single-file distribution.
`command-line-profile.tar.gz` and its validation manifest retain both original
observations, exact corrected portable runtime, source snapshots, the failed
foreground diagnostic and the earlier unchanged single-image preparation.

The input-method and selection fixtures previously recorded the requested
`--tabs` flag as proof of tab hosting. Both now check the actual HWND root and
window class before claiming hosted coverage. Earlier successful CI groups with
that argument order therefore do not prove their claimed tab-host variant.
Other tab suites that explicitly observe their host retain their own evidence.

The foreground-dependent IME check now has an explicit `--foreground` opt-in
for local use and prepares actual foreground automatically on disposable CI.
The helper checks the target PID and root HWND, and only clicks a caption when
the actual window beneath the pointer belongs to that target. It restores the
temporary topmost setting and restores the pointer only if it has not moved.
Foreground-lock policy and the production focus gate are not changed.

Local preparation on the corrected product is refused: hit testing finds the
owned caption, but `WindowFromPoint` reports a separate Windows
`LockScreenBackstopFrame` over it. No caption click is sent. The actual hosted
window is confirmed, but foreground, IME DPI, physical input and clipboard
acceptance remain open until the desktop is available. The earlier assumption
that the standalone window was merely transient was incorrect; the command-line
regression above establishes why it persisted.

Both complete product workflows include the new regression. Their results on
this source change are pending; existing passing CI belongs to `12ee33b`.
The correctly hosted resize variant subsequently exposes and fixes a separate
[minimized restore-size defect](host-restore-size.md). Its combined full
workflows supersede the initial CLI-only runs; a superseded run is not a pass.
