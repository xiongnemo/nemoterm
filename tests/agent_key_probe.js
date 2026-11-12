// Test-only input on the owned terminal's UI thread. No global SendInput,
// foreground changes, layout activation or modifications to the agent process.
const U = Process.getModuleByName('user32.dll');
const getState = new NativeFunction(U.getExportByName('GetKeyboardState'), 'int', ['pointer']);
const setState = new NativeFunction(U.getExportByName('SetKeyboardState'), 'int', ['pointer']);
const sendMessage = new NativeFunction(U.getExportByName('SendMessageW'), 'pointer', ['pointer','uint','pointer','pointer']);
let pending = null, completed = null;
Interceptor.attach(U.getExportByName('DispatchMessageW'), {onEnter(args) {
    const msg = args[0];
    if (msg.add(8).readU32() !== 0x8322 || !pending) return;
    const op = pending; pending = null;
    const hwnd = msg.readPointer(), original = Memory.alloc(256), state = Memory.alloc(256);
    if (!getState(original)) { completed = {id:op.id,error:'GetKeyboardState'}; return; }
    state.writeByteArray(new Uint8Array(256));
    for (const key of op.modifiers || []) state.add(key).writeU8(0x80);
    const lp = 1 | (op.scan << 16);
    try {
        if (!setState(state)) throw new Error('SetKeyboardState');
        sendMessage(hwnd, 0x100, ptr(op.key), ptr(lp));
        sendMessage(hwnd, 0x101, ptr(op.key), ptr((lp | 0xc0000000) >>> 0));
        completed = {id:op.id};
    } finally { setState(original); }
}});
rpc.exports = {
    key(op) { if (pending) throw new Error('Pending key'); completed = null; pending = op; },
    result() { return completed; }
};
