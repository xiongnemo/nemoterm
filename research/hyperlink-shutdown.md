# Hyperlink fixture shutdown and truthful completion

The compiler comparison at [`6cbe05f`](https://github.com/xiongnemo/nemoterm/actions/runs/43503351523)
failed in the hyperlink fixture's ten-second natural-exit check. Its functional
assertions had passed, but the old fixture had already written `completed: true`
and printed success before waiting for shutdown. That JSON was not evidence of
a successful complete test. The original log and JSON are retained in the
[validation manifest](hyperlink-shutdown-validation.json).

The same commit's [single-image workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43503351475)
passed all 93 groups. The downloaded single image is 4,448,768 bytes, SHA-256
`53658a13e96e1d55f3f871f318912a8c7cd5c89ac63a05c6012d76c25f485f84`.
Its hash matches that workflow's validation JSON. This does not make the failed
compiler comparison green or qualify the commit as the next accepted release.

## Fixture change

Each preference/full case now owns its process tree in a private unnamed job.
The pointer observer detaches while the frontend is alive, before requesting
the child's normal exit. Attach/load/detach use the existing bounded Frida
helper; synchronous RPC remains under the fixture/controller deadline. The
fixture sends `WM_CANCELMODE` to dismiss its UI state instead of injecting an
Escape keystroke into a potentially exiting child.

The original ten-second frontend deadline is unchanged. A timeout records
retained process identities and exit states, requests window closure solely for
cleanup, and still fails. Natural cleanup must drain the owned job without
forced termination. Retained frontend/host/child handles must report exit code
zero after that drain. A three-second job drain allows already exiting children
to finish; it does not extend the frontend's ten-second gate.

`completed` is set only after both functional assertions and successful cleanup,
including the local activation-only diagnostic path. Intermediate stages and
functional/cleanup errors are saved atomically. No product source, functional
workload, clipboard assertion, close-on-exit preference, or memory limit changed.
The full test still exercises 6,000 long URIs and 800 Sixel images.

This repairs concrete fixture lifetime and evidence problems. The original CI
record did not retain child exit codes or an exit-time stack, so it does not
prove that Frida caused that particular timeout.

## Retained local checks

All checks ran sequentially on newly spawned owned instances. The manifest
retains exact fixture sources per case, controller results, raw JSON, logs,
the extra observation script, and the injected child source.

| Case | Result | Owned cleanup |
| --- | --- | --- |
| Incremental source-built single image | Full functional test and exit passed | 19 processes, none forced |
| MinGW frontend plus verified same-source host | Full functional test and exit passed | 19 processes, none forced |
| Downloaded CI image, additional menu/clipboard observation | Full functional test and exit passed | 19 processes, none forced |
| Downloaded CI image, final activation-only path | Scoped activation test and exit passed | 10 processes, none forced |
| Child deliberately ignores stop request | Expected failure after 10 seconds | 5 processes, none left or job-terminated |

The injected timeout retained all three child-tree processes at exit code 259
(`STILL_ACTIVE`) before cleanup. Closing the test window then ended the console
client with `0xC000013A`, as expected for that forced-close diagnostic; the test
remained failed and its JSON never reported completion. No stop-ignore behavior
was added to the repository fixture.

The local MinGW frontend is SHA-256
`b4502082809e68190ef7c060da45e76d0ab94ab8deabcf1bf8a3ee2701ac73bf`.
Its separately installed source host is SHA-256
`45f9d4754a97b575e9626a2900a6f0f64a3f31828067fc7a3dfb2674d3249428`,
verified against the `6cbe05f` host artifact metadata. The local compiler uses
MSVCRT; the failing hosted comparison uses UCRT64. This is a relevant local
configuration check, not an exact reproduction of the hosted executable.

Two additional failures remain visible:

* The first collector attempted to query an image path after process exit and
  failed. It was corrected to cache names while alive and use retained handles
  only for exit codes afterward. That was a diagnostic collector defect.
* The first downloaded-image full run timed out checking the remote-file link's
  clipboard value. It still completed normal shutdown with all retained exit
  codes zero. A fresh diagnostic run observed `TrackPopupMenu` returning the
  expected copy command (`0x1D0`), followed by successful `OpenClipboard` and
  `SetClipboardData`, and passed. The extra hooks only recorded bounded API
  results; they did not modify arguments or returns. This single subsequent
  pass does not explain or close the earlier clipboard failure. Its cause is
  still unproven; the original failed log/JSON are retained.

Every hyperlink run uses the existing owned pointer instrumentation. Reported
memory is diagnostic, not the uninstrumented Sarasa 160x48 memory acceptance.
The accepted root executable remains unchanged. Both full workflows for the
fixture fix at `37ef26d` now pass; the
[downloaded-image record](underline-capabilities.md#downloaded-ci-image-and-local-follow-up)
retains complete single-image and MinGW hyperlink shutdown evidence. This does
not establish a cause for every earlier intermittent failure.

A follow-up diagnostic on the same downloaded image repeats the remote-file
copy case 32 times with a distinct URI each time, retaining the menu/clipboard
API observer and per-attempt clipboard sequence, ownership and equality flags.
All 32 attempts pass, followed by the unchanged 6,000-URI/800-image workload
and natural 19-process cleanup. This bounded repeat did not reproduce the
earlier clipboard timeout and does not establish its cause or a product fix.
