// Scoped to the newly spawned fixture process. No real clipboard is opened.
const user = Process.getModuleByName('user32.dll');
const kernel = Process.getModuleByName('kernel32.dll');
const getProp = new NativeFunction(user.getExportByName('GetPropW'), 'pointer', ['pointer','pointer']);
const sendMessage = new NativeFunction(user.getExportByName('SendMessageW'), 'pointer',
    ['pointer','uint','pointer','pointer']);
const globalAlloc = new NativeFunction(kernel.getExportByName('GlobalAlloc'), 'pointer', ['uint','size_t']);
const globalLock = new NativeFunction(kernel.getExportByName('GlobalLock'), 'pointer', ['pointer']);
const globalUnlock = new NativeFunction(kernel.getExportByName('GlobalUnlock'), 'int', ['pointer']);
const globalFree = new NativeFunction(kernel.getExportByName('GlobalFree'), 'pointer', ['pointer']);
const getPid = new NativeFunction(user.getExportByName('GetWindowThreadProcessId'), 'uint', ['pointer','pointer']);
let armed = '', failurePending = false, closeDialogs = false;
const hits = [];
Interceptor.attach(kernel.getExportByName('CreateProcessW'), {
    onEnter(args) {
        if (armed === 'process' && !args[1].isNull() && args[1].readUtf16String().includes('session_fixture.py')) {
            armed = '';
            failurePending = true;
            this.failed = true;
            this.name = Memory.allocUtf16String('Z:\\nemoterm-missing-fixture-'+Process.id+'\\no.exe');
            args[0] = this.name;
        }
    },
    onLeave(result) {
        if (this.failed) hits.push({event:'create-failure', result:result.toInt32()});
    }
});
Interceptor.attach(user.getExportByName('CreateWindowExW'), {
    onEnter(args) {
        if (armed === 'window' && args[1].compare(ptr(65535)) > 0 &&
            args[1].readUtf16String() === 'Nemoterm') {
            armed = '';
            failurePending = true;
            this.failed = true;
            this.name = Memory.allocUtf16String('NemotermMissingFixtureClass');
            args[1] = this.name;
        }
    },
    onLeave(result) {
        if (this.failed) hits.push({event:'window-failure', result:result.toString()});
    }
});
for (const suffix of ['A','W']) {
    const address = user.getExportByName('MessageBox'+suffix);
    const original = new NativeFunction(address, 'int', ['pointer','pointer','pointer','uint']);
    Interceptor.replace(address, new NativeCallback((hwnd,message,title,flags) => {
        const value = suffix === 'W' ? message.readUtf16String() : message.readUtf8String();
        if (closeDialogs && value === 'Connection closed by remote host') {
            hits.push({event:'inactive-dialog'});
            return 1;
        }
        if (failurePending && (value.includes('Unable to open terminal:') ||
            value.includes('Unable to create terminal window:'))) {
            failurePending = false;
            hits.push({event:'start-error', message:value});
            return 1;
        }
        return original(hwnd,message,title,flags);
    }, 'int', ['pointer','pointer','pointer','uint']));
}
function owned(value) {
    const hwnd = ptr(value), pid = Memory.alloc(4);
    getPid(hwnd,pid);
    if (pid.readU32() !== Process.id) throw new Error('Not an owned fixture window');
    return hwnd;
}
rpc.exports = {
    arm(kind) { armed = kind; },
    inactiveDialogs() { closeDialogs = true; },
    status() { return {armed,failurePending,hits}; },
    session(value) {
        return getProp(owned(value),Memory.allocUtf16String('NemotermSessionId')).toString();
    },
    paste(value,cookie,text) {
        const hwnd = owned(value), data = globalAlloc(0x42,(text.length+1)*2);
        if (data.isNull()) throw new Error('GlobalAlloc failed');
        const memory = globalLock(data);
        memory.writeUtf16String(text);
        globalUnlock(data);
        const size = Process.pointerSize, request = Memory.alloc(size*4);
        request.writePointer(hwnd);
        request.add(size).writePointer(ptr(cookie));
        request.add(size*2).writePointer(data);
        request.add(size*3).writeU8(1);
        try { sendMessage(hwnd,0x8004,ptr(cookie),request); }
        finally { globalFree(data); }
    }
};
