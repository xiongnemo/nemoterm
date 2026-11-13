/* Test-only allocation metadata. No allocation payload is read.
 * All snapshots are instrumented diagnostics, never working-set acceptance.
 * CModule writable globals are externally allocated and retained until unload.
 * https://frida.re/docs/javascript-api/#cmodule
 */
let census = null;

function startCensus(scope, header) {
    if (Process.platform !== 'windows' || Process.pointerSize !== 8)
        throw Error('The native adapter requires Windows x64');
    if (scope.pid !== Process.id || census !== null)
        throw Error('Wrong owned PID or observer already initialized');
    const capacity = scope.capacity || 65536;
    if (!Number.isInteger(capacity) || capacity < 16 || capacity > 262144 ||
        (capacity & (capacity - 1)) !== 0) throw Error('Invalid table capacity');
    const ranges = scope.ranges || [];
    const heap = ptr(scope.heap || '0');
    if (ranges.length > 128 || (heap.isNull() && ranges.length === 0))
        throw Error('An explicit heap or pre-injection allocation ranges are required');
    const limits = Memory.alloc(Math.max(1, ranges.length) * 16);
    ranges.forEach((r, i) => {
        const start = ptr(r.start), end = ptr(r.end);
        if (start.compare(end) >= 0) throw Error('Invalid allocation range');
        limits.add(i * 16).writePointer(start);
        limits.add(i * 16 + 8).writePointer(end);
    });
    const kernel = Process.getModuleByName('kernel32.dll');
    const nt = Process.getModuleByName('ntdll.dll');
    const records = Memory.alloc(capacity * 40), state = Memory.alloc(64);
    const lock = Memory.alloc(8), selectedHeap = Memory.alloc(8), report = Memory.alloc(48);
    lock.writeU64(0); selectedHeap.writePointer(heap);
    const cm = new CModule(header + `
#include <gum/guminterceptor.h>
typedef char EntrySizeMustMatch[sizeof(ACEntry)==40?1:-1];
typedef char StateMustFit[sizeof(ACState)<=64?1:-1];
typedef struct { ACValue start,end; } Range;
typedef struct { ACValue heap,bytes,caller,old_address,old_generation,cutoff; } Call;
extern ACEntry records[];
extern ACState state;
extern ACValue lock,selected_heap;
extern Range limits[];
extern void acquire(gpointer);
extern void release(gpointer);
static int selected(ACValue address, ACValue heap) {
    unsigned i;
    if (!address) return 0;
    if (selected_heap) return heap==selected_heap;
    for (i=0;i<${ranges.length};i++)
        if (address>=limits[i].start && address<limits[i].end) return 1;
    return 0;
}
void census_initialize(void) { ac_init(&state,records,${capacity}); }
void census_report(ACValue *out) {
    acquire(&lock);
    out[0]=state.active;out[1]=state.errors;out[2]=state.generation;
    out[3]=state.live_count;out[4]=state.live_bytes;out[5]=state.capacity;
    release(&lock);
}
void census_freeze(void) {
    acquire(&lock);ac_freeze(&state);release(&lock);
}
static Call *context(GumInvocationContext *ic) {
    return gum_invocation_context_get_listener_invocation_data(ic,sizeof(Call));
}
void alloc_enter(GumInvocationContext *ic) {
    Call *v=context(ic);
    v->heap=(ACValue)gum_invocation_context_get_nth_argument(ic,0);
    v->bytes=(ACValue)gum_invocation_context_get_nth_argument(ic,2);
    v->caller=(ACValue)gum_invocation_context_get_return_address(ic);
}
void alloc_leave(GumInvocationContext *ic) {
    Call *v=context(ic);
    ACValue p=(ACValue)gum_invocation_context_get_return_value(ic);
    if (!selected(p,v->heap)) return;
    acquire(&lock);ac_record(&state,p,v->heap,v->bytes,v->caller);release(&lock);
}
void realloc_enter(GumInvocationContext *ic) {
    Call *v;
    alloc_enter(ic);v=context(ic);
    v->old_address=(ACValue)gum_invocation_context_get_nth_argument(ic,2);
    v->bytes=(ACValue)gum_invocation_context_get_nth_argument(ic,3);
    acquire(&lock);v->old_generation=ac_generation(&state,v->old_address);release(&lock);
}
void realloc_leave(GumInvocationContext *ic) {
    Call *v=context(ic);
    ACValue p=(ACValue)gum_invocation_context_get_return_value(ic);
    if (!p) return;
    acquire(&lock);
    if (selected(p,v->heap))
        ac_realloc_done(&state,v->old_address,v->old_generation,p,v->heap,v->bytes,v->caller);
    else
        ac_free_done(&state,v->old_address,v->old_generation,1);
    release(&lock);
}
void free_enter(GumInvocationContext *ic) {
    Call *v=context(ic);
    v->old_address=(ACValue)gum_invocation_context_get_nth_argument(ic,2);
    acquire(&lock);v->old_generation=ac_generation(&state,v->old_address);release(&lock);
}
void free_leave(GumInvocationContext *ic) {
    Call *v=context(ic);
    acquire(&lock);
    ac_free_done(&state,v->old_address,v->old_generation,
        (ACValue)gum_invocation_context_get_return_value(ic)!=0);
    release(&lock);
}
void destroy_enter(GumInvocationContext *ic) {
    Call *v=context(ic);
    v->heap=(ACValue)gum_invocation_context_get_nth_argument(ic,0);
    acquire(&lock);v->cutoff=state.generation;release(&lock);
}
void destroy_leave(GumInvocationContext *ic) {
    Call *v=context(ic);
    acquire(&lock);
    ac_destroy_done(&state,v->heap,v->cutoff,
        gum_invocation_context_get_return_value(ic)==NULL);
    release(&lock);
}
`, { records, state, lock, limits, selected_heap: selectedHeap,
        acquire: kernel.getExportByName('AcquireSRWLockExclusive'),
        release: kernel.getExportByName('ReleaseSRWLockExclusive') });
    census = { cm, records, state, lock, limits, selectedHeap, report, capacity,
        scope, hooks: [], stopped: false,
        stop: new NativeFunction(cm.census_freeze, 'void', []),
        reportState: new NativeFunction(cm.census_report, 'void', ['pointer']) };
    new NativeFunction(cm.census_initialize, 'void', [])();
    try {
        for (const [name, enter, leave] of [
            ['RtlAllocateHeap', 'alloc_enter', 'alloc_leave'],
            ['RtlReAllocateHeap', 'realloc_enter', 'realloc_leave'],
            ['RtlFreeHeap', 'free_enter', 'free_leave'],
            ['RtlDestroyHeap', 'destroy_enter', 'destroy_leave']]) {
            census.hooks.push(Interceptor.attach(nt.getExportByName(name),
                { onEnter: cm[enter], onLeave: cm[leave] }));
        }
        Interceptor.flush();
    } catch (error) {
        census.stop();
        census.hooks.forEach(h => h.detach());
        throw error;
    }
    return censusCounts();
}

function censusCounts() {
    if (!census) throw Error('Observer not initialized');
    const p = census.report;
    census.reportState(p);
    return { active: p.readU64().toNumber(), errors: p.add(8).readU64().toNumber(),
        generation: p.add(16).readU64().toString(), live_count: p.add(24).readU64().toNumber(),
        live_requested_bytes: p.add(32).readU64().toString(), capacity: census.capacity };
}

function freezeCensus() {
    if (!census) throw Error('Observer not initialized');
    census.stop();
    census.hooks.forEach(h => h.detach());census.hooks = [];
    Interceptor.flush();census.stopped = true;
    const counts = censusCounts(), entries = [];
    for (let i = 0; i < census.capacity; i++) {
        const p = census.records.add(i * 40), address = p.readPointer();
        if (address.compare(ptr(1)) <= 0) continue;
        const caller = p.add(16).readPointer(), module = Process.findModuleByAddress(caller);
        entries.push({ address: address.toString(), heap: p.add(8).readPointer().toString(),
            caller: caller.toString(), module: module ? module.name : null,
            offset: module ? caller.sub(module.base).toString() : null,
            requested_bytes: p.add(24).readU64().toString(),
            generation: p.add(32).readU64().toString() });
    }
    if (entries.length !== counts.live_count) throw Error('Inconsistent frozen census');
    return { pid: Process.id, instrumented: true, memory_acceptance: false,
        scope: census.scope, counts, entries, valid: counts.errors === 0,
        limits: 'Observed heap blocks only; excludes pre-attach and out-of-scope allocations. Requested bytes are not private working set. Instrumentation may change allocation behaviour.' };
}

rpc.exports = { initialize: startCensus, counts: censusCounts, freeze: freezeCensus };
