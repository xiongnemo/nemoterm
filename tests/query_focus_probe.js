// Test-only focus model inside the owned terminal process. This never changes
// the desktop foreground window, keyboard state or any other application's UI.
// It lets pixel tests cover active and inactive cursors even when the desktop
// transfers focus during a sample. Unloading the script removes every hook.
const user32 = Process.getModuleByName('user32.dll');
const sendMessage = new NativeFunction(user32.getExportByName('SendMessageW'),
    'pointer', ['pointer', 'uint', 'pointer', 'pointer']);
const getProc = new NativeFunction(user32.getExportByName('GetWindowLongPtrW'),
    'pointer', ['pointer', 'int']);
const rootWindow = new NativeFunction(user32.getExportByName('GetAncestor'),
    'pointer', ['pointer', 'uint']);
let window = null, focused = true, installed = false;
let mouseMessages = 0, focusMessages = 0;

rpc.exports = {
    setFocus(hwnd, active) {
        const target = ptr(hwnd);
        if (window && !window.equals(target)) throw new Error('One owned HWND only');
        window = target;
        focused = active;
        if (!installed) {
            installed = true;
            Interceptor.attach(user32.getExportByName('GetForegroundWindow'), {
                onLeave(result) { result.replace(focused ? rootWindow(window,2) : ptr(0)); }
            });
            Interceptor.attach(getProc(window, -4), {onEnter(args) {
                if (!args[0].equals(window)) return;
                const message = args[1].toUInt32();
                if (message === (focused ? 8 : 7)) { // conflicting focus event
                    focusMessages++;
                    args[1] = ptr(0); // WM_NULL, only this test window
                }
            }});
            Interceptor.attach(user32.getExportByName('DispatchMessageW'), {onEnter(args) {
                const msg = args[0], message = msg.add(Process.pointerSize).readU32();
                if (msg.readPointer().equals(window) && message >= 0x200 && message <= 0x20e) {
                    mouseMessages++;
                    msg.add(Process.pointerSize).writeU32(0);
                }
            }});
        }
        sendMessage(window, focused ? 7 : 8, ptr(0), ptr(0));
    },
    stats() { return {focused, suppressed_mouse_messages:mouseMessages,
                      suppressed_focus_messages:focusMessages}; }
};
