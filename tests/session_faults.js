// Scoped to the newly spawned fixture process. No real clipboard is opened.
const user = Process.getModuleByName('user32.dll');
const kernel = Process.getModuleByName('kernel32.dll');
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
rpc.exports = {
    arm(kind) { armed = kind; },
    inactiveDialogs() { closeDialogs = true; },
    status() { return {armed,failurePending,hits}; }
};
