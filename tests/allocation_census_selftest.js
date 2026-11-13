/* Appended only by the controlled native adapter test, never the app probe. */
rpc.exports.selftest = function(pid, header, retainLiveBlock) {
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
    const heap = heapCreate(0, 0, 0);
    if (heap.isNull()) throw Error('Private test heap creation failed');
    let destroyed = false;
    const checks = [];
    function check(name, count, bytes) {
        const actual = censusCounts();
        if (actual.errors !== 0 || actual.live_count !== count ||
            actual.live_requested_bytes !== String(bytes))
            throw Error(name + ': ' + JSON.stringify(actual));
        checks.push({name, ...actual});
    }
    try {
        startCensus({pid, heap: heap.toString(), capacity: 64}, header);
        check('empty', 0, 0);
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
    }
};
