// Observe only the fixture's window and its UI thread. No window messages,
// allocator arguments, return values or process lifetime are modified.
const user32 = Process.getModuleByName('user32.dll');
const isWindow = new NativeFunction(user32.getExportByName('IsWindow'), 'int', ['pointer']);
const getData = new NativeFunction(user32.getExportByName('GetWindowLongPtrW'),
    'pointer', ['pointer', 'int']);
const getThread = new NativeFunction(user32.getExportByName('GetWindowThreadProcessId'),
    'uint', ['pointer', 'pointer']);
rpc.exports = {
    watch(value) {
        const window = ptr(value), seat = getData(window, -21);
        if (seat.isNull() || !isWindow(window)) throw new Error('No live fixture seat');
        const thread = getThread(window, ptr(0));
        let freed = false;
        Interceptor.attach(Process.getModuleByName('ntdll.dll').getExportByName('RtlFreeHeap'), {
            onEnter(args) {
                if (args[2].equals(seat)) {
                    freed = true;
                    send({event:'seat-free', window_alive:!!isWindow(window)});
                }
            }
        });
        Interceptor.attach(Process.getModuleByName('ole32.dll').getExportByName('CoUninitialize'), {
            onEnter() {
                if (this.threadId === thread)
                    send({event:'com-uninitialize', window_alive:!!isWindow(window), seat_freed:freed});
            }
        });
        Interceptor.attach(getData(window, -4), {
            onEnter(args) {
                if (freed && args[0].equals(window))
                    send({event:'callback-after-seat-free', message:args[1].toUInt32()});
            }
        });
    }
};
