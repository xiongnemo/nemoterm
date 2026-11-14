# Periodic traceback observer failure

The single-image run [43546782899](https://github.com/xiongnemo/nemoterm/actions/runs/43546782899)
at `c2606cd8b77731212a839178faa2634293b9c4dd` failed during the relative-cursor
fixture, immediately after its first periodic Python traceback at 60 seconds.
The traceback stops midway through a frame and no fixture-finally report exists.
This is not evidence of a 60-second terminal deadline: the observer used
`dump_traceback_later(..., repeat=True)` with the default `exit=False`.
The run remains failed and its build is unverified.

A separate local reproduction uses the official Windows x64 Python 3.12.10
embeddable runtime (the same interpreter version in that CI log), repeated JSON
file reads, and a 5 ms periodic traceback. It does not launch Nemoterm, Frida or
any console host. **8/8 processes exited with 0xC0000005** during traceback
output. Replacing only the timer implementation with a normal Python thread
calling `faulthandler.dump_traceback` completed **8/8 three-second runs**.
This reproduces an observer failure independently; the absent CI crash dump
means the exact instruction in the original CI failure remains unknown.

CPython's [upstream report](https://github.com/python/cpython/issues/140815)
describes the native watchdog reading freed frames without the GIL. The new
helper invokes the synchronous dump from a Python thread on the GIL-enabled
test interpreters. It retains periodic stacks and cancellation, with no test
assertion, timeout, memory allowance or terminal code change. Native calls that
retain the GIL indefinitely can prevent this observer from running; external
process/job deadlines still apply.

The regression checks busy frame churn, natural timer shutdown and propagation
of a failing child's exit code. They passed locally on Python 3.12.10 and 3.15.0.
They are now part of single-executable CI. The
[manifest](fixture-traceback-validation.json) preserves the standalone scripts,
old crash logs, corrected logs, interpreter archive provenance and helper source
with verified decompressed SHA-256 hashes. These are local subprocess
observations, not REA-server Evidence. The downloaded runtime is isolated under
the worktree build directory and does not replace any installed Python.
