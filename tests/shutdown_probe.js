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
        send({event:'probe-phase', phase:'window-data'});
        const window = ptr(value), seat = getData(window, -21);
        if (seat.isNull() || !isWindow(window)) throw new Error('No live fixture seat');
        const thread = getThread(window, ptr(0));
        let freed = false, heapListener = null, comListener = null, windowListener = null;
        const detached = [];
        send({event:'probe-phase', phase:'install-heap-observer'});
        heapListener = Interceptor.attach(Process.getModuleByName('ntdll.dll').getExportByName('RtlFreeHeap'), {
            onEnter(args) {
                this.watchedSeat = args[2].equals(seat);
            },
            onLeave(result) {
                if (this.watchedSeat) {
                    freed = !result.isNull();
                    heapListener.detach(); heapListener = null; detached.push('heap');
                    send({event:'seat-free', success:freed, window_alive:!!isWindow(window)});
                }
            }
        });
        send({event:'probe-phase', phase:'install-com-observer'});
        comListener = Interceptor.attach(Process.getModuleByName('ole32.dll').getExportByName('CoUninitialize'), {
            onEnter() {
                this.watchedThread = this.threadId === thread;
                if (this.watchedThread)
                    send({event:'com-uninitialize', window_alive:!!isWindow(window), seat_freed:freed});
            },
            onLeave() {
                if (!this.watchedThread) return;
                const alive = !!isWindow(window);
                // Observe callbacks through the complete COM cleanup, then
                // retire this script's hooks before CRT/DLL shutdown. Do not
                // leave JavaScript heap callbacks installed as worker threads
                // disappear. No application call, result or lifetime is changed.
                if (heapListener) { heapListener.detach(); heapListener = null; detached.push('heap'); }
                windowListener.detach(); windowListener = null; detached.push('window');
                comListener.detach(); comListener = null; detached.push('com');
                send({event:'com-uninitialize-return', window_alive:alive, seat_freed:freed,
                      detached_observers:detached});
            }
        });
        send({event:'probe-phase', phase:'install-window-observer'});
        windowListener = Interceptor.attach(getData(window, -4), {
            onEnter(args) {
                if (freed && args[0].equals(window))
                    send({event:'callback-after-seat-free', message:args[1].toUInt32()});
            }
        });
        send({event:'probe-phase', phase:'observers-installed'});
    }
};
