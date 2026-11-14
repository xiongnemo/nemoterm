# GDI startup resource timeline

Both the pre-fix C1 image and the I/O-fix image initialize additional native UI
while their first terminal is starting. This is evidence against attributing
those windows to the I/O change. It does **not** yet explain the previously
recorded post-baseline 361-to-407 resource failure, or the experimental image's
36-to-39 USER-object failure. Those gates remain open.

## Scope and method

The two images are the downloaded CI artifacts already identified in
[C1](c1-controls.md) and [I/O lifetime](io-lifetime.md):

| Image | SHA-256 | First additional UI sample | First two-terminal sample |
| --- | --- | --- | --- |
| C1, before I/O fix | `4beee874e66f49981ad39b6887cb05852fd77d7afea19cb0eac5346f7823527f` | 0.150 s, 390 handles | 0.594 s |
| I/O fix | `b1a1f25ca3014714b03de2559ce695281b3ef26bc3c2b450f8ca3e85cdceec50` | 0.173 s, 390 handles | 0.661 s |

Each run uses a fresh owned process/job and the same copied original I/O-branch
tab fixture, SarasaTermSC Nerd Font Light, actual 160x48, GDI and full workload.
An external controller thread samples only that process's handle/GDI/USER
counts and window metadata for at most 15 seconds, with a 20 ms interval.
The original resource samples and numerical assertions are unchanged. A separate
180-second outer controller bounds the entire test and checks cleanup.

The window observer reads class, owner TID, parent, visibility, class module and
instance. It reads no window text, sends no input and does not change focus.
The module and thread catalogue is read after the 12 original resource cycles,
before target shutdown. The snapshots are sequential rather than atomic; the
observer's scheduling overhead can affect initialization timing. These are
diagnostic runs, explicitly `completed=false`, with exit code 2; their memory
measurements are not acceptance results. Later existing pixel tests still use
their normal injected capture helper.

## Observed initialization

The I/O image moves from 343 handles at 0.138 s to 390 at 0.173 s; the older
C1 image records 338 at 0.098 s, 367 at 0.122 s and 390 at 0.150 s. In both
traces `NativeHWNDHost` and `Mode Indicator Button` first appear in the
390-handle sample, alongside `MSCTFIME UI` and `IME`. Only one terminal exists
at that time, before the first temporary tab and its I/O workers are closed.

The observed class-module handle for `NativeHWNDHost` maps to `DUI70.dll`;
`MSCTFIME UI` maps to `MSCTF.dll`, and `IME` to `USER32.dll`. The value returned
by [GetClassLongPtrW with GCLP_HMODULE](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getclasslongptrw)
identifies the class registration module, not necessarily its calling code.
In particular, `Mode Indicator Button` reports the executable's module handle.
Read-only byte inspection of the three exact local DLLs finds that UTF-16
class string in `msctfuimanager.dll`, offset 357352, and `NativeHWNDHost` in
`DUI70.dll`, offset 1186912. DLL hashes and offsets are retained. This supports
an input-UI initialization hypothesis; strings and temporal correlation do not
identify the owner of all new OS handles or prove the original failure's cause.
These are shell/Win32 observations, not REA-server Evidence records.

Both timeline runs enter the original two-tab baseline at 405 handles / 38 GDI
/ 50 USER and complete all nine functional groups. Their 56 inner and 58 outer
processes exit naturally. The old and new images therefore share the observed
early initialization; neither run reproduces delayed initialization after the
baseline. No global or per-window IME setting was disabled.

## Failed diagnostic attempts and remaining work

The preceding fast-window diagnostic also completes all nine groups, but then
incorrectly queries metadata after the target has exited. Its owner guard
rejects that query. The original failure and natural cleanup are retained; the
corrected timeline collects the catalogue before shutdown. An initial timeline
preparation also fails because its replacement anchor matches two `finally`
clauses. No target starts in that attempt; a unique anchor and fresh directory
correct it. Neither attempt is reported as a successful diagnostic.

The [manifest](gdi-startup-validation.json) verifies 44 compressed records,
including sources, all three executed runs, the preparation failure source,
raw timelines, memory observations and cleanup. Next evidence must connect the
actual low baseline to subsequent initialization or otherwise identify the
resources. The I/O product change and worker-wait tab fixture remain unmerged;
the accepted distribution is unchanged. No count allowance or memory limit
has been raised.
