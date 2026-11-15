# Application resize expectations on small screens

The complete ordinary CI for `d914972` passes the source-host build, MSVC native
diagnostics and ASan/UBSan jobs, then fails the portable tab-resize fixture on
left tabs. Its 1024x768 monitor, 225-pixel horizontal frame/sidebar and
9x19-pixel cells permit a client width of 799 pixels. The fixture incorrectly
expects a 90-column request to produce 812 pixels. The product correctly bounds
the client to 799 pixels under its existing monitor-size policy.

The fixture now bounds those requested client dimensions using the observed
monitor and frame, and checks the corresponding complete-cell grid. Every
request retains the original requested dimensions, bounded expectation and
monitor client limit. Exact replies, actual Win32 rectangles, ConPTY grid,
minimized restoration, pixel and cleanup assertions remain in force. A
`--font-size` option supports reproducing this case without changing the user's
display settings. No product source or memory limit is changed.

On the same retained portable image, Courier New 24pt reproduces the original
failure on a 1920x1080 monitor: the requested 1712x1082 client is bounded to
1695x1041. The corrected fixture passes all 58 stages, including the resulting
89x28 character grid. A further six-command matrix passes **348 stages**, with
**32 explicitly clamped requests**: GDI top/bottom/left/right, actual OpenGL
right and actual DirectX left. All owned processes exit naturally.

The first matrix setup used 24pt for top tabs too. Startup correctly limited
that grid to 26 rows to fit the work area, so it failed the fixture's unchanged
83x27 starting-grid requirement. That original setup failure is retained.
Top/bottom cases use 23pt in the final matrix; they fit the initial grid and
still exercise oversized row requests. Side tabs continue to use 24pt.

`window-resize-screen-clamp.tar.gz` retains the original CI failure and exact
unverified portable runtime, the local before/after reports, the setup failure,
the six matrix passes, captures, logs and fixture sources. The validation
manifest hashes every record. The earlier successful CI hosted-input check uses
an English keyboard layout with no installed Chinese IMM submission; it does
not certify local physical IME behavior.

Fresh complete CI is required for these corrected fixture expectations and the
[actual-host guards](tab-host-fixture-guards.md). The accepted single executable
remains unchanged.
