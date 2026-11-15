// Fixture-only keyboard state on the owned terminal's UI thread. No SendInput,
// foreground activation, clipboard, or hooks in other processes.
const U = Process.getModuleByName('user32.dll');
const getState = new NativeFunction(U.getExportByName('GetKeyboardState'), 'int', ['pointer']);
const setState = new NativeFunction(U.getExportByName('SetKeyboardState'), 'int', ['pointer']);
const sendMessage = new NativeFunction(U.getExportByName('SendMessageW'), 'pointer', ['pointer','uint','pointer','pointer']);
let pending = null, completed = null;
Interceptor.attach(U.getExportByName('DispatchMessageW'), {onEnter(args) {
    const msg = args[0];
    if (msg.add(Process.pointerSize).readU32() !== 0x8323 || !pending) return;
    const op = pending; pending = null;
    const hwnd = msg.readPointer(), original = Memory.alloc(256), state = Memory.alloc(256);
    if (!getState(original)) { completed = {id:op.id,error:'GetKeyboardState'}; return; }
    let count = 0, error = null;
    try {
        for (const e of op.events) {
            const bytes = new Uint8Array(256);
            if (e.mods & 1) bytes[16] = bytes[160] = 0x80;
            if (e.mods & 4) bytes[17] = bytes[162] = 0x80;
            if (e.mods & 2) bytes[18] = bytes[164] = 0x80;
            bytes[20] |= e.state_before & 2 ? 1 : 0;
            bytes[144] |= e.state_before & 16 ? 1 : 0;
            bytes[e.vk] = (bytes[e.vk] & 1) | (e.down ? 0x80 : 0);
            bytes[16] = bytes[160] | bytes[161];
            bytes[17] = bytes[162] | bytes[163];
            bytes[18] = bytes[164] | bytes[165];
            state.writeByteArray(bytes);
            if (!setState(state)) throw new Error('SetKeyboardState');
            const alt = !!(e.mods & 2) || e.vk === 164;
            const lp = 1 | (e.scan << 16) | (alt ? 0x20000000 : 0) | (e.down ? 0 : 0xc0000000);
            sendMessage(hwnd, (alt ? 0x104 : 0x100)+(e.down ? 0 : 1), ptr(e.vk), ptr(lp >>> 0));
            count++;
        }
    } catch (e) { error = String(e); }
    finally {
        const restored = !!setState(original);
        completed = {id:op.id,count,restored};
        if (error) completed.error = error;
    }
}});
rpc.exports = {
    keys(op) { if (pending) throw new Error('Pending batch'); completed = null; pending = op; },
    result() { return completed; }
};
