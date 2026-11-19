# WSL PTY relay (Linux x86-64)

This component provides a controlling terminal to a guest program even when
`wsl.exe` has redirected standard handles. The Windows frontend does not yet
select this transport. It needs no interpreter or shared C library at runtime.

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
