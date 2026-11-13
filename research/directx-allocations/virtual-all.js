// Only a newly created, fixture-owned process is attached. Metadata and call
// stacks are observed; this is attribution evidence, not memory acceptance.
const evidenceDir='C:/Users/nemo/Documents/Projects/nemoterm/build/rtl-worktree/build/local-directx-small-allocation-probe/research/';
const ntdll=Process.getModuleByName('ntdll.dll');
let serial=0,finished=false;
function frames(context) {
  return Thread.backtrace(context,Backtracer.ACCURATE).map(address=>{
    const module=Process.findModuleByAddress(address);
    return {address:address.toString(),module:module?module.name:null,
      offset:module?address.sub(module.base).toString():null};
  });
}
function log(value) {if(serial++<6000)send({...value,epoch_ms:Date.now()});}
const allocation=Interceptor.attach(ntdll.getExportByName('NtAllocateVirtualMemory'),{
  onEnter(args) {
    this.record=args[0].equals(ptr(-1));
    if(!this.record)return;
    this.base=args[1];this.size=args[3];this.flags=args[4].toUInt32();this.protect=args[5].toUInt32();
    this.requested=this.size.readU64().toNumber();
    
    this.stack=frames(this.context);
    if(this.stack.some(f=>f.module&&/frida|gum-js/i.test(f.module)))this.record=false;
  },
  onLeave(status) {
    if(this.record&&status.toInt32()>=0)log({kind:'allocate',base:this.base.readPointer().toString(),
      bytes:this.size.readU64().toNumber(),requested:this.requested,flags:this.flags,protect:this.protect,stack:this.stack});
  }
});
const release=Interceptor.attach(ntdll.getExportByName('NtFreeVirtualMemory'),{
  onEnter(args) {
    this.record=args[0].equals(ptr(-1));if(!this.record)return;
    this.base=args[1].readPointer().toString();this.bytes=args[2].readU64().toNumber();
    this.flags=args[3].toUInt32();
  },
  onLeave(status) {if(this.record&&status.toInt32()>=0)log({kind:'free',base:this.base,bytes:this.bytes,flags:this.flags});}
});
send({kind:'ready',pid:Process.id,epoch_ms:Date.now()});
File.writeAllText(evidenceDir+'allocation-release.json',JSON.stringify({go:true,pid:Process.id}));
const timer=setInterval(()=>{
  if(finished)return;
  try{File.readAllText(evidenceDir+'allocation-done.json');}catch(error){return;}
  finished=true;allocation.detach();release.detach();
  const kernel=Process.getModuleByName('kernel32.dll');
  const getHeaps=new NativeFunction(kernel.getExportByName('GetProcessHeaps'),'uint',['uint','pointer']);
  const getHeap=new NativeFunction(kernel.getExportByName('GetProcessHeap'),'pointer',[]);
  const capacity=1024,buffer=Memory.alloc(capacity*Process.pointerSize),count=getHeaps(capacity,buffer);
  const heaps=[];for(let i=0;i<Math.min(count,capacity);i++)heaps.push(buffer.add(i*Process.pointerSize).readPointer().toString());
  send({kind:'done',pid:Process.id,epoch_ms:Date.now(),events:serial,truncated:serial>6000,
    process_heap:getHeap().toString(),heap_count:count,heaps,
    modules:Process.enumerateModules().map(m=>({name:m.name,base:m.base.toString(),size:m.size,path:m.path}))});
  File.writeAllText(evidenceDir+'allocation-detached.json',JSON.stringify({hooks_detached:true,pid:Process.id}));
  clearInterval(timer);
},100);

