// Metadata-only attribution within regions that existed before injection.
const dir='C:/Users/nemo/Documents/Projects/nemoterm/build/rtl-worktree/build/local-directx-heap-region-probe-v2/research/';
const ready=JSON.parse(File.readAllText(dir+'allocation-ready.json'));
if(ready.pid!==Process.id)throw Error('Wrong owned process');
const kernel=Process.getModuleByName('kernel32.dll'),nt=Process.getModuleByName('ntdll.dll');
const query=new NativeFunction(kernel.getExportByName('VirtualQuery'),'size_t',['pointer','pointer','size_t']);
const info=Memory.alloc(48),ranges=[];
for(const region of ready.before_regions.allocations){
  if(region.kind!=='private'||region.private_ws<524288)continue;
  const start=ptr(region.allocation);let end=start,committed=0;
  for(let i=0;i<4096;i++){
    if(Number(query(end,info,48))!==48||!info.add(8).readPointer().equals(start))break;
    const bytes=info.add(24).readU64().toNumber();if(!bytes)break;
    if(info.add(32).readU32()===0x1000)committed+=bytes;
    end=end.add(bytes);
  }
  if(end.compare(start)>0)ranges.push({start:start.toString(),end:end.toString(),committed,before_private_ws:region.private_ws});
}
if(!ranges.length)throw Error('No pre-injection ranges mapped');
const limits=Memory.alloc(ranges.length*16),stats=Memory.alloc(4096*40),lock=Memory.alloc(8),overflow=Memory.alloc(8);
ranges.forEach((r,i)=>{limits.add(i*16).writePointer(ptr(r.start));limits.add(i*16+8).writePointer(ptr(r.end));});
const cm=new CModule(`
#include <gum/guminterceptor.h>
typedef struct {gpointer start,end;} Range;
typedef struct {guint64 region,caller,calls,bytes,maximum;} Stat;
typedef struct {guint64 bytes;gpointer caller;} Call;
extern Range limits[];
extern Stat stats[];
extern guint64 lock,overflow;
extern void acquire(gpointer);
extern void release(gpointer);
void enter(GumInvocationContext *ic) {
  Call *c=gum_invocation_context_get_listener_invocation_data(ic,sizeof(Call));
  c->bytes=(guint64)gum_invocation_context_get_nth_argument(ic,2);
  c->caller=gum_invocation_context_get_return_address(ic);
}
void reenter(GumInvocationContext *ic) {
  enter(ic);
  Call *c=gum_invocation_context_get_listener_invocation_data(ic,sizeof(Call));
  c->bytes=(guint64)gum_invocation_context_get_nth_argument(ic,3);
}
void leave(GumInvocationContext *ic) {
  gpointer p=gum_invocation_context_get_return_value(ic);
  if(!p)return;
  Call *c=gum_invocation_context_get_listener_invocation_data(ic,sizeof(Call));
  for(guint64 i=0;i<${ranges.length};i++){
    if(p<limits[i].start||p>=limits[i].end)continue;
    guint64 caller=(guint64)c->caller;
    guint64 slot=((caller>>4)^i)&4095;
    acquire(&lock);
    for(guint64 n=0;n<4096;n++,slot=(slot+1)&4095){
      Stat *s=&stats[slot];
      if(!s->calls||(s->region==i&&s->caller==caller)){
        s->region=i;s->caller=caller;s->calls++;s->bytes+=c->bytes;
        if(c->bytes>s->maximum)s->maximum=c->bytes;
        release(&lock);return;
      }
    }
    overflow++;release(&lock);return;
  }
}
`,{limits,stats,lock,overflow,acquire:kernel.getExportByName('AcquireSRWLockExclusive'),release:kernel.getExportByName('ReleaseSRWLockExclusive')});
const hooks=[Interceptor.attach(nt.getExportByName('RtlAllocateHeap'),{onEnter:cm.enter,onLeave:cm.leave}),
  Interceptor.attach(nt.getExportByName('RtlReAllocateHeap'),{onEnter:cm.reenter,onLeave:cm.leave})];
send({kind:'ready',pid:Process.id,ranges,scope:'Requested heap allocations and reallocations, grouped by immediate caller and pre-injection region; not live allocation sizes.'});
File.writeAllText(dir+'allocation-release.json',JSON.stringify({pid:Process.id}));
const timer=setInterval(()=>{
  try{File.readAllText(dir+'allocation-done.json');}catch(e){return;}
  hooks.forEach(h=>h.detach());clearInterval(timer);
  const entries=[];
  for(let i=0;i<4096;i++){
    const p=stats.add(i*40),calls=p.add(16).readU64().toNumber();if(!calls)continue;
    const address=p.add(8).readPointer(),module=Process.findModuleByAddress(address);
    entries.push({region:p.readU64().toNumber(),caller:address.toString(),module:module?.name,
      offset:module?address.sub(module.base).toString():null,calls,
      bytes:p.add(24).readU64().toNumber(),maximum:p.add(32).readU64().toNumber()});
  }
  const result={kind:'done',pid:Process.id,ranges,entries,overflow:overflow.readU64().toNumber()};
  File.writeAllText(dir+'heap-regions.json',JSON.stringify(result,null,2));send(result);
  File.writeAllText(dir+'allocation-detached.json',JSON.stringify({pid:Process.id,hooks_detached:true}));
},100);


