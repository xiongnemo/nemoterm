/* Appended only by the controlled native adapter test, never the app probe. */
rpc.exports.allheapstest = function(pid, header) {
    const kernel = Process.getModuleByName('kernel32.dll');
    const nt = Process.getModuleByName('ntdll.dll');
    const create = new NativeFunction(kernel.getExportByName('HeapCreate'),
        'pointer', ['uint', 'size_t', 'size_t']);
    const destroy = new NativeFunction(kernel.getExportByName('HeapDestroy'), 'int', ['pointer']);
    const alloc = new NativeFunction(nt.getExportByName('RtlAllocateHeap'),
        'pointer', ['pointer', 'uint', 'size_t']);
    const free = new NativeFunction(nt.getExportByName('RtlFreeHeap'),
        'uint8', ['pointer', 'uint', 'pointer']);
    const first = create(0, 0, 0), second = create(0, 0, 0);
    if (first.isNull() || second.isNull()) throw Error('Private heap creation failed');
    try {
        let rejected = false;
        try { startCensus({pid, heap:first.toString(), all_post_attach_heaps:true}, header); }
        catch (e) { rejected = String(e).includes('cannot also select'); }
        if (!rejected) throw Error('Mixed scope was not rejected');
        startCensus({pid, all_post_attach_heaps:true, capacity:65536}, header);
        const a = alloc(first, 0, 113), b = alloc(second, 0, 257), gone = alloc(second, 0, 509);
        if (a.isNull() || b.isNull() || gone.isNull()) throw Error('Test allocation failed');
        if (!free(second, 0, gone)) throw Error('Test free failed');
        const result = freezeCensus();
        const entryA = result.entries.find(e => e.address === a.toString());
        const entryB = result.entries.find(e => e.address === b.toString());
        if (!result.valid || !entryA || !entryB || entryA.heap !== first.toString() ||
            entryB.heap !== second.toString() || entryA.requested_bytes !== '113' ||
            entryB.requested_bytes !== '257' || result.entries.some(e =>
                e.address === gone.toString() && e.heap === second.toString()))
            throw Error('All-heap live allocation metadata mismatch');
        return {checks:['mixed scope rejected','two independent heaps captured',
            'freed block absent'], final:result, expected_entries:[entryA,entryB]};
    } finally {
        if (census && !census.stopped) freezeCensus();
        destroy(first);destroy(second);
    }
};
rpc.exports.selftest = function(pid, header, retainLiveBlock, rangeScope) {
    const kernel = Process.getModuleByName('kernel32.dll');
    const nt = Process.getModuleByName('ntdll.dll');
    const heapCreate = new NativeFunction(kernel.getExportByName('HeapCreate'),
        'pointer', ['uint', 'size_t', 'size_t']);
    const heapDestroy = new NativeFunction(kernel.getExportByName('HeapDestroy'), 'int', ['pointer']);
    const alloc = new NativeFunction(nt.getExportByName('RtlAllocateHeap'),
        'pointer', ['pointer', 'uint', 'size_t']);
    const realloc = new NativeFunction(nt.getExportByName('RtlReAllocateHeap'),
        'pointer', ['pointer', 'uint', 'pointer', 'size_t']);
    const free = new NativeFunction(nt.getExportByName('RtlFreeHeap'),
        'uint8', ['pointer', 'uint', 'pointer']);
    const heap = heapCreate(0, rangeScope ? 1048576 : 0, rangeScope ? 2097152 : 0);
    if (heap.isNull()) throw Error('Private test heap creation failed');
    let destroyed = false, excludedHeap = ptr(0);
    const checks = [];
    function check(name, count, bytes) {
        const actual = censusCounts();
        if (actual.errors !== 0 || actual.live_count !== count ||
            actual.live_requested_bytes !== String(bytes))
            throw Error(name + ': ' + JSON.stringify(actual));
        checks.push({name, ...actual});
    }
    try {
        const scope = {pid, heap: heap.toString(), capacity: 64};
        if (rangeScope) {
            // Query the complete reservation, including its uncommitted tail.
            // Windows x64 MEMORY_BASIC_INFORMATION: allocation at 8, size at 24.
            const query = new NativeFunction(kernel.getExportByName('VirtualQuery'),
                'size_t', ['pointer', 'pointer', 'size_t']);
            const info = Memory.alloc(48);
            function region(address) {
                if (query(address, info, 48).toString() !== '48')
                    throw Error('VirtualQuery failed');
                return {base: info.readPointer(), allocation: info.add(8).readPointer(),
                    size: info.add(24).readU64(), state: info.add(32).readU32()};
            }
            const base = region(heap).allocation;
            if (base.isNull()) throw Error('Missing private heap reservation');
            let end = base, complete = false;
            for (let i = 0; i < 256; i++) {
                const part = region(end);
                if (part.state === 0x10000 || !part.allocation.equals(base)) {
                    complete = true; break;
                }
                const next = part.base.add(part.size);
                if (next.compare(end) <= 0) throw Error('Non-advancing reservation');
                end = next;
            }
            if (!complete || end.compare(base) <= 0) throw Error('Incomplete reservation');
            delete scope.heap;
            scope.ranges = [{start: base.toString(), end: end.toString()}];
            excludedHeap = heapCreate(0, 0, 0);
            if (excludedHeap.isNull()) throw Error('Excluded heap creation failed');
        }
        startCensus(scope, header);
        check('empty', 0, 0);
        if (rangeScope) {
            let outside = alloc(excludedHeap, 0, 512);
            if (outside.isNull()) throw Error('Excluded allocation failed');
            check('out-of-range-allocation-excluded', 0, 0);
            outside = realloc(excludedHeap, 0, outside, 768);
            if (outside.isNull() || !free(excludedHeap, 0, outside))
                throw Error('Excluded reallocation/free failed');
            check('out-of-range-realloc-free-excluded', 0, 0);
        }
        let a = alloc(heap, 0, 64), b = alloc(heap, 0, 128);
        if (a.isNull() || b.isNull()) throw Error('Allocation failed');
        check('two-allocations', 2, 192);
        a = realloc(heap, 0, a, 96);
        if (a.isNull()) throw Error('Reallocation failed');
        check('successful-realloc', 2, 224);
        if (!free(heap, 0, a)) throw Error('Free failed');
        check('successful-free', 1, 128);
        for (let i = 0; i < 100; i++) {
            const p = alloc(heap, 0, 32);
            if (p.isNull() || !free(heap, 0, p)) throw Error('Reuse cycle failed');
        }
        check('allocation-reuse-cycles', 1, 128);
        if (retainLiveBlock) {
            check('live-block-before-freeze', 1, 128);
        } else {
            if (!heapDestroy(heap)) throw Error('Heap destruction failed');
            destroyed = true;
            check('heap-destruction', 0, 0);
        }
        return {checks, final: freezeCensus(), expected_address: b.toString(),
            expected_heap: heap.toString()};
    } finally {
        if (census) freezeCensus();
        if (!destroyed) heapDestroy(heap);
        if (!excludedHeap.isNull()) heapDestroy(excludedHeap);
    }
};

rpc.exports.lfhtest = function(pid, header) {
    const kernel=Process.getModuleByName('kernel32.dll'),nt=Process.getModuleByName('ntdll.dll');
    const create=new NativeFunction(kernel.getExportByName('HeapCreate'),'pointer',['uint','size_t','size_t']);
    const destroy=new NativeFunction(kernel.getExportByName('HeapDestroy'),'int',['pointer']);
    const setInfo=new NativeFunction(kernel.getExportByName('HeapSetInformation'),
        'int',['pointer','uint','pointer','size_t']);
    const queryInfo=new NativeFunction(kernel.getExportByName('HeapQueryInformation'),
        'int',['pointer','uint','pointer','size_t','pointer']);
    const alloc=new NativeFunction(nt.getExportByName('RtlAllocateHeap'),'pointer',['pointer','uint','size_t']);
    const free=new NativeFunction(nt.getExportByName('RtlFreeHeap'),'uint8',['pointer','uint','pointer']);
    const resize=new NativeFunction(nt.getExportByName('RtlReAllocateHeap'),
        'pointer',['pointer','uint','pointer','size_t']);
    const heap=create(0,1048576,0),mode=Memory.alloc(4);
    if (heap.isNull()) throw Error('LFH test heap creation failed');
    const live=new Map(),checks=[];
    function check(name) {
        const counts=censusCounts();
        const bytes=Array.from(live.values()).reduce((total,item)=>total+item.size,0);
        if (counts.errors || counts.live_count!==live.size || counts.live_requested_bytes!==String(bytes))
            throw Error(name+': '+JSON.stringify({counts,expected_count:live.size,expected_bytes:bytes}));
        checks.push({name,...counts});
    }
    try {
        mode.writeU32(2);
        if (!setInfo(heap,0,mode,4)) throw Error('Enabling LFH failed');
        mode.writeU32(0);
        if (!queryInfo(heap,0,mode,4,ptr(0)) || mode.readU32()!==2)
            throw Error('LFH mode was not confirmed');
        startCensus({pid,heap:heap.toString(),capacity:4096},header);
        check('lfh-empty');
        for (let i=0;i<2048;i++) {
            const size=64+(i%8)*16,address=alloc(heap,0,size);
            if (address.isNull()) throw Error('LFH allocation failed');
            live.set(i,{address:address.toString(),size});
        }
        check('lfh-2048-live-requests');
        for (let i=0;i<2048;i+=2) {
            if (!free(heap,0,ptr(live.get(i).address))) throw Error('LFH free failed');
            live.delete(i);
        }
        check('lfh-half-freed');
        for (let i=1;i<2048;i+=64) {
            const address=resize(heap,0,ptr(live.get(i).address),512);
            if (address.isNull()) throw Error('LFH realloc failed');
            live.set(i,{address:address.toString(),size:512});
        }
        check('lfh-reallocated');
        return {checks,lfh_mode:2,expected_entries:Array.from(live.values()),final:freezeCensus()};
    } finally {
        if (census) freezeCensus();
        destroy(heap);
    }
};
