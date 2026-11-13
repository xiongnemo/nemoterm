// Diagnostic only: bounded creation/close metadata, never names or payloads.
// Raw PCs are resolved against the retained module inventory outside hooks.
'use strict';
const limit = 8192;
const durationMs = 60000;
const events = [], active = new Map(), listeners = [];
let enabled = false, overflow = false, sequence = 0, stopReason = null;
const begun = Date.now();
function modules() {
    return Process.enumerateModules().map(m => ({name:m.name, base:m.base.toString(), size:m.size}));
}
const initialModules = modules();
function record(value) {
    if (events.length >= limit) { overflow = true; enabled = false; return null; }
    value.sequence = ++sequence; value.milliseconds = Date.now() - begun;
    events.push(value); return value.sequence;
}
function frames(context, caller) {
    return {caller:caller.toString(), frames:Thread.backtrace(context, Backtracer.ACCURATE).slice(0,12).map(p => p.toString())};
}
const timer = setTimeout(() => { enabled = false; stopReason = 'duration'; }, durationMs);
const nt = Process.getModuleByName('ntdll.dll');
for (const [name, type] of [['NtCreateEvent','Event'], ['NtCreateSemaphore','Semaphore'],
                          ['NtCreateTimer','Timer'], ['NtCreateIoCompletion','IoCompletion'],
                          ['NtOpenEvent','Event'], ['NtOpenIoCompletion','IoCompletion'],
                          ['NtCreateWaitCompletionPacket','WaitCompletionPacket']]) {
    listeners.push(Interceptor.attach(nt.getExportByName(name), {
        onEnter(args) {
            this.observe = enabled;
            if (!this.observe) return;
            this.output = args[0]; this.access = args[1].toUInt32();
            this.trace = frames(this.context, this.returnAddress);
        },
        onLeave(status) {
            if (!this.observe || !enabled) return;
            if (status.toInt32() < 0) {
                record({operation:'create-failed', api:name, type, status:status.toString()}); return;
            }
            const handle = this.output.readPointer().toString();
            const generation = record({operation:'create', api:name, type, handle,
                access:this.access, thread:this.threadId, ...this.trace});
            if (generation !== null) active.set(handle, {handle, type, generation});
        }
    }));
}
listeners.push(Interceptor.attach(nt.getExportByName('NtDuplicateObject'), {
    onEnter(args) {
        this.observe = enabled;
        if (!this.observe) return;
        this.sourceProcess = args[0].toString(); this.sourceHandle = args[1].toString();
        this.targetProcess = args[2].toString(); this.output = args[3];
        this.options = args[6].toUInt32(); this.trace = frames(this.context, this.returnAddress);
        this.sourceGeneration = this.sourceProcess === '0xffffffffffffffff' ? active.get(this.sourceHandle) : undefined;
    },
    onLeave(status) {
        if (!this.observe || !enabled) return;
        const succeeded = status.toInt32() >= 0;
        const handle = succeeded && !this.output.isNull() ? this.output.readPointer().toString() : null;
        const type = this.sourceGeneration?.type || 'Unknown';
        const generation = record({operation:succeeded?'duplicate':'duplicate-failed', api:'NtDuplicateObject',
            sourceProcess:this.sourceProcess, sourceHandle:this.sourceHandle, targetProcess:this.targetProcess,
            sourceGeneration:this.sourceGeneration?.generation || null, handle, type, options:this.options,
            status:status.toString(), thread:this.threadId, ...this.trace});
        // Only the current-process pseudo handle establishes local ownership.
        // Other process handle values are retained metadata, never dereferenced.
        if (succeeded && handle && this.targetProcess === '0xffffffffffffffff' && generation !== null)
            active.set(handle,{handle,type,generation});
        if (succeeded && (this.options & 1) && this.sourceGeneration &&
            active.get(this.sourceHandle)?.generation === this.sourceGeneration.generation)
            active.delete(this.sourceHandle);
    }
}));
listeners.push(Interceptor.attach(nt.getExportByName('NtClose'), {
    onEnter(args) {
        this.entry = enabled ? active.get(args[0].toString()) : undefined;
        if (this.entry) this.trace = frames(this.context, this.returnAddress);
    },
    onLeave(status) {
        if (!this.entry || !enabled) return;
        const succeeded = status.toInt32() >= 0;
        record({operation:succeeded?'close':'close-failed', ...this.entry,
            thread:this.threadId, status:status.toString(), ...this.trace});
        if (succeeded && active.get(this.entry.handle)?.generation === this.entry.generation)
            active.delete(this.entry.handle);
    }
}));
enabled = true;
rpc.exports = {
    mark(label) {
        if (!enabled) throw new Error('Trace no longer accepting markers');
        return record({operation:'mark', label});
    },
    stop() {
        enabled = false; clearTimeout(timer);
        for (const listener of listeners) listener.detach();
        Interceptor.flush();
        return {limit, durationMs, overflow, stopReason:stopReason || 'caller',
            frida:Frida.version, platform:Process.platform, arch:Process.arch, pid:Process.id,
            events, outstanding:Array.from(active.values()), initialModules, finalModules:modules(),
            limitations:['Selected APIs after attach only; other creation paths and kernel-created handles are unobserved',
                'Duplicate ownership is tracked only for the current-process pseudo handle; other process-handle targets are metadata',
                'Unmatched live generations are not proof of a leak',
                'Injection changes resource counts and scheduling; not memory acceptance']};
    }
};
