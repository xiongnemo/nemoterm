// Model pointer movement only inside one fixture-owned terminal. SendMessage
// supplies all test motion. Queued desktop motion/leave events must not mix
// real modifier state with those synthetic button gestures. Explicit focus,
// capture cancellation, button messages and sent motion remain unmodified.
const user = Process.getModuleByName('user32.dll');
const getProc = new NativeFunction(user.getExportByName('GetWindowLongPtrW'),
    'pointer', ['pointer', 'int']);
const dispatchDepth = new Map();
let count = 0;
let suppressed = 0, tracked = 0;
const trackAddress=user.getExportByName('TrackMouseEvent');
const originalTrack=new NativeFunction(trackAddress,'int',['pointer']);
Interceptor.replace(trackAddress,new NativeCallback(function(event) {
    if (event.add(8).readPointer().equals(ownedWindow)) { tracked++;return 1; }
    return originalTrack(event);
},'int',['pointer']));
Interceptor.attach(user.getExportByName('DispatchMessageW'), {
    onEnter(args) {
        this.thread = Process.getCurrentThreadId();
        dispatchDepth.set(this.thread, (dispatchDepth.get(this.thread) || 0) + 1);
        const msg=args[0],message=msg.add(Process.pointerSize).readU32();
        if (msg.readPointer().equals(ownedWindow) && [0x200,0xa0,0x2a3].includes(message)) {
            suppressed++;
            if (count<512) send({sequence:++count,event:'suppressed-queued-pointer',message,
                keys:msg.add(2*Process.pointerSize).readPointer().toString()});
            msg.add(Process.pointerSize).writeU32(0);
        }
    },
    onLeave() {
        const depth = dispatchDepth.get(this.thread) - 1;
        if (depth) dispatchDepth.set(this.thread, depth);
        else dispatchDepth.delete(this.thread);
    }
});
rpc.exports.stats=function() { return {suppressed_queued_pointer:suppressed,owned_leave_requests:tracked}; };
Interceptor.attach(getProc(ownedWindow, -4), {
    onEnter(args) {
        if (!args[0].equals(ownedWindow) || count >= 512) return;
        const message = args[1].toUInt32();
        if (![7, 8, 0x1f, 0xa0, 0x200, 0x201, 0x202, 0x215, 0x2a3].includes(message)) return;
        send({sequence: ++count, message, keys: args[2].toString(),
              parameter: args[3].toString(), inside_dispatch: dispatchDepth.has(Process.getCurrentThreadId())});
    }
});
