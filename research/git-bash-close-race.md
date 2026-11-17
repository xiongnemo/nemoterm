# Git Bash duplicate-close investigation — 2026-11-17

Follow-up: [the closed-console correction](closed-console-connections.md) at
`8084338` passes all 30 hosted lifetime cases. The same-fixture old-product
control still fails all four delayed connections. The original image's
failures below remain unchanged; the new full aggregate is still running.

## Product and original failure

All diagnosis runs use the exact single executable from source `62478182996cc0957800f2d03aa009382f86d7fe`, 4,599,808 bytes, SHA-256 `294912cf11f5cc5be92148ba95435415dabe40c32ea62345d35d5625872bb89f`. Builds, native controls, test execution and capture take place only on GitHub-hosted runners. Local work edits source and inspects downloaded evidence.

The [original full run](https://github.com/xiongnemo/nemoterm/actions/runs/44041617145) passes all six shell launch/directory checks but fails the private-job drain: a same-image process and Git Bash remain after three seconds. The single [diagnostic replay](https://github.com/xiongnemo/nemoterm/actions/runs/44043921945) passes and does not establish a fix. The product is unchanged throughout the runs below.

## Reproduction and observation controls

The repeat driver interleaves twelve ordinary Git Bash duplicate/close cases with twelve cases that retain read-only process identities before closure. Each case uses a fresh saved fixture snapshot and private process job, with the same three-second cleanup gate. Every result is retained; failures are not discarded or retried until green.

| Run | Fixture | Ordinary failures / 12 | Observed failures / 12 | Additional evidence |
| --- | --- | ---: | ---: | --- |
| [44050907950](https://github.com/xiongnemo/nemoterm/actions/runs/44050907950) | `821cd70` | 3 | 0 | Repeatable original cleanup failure. |
| [44051625127](https://github.com/xiongnemo/nemoterm/actions/runs/44051625127) | `9ed9693` | 2 | 1 | All three pairs remain alive for another 12 seconds after the failed deadline. |
| [44053336852](https://github.com/xiongnemo/nemoterm/actions/runs/44053336852) | `9858157` | 1 | 0 | Post-deadline commands, threads and minidumps. |
| [44053708199](https://github.com/xiongnemo/nemoterm/actions/runs/44053708199) | `351bfd5` | 2 | 0 | Snapshot ownership controls and two more surviving pairs. |
| [44055294894](https://github.com/xiongnemo/nemoterm/actions/runs/44055294894) | `a5c1597` | 3 | 0 | Repeated cleanup failures; initial controlled fixture times out before resuming its child. |
| [44056799690](https://github.com/xiongnemo/nemoterm/actions/runs/44056799690) | `e1f468d` | 2 | 2 | Four Git Bash failures; all four controlled cases reach child resumption, then time out on frontend exit. |

The post-deadline observer keeps `grace_exceeded=true` even if processes later exit naturally. It does not convert a late exit to a pass. Remote native controls verify late natural exit, bounded termination of a stuck process, isolation from unrelated processes, and natural exit. Further controls verify metadata against a retained private-job member, reject a foreign job, and prove that minidump collection leaves a live target running and rejects foreign/exited targets.

No observed failure drained during the extra twelve seconds. This contradicts the explanation that the original three-second grace only missed a short, otherwise normal cleanup. Observation before close can affect the reproduction rate; it is not a cure.

## Recorded process facts

In run `44051625127`, observed case 04 identifies the duplicate's console host (PID 9276). Every Bash client present in the pre-close snapshot is signaled after closure. The host survives with another Bash PID (6592) that was absent from that snapshot. This supports investigating a client starting or connecting around the close event, but does not establish when its console connection completed.

In run `44053336852`, ordinary case 05 records the retained host's command as `nemoterm.exe --headless ... --signal ... --server ...` and the other process as Git's `usr/bin/bash.exe --login -i`. Both remain alive after the failed deadline plus twelve seconds. The Bash process creation FILETIME is `134393804077818415`; the fixture's close-request FILETIME is `134393804077832452`, about 1.4 ms later. Creation time is not console-connection time.

The host's surviving thread metadata lists two threads, one with pending I/O; both successful minidumps contain live thread contexts. The Bash process contains its main thread and MSYS runtime threads. These are retained observations. Raw stack words that resemble module addresses are not treated as an unwound stack or named call-path proof.

Source inspection of the pinned host shows that `VtIo::SendCloseEvent` sends the close notification once; `ProcessCtrlEvents` takes a snapshot of registered console clients before dispatching close events. The connection path can still add clients later. A client missing that initial snapshot is therefore a hypothesis to test, not yet a demonstrated production fix.

## Controlled late-client check

The new native fixture creates a suspended child with an inherited console. Its controller requests closure of the owned terminal, waits for the parent client to exit, then resumes the child's retained initial thread. The original three-second job drain and failed-deadline observation remain intact. This separates the timing boundary from Git Bash's prompt/fork behavior.

The first remote build at `f9a1a05` fails compiling the test helper because `_countof` is not declared in its selected C headers; no product test result is claimed for that run. Fixture `a5c1597` uses an explicit array-length macro and includes declared x64 Windows handle signatures. All four controlled cases then time out waiting for the frontend to exit, before the child is resumed. Their retained job records show the frontend, host and suspended child still alive, with the parent gone. These results do not establish what a resumed late client would do.

Fixture `e1f468d` removes that circular fixture ordering: parent exit is the close-delivery witness, and frontend exit is checked after resuming the child. It also captures owned-process diagnostics if a prerequisite fails. Product source and the final cleanup requirements are unchanged.

In [run 44056799690](https://github.com/xiongnemo/nemoterm/actions/runs/44056799690), all four controlled cases confirm parent exit and a previous suspend count of one, then fail the ten-second frontend exit deadline. All retain three live processes: frontend, headless host and resumed native child. All twelve failure minidumps succeed; all eight prerequisite ownership/lifetime/dump controls pass. The first case's child thread has pending I/O. Unlike the original Git Bash residue, the controlled case also retains the frontend and one additional host thread. The child's phase report is not retained on this failure path, so the evidence does not yet prove its connection/read phase or establish that both cases have the same root cause.

The repeat runs establish **13 failures out of 72 ordinary cases** and **3 out of 72 process-observed cases** on the unchanged product. The failure remains open. [Artifact 14315819838](https://github.com/xiongnemo/nemoterm/actions/runs/44056799690/artifacts/14315819838) retains the latest exact-image identity, results, controls and dumps.

The [retained evidence archive](git-bash-close-race-evidence.zip) contains 884 source records and an internal per-file SHA-256 manifest, including all six repeat runs, both early controlled-fixture failures, the latest controlled results, and available run metadata and dumps. It is 3,805,037 bytes, SHA-256 `c0ac68759d4b2b4357fe9b6f2b965482aa6ef3bf8aae61b1821d0444f970606b`. Archive creation and hash inspection read downloaded files only; no product executable or test ran locally.
