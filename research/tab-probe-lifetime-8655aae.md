# Controlled probe lifetimes on the failed MSVC image

The access violation from core run `43768960240`, source
`8655aae163a81c927537e18845f930d42df6cafc`, remains unexplained. The exact
3,538,432-byte executable has SHA256
`11d36b78d616b27407e485bf4df36f304d84f292127432b6617749d5b6b37244`.
This comparison changes test instrumentation only; it is not a product fix or
an accepted-image replacement.

Six local lifetimes run in order A/B/C/C/B/A with Frida 17.24.3:

* A detaches the session at the original point before synchronized tab switching.
* B explicitly unloads the key and hover scripts, snapshots code, then detaches
  the session at that same point.
* C keeps the probes through synchronized switching, fullscreen and resize,
  then detaches before closing the capture clients and tabs.

All nine original assertions remain enabled. The image, sidecars, right-hand
tab bar, 88x35 grid, Consolas font and 300-second client lifetime are fixed.
Local runs explicitly request GDI to match the failing runner's actual renderer;
hosted diagnosis retains its original OpenGL request and records any fallback.
No external debugger, global input or clipboard is used in these tab runs.
The ordinary fixture path is unchanged when the new option is absent.

## Local observations

All six lifetimes pass nine checks and naturally drain 54 owned processes each.
The code observer reads executable PE sections from the frontend, ntdll,
user32 and kernelbase before attach and at selected boundaries. It retains
section hashes and at most 64 changed 32-byte blocks per snapshot. It neither
reads terminal/heap data nor suspends or writes to the target. Capturing these
snapshots still changes controller timing, so a successful run is finite
diagnostic evidence, not an equivalent unobserved acceptance run.

Each run sees five changed code blocks with the probes loaded. In A and B,
three ntdll blocks are still changed immediately after `session.detach()`
returns; all selected executable sections match their baseline after the
first tab selection. C retains the five changes during switching, as intended.
Its two immediate post-detach snapshots show zero and three changed blocks.
These measurements do not establish a stale executable pointer or a crash cause.

The independent observer control detects its deliberately installed kernelbase
hook, verifies its restoration, rejects an unrelated job, and avoids reads
after exit. In its successful run, the three ntdll changes seen just after
detach are gone at the next snapshot after a requested 10 ms wait and stay
absent in the later snapshots. The control handles its own exception, exits
with its expected status 23, and drains naturally. Four existing exception
observer controls also pass with the extended control executable.

Two earlier control attempts are retained as failures, before any terminal
comparison ran. The first sampled before loader initialization completed and
missed kernelbase; an explicit readiness event fixes that race. The second
incorrectly required all runtime patches to disappear synchronously with
detach. The final control asserts restoration of its own explicit hook and
records runtime cleanup at bounded intervals instead. Its reads are identical;
the unsupported synchrony assumption is not treated as a product requirement.

Frida's historical unwind-hook lifetime bug was reported in
[frida-gum issue 1170](https://github.com/frida/frida-gum/issues/1170) and fixed in
[17.23.2](https://frida.re/news/2026/10/09/frida-17-23-2-released/).
Our pinned 17.24.3 is newer. The report motivates checking more than the host
window-procedure entry, but does not diagnose this failure or justify an
unverified dependency upgrade.

`tabs-close-replay.yml` offers `tabs-probes` as a manual diagnostic: it verifies
the failed job, exact artifact hash and matching production source, runs the
observer controls, then performs the fixed six-way comparison. It never replaces
ordinary product CI or memory acceptance. A recurrence with an exception address
or a differing controlled outcome is still needed before attributing the crash.

## Hosted comparison

[Run 43778543052](https://github.com/xiongnemo/nemoterm/actions/runs/43778543052)
at fixture `4f319c0` passes the observer controls and the same six lifetimes on
the exact failed image. The OpenGL request falls back to actual GDI, as in the
original failing job. Each lifetime passes all nine checks and naturally drains
54 owned processes. No observation errors or truncated change lists occur.

The first immediate-detach snapshot retains one changed ntdll block; the second
retains none. Both are fully restored after the first tab selection. The two
explicit-unload runs retain three blocks between script unload and session
detach, then none after detach. Both delayed-detach runs retain five blocks
during the interaction checks and none in their post-detach snapshots. All
three controlled paths pass, so these results do not discriminate a crash cause.
The original access violation remains unresolved.

The original artifact ZIP is retained as `tab-probe-lifetime-8655aae-hosted.zip`
(107,104 bytes, SHA256
`a9cd3399a333ca95ecae081918f0c8cbc233e2887de72474b91e44e79a6ee130`).
Its validation manifest verifies the GitHub digest, every extracted member,
fixture and observer source hashes, image identity, results and process cleanup.
Local observations and both failed controls remain separately retained in
`tab-probe-lifetime-8655aae.tar.gz` (SHA256
`c1053d8f43d56f739687242f6f0e7d3a58d4039dbaf788b47f9bdfad1ae16685`).
