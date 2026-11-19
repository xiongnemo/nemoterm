# WSL PTY relay (Linux x86-64)

The Windows single executable includes this relay and the musl notices. The
opt-in `NEMOTERM_WSL_PTY_RELAY=builtin` applies to a system `wsl.exe --exec`
session (including the WSL Bash profile). Other profiles and ordinary launches
continue using ConPTY. The relay needs no interpreter or shared C library.
For bundled launch, the distro's `/bin/sh` uses `wslpath` to convert one
Windows pathname before the relay takes over; program arguments stay separate.

The frontend creates one temporary `nemoterm-wsl-{GUID}.elf` in the user's
temporary directory, verifies its bytes against the PE resource, and keeps a
read handle that denies changes until session end. Normal session teardown
removes that file; force-killing the frontend can leave it behind. No guest
package installation is required. The remote GUI test checks the actual
parent executable's SHA-256, its path, and removal after a normal exit.

`bundled/manifest.json` identifies the Linux source, checked-in ELF and
original compiler artifact. GitHub Actions builds this source with static musl
and requires a byte-identical ELF before exercising it and the candidate PE.

`relay COLS ROWS PROGRAM [ARG ...]` launches the supplied argv on a new PTY.
Stdout is the slave's exact terminal stream (including the child's stderr).
The relay's own diagnostics use its inherited stderr. Input packets use one
byte for the type followed by an unsigned big-endian 16-bit payload length:

| Type | Payload |
| --- | --- |
| 1 | 1–16,384 uninterpreted input bytes |
| 2 | Exactly four bytes: new columns, then rows (unsigned big-endian 16-bit values, 1–32767) |

A resize is applied after the preceding data has been written to the PTY, and
before the next packet. Closing the owner's input ends the session. On natural
slave closure, the relay drains output and returns the program's status. A
malformed or incomplete packet exits 125. The relay neither interprets VT
input nor rewrites the guest kernel's terminal line discipline.
