// Test-only input on the owned terminal's UI thread. No global SendInput,
// foreground changes, layout activation or modifications to the agent process.
const U = Process.getModuleByName('user32.dll');
const getState = new NativeFunction(U.getExportByName('GetKeyboardState'), 'int', ['pointer']);
const setState = new NativeFunction(U.getExportByName('SetKeyboardState'), 'int', ['pointer']);
const sendMessage = new NativeFunction(U.getExportByName('SendMessageW'), 'pointer', ['pointer','uint','pointer','pointer']);
let pending = null, completed = null;
let isolatedMouseWindow = null;
Interceptor.attach(U.getExportByName('DispatchMessageW'), {onEnter(args) {
    const msg = args[0];
    const message = msg.add(Process.pointerSize).readU32();
    // Opt-in isolation of this fixture's HWND from queued desktop mouse input.
    // SendMessage-based fixture actions still execute the real window procedure.
    if (isolatedMouseWindow && msg.readPointer().equals(isolatedMouseWindow) &&
        message >= 0x200 && message <= 0x20e) {
        msg.add(Process.pointerSize).writeU32(0); // WM_NULL, only this queued MSG
        return;
    }
    if (message !== 0x8322 || !pending) return;
    const op = pending; pending = null;
    const hwnd = msg.readPointer(), original = Memory.alloc(256), state = Memory.alloc(256);
    if (!getState(original)) { completed = {id:op.id,error:'GetKeyboardState'}; return; }
    state.writeByteArray(new Uint8Array(256));
    for (const key of op.modifiers || []) state.add(key).writeU8(0x80);
    const alt = (op.modifiers || []).some(k => k === 18 || k === 164 || k === 165);
    const lp = 1 | ((op.scan || 0) << 16) | (alt ? 0x20000000 : 0);
    try {
        if (!setState(state)) throw new Error('SetKeyboardState');
        if (op.mouse) {
            for (const m of op.mouse) sendMessage(hwnd, m.message, ptr(m.keys), ptr(m.point));
        } else {
            sendMessage(hwnd, alt ? 0x104 : 0x100, ptr(op.key), ptr(lp));
            sendMessage(hwnd, alt ? 0x105 : 0x101, ptr(op.key), ptr((lp | 0xc0000000) >>> 0));
        }
        completed = {id:op.id};
    } finally { setState(original); }
}});
rpc.exports = {
    isolateMouse(hwnd) { isolatedMouseWindow = ptr(hwnd); },
    key(op) { if (pending) throw new Error('Pending key'); completed = null; pending = op; },
    result() { return completed; }
};
