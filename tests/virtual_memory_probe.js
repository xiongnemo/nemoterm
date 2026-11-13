/* Scoped diagnostic metadata only: API in/out addresses, sizes and call stacks.
 * Never reads allocation payloads, changes target arguments or trims memory.
 */
let virtualTrace=null;

function startVirtualTrace(scope) {
    if (Process.platform!=='windows' || Process.pointerSize!==8 || scope.pid!==Process.id || virtualTrace)
        throw Error('Expected a new observer for this owned Windows x64 PID');
    if (!scope.ranges || !scope.ranges.length || scope.ranges.length>64)
        throw Error('Explicit pre-attach reservation ranges are required');
    const ranges=scope.ranges.map(r=>({start:ptr(r.start),end:ptr(r.end)}));
    if (ranges.some(r=>r.start.compare(r.end)>=0)) throw Error('Invalid range');
    const capacity=scope.event_capacity || 4096;
    if (!Number.isInteger(capacity) || capacity<8 || capacity>16384) throw Error('Invalid event capacity');
    const trace=virtualTrace={scope,capacity,events:[],errors:[],overflow:0,hooks:[],active:true,
        calls:{},ignored_out_of_scope:0,ignored_process_handle:0,started:Date.now()};
    function matches(base,size) {
        if (base.isNull()) return false;
        const end=base.add(size);
        return ranges.some(r=>base.compare(r.end)<0 &&
            (size.compare(uint64(0))===0 ? base.compare(r.start)>=0 : end.compare(r.start)>0));
    }
    function location(address) {
        const module=Process.findModuleByAddress(address);
        return {address:address.toString(),module:module ? module.name : null,
            offset:module ? address.sub(module.base).toString() : null};
    }
    const nt=Process.getModuleByName('ntdll.dll');
    try {
        // NtAllocateVirtualMemory has ZeroBits at argument 2; Ex omits it.
        for (const [name,sizeIndex,flagsIndex,protectIndex] of [
                ['NtAllocateVirtualMemory',3,4,5],
                ['NtAllocateVirtualMemoryEx',2,3,4],
                ['NtFreeVirtualMemory',2,3,-1]]) {
            const address=nt.findExportByName(name);
            if (!address) {
                if (name!=='NtAllocateVirtualMemoryEx') throw Error('Missing required API '+name);
                continue;
            }
            trace.calls[name]=0;
            trace.hooks.push(Interceptor.attach(address,{
                onEnter(args) {
                    this.observe=false;
                    if (!trace.active) return;
                    trace.calls[name]++;
                    // Only NtCurrentProcess. An arbitrary process handle is
                    // deliberately outside this owned-process diagnostic.
                    if (!args[0].equals(ptr('0xffffffffffffffff'))) {
                        trace.ignored_process_handle++;return;
                    }
                    this.observe=true;this.basePointer=args[1];this.sizePointer=args[sizeIndex];
                    this.flags=args[flagsIndex].toUInt32();
                    this.protection=protectIndex<0 ? null : args[protectIndex].toUInt32();
                    this.caller=this.returnAddress;this.frames=[];this.requested=null;this.readError=null;
                    try {
                        const base=this.basePointer.readPointer(),size=this.sizePointer.readU64();
                        this.requested={base,size};
                        if (matches(base,size))
                            this.frames=Thread.backtrace(this.context,Backtracer.ACCURATE).slice(0,12);
                    } catch (error) { this.readError=String(error); }
                },
                onLeave(value) {
                    if (!this.observe || !trace.active) return;
                    const status=value.toInt32();
                    try {
                        const result=status>=0 ? {base:this.basePointer.readPointer(),size:this.sizePointer.readU64()} : this.requested;
                        if (!result || !matches(result.base,result.size)) {
                            trace.ignored_out_of_scope++;return;
                        }
                        if (this.readError) throw Error(this.readError);
                        if (trace.events.length>=capacity) {trace.overflow++;return;}
                        trace.events.push({sequence:trace.events.length+1,seconds:(Date.now()-trace.started)/1000,
                            api:name,status,success:status>=0,thread_id:this.threadId,
                            flags:this.flags,protection:this.protection,
                            requested_address:this.requested.base.toString(),requested_bytes:this.requested.size.toString(),
                            address:result.base.toString(),bytes:result.size.toString(),
                            caller:location(this.caller),stack:this.frames.map(location)});
                    } catch (error) {
                        if (trace.errors.length<16) trace.errors.push({api:name,error:String(error)});
                        else trace.overflow++;
                    }
                }
            }));
        }
        Interceptor.flush();
    } catch (error) {
        trace.active=false;trace.hooks.forEach(h=>h.detach());trace.hooks=[];
        throw error;
    }
    return {apis:Object.keys(trace.calls),event_capacity:capacity};
}

function freezeVirtualTrace() {
    if (!virtualTrace) throw Error('Observer not initialized');
    const trace=virtualTrace;
    trace.active=false;trace.hooks.forEach(h=>h.detach());trace.hooks=[];Interceptor.flush();
    return {pid:Process.id,scope:trace.scope,active:false,valid:!trace.overflow && !trace.errors.length,
        instrumented:true,memory_acceptance:false,event_capacity:trace.capacity,
        events:trace.events,overflow:trace.overflow,errors:trace.errors,calls:trace.calls,
        ignored_out_of_scope:trace.ignored_out_of_scope,ignored_process_handle:trace.ignored_process_handle,
        limits:'Selected address ranges and NtCurrentProcess calls only. API sizes are not resident pages or net new commitment. Other allocation paths and incomplete stacks remain unresolved. Memory and event snapshots are not atomic.'};
}

rpc.exports={initialize:startVirtualTrace,freeze:freezeVirtualTrace};
