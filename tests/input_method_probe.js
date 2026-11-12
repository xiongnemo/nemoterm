// Test-only Frida probe. It is loaded only into the newly owned terminal PID.
const U=Process.getModuleByName('user32.dll'), I=Process.getModuleByName('imm32.dll');
const api=(m,n,r,a)=>new NativeFunction(m.getExportByName(n),r,a);
const context=api(I,'ImmGetContext','pointer',['pointer']);
const release=api(I,'ImmReleaseContext','int',['pointer','pointer']);
const layout=api(U,'GetKeyboardLayout','pointer',['uint']);
const prop=api(I,'ImmGetProperty','uint',['pointer','uint']);
const open=api(I,'ImmGetOpenStatus','int',['pointer']);
const setOpen=api(I,'ImmSetOpenStatus','int',['pointer','int']);
const setComp=api(I,'ImmSetCompositionStringW','int',['pointer','uint','pointer','uint','pointer','uint']);
const notify=api(I,'ImmNotifyIME','int',['pointer','uint','uint','uint']);
const compWindow=api(I,'ImmGetCompositionWindow','int',['pointer','pointer']);
const compFont=api(I,'ImmGetCompositionFontW','int',['pointer','pointer']);
const sendMessage=api(U,'SendMessageW','pointer',['pointer','uint','pointer','pointer']);
const getRect=api(U,'GetWindowRect','int',['pointer','pointer']);
const getFocus=api(U,'GetFocus','pointer',[]);
let fault=null,operation=null,lastDpi=96,originalOpen=null;
Interceptor.attach(I.getExportByName('ImmGetContext'),{onLeave(r){if(fault&&r.isNull())r.replace(ptr(0x1234));}});
Interceptor.attach(I.getExportByName('ImmGetCompositionStringW'),{
 onEnter(a){this.active=fault&&a[1].toUInt32()===0x800;this.buffer=a[2];this.capacity=a[3].toUInt32();},
 onLeave(r){if(!this.active)return;let result=fault.query;
  if(this.capacity){const bytes=fault.bytes.slice(0,this.capacity);this.buffer.writeByteArray(bytes);result=fault.actual;}
  r.replace(result);send({event:'read',name:fault.name,capacity:this.capacity,returned:result});}
});
Interceptor.attach(U.getExportByName('DispatchMessageW'),{onEnter(a){
 const msg=a[0];if(msg.add(8).readU32()!==0x8321||!operation)return;
 const op=operation;operation=null;const hwnd=msg.readPointer();const answer={event:'operation',id:op.id,kind:op.kind};
 if(op.kind==='dpi'){
  const rect=Memory.alloc(16);getRect(hwnd,rect);
  rect.add(8).writeS32(rect.readS32()+Math.round((rect.add(8).readS32()-rect.readS32())*op.dpi/lastDpi));
  rect.add(12).writeS32(rect.add(4).readS32()+Math.round((rect.add(12).readS32()-rect.add(4).readS32())*op.dpi/lastDpi));
  sendMessage(hwnd,0x2e0,ptr(op.dpi|(op.dpi<<16)),rect);lastDpi=op.dpi;
 }
 // IMM geometry is intentionally updated only for a focused terminal. Own
 // the test window's focus messages within this UI-thread operation without
 // activating its window or changing the user's real foreground focus.
 const controlledFocus=op.kind==='focused-capabilities';
 const hadFocus=getFocus().equals(hwnd);
 if(controlledFocus){sendMessage(hwnd,0x7,ptr(0),ptr(0));answer.controlledFocus=true;}
 const h=context(hwnd);answer.context=!h.isNull();answer.layout=layout(0).toString();answer.caps=prop(layout(0),0x14);
 if(!h.isNull()){
  if(originalOpen===null)originalOpen=open(h);
  if(op.kind==='ime'){
   answer.setOpen=setOpen(h,1);const str=Memory.allocUtf16String(op.text);
   answer.setComposition=setComp(h,9,str,op.text.length*2,ptr(0),0);answer.complete=notify(h,0x15,1,0);
  }
  if(op.kind==='restore'){answer.cancel=notify(h,0x15,4,0);answer.restored=setOpen(h,originalOpen);}
  const cf=Memory.alloc(28);if(compWindow(h,cf))answer.compositionWindow={style:cf.readU32(),x:cf.add(4).readS32(),y:cf.add(8).readS32()};
  const lf=Memory.alloc(92);if(compFont(h,lf))answer.compositionFontHeight=lf.readS32();
  release(hwnd,h);
 }
 if(controlledFocus&&!hadFocus)sendMessage(hwnd,0x8,ptr(0),ptr(0));
 send(answer);
}});
rpc.exports={configure(value){fault=value;return true;},command(value){operation=value;return true;}};
send({event:'ready'});
