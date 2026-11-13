# Local terminal automation (version 1)

Start an instance with `nemoterm.exe --automation` (before `-e`, if used).
The switch enables a local Windows named pipe for that process. It is off by
default, creates no discovery files, and adds no service or DLL to the single
executable distribution. An already running instance without the switch is not
exposed. Restart that instance with the switch to enable this interface.

The standard-library Python client is a development tool in
[`tools/nemoterm_debug.py`](../tools/nemoterm_debug.py). Python is not a terminal
runtime dependency. Any program implementing the protocol below can connect.

```powershell
python tools/nemoterm_debug.py discover
python tools/nemoterm_debug.py discover --pid 1234
# Copy the endpoint and session id from discovery (the values below are examples).
$endpoint = 'Nemoterm.Debug.v1.1234.01dc123456789abc'
python tools/nemoterm_debug.py list --endpoint $endpoint
python tools/nemoterm_debug.py input --endpoint $endpoint --session 1 --text 'echo hello'
python tools/nemoterm_debug.py key --endpoint $endpoint --session 1 --vk 13
python tools/nemoterm_debug.py text --endpoint $endpoint --session 1
python tools/nemoterm_debug.py image --endpoint $endpoint --session 1 --output screen.png
python tools/nemoterm_debug.py key --endpoint $endpoint --session 1 --vk 0x56 --ctrl
python tools/nemoterm_debug.py paste --endpoint $endpoint --session 1 --file text.txt
```

`input` delivers UTF-8 text to the terminal input path, without automatically
adding Enter. It can contain explicit control characters. `paste` uses the
terminal's regular paste path, including negotiated bracketed paste. An
acceptance response means input was queued, not that the child program finished
processing it. Poll `text` or `image` to observe the result. `key` sends a complete
Windows virtual-key press/release through the frontend's normal key translator;
Ctrl, Shift and Alt, application keyboard protocols and configured terminal
bindings apply. Bindings such as opening or closing a tab retain their normal
behavior. Neither text nor image reads use the clipboard, and ordinary input
does not focus the window or send global desktop input.

Discovery returns process ID and all live session IDs, terminal/host HWNDs,
active status, dimensions, actual renderer (0 GDI, 1 OpenGL, 2 DirectX), and title.
A session ID is monotonically allocated within its process and never reused.
Every operation except `list` requires an explicit ID; a missing/closed target
is an error, never an implicit redirect to the active tab. The endpoint contains
both PID and process creation time. The client verifies both against the actual
pipe server before sending anything. Closing the process removes its endpoint.

`text` returns the visible logical screen rows in UTF-8, including spaces and a
newline per row. Wide-cell continuations are skipped and combining characters
are included. It does not return scrollback or pixel layout/BiDi visual order.
Legacy DBCS direct-font byte extraction is not a guaranteed lossless view; use
the screenshot when checking presentation. `image` returns a top-down 32-bit
BGRA BMP of the terminal client area, excluding the tab bar/window frame. Active
views use the existing renderer capture, including a retained synchronized
frame; inactive tabs are rendered from their current grid through GDI without
activation. Inactive capture is therefore content evidence, not a DirectX pixel
comparison. The Python client can convert this BMP to PNG with the standard
library. Both read APIs are snapshots; there is no continuous output subscription.

## Transport and boundaries

The endpoint is `\\.\pipe\Nemoterm.Debug.v1.<decimal PID>.<16 hex FILETIME>`.
Enumerate the local pipe directory and connect to matching names to discover
instances. No TCP listener is created. The pipe DACL allows only the process
owner's user SID; the server also requires the same Windows session and rejects
remote clients. This is local automation authority for that user: clients can
read terminal contents and type commands, so only enable it in sessions intended
for automation. The supplied client requests identification-only security
quality of service so a pipe server cannot impersonate it.

Requests are serialized, one request per connection. Integers are little endian.
The 24-byte request header is `struct.pack('<4sHHQII', ...)`:

| Field | Value |
| --- | --- |
| 4-byte magic | ASCII `NDBG` |
| uint16 version | 1 |
| uint16 operation | 1 list, 2 text, 3 input, 4 paste, 5 key, 6 image |
| uint64 session | 0 for list; explicit session ID otherwise |
| uint32 payload length | 0 through 65,536 |
| uint32 reserved | 0 |

The payload immediately follows the header. List/text/image require an empty
payload. Input/paste take strict UTF-8. Key takes two uint32 values: Windows
virtual-key code and modifiers (Shift=1, Ctrl=2, Alt=4). VK_PACKET and
VK_PROCESSKEY are rejected; send Unicode text using `input` or `paste` instead.

The 16-byte response header uses `'<4sHHII'`: magic, version, status, payload
length, payload kind. Status is 0 for success, 1 for invalid request, 2 for a
closed/unknown session, or 3 for resource/capture failure. Kinds are 1 UTF-8 JSON,
2 BMP, 3 UTF-8 screen text. Errors use JSON `{ "error": "..." }`. After reading
the entire payload the client sends one zero byte to acknowledge receipt, then
closes the connection. This prevents disconnect from discarding unread pipe
data. Malformed framing/oversized input closes the connection without execution.

The server bounds each I/O stage to five seconds and keeps one pending request.
Pipe waits run on a worker; all terminal access runs on the UI thread. Output
is capped at 16 MiB, screen text at 1 MiB, and image dimensions at 8192 per axis
within the byte cap. Snapshot buffers are transient and released after receipt
or timeout; capture can temporarily raise working set. Idle automation overhead
and capture workload should be measured separately from normal terminal usage.
Use retries only for read operations: a timed-out input request may already have
executed, and repeating it could type twice.

## Regression coverage

[`tests/automation_window_smoke.py`](../tests/automation_window_smoke.py) launches
owned terminal processes and real ConPTY children. It checks discovery, Unicode
text, native screenshot parity, text/bracketed paste/key delivery, malformed
frames, stalled-client recovery, multi-tab isolation, closed target errors,
opt-in behavior and natural shutdown. Run with `--renderer directx` for DirectX.
The pixel comparison records changed channels and permits at most one intensity
step for fallback-glyph rasterization rounding between the two DCs. The DirectX
test uses the existing owned-process GPU probe as its independent capture path,
because cross-process PrintWindow does not reliably capture the child GPU
surface. Its post-probe memory samples are marked instrumented. The API itself
and its Python client require no instrumentation. Tests never attach to existing
user terminals.

Windows implementation references: [named pipe access security](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights),
[CreateNamedPipeW](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-createnamedpipew),
and [overlapped I/O](https://learn.microsoft.com/en-us/windows/win32/ipc/synchronous-and-overlapped-input-and-output).
