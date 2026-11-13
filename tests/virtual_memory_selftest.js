/* Disposable test worker only. Reserves its own memory and never reads payload. */
let vmTest=null;
rpc.exports.prepare=function(pid) {
    if (pid!==Process.id || vmTest) throw Error('Wrong owned test process');
    const kernel=Process.getModuleByName('kernel32.dll'),nt=Process.getModuleByName('ntdll.dll');
    const reserve=new NativeFunction(kernel.getExportByName('VirtualAlloc'),
        'pointer',['pointer','size_t','uint','uint']);
    const release=new NativeFunction(kernel.getExportByName('VirtualFree'),'int',['pointer','size_t','uint']);
    const base=reserve(ptr(0),65536,0x2000,4),excluded=reserve(ptr(0),65536,0x2000,4);
    if (base.isNull() || excluded.isNull()) throw Error('Controlled reservation failed');
    vmTest={base,excluded,release,baseArg:Memory.alloc(8),sizeArg:Memory.alloc(8),released:false,
        alloc:new NativeFunction(nt.getExportByName('NtAllocateVirtualMemory'),
            'int',['pointer','pointer','size_t','pointer','uint','uint']),
        allocEx:new NativeFunction(nt.getExportByName('NtAllocateVirtualMemoryEx'),
            'int',['pointer','pointer','pointer','uint','uint','pointer','uint']),
        free:new NativeFunction(nt.getExportByName('NtFreeVirtualMemory'),
            'int',['pointer','pointer','pointer','uint'])};
    return {pid,ranges:[{start:base.toString(),end:base.add(65536).toString()}],event_capacity:64};
};
rpc.exports.transition=function(name) {
    const v=vmTest;
    if (!v) throw Error('Test not prepared');
    let base=v.base.add(4096),size=8192,flags=0x1000,protection=4,operation='alloc';
    if (name==='excluded') {base=v.excluded;size=4096;}
    else if (name==='failed') {protection=0xffffffff;size=4096;}
    else if (name==='decommit') {size=4096;flags=0x4000;operation='free';}
    else if (name==='extended') {base=v.base.add(12288);size=4096;operation='extended';}
    else if (name==='release') {base=v.base;size=0;flags=0x8000;operation='free';}
    else if (name!=='commit') throw Error('Unknown transition');
    v.baseArg.writePointer(base);v.sizeArg.writeU64(size);
    const self=ptr('0xffffffffffffffff');
    const status=operation==='free' ? v.free(self,v.baseArg,v.sizeArg,flags) :
        operation==='extended' ? v.allocEx(self,v.baseArg,v.sizeArg,flags,protection,ptr(0),0) :
        v.alloc(self,v.baseArg,0,v.sizeArg,flags,protection);
    if (name==='release' && status>=0) v.released=true;
    return {name,status,address:v.baseArg.readPointer().toString(),bytes:v.sizeArg.readU64().toString()};
};
rpc.exports.cleanup=function() {
    if (virtualTrace) freezeVirtualTrace();
    if (vmTest) {
        if (!vmTest.released) vmTest.release(vmTest.base,0,0x8000);
        vmTest.release(vmTest.excluded,0,0x8000);vmTest=null;
    }
};
