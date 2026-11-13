/* Diagnostic only: synchronous pipe I/O called directly by the owned frontend.
 * No argument, result or byte modifications. Frida's own callers are excluded.
 * https://frida.re/docs/javascript-api/#interceptor */
'use strict';
const main = Process.mainModule;
const end = main.base.add(main.size);
const kernel = Process.getModuleByName('kernelbase.dll');
const fileType = new NativeFunction(kernel.getExportByName('GetFileType'), 'uint', ['pointer']);
let events = 0, bytes = 0, truncated = false;

function emit(record, data) {
    if (truncated) return;
    const length = data ? data.byteLength : 0;
    if (events >= 20000 || bytes + length > 4 * 1024 * 1024) {
        truncated = true;
        send({kind: 'truncated', events, bytes});
        return;
    }
    record.event = ++events;
    record.time_ms = Date.now();
    bytes += length;
    send(record, data || null);
}

for (const api of ['ReadFile', 'WriteFile']) {
    Interceptor.attach(kernel.getExportByName(api), {
        onEnter(args) {
            this.owned = this.returnAddress.compare(main.base) >= 0 && this.returnAddress.compare(end) < 0;
            if (!this.owned) return;
            const error = this.lastError;
            this.owned = fileType(args[0]) === 3; // FILE_TYPE_PIPE
            this.lastError = error;
            if (!this.owned) return;
            this.handle = args[0].toString();
            this.buffer = args[1];
            this.requested = args[2].toUInt32();
            this.count = args[3];
            this.overlapped = !args[4].isNull();
            this.caller = this.returnAddress.sub(main.base).toString();
        },
        onLeave(result) {
            if (!this.owned) return;
            const record = {kind: 'io', api, handle: this.handle, thread: this.threadId,
                caller_rva: this.caller, requested: this.requested,
                success: result.toInt32() !== 0, last_error: this.lastError,
                overlapped: this.overlapped};
            try {
                // PuTTY's ConPTY handles use synchronous I/O. Report rather
                // than guess if a different call path is encountered.
                if (record.success && !this.overlapped && !this.count.isNull()) {
                    record.completed = this.count.readU32();
                    if (record.completed > this.requested || record.completed > 65536)
                        throw new Error('unexpected completed byte count');
                    emit(record, record.completed ? this.buffer.readByteArray(record.completed) : null);
                } else {
                    emit(record);
                }
            } catch (error) {
                record.capture_error = String(error);
                emit(record);
            }
        }
    });
}
send({kind: 'ready', pid: Process.id, module: main.path, base: main.base.toString(), size: main.size,
    coverage: 'synchronous pipe calls whose direct return address is in the frontend image; reads already pending at attach are not captured'});
