# Tab system-menu reuse and resource investigation

This candidate is based on `420363b`. It retains one host system-menu copy,
removes only the appended seat items on a tab switch, and preserves native
commands and separators by their original positional boundary. Borrowed
submenus stay owned by each seat's context menu. Host destruction detaches the
borrowed entries before requesting child closure, retaining the active pointer
until ordinary seat cleanup releases the shared GPU.

Previously every switch reset the entire system menu. Windows documents that
[`GetSystemMenu(hwnd, TRUE)`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getsystemmenu)
destroys its previous copy. [`RemoveMenu`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-removemenu)
detaches submenu entries without destroying their handles. The candidate uses
that existing ownership model and redraws the host menu after attachment.

## Local candidate results

The linked executable is 4,509,696 bytes, SHA-256
`18d20efbc85257fb8a04822debf2bc8a0a9a49d6a8e7c86a6871c10eb10eae6c`.
Fresh frontend libraries are linked to the previously validated host objects;
all link inputs and source hashes are retained. It has not replaced `dist`.

The new read-only menu fixture first fails on accepted image `aa11c539...`
because the first duplicate changes the host HMENU. On the candidate:

| Scenario | Result |
| --- | --- |
| GDI top, actual 160x48, full memory workload | Nine groups pass; 73 menu snapshots and 13 retired-tab ownership checks |
| Actual OpenGL bottom, 80x24 | Nine groups pass; 45 menu snapshots and 12 retired-tab checks |
| GDI right, 80x24 | Nine groups pass; 45 menu snapshots and 12 retired-tab checks |
| Mixed renderer profiles | Six existing groups pass |
| DirectX left, actual 160x48 | Resource gate fails before the full workload; 10 menu snapshots and three retired-tab checks pass |

GDI's 464 samples peak at 16,580,608 bytes private working set, 43,360,256 total
working set and 19,144,704 private commit. Its 56 inner / 58 outer processes
exit naturally. The other successful jobs also exit naturally. DirectX changes
489 -> 540 handles, 37 -> 38 GDI and 41 -> 54 USER objects; its five remaining
owned processes require inner-job termination. The outer controller finds no
survivors. Its 57 early samples are not full DirectX memory acceptance.

The helper checks native command IDs/separators, stable host HMENU, active-seat
submenu identity and destruction of closed-seat submenus without harming live
seats. It does not inspect saved-session labels. Dynamic Restart/Specials menu
mutation, native enabled states after actually opening the menu, direct host
destruction and allocation-failure paths still need focused coverage. The
existing RemoveMenu/InsertMenuItem failure handling is not claimed exhaustive.

## Separate causes observed in the resource gate

The earlier delayed initialization transition (+51 OS handles with new
`msctfuimanager`, DUser/DUI/UIAnimation modules and hidden input-method windows)
is retained in the enclosure branch. A diagnostic stable startup baseline alone
does not solve the second failure: a closed-tab sample can report four extra
USER objects with unchanged OS/GDI counts, then return to baseline on the next
sample. Both the accepted image and this menu-reuse candidate reproduce it.
No numeric limits or acceptance fixture timing have been changed here.

Three additional REA attach runs use fresh job-owned instances of the exact
candidate, at most three cycles and 4,096 probe messages. They retain the
original failing assertion and 20 subsequent diagnostic samples. They observe
arguments, module/RVA stacks and GetGuiResources before/after selected API calls;
they never change return values, send global input or attach to user sessions.
All are instrumented diagnostics, not memory acceptance.

* `ev_00f6b7abd5ca8319a82f392ca68e599f5aef5b5eb6c34d0d3471d0c1f871d60d`
  retains 111 messages. Nine GetSystemMenu calls use FALSE and the same HMENU;
  no LoadMenuW call is observed in this capture. The four-object transient remains.
* `ev_9a9f138e26ef1674641a09a36375fe0c63353a726eca5e6ab5378d66e0870794`
  retains 129 messages. Adding caret and hook paths records 18 caret creations
  with unchanged USER counts and no selected hook-registration calls.
* `ev_cbc4329af6a162857f8485006eaedb88c4bb7f70519b10109e4da880f8f5a0e8`
  retains 421 messages, including 165 NtUserSetTimer and 127 NtUserKillTimer calls.
  The failed sample at Unix ms 1794633686773 has 53 USER objects against baseline
  49. Three successful timer kills at 1794633686918-6919 each lower the count
  by one: one caller in nemoterm.exe (RVA 0x128e87, timer ID 1234), two in MSCTF.dll.
  The next external sample at 1794633686978 reports 49. These calls explain three
  decrements; the fourth decrement is not attributed by the selected hooks.
  The terminal source also uses timer ID 1234 in `windows/utils/gui-timing.c`,
  but an attempted local PDB lookup failed with Windows error 126, so no exact
  symbol mapping is claimed.

None of these captures is truncated or reports script errors. Each REA session
is closed before the driver releases its target; all nine inner / eleven outer
owned processes exit naturally. REA's detach result says target state unknown;
the independent job records establish termination. Complete REA wrappers retain
their provider limitations, including missing artifact/architecture attribution;
the owned driver's PID, creation identity and SHA-256 provide the local link.
This is not a complete USER-object census or proof of leak absence.

The older accepted-image traces are also retained, including the first trace's
cleanup timeout/forced private-job cleanup and the second trace's shorter
capture window. A shell command-length error while saving the first candidate
trace was recovered by writing the already-returned wrapper through apply_patch;
the target was detached/released in finally and the run was not repeated.

The [manifest](tab-menu-validation.json) verifies 136 compressed records
(3,615,792 bytes), including prior failed hypotheses, original assertions,
native captures, REA Evidence, probe sources and job cleanup. The candidate is
not merged or accepted. A bounded resource-settling check may be worth testing
next, with unchanged thresholds, retained transient peaks and a persistent-leak
negative control; no such check has yet been adopted.
