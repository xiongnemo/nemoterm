# Application resize while a tab host is minimized

After the CLI fix enabled the previously untested real tab-host variant, the
unchanged application-resize fixture reproduced a product defect. A minimized
left-tab host accepted an 81x25-cell request, but restored its content to
442x463 pixels instead of 650x502. The minimized path counted the child view's
frame while omitting the outer host's title/resize border and the tab strip.

The fix adds the host's actual style/DPI frame and current tab-strip metrics
to the existing child-frame calculation. The child scrollbar and sunken edge
remain accounted for independently. The normal restore rectangle is updated
without showing or activating the minimized host; output continues at the
requested grid size. Standalone behavior and memory policies are unchanged.

The corrected portable frontend passes six unchanged fixture invocations:
GDI with top/bottom/left/right tabs, actual DirectX with left tabs, and actual
OpenGL with right tabs. Each invocation checks 42 normal resize stages plus
5 denied, 5 locked and 6 font-resize stages: **348 stages total**. Each checks
the restored dimensions, retained output pixels and natural process cleanup.
The existing seven-stage hosted geometry fixture also passes on the preceding
CLI candidate; that is separately identified evidence.

`host-restore-size.tar.gz` retains the original failure, six original pass
reports, logs, source snapshots, captures and the exact corrected portable
runtime. Its validation manifest identifies all 30 records. The original
failed fixture forcibly cleaned up its owned processes after the assertion;
this is preserved and is not reported as a natural product exit or a crash.

The complete tab regression suite now exercises application resizing with all
four tab-strip positions. Full CI for the combined source remains pending;
this portable result does not replace the accepted single EXE or certify
physical multi-monitor/DPI behavior.

The subsequent ordinary CI passes real hosted input and top/bottom resizing,
then exposes an incorrect small-screen expectation in the left-tab fixture.
The product's 799-pixel client is the correct monitor-bounded result; see the
[screen-clamp correction and retained failure](window-resize-screen-clamp.md).
