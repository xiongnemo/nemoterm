/* Appended only by the controlled native adapter test, never the app probe. */
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
