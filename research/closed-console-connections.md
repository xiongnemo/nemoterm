# Closing a console is final

This continues the [retained Git Bash investigation](git-bash-close-race.md).
All product builds and runtime checks run on GitHub-hosted runners. Local
analysis reads source and downloaded artifact/dump bytes only.

## Evidence behind the change

The old image is source `62478182996cc0957800f2d03aa009382f86d7fe`, SHA-256
`294912cf11f5cc5be92148ba95435415dabe40c32ea62345d35d5625872bb89f`.
Six hosted repeats retain 13/72 ordinary and 3/72 process-observed Git Bash
cleanup failures. In run `44056799690`, four controlled children resumed after
their parent exited also leave the frontend, host and child alive.

In that run's first controlled case, frontend PID 1844/thread 752 has captured
RIP `ntdll.dll+0x1624a4`. Its raw stack includes a candidate return address
`nemoterm.exe+0xd531a`. The exact product's instruction at RVA `0xd5314` calls
IAT RVA `0x149c10`; the following instruction at `0xd531a` writes the invalid
handle value to the ConPTY structure's input-pipe field. The surrounding body
matches `conpty_terminate`'s sequence of retiring the output/input contexts,
closing both pipes, removing its process wait, and closing the pseudoconsole.

[REA's import-table Evidence](closed-console-pe-imports.json), ID
`ev_681118e9a43e363ccd7b42bd30e617ff746371e2a9e6408b80a6d5db62db85eb`,
identifies IAT RVA `0x149c10` as `CloseHandle`. The
[instruction listing](closed-console-teardown-llvm.txt) is from the installed
LLVM 23.1.3 `llvm-objdump`, not REA. REA's deep assembly provider was unavailable
(Ghidra was not configured), so no REA decompilation or unwound call stack is
claimed. Raw stack candidates remain distinct from an unwound stack.

Source inspection establishes a related admission race: `SendCloseEvent`
changes `_closeEventSent` under the console lock, and control-event dispatch
copies the then-registered clients. `ConsoleHandleConnectionRequest` previously
admitted a client regardless of that state. A suspended child's inherited
console reference can outlive its parent and reach admission after close.

## Change and acceptance

`8084338` adds a narrow overlay to the pinned Microsoft Terminal source;
the submodule is unchanged. Under the existing console lock, connection
admission returns `STATUS_PIPE_DISCONNECTED` if close has already begun,
before allocating per-client state. Existing connected clients retain their
normal close-event handling. Normal launcher delegation does not set the close
flag, and detached processes do not connect to this closed console.

The full workflow now invokes the shell-lifetime gate alongside the other
regressions. It retains all 24 ordinary/observed Git Bash repetitions. The native
control adds two pre-close connections that must reach a console read before
closure, and four child resumptions after parent exit. Child phase reports are
retained on failed paths as well as successful paths. Frontend exit and natural
private-job drain are required; forced cleanup fails the check.

[Full run 44058990446](https://github.com/xiongnemo/nemoterm/actions/runs/44058990446)
builds the new 4,600,320-byte product, SHA-256
`bf403e3d4a6451ca90c6898a0617af63dc85987ae3725c1c383385f9035fa394`.
Its shell-lifetime job passes **24/24** Git Bash cases and **6/6** native
controls. Every private job drains naturally with zero active processes,
without an exceeded grace or forced cleanup. Both pre-close children report
two connected processes and reach their console read. All four delayed
children are resumed with an initial suspend count of one; the frontend exits
zero and no child phase report is produced. This is consistent with rejection
before its `wmain`, not a claim about an unrecorded child exit status.

The complete aggregate is still running. A separate
[negative-control run 44060474431](https://github.com/xiongnemo/nemoterm/actions/runs/44060474431)
uses the same six-case fixture with the exact old product. Control branch
`test/closed-console-negative-20261117` restores only the old host preparation
recipe, so the existing production-identity check remains enforced. Its
two pre-close controls pass, but all four delayed children reach `before-read`
with `connected: 1` after the parent exits, and all four frontends exceed their
ten-second exit deadline. Each retains frontend, host and child until the
fixture's forced cleanup. The twelve post-failure dumps succeed. This supplies
the previously missing child-phase evidence: the old console admits the child
after closure and leaves it reading without its parent. Three ordinary Git
Bash repetitions also retain host/Bash pairs; none of the twelve
process-observed repetitions fail in this control run.

| Same-fixture check | Old product `6247818` | New product `8084338` |
| --- | ---: | ---: |
| Ordinary Git Bash duplicate/close | 9/12 pass | 12/12 pass |
| Process-observed Git Bash duplicate/close | 12/12 pass | 12/12 pass |
| Native child connected before close | 2/2 pass | 2/2 pass |
| Native child resumed after parent exit | 0/4 pass | 4/4 pass |

The positive [lifetime artifact 14317856571](https://github.com/xiongnemo/nemoterm/actions/runs/44058990446/artifacts/14317856571)
retains the exact new image identity and all 30 natural-cleanup receipts.
The ordinary six-shell interaction group, profiles, actual DPI, sanitizer and
MSVC jobs also pass in the new run. At this checkpoint 18/22 aggregate jobs
pass; MinGW, the complete single-image suite and the two full-grid memory groups
remain live. The original failures and DirectX memory gate remain intact;
this is not complete protocol or full-product acceptance.

The [retained lifetime archive](closed-console-lifetime-evidence.zip) contains
316 records plus an internal per-file SHA-256 manifest: both completed
lifetime artifacts, the new product manifest and completed job/run metadata.
It is 1,343,264 bytes, SHA-256
`997e84e155fcfd64d89d4d7ca38fcd5b1e80fad02f972e91756563ad5604ef0b`.
The archive does not claim to contain the unfinished aggregate's final results.
